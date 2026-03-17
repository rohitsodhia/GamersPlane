"""
BBCode → HTML parser for FastAPI/uvicorn.

Design notes
------------
* A new BBCodeParser is instantiated per parse() call so counters are
  request-scoped and there is no shared mutable state between concurrent
  async requests.
* [code] is handled before tokenisation so its contents are never
  tokenised; this means [code] cannot be nested inside other tags, which
  is intentional.
* All user-supplied attribute values are HTML-escaped before being written
  into HTML attributes to prevent XSS injection.
* [url] and [img] block javascript: and data: URI schemes.
"""

import re
from html import escape as html_escape
from itertools import count
from typing import Any

from app.configs import configs

# ---------------------------------------------------------------------------
# Module-level compiled patterns (created once at import time)
# ---------------------------------------------------------------------------

# Tokeniser: splits text into tag tokens and plain-text chunks.
# Note: [#] and [*] are handled as special cases in the walk loop because
# their closing tags ([/#] and [/*]) cannot be expressed in this character
# class without ambiguity.
_TAG_TOKENIZER = re.compile(r"(\[/?[a-zA-Z0-9=\s\"\'\-\_\$\.\+\;\,]+\])", re.IGNORECASE)

# Tags whose closing tag should consume one trailing newline in the source.
_TAGS_TO_STRIP = frozenset(
    [
        "quote",
        "list",
        "table",
        "ooc",
        "style",
        "charsheet",
        "snippet",
        "spoiler",
        "2column",
        "3column",
        "col",
        "abilities",
        "snippets",
    ]
)

# URI schemes that must never appear in href/src attributes.
_BLOCKED_SCHEMES = re.compile(r"^\s*(javascript|data|vbscript)\s*:", re.IGNORECASE)

# Mention pattern
_MENTION_RE = re.compile(r"@[0-9a-zA-Z\-\.\_]+[0-9a-zA-Z\-\_]")

# Code block (pre-tokenisation)
_CODE_RE = re.compile(r"\[code\](.*?)\[/code\]", re.DOTALL | re.IGNORECASE)

# Form-field inline pattern
_FORM_FIELD_RE = re.compile(r"\[\_(([\w\_\$]*)\=)?([^\]]*)\]")

# Poll flag detection
_POLL_TITLE_RE = re.compile(r'^"([^"]*)"(.*)|^([^\s\[]*)(.*)')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_attr(value: str) -> str:
    """HTML-escape a value before writing it into an HTML attribute."""
    return html_escape(value, quote=True)


def _safe_url(url: str) -> str:
    """Return the URL if it is safe, otherwise '#'."""
    if _BLOCKED_SCHEMES.match(url):
        return "#"
    return url


