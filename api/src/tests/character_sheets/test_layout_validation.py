import pytest

from app.character_sheets.defaults import default_sheet_layout, empty_sheet_layout
from app.character_sheets.layout_validation import validate_sheet_layout
from app.exceptions import ValidationError


class TestValidateSheetLayoutAccepts:
    @pytest.mark.parametrize(
        "factory", [default_sheet_layout, empty_sheet_layout], ids=["default", "empty"]
    )
    def test_accepts_the_canned_layouts(self, factory):
        validate_sheet_layout(factory())

    def test_accepts_deeply_nested_containers_and_child_array_keys(self):
        layout = {
            "version": 1,
            "classes": {"bubble": {"width": "30px"}},
            "elements": [
                {
                    "type": "section",
                    "content": [
                        {
                            "type": "grid",
                            "name": "stats",
                            "header": [{"type": "text", "text": "Score"}],
                            "row": [{"type": "input", "name": "score"}],
                        },
                        {
                            "type": "repeater",
                            "name": "skills",
                            "header": [{"type": "text", "text": "Skill"}],
                            "content": [{"type": "input", "name": "skill"}],
                        },
                    ],
                }
            ],
        }

        validate_sheet_layout(layout)

    def test_ignores_non_element_array_keys(self):
        # `items` (loop entries) and `values` (select options) are not element
        # arrays -- their bare-object entries must not be walked as nodes.
        layout = {
            "version": 1,
            "elements": [
                {
                    "type": "select",
                    "name": "size",
                    "values": [{"value": "s", "label": "Small"}],
                },
                {
                    "type": "loop",
                    "items": [{"label": "a"}, {"label": "b"}],
                    "content": [{"type": "text", "text": "x"}],
                },
            ],
        }

        validate_sheet_layout(layout)


class TestValidateSheetLayoutRejects:
    def test_rejects_a_non_object_layout(self):
        with pytest.raises(ValidationError):
            validate_sheet_layout([{"type": "section"}])

    @pytest.mark.parametrize(
        "layout",
        [{"elements": []}, {"version": 2, "elements": []}],
        ids=["missing", "unsupported"],
    )
    def test_rejects_a_bad_version(self, layout):
        with pytest.raises(ValidationError, match="version"):
            validate_sheet_layout(layout)

    def test_rejects_elements_that_is_not_an_array(self):
        with pytest.raises(ValidationError, match="elements"):
            validate_sheet_layout({"version": 1, "elements": {}})

    def test_rejects_classes_that_is_not_an_object(self):
        with pytest.raises(ValidationError, match="classes"):
            validate_sheet_layout({"version": 1, "classes": [], "elements": []})

    def test_rejects_an_element_that_is_not_an_object(self):
        with pytest.raises(ValidationError, match=r"elements\[0\]"):
            validate_sheet_layout({"version": 1, "elements": ["header"]})

    @pytest.mark.parametrize(
        "node", [{"text": "hi"}, {"type": ""}], ids=["absent", "empty-string"]
    )
    def test_rejects_an_element_without_a_usable_type(self, node):
        with pytest.raises(ValidationError, match="missing a 'type'"):
            validate_sheet_layout({"version": 1, "elements": [node]})

    def test_rejects_an_unknown_element_type(self):
        with pytest.raises(ValidationError, match="unknown type 'sektion'"):
            validate_sheet_layout(
                {"version": 1, "elements": [{"type": "sektion", "content": []}]}
            )

    def test_reports_the_path_to_a_nested_bad_node(self):
        layout = {
            "version": 1,
            "elements": [
                {"type": "section", "content": [{"type": "bogus"}]},
            ],
        }

        with pytest.raises(ValidationError, match=r"elements\[0\].content\[0\]"):
            validate_sheet_layout(layout)

    def test_rejects_a_child_array_key_that_is_not_an_array(self):
        layout = {
            "version": 1,
            "elements": [{"type": "section", "content": {"type": "header"}}],
        }

        with pytest.raises(ValidationError, match="content must be an array"):
            validate_sheet_layout(layout)

    def test_rejects_a_pathologically_deep_layout(self):
        node = {"type": "section", "content": []}
        root = node
        for _ in range(200):
            child = {"type": "section", "content": []}
            node["content"].append(child)
            node = child

        with pytest.raises(ValidationError, match="nests too deeply"):
            validate_sheet_layout({"version": 1, "elements": [root]})
