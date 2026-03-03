import re
from itertools import count

from app.configs import configs

# Pre-compiled Tokenizer: Identifies all opening/closing tags and chunks of text.
TAG_TOKENIZER = re.compile(r"(\[/?[a-zA-Z0-9=\s\"\'\-\_\$\.\+\;\,]+\])", re.IGNORECASE)


class BBCodeParser:
    def __init__(self):
        self.site_url = configs.HOST_NAME
        # Shared counters for unique data attributes
        self.counters = {
            "charsheet": count(),
            "formField": count(),
            "snippetCount": count(),
        }
        # Simple tag mapping (Tag: (HTML_Tag, CSS_Classes))
        self.simple_map = {
            "b": ("strong", ""),
            "i": ("em", ""),
            "u": ("u", ""),
            "s": ("span", "text-decoration:line-through"),
            "ooc": ("blockquote", "oocText"),
            "style": ("div", 'style="display:none;"'),
        }

    def parse(
        self,
        text: str,
        current_user=None,
        post=None,
        is_gm=False,
        is_thread_admin=False,
    ):
        if not text:
            return ""

        # Normalize quotes and initial cleanup
        text = text.strip().replace("“", '"').replace("”", '"')
        tokens = TAG_TOKENIZER.split(text)

        stack = []
        output = []

        for token in tokens:
            if not token:
                continue

            # --- PROCESS TAGS ---
            if token.startswith("[") and token.endswith("]"):
                tag_raw = token[1:-1]

                # Closing Tag Logic
                if tag_raw.startswith("/"):
                    tag_name = tag_raw[1:].lower()
                    if stack and stack[-1]["name"] == tag_name:
                        opening_node = stack.pop()
                        # Extract everything from the buffer since the tag opened
                        content_list = output[opening_node["index"] :]
                        del output[opening_node["index"] :]
                        inner_text = "".join(content_list)

                        # Dispatch to the specialized transform logic
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
                    else:
                        output.append(token)

                # Opening Tag Logic
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

            # --- PROCESS TEXT & FORM FIELDS ---
            else:
                if "[_" in token:
                    token = self._handle_form_fields(token)
                output.append(token)

        final_html = "".join(output)

        # Cleanup semantic tags as per PHP suffix logic
        for tag in ["blockquote", "aside"]:
            final_html = final_html.replace(f"<{tag}", "<div").replace(
                f"</{tag}", "</div"
            )

        return final_html

    def _transform(self, tag, attr, content, user, post, is_gm, is_thread_admin):
        attr = attr.replace('"', "").strip()

        # 1. GP Class Formatter Logic (Port of gpClassFormatter)
        if tag in ["f", "b"]:
            html_tag = "span" if tag == "f" else "strong"
            styles, classes = [], []
            for part in attr.split():
                if ":" in part:
                    styles.append(part)
                else:
                    classes.append(f"gpFormat-{part.lower()}")

            style_attr = f' style="{";".join(styles)}"' if styles else ""
            class_attr = f' class="userColor {" ".join(classes)}"'
            return f"<{html_tag}{class_attr}{style_attr}>{content}</{html_tag}>"

        # 2. Advanced List Logic (Port of listTagBuilder)
        if tag == "list":
            if not attr:
                return f"<ul>{content}</ul>"
            if attr.isdigit():
                return f'<ol start="{attr}">{content}</ol>'
            if "," in attr:
                l_type, start = attr.split(",", 1)
                return f'<ol type="{l_type.strip()}" start="{start.strip()}">{content}</ol>'
            return f'<ol type="{attr}">{content}</ol>'

        if tag == "*":
            return f"<li>{content}</li>"

        # 3. Ability/Snippet Logic (Port of splitByHeader)
        if tag in ["abilities", "snippets"]:
            mode = "abilities" if tag == "abilities" else "snippets"
            idx_attr = ""
            if tag == "abilities":
                idx = next(self.counters["formField"])
                idx_attr = f" data-abilitiesfieldidx='{idx}'"
            return self._split_by_header(attr, content, mode, idx_attr)

        # 4. Table Logic
        if tag == "table":
            classes = ["bbTable"]
            mapping = {
                "center": "Center",
                "stats": "Stats",
                "htl": "-htl",
                "ht": "-ht",
                "hl": "-hl",
                "zebra": "Zebra",
                "grid": "Grid",
            }
            for k, v in mapping.items():
                if k in attr.lower():
                    classes.append(f"bbTable{v}")

            rows = content.replace("<br />", "").strip().split("\n")
            inner = "".join(
                [
                    f"<tr><td>{r.replace('|', '</td><td>')}</td></tr>"
                    for r in rows
                    if r.strip()
                ]
            )
            return f"<div class='bbTableWrapper'><table class='{' '.join(classes)}'>{inner}</table></div>"

        # 5. Media & Links
        if tag == "url":
            target = ' target="_blank"'
            if content.startswith("/") or (
                self.site_url and self.site_url in content.lower()
            ):
                target = ""
            return f'<a href="{content}"{target} rel="nofollow">{attr if attr else content}</a>'

        if tag == "spotify":
            m = re.search(
                r"spotify\.com/(track|album|episode|show|playlist)/([a-zA-Z0-9]+)",
                content,
            )
            if m:
                s_type, s_id = m.groups()
                height = 152 if s_type in ["episode", "show"] else 80
                return f"<iframe src='https://open.spotify.com/embed/{s_type}/{s_id}' width='100%' height='{height}' frameBorder='0' allow='encrypted-media'></iframe>"
            return content

        # 6. Permissions (Note/Private)
        if tag in ["note", "private"]:
            note_to = [x.lower() for x in re.split(r"[^\w\.]+", attr)]
            curr_name = user.username.lower() if user else ""
            is_author = (
                (post.getAuthor("userID") == user.userID) if (post and user) else False
            )
            can_view = is_gm or is_thread_admin or is_author or curr_name in note_to

            if tag == "private":
                return (content + "<br/>") if can_view else ""

            label = f"Note to <span>{attr}</span>" if attr else "Note"
            if not can_view:
                author_name = post.getAuthor("username") if post else "User"
                return f'<aside class="note"><div>{author_name} sent a note to <span>{attr}</span></div></aside>'
            return f'<aside class="note"><div>{label}</div>{content}</aside>'

        # 7. Snippets & Charsheets
        if tag in ["charsheet", "snippet", "#"]:
            escaped = (
                content.replace("[", "&#91;")
                .replace("]", "&#93;")
                .replace("\n", "<br />")
            )
            if tag == "charsheet":
                idx = next(self.counters["charsheet"])
                return f'<blockquote class="spoiler closed charsheet" data-charsheet="{idx}"><div class="tag">[ <span class="open">+</span><span class="close">-</span> ] <span class="snippetName">{attr}</span></div><div class="hidden">{content}</div><div style="display:none;" class="snippetBBCode">{escaped}</div></blockquote>'
            if tag == "snippet":
                idx = next(self.counters["snippetCount"])
                return f'<blockquote class="spoiler closed snippet" data-snippetidx="{idx}"><div class="tag">[ <span class="open">+</span><span class="close">-</span> ] <span class="snippetName">{attr}</span></div><div class="hidden">{content}</div><div style="display:none;" class="snippetBBCode">{escaped}</div></blockquote>'
            if tag == "#":
                idx = next(self.counters["formField"])
                return f'<div class="formBlock" data-blockfieldidx="{idx}"><h2 class="headerbar hbDark">{attr}</h2><div class="formBlockRendered">{content}</div><div style="display:none;" class="formBlockBBCode">{escaped}</div></div>'

        # Fallback for simple tags
        if tag in self.simple_map:
            t, c = self.simple_map[tag]
            c_attr = f' class="{c}"' if c and "=" not in c else f" {c}" if c else ""
            return f"<{t}{c_attr}>{content}</{t}>"

        return f"[{tag}]{content}[/{tag}]"

    def _split_by_header(self, title, text, css_class, collection_data):
        ret = [f'<div class="{css_class} ddCollection"{collection_data}>']
        if title:
            ret.append(f'<h2 class="headerbar hbDark">{title}</h2>')

        lines = text.strip().split("\n")
        ability_open, ability_raw = False, []

        for line in lines:
            if line.startswith("#"):
                if ability_open:
                    raw_str = (
                        "".join(ability_raw).replace("[", "&#91;").replace("]", "&#93;")
                    )
                    ret.append(
                        f'</div><div style="display:none" class="abilityBBCode">{raw_str}</div></div>'
                    )

                ret.append(
                    f'<div class="ability"><span class="abilityName">{line[1:].strip()}</span><a href="" class="ability_notesLink">Notes</a><div class="abilityNotes notes">'
                )
                ability_open, ability_raw = True, []
            else:
                ret.append(line + "\n")
                ability_raw.append(line + "&#10;")

        if ability_open:
            raw_str = "".join(ability_raw).replace("[", "&#91;").replace("]", "&#93;")
            ret.append(
                f'</div><div style="display:none" class="abilityBBCode">{raw_str}</div></div>'
            )

        ret.append("</div>")
        return "".join(ret)

    def _handle_form_fields(self, text):
        def sub_f(m):
            var_name, val = m.group(2) or "", m.group(3) or ""
            is_calc = var_name.endswith("$")
            if is_calc:
                var_name = var_name.rstrip("$")
            idx = next(self.counters["formField"])
            classes = [
                "formVal",
                "formVar" if var_name else "",
                "formCalc" if is_calc else "",
            ]

            chk = re.search(r"(\d+)/(\d+)", val)
            if chk:
                v, total = int(chk.group(1)), int(chk.group(2))
                if 0 < total <= 20:
                    html_val = ('<input type="checkbox" checked/>' * v) + (
                        '<input type="checkbox"/>' * (total - v)
                    )
                    classes.append("formCheck")
                    return f'<span class="{" ".join(filter(None, classes))}" data-varname="{var_name}" data-formfieldidx="{idx}">{html_val}</span>'

            classes.append("formText" if not is_calc else "")
            return f'<span class="{" ".join(filter(None, classes))}" data-varname="{var_name}" data-formfieldidx="{idx}">{"" if is_calc else val}</span>'

        return re.sub(r"\[\_(([\w\_]*)\=)?([^\]]*)\]", sub_f, text)


# Usage
parser = BBCodeParser()
BBCode2Html = parser.parse