def _escape_bbcode_content(content: str) -> str:
    """Escape brackets and newlines for hidden BBCode storage spans."""
    return (
        content.replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace("\r\n", "\n")
        .replace("\n", "&#10;")
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class BBCodeParser:
    """
    Instantiate once per parse call (via the module-level BBCode2Html helper)
    so that counters are fully request-scoped.
    """

    def __init__(self, site_url: str):
        self.site_url = site_url
        self.counters: dict[str, Any] = {
            "charsheet": count(),
            "formField": count(),
            "snippetCount": count(),
        }
        # Dispatch table: tag name -> bound handler method.
        # Handlers receive (attr, content, user, post, is_gm, is_thread_admin)
        # and return an HTML string.
        self._dispatch: dict[str, Any] = {
            # GP formatter (these two share one handler each)
            "f": self._tag_gp_format,
            # Simple / compound inline tags
            "b": self._tag_b,
            "i": self._tag_simple_factory("<em>", "</em>"),
            "u": self._tag_simple_factory("<u>", "</u>"),
            "s": self._tag_simple_factory("<s>", "</s>"),
            "ooc": self._tag_ooc,
            "style": self._tag_style,
            # Media
            "img": self._tag_img,
            "email": self._tag_email,
            "url": self._tag_url,
            "youtube": self._tag_youtube,
            "spotify": self._tag_spotify,
            "map": self._tag_map,
            # Formatting
            "size": self._tag_size,
            "color": self._tag_color,
            "zoommap": self._tag_zoommap,
            "spoiler": self._tag_spoiler,
            # Layout
            "2column": self._tag_simple_factory(
                '<div class="layout-columns-2">', "</div>"
            ),
            "3column": self._tag_simple_factory(
                '<div class="layout-columns-3">', "</div>"
            ),
            "col": self._tag_simple_factory('<div class="layout-column">', "</div>"),
            # Lists
            "list": self._tag_list,
            "*": self._tag_li,
            # Tables
            "table": self._tag_table,
            # NPCs
            "npc": self._tag_npc,
            "npcs": self._tag_npcs,
            # Access-controlled blocks
            "note": self._tag_note,
            "private": self._tag_private,
            # Structural
            "quote": self._tag_quote,
            "abilities": self._tag_abilities,
            "snippets": self._tag_snippets,
            "charsheet": self._tag_charsheet,
            "snippet": self._tag_snippet,
            "#": self._tag_formblock,
            # Poll
            "poll": self._tag_poll,
        }

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse(
        self,
        text: str,
        current_user=None,
        post=None,
        is_gm: bool = False,
        is_thread_admin: bool = False,
    ) -> str:
        if not text:
            return ""

        # Normalise smart quotes (iOS keyboard sends these)
        text = text.strip().replace("\u201c", '"').replace("\u201d", '"')

        # [code] must be handled before tokenisation so its contents are
        # never interpreted as BBCode tags.
        text = _CODE_RE.sub(self._escape_code, text)

        tokens = _TAG_TOKENIZER.split(text)
        stack: list[dict] = []
        output: list[str] = []
        num_tokens = len(tokens)

        for i in range(num_tokens):
            token = tokens[i]
            if not token:
                continue

            if token.startswith("[") and token.endswith("]"):
                tag_raw = token[1:-1]

                # ---- Closing tag ----------------------------------------
                if tag_raw.startswith("/"):
                    tag_name = tag_raw[1:].lower()
                    if stack and stack[-1]["name"] == tag_name:
                        opening_node = stack.pop()
                        content_list = output[opening_node["index"] :]
                        del output[opening_node["index"] :]
                        inner_text = "".join(content_list)

                        output.append(
                            self._transform(
                                tag_name,
                                opening_node["attr"],
                                inner_text,
                                current_user,
                                post,
                                is_gm,
                                is_thread_admin,
                            )
                        )

                        if tag_name in _TAGS_TO_STRIP and i + 1 < num_tokens:
                            tokens[i + 1] = re.sub(r"^\r?\n", "", tokens[i + 1])
                    else:
                        output.append(token)

                # ---- Opening tag ----------------------------------------
                else:
                    parts = tag_raw.split("=", 1)
                    tag_name = parts[0].lower()
                    attr = parts[1] if len(parts) > 1 else ""

                    if tag_name == "linebreak":
                        output.append("<hr>")
                    else:
                        stack.append(
                            {"name": tag_name, "attr": attr, "index": len(output)}
                        )

            # ---- Plain text / form fields / mentions --------------------
            else:
                if "[_" in token:
                    token = self._handle_form_fields(token)
                if current_user and "@" in token:
                    token = self._handle_mentions(token, current_user)
                output.append(token)

        final_html = "".join(output)

        # Convert semantic block elements back to divs (matches PHP behaviour)
        for semantic in ("blockquote", "aside"):
            final_html = final_html.replace(f"<{semantic}", "<div").replace(
                f"</{semantic}", "</div"
            )

        return final_html

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def _transform(self, tag, attr, content, user, post, is_gm, is_thread_admin):
        attr = attr.replace('"', "").strip()
        handler = self._dispatch.get(tag)
        if handler:
            return handler(attr, content, user, post, is_gm, is_thread_admin)
        # Unrecognised tag — return verbatim so content is not lost
        return f"[{tag}]{content}[/{tag}]"

    # ------------------------------------------------------------------
    # Tag handlers  (signature: attr, content, user, post, is_gm, is_thread_admin)
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_code(m: re.Match) -> str:
        code = m.group(1)
        code = code.replace("[", "&#91;").replace("]", "&#93;")
        code = code.replace("\r\n", "\n").replace("\n", "&#10;")
        return f"<pre><code>{code}</code></pre>"

    @staticmethod
    def _tag_simple_factory(open_tag: str, close_tag: str):
        """Return a handler that wraps content in fixed open/close tags."""

        def _handler(attr, content, user, post, is_gm, is_thread_admin):
            return f"{open_tag}{content}{close_tag}"

        return _handler

    def _tag_gp_format(self, attr, content, user, post, is_gm, is_thread_admin):
        """[f=…] — span with gpFormat classes / inline styles."""
        styles, classes = [], []
        for part in attr.split():
            if ":" in part:
                styles.append(_safe_attr(part))
            else:
                classes.append(f"gpFormat-{html_escape(part.lower())}")
        style_attr = f' style="{";".join(styles)}"' if styles else ""
        class_attr = f' class="userColor {" ".join(classes)}"'
        return f"<span{class_attr}{style_attr}>{content}</span>"

    def _tag_b(self, attr, content, user, post, is_gm, is_thread_admin):
        """[b] plain bold  OR  [b=…] GP formatter on <strong>."""
        if not attr:
            return f"<strong>{content}</strong>"
        # GP formatter variant
        styles, classes = [], []
        for part in attr.split():
            if ":" in part:
                styles.append(_safe_attr(part))
            else:
                classes.append(f"gpFormat-{html_escape(part.lower())}")
        style_attr = f' style="{";".join(styles)}"' if styles else ""
        class_attr = f' class="userColor {" ".join(classes)}"'
        return f"<strong{class_attr}{style_attr}>{content}</strong>"

    @staticmethod
    def _tag_ooc(attr, content, user, post, is_gm, is_thread_admin):
        return f'<blockquote class="oocText"><div>OOC:</div>{content}</blockquote>'

    @staticmethod
    def _tag_style(attr, content, user, post, is_gm, is_thread_admin):
        return f'<div style="display:none;">{content}</div>'

    @staticmethod
    def _tag_img(attr, content, user, post, is_gm, is_thread_admin):
        src = _safe_url(content.strip())
        safe_src = _safe_attr(src)
        return f'<img src="{safe_src}" alt="{safe_src}" class="usrImg">'

    @staticmethod
    def _tag_email(attr, content, user, post, is_gm, is_thread_admin):
        addr = _safe_attr(content.strip())
        return f'<a href="mailto:{addr}">{addr}</a>'

    def _tag_url(self, attr, content, user, post, is_gm, is_thread_admin):
        raw_href = attr if attr else content.strip()
        href = _safe_url(raw_href)
        safe_href = _safe_attr(href)
        display = content if attr else safe_href
        target = ' target="_blank"'
        if href.startswith("/") or (
            self.site_url and self.site_url.lower() in href.lower()
        ):
            target = ""
        return f'<a href="{safe_href}"{target} rel="nofollow">{display}</a>'

    @staticmethod
    def _tag_youtube(attr, content, user, post, is_gm, is_thread_admin):
        m = re.search(r"(?:youtu\.be/|v=)([A-Za-z0-9_\-]+)", content)
        vid_id = _safe_attr(m.group(1) if m else content.strip())
        return (
            f'<div class="youtube_bb"><iframe '
            f'src="https://www.youtube.com/embed/{vid_id}" '
            f'title="YouTube video player" frameborder="0" '
            f'allow="accelerometer; autoplay; clipboard-write; '
            f'encrypted-media; gyroscope; picture-in-picture" '
            f"allowfullscreen></iframe></div>"
        )

    @staticmethod
    def _tag_spotify(attr, content, user, post, is_gm, is_thread_admin):
        m = re.search(
            r"spotify\.com/(track|album|episode|show|playlist)/([a-zA-Z0-9]+)",
            content,
        )
        if not m:
            return content
        s_type, s_id = m.groups()
        height = 152 if s_type in ("episode", "show") else 80
        return (
            f"<iframe src='https://open.spotify.com/embed/{s_type}/{s_id}?theme=0' "
            f"width='100%' height='{height}' frameBorder='0' "
            f"allowtransparency='true' allow='encrypted-media'></iframe>"
        )

    @staticmethod
    def _tag_map(attr, content, user, post, is_gm, is_thread_admin):
        link = re.sub(r"^[\s]*(--).*?$", "", content, flags=re.MULTILINE)
        link = _safe_url(re.sub(r"\s+", "", link))
        safe_link = _safe_attr(link)
        return (
            f'<a class="mapLink" target="_blank" href="{safe_link}">'
            f'<img class="usrImg" src="{safe_link}"/></a>'
        )

    @staticmethod
    def _tag_size(attr, content, user, post, is_gm, is_thread_admin):
        # Only allow numeric size values
        safe_size = _safe_attr(attr) if re.match(r"^\d+$", attr) else "100"
        return f'<span class="userSize" style="font-size:{safe_size}%">{content}</span>'

    @staticmethod
    def _tag_color(attr, content, user, post, is_gm, is_thread_admin):
        # Allow CSS colour values: named colours, hex, rgb(), hsl()
        safe_color = (
            _safe_attr(attr) if re.match(r"^[\w#(),%. ]+$", attr) else "inherit"
        )
        return f'<span class="userColor" style="color:{safe_color}">{content}</span>'

    @staticmethod
    def _tag_zoommap(attr, content, user, post, is_gm, is_thread_admin):
        return (
            f'<div class="zoommap" data-mapimage="{_safe_attr(attr)}" '
            f'style="display:none">{content}</div>'
        )

    @staticmethod
    def _tag_spoiler(attr, content, user, post, is_gm, is_thread_admin):
        label = html_escape(attr) if attr else "Spoiler"
        return (
            f'<blockquote class="spoiler closed">'
            f'<div class="tag">[ <span class="open">+</span>'
            f'<span class="close">-</span> ] {label}</div>'
            f'<div class="hidden">{content}</div></blockquote>'
        )

    @staticmethod
    def _tag_list(attr, content, user, post, is_gm, is_thread_admin):
        if not attr:
            return f"<ul>{content}</ul>"
        if attr.isdigit():
            return f'<ol start="{_safe_attr(attr)}">{content}</ol>'
        if "," in attr:
            l_type, start = attr.split(",", 1)
            return (
                f'<ol type="{_safe_attr(l_type.strip())}" '
                f'start="{_safe_attr(start.strip())}">{content}</ol>'
            )
        return f'<ol type="{_safe_attr(attr)}">{content}</ol>'

    @staticmethod
    def _tag_li(attr, content, user, post, is_gm, is_thread_admin):
        return f"<li>{content}</li>"

    @staticmethod
    def _tag_table(attr, content, user, post, is_gm, is_thread_admin):
        t = attr.lower()
        classes = ["bbTable"]
        if "center" in t or "centre" in t:
            classes.append("bbTableCenter")
        if "right" in t:
            classes.append("bbTableRight")
        if "stats" in t:
            classes.append("bbTableStats")
        if "htl" in t:
            classes.append("bbTable-htl")
        elif "ht" in t:
            classes.append("bbTable-ht")
        elif "hl" in t:
            classes.append("bbTable-hl")
        if "rolls" in t:
            classes.append("bbTableRolls")
        if "d20" in t:
            classes.append("bbTableD20")
        if "compact" in t:
            classes.append("bbTableCompact")
        if "dnd5e" in t:
            classes.append("bbTableDnd5e")
        if "grid" in t or "lines" in t:
            classes.append("bbTableGrid")
        if "zebra" in t:
            classes.append("bbTableZebra")
        if "pool-add" in t:
            classes.append("bbTablePoolAdd")
        elif "pool" in t:
            classes.append("bbTablePool")

        rows = content.replace("<br />", "").strip().split("\n")
        inner = "".join(
            f"<tr><td>{r.replace('|', '</td><td>')}</td></tr>"
            for r in rows
            if r.strip()
        )
        return (
            f"<div class='bbTableWrapper'>"
            f"<table class='{' '.join(classes)}'>{inner}</table></div>"
        )

    @staticmethod
    def _tag_npc(attr, content, user, post, is_gm, is_thread_admin):
        avatar = _safe_attr(_safe_url(content.strip()))
        name = html_escape(attr)
        return (
            f'<div class="inlineNpcPrefix"></div>'
            f'<div class="inlineNpc">'
            f'<img class="inlineNpcAvatar" src="{avatar}"/>'
            f'<div class="inlineNpcName">{name}</div>'
            f"</div>"
        )

    @staticmethod
    def _tag_npcs(attr, content, user, post, is_gm, is_thread_admin):
        title = html_escape(attr) if attr else "NPCs"
        lines = content.replace("<br />", "").replace("\r", "").strip().split("\n")
        items = []
        for row in lines:
            parts = row.split("|", 1)
            if len(parts) == 2:
                name = html_escape(parts[0].strip())
                avatar = _safe_attr(_safe_url(parts[1].strip()))
                items.append(
                    f"<div class='npcList_item'>"
                    f"<img class='npcList_itemAvatar' data-avatar='{avatar}' src='{avatar}'/>"
                    f"<div class='npcList_itemName'>{name}</div>"
                    f"</div>"
                )
        return (
            f"<div class='npcs'><h3>{title}</h3>"
            f"<div class='npcList'>{''.join(items)}</div></div>"
        )

    @staticmethod
    def _tag_note(attr, content, user, post, is_gm, is_thread_admin):
        note_to = [x.lower() for x in re.split(r"[^\w\.]+", attr) if x]
        curr_name = user.username.lower() if user else ""
        is_author = (
            (post.getAuthor("userID") == user.userID) if (post and user) else False
        )
        can_view = (
            is_gm
            or is_thread_admin
            or is_author
            or (curr_name and curr_name in note_to)
        )

        safe_attr = html_escape(attr)
        author_name = html_escape(post.getAuthor("username")) if post else "User"

        if attr:
            visible_label = f"Note to <span>{safe_attr}</span>"
            hidden_label = f"{author_name} sent a note to <span>{safe_attr}</span>"
        else:
            visible_label = "Note <span></span>"
            hidden_label = f"{author_name}'s note <span></span>"

        if not can_view:
            return f'<aside class="note"><div>{hidden_label}</div></aside>'
        return f'<aside class="note"><div>{visible_label}</div>{content}</aside>'

    @staticmethod
    def _tag_private(attr, content, user, post, is_gm, is_thread_admin):
        if not attr:
            return ""  # no recipient — always hidden
        note_to = [x.lower() for x in re.split(r"[^\w\.]+", attr) if x]
        curr_name = user.username.lower() if user else ""
        is_author = (
            (post.getAuthor("userID") == user.userID) if (post and user) else False
        )
        can_view = (
            is_gm
            or is_thread_admin
            or is_author
            or (curr_name and curr_name in note_to)
        )
        return (content + "<br/>") if can_view else ""

    @staticmethod
    def _tag_quote(attr, content, user, post, is_gm, is_thread_admin):
        quotee_text = f"{html_escape(attr)} says:" if attr else "Quote:"
        return (
            f'<blockquote class="quote">'
            f'<div class="quotee">{quotee_text}</div>'
            f"{content.strip()}</blockquote>"
        )

    def _tag_abilities(self, attr, content, user, post, is_gm, is_thread_admin):
        idx = next(self.counters["formField"])
        icon = '<i class="ra ra-quill-ink"></i> '
        return self._split_by_header(
            f"{icon}{html_escape(attr)}",
            content,
            "abilities",
            f" data-abilitiesfieldidx='{idx}'",
        )

    def _tag_snippets(self, attr, content, user, post, is_gm, is_thread_admin):
        return self._split_by_header(html_escape(attr), content, "snippets")

    def _tag_charsheet(self, attr, content, user, post, is_gm, is_thread_admin):
        idx = next(self.counters["charsheet"])
        escaped = _escape_bbcode_content(content)
        safe_name = html_escape(attr)
        return (
            f'<blockquote class="spoiler closed charsheet" data-charsheet="{idx}">'
            f'<div class="tag">[ <span class="open">+</span>'
            f'<span class="close">-</span> ] '
            f'<span class="snippetName">{safe_name}</span></div>'
            f'<div class="hidden">'
            f'<div class="createSheet"><span class="createSheetButton">Create character</span></div>'
            f"{content}</div>"
            f'<div style="display:none;" class="snippetBBCode">{escaped}</div>'
            f"</blockquote>"
        )

    def _tag_snippet(self, attr, content, user, post, is_gm, is_thread_admin):
        idx = next(self.counters["snippetCount"])
        escaped = _escape_bbcode_content(content)
        safe_name = html_escape(attr)
        return (
            f'<blockquote class="spoiler closed snippet" data-snippetidx="{idx}">'
            f'<div class="tag">[ <span class="open">+</span>'
            f'<span class="close">-</span> ] '
            f'<span class="snippetName">{safe_name}</span></div>'
            f'<div class="hidden">{content}</div>'
            f'<div style="display:none;" class="snippetBBCode">{escaped}</div>'
            f"</blockquote>"
        )

    def _tag_formblock(self, attr, content, user, post, is_gm, is_thread_admin):
        idx = next(self.counters["formField"])
        escaped = _escape_bbcode_content(content)
        icon = '<i class="ra ra-quill-ink"></i> '
        safe_attr = html_escape(attr)
        return (
            f'<div class="formBlock" data-blockfieldidx="{idx}">'
            f'<h2 class="headerbar hbDark">{icon}{safe_attr}</h2>'
            f'<div class="formBlockRendered">{content}</div>'
            f'<div style="display:none;" class="formBlockBBCode">{escaped}</div>'
            f"</div>"
        )

    def _tag_poll(self, attr, content, user, post, is_gm, is_thread_admin):
        if not post:
            return content

        # attr format (from PHP):  "Poll title" multi show public
        # or without quotes:        PollTitle multi show public
        m = _POLL_TITLE_RE.match(attr)
        if m:
            title = m.group(1) or m.group(3) or ""
            flags = (m.group(2) or m.group(4) or "").lower()
        else:
            title, flags = attr, ""

        multiple_votes = "multi" in flags
        show_before_vote = "show" in flags
        public_vote = "public" in flags

        is_author = post.getAuthor("userID") == (user.userID if user else None)
        poll_results = post.getPollResults(public_vote)
        questions = [
            q.strip()
            for q in content.replace("<br />", "").strip().split("\n")
            if q.strip()
        ]

        extra_cls = (" pollAllowMulti" if multiple_votes else "") + (
            " pollPublic" if public_vote else ""
        )
        multi_badge = (
            " <span class='badge badge-pollMulti'>Multi</span>"
            if multiple_votes
            else ""
        )
        pub_badge = (
            " <span class='badge badge-pollPublic'>Public</span>" if public_vote else ""
        )

        ret = [
            f"<div class='postPoll{extra_cls}' data-postid='{post.getPostID()}'>",
            f"<h3>{html_escape(title)}{multi_badge}{pub_badge}</h3>",
            "<div class='pollQuestions'>",
        ]
        for n, question in enumerate(questions, start=1):
            my_vote_cls = " pollMyVote" if poll_results["votes"][n].get("me") else ""
            ret.append(
                f"<div class='pollQuestion{my_vote_cls}' data-q='{n}'>"
                f"<div class='pollQuestionLabel'>{html_escape(question)}</div>"
                f"<div class='pollQuestionResults'>"
            )
            if poll_results.get("voted") or show_before_vote or is_author or is_gm:
                ret.append(poll_results["votes"][n]["html"])
            else:
                ret.append('<div class="voteToView">Vote to view results.</div>')
            ret.append("</div></div>")

        ret.append("</div></div>")
        return "".join(ret)

    # ------------------------------------------------------------------
    # Non-tag helpers
    # ------------------------------------------------------------------

    def _split_by_header(
        self, title: str, text: str, css_class: str, collection_data: str = ""
    ) -> str:
        ret = [f'<div class="{css_class} ddCollection"{collection_data}>']
        if title:
            ret.append(f'<h2 class="headerbar hbDark">{title}</h2>')

        # PHP opens a stub ability div before iterating — replicated here.
        ret.append('<div class="ability"><div class="abilityNotes">')
        ability_open = True
        ability_raw: list[str] = []

        for line in text.strip().split("\n"):
            if line.startswith("#"):
                if ability_open:
                    ret.append(
                        f'</div><div style="display:none" class="abilityBBCode">{"".join(ability_raw)}</div></div>'
                    )
                ret.append(
                    f'<div class="ability">'
                    f'<span class="abilityName">{html_escape(line[1:].strip())}</span>'
                    f'<a href="" class="ability_notesLink">Notes</a>'
                    f'<div class="abilityNotes notes">'
                )
                ability_open = True
                ability_raw = []
            else:
                ret.append(line + "\n")
                ability_raw.append(
                    line.replace("[", "&#91;").replace("]", "&#93;") + "&#10;"
                )

        if ability_open:
            ret.append(
                f'</div><div style="display:none" class="abilityBBCode">{"".join(ability_raw)}</div></div>'
            )

        ret.append("</div>")
        return "".join(ret)

    def _handle_form_fields(self, text: str) -> str:
        def sub_f(m: re.Match) -> str:
            var_name = m.group(2) or ""
            val = m.group(3) or ""
            is_calc = var_name.endswith("$")
            if is_calc:
                var_name = var_name.rstrip("$")

            idx = next(self.counters["formField"])
            classes = ["formVal"]
            if is_calc:
                classes.append("formCalc")
            if var_name:
                classes.append("formVar")

            chk = re.search(r"(\d+)/(\d+)", val)
            if chk:
                v, total = int(chk.group(1)), int(chk.group(2))
                if 0 < total <= 20 and 0 <= v <= total:
                    classes.append("formCheck")
                    html_val = (
                        '<input class="notPretty" type="checkbox" checked/>' * v
                        + '<input class="notPretty" type="checkbox"/>' * (total - v)
                    )
                    return (
                        f'<span class="{" ".join(classes)}" '
                        f'data-varname="{_safe_attr(var_name)}" '
                        f'data-varcalc="" '
                        f'data-formfieldidx="{idx}">{html_val}</span>'
                    )

            if not is_calc:
                classes.append("formText")
            display_val = "" if is_calc else val
            calc_val = val if is_calc else ""
            return (
                f'<span class="{" ".join(classes)}" '
                f'data-varname="{_safe_attr(var_name)}" '
                f'data-varcalc="{_safe_attr(calc_val)}" '
                f'data-formfieldidx="{idx}">{display_val}</span>'
            )

        return _FORM_FIELD_RE.sub(sub_f, text)

    @staticmethod
    def _handle_mentions(text: str, user) -> str:
        curr = "@" + user.username.lower()

        def _sub(m: re.Match) -> str:
            if m.group(0).lower() == curr:
                return f'<span class="atHighlight">{m.group(0)}</span>'
            return m.group(0)

        return _MENTION_RE.sub(_sub, text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def BBCode2Html(
    text: str,
    current_user=None,
    post=None,
    is_gm: bool = False,
    is_thread_admin: bool = False,
) -> str:
    """
    Parse BBCode and return HTML.

    A fresh BBCodeParser is created for every call so that counters
    (charsheet, formField, snippetCount) are scoped to a single request
    and concurrent async calls never share state.

    The per-call overhead is negligible: BBCodeParser.__init__ does nothing
    heavier than building a dict of already-bound methods.
    """
    return BBCodeParser(site_url=configs.HOST_NAME).parse(
        text,
        current_user=current_user,
        post=post,
        is_gm=is_gm,
        is_thread_admin=is_thread_admin,
    )
