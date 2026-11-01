from app.schema_base import (
    SchemaBase,
    escape_html,
    filtered_str,
    nl2br,
    strip_whitespace,
)


class DefaultPipelineSchema(SchemaBase):
    text: str = filtered_str()


class CustomPipelineSchema(SchemaBase):
    text: str = filtered_str(pipelines=[nl2br, escape_html])


class ReversedPipelineSchema(SchemaBase):
    text: str = filtered_str(pipelines=[escape_html, nl2br])


class NoPipelineSchema(SchemaBase):
    text: str


class DedupedPipelineSchema(SchemaBase):
    text: str = filtered_str(pipelines=[strip_whitespace, strip_whitespace, nl2br])


class TestApplyPipelines:
    def test_default_pipeline_strips_then_applies_nl2br(self):
        # Stripping first means a trailing/leading newline never becomes a
        # <br> that strip_whitespace can't remove.
        schema = DefaultPipelineSchema(text="\n hello\nworld \n")

        assert schema.text == "hello<br>world"

    def test_custom_pipeline_runs_in_declared_order(self):
        # The same two steps in opposite orders differ: <br> is only escaped
        # when nl2br runs first.
        assert CustomPipelineSchema(text="a\nb").text == "a&lt;br&gt;b"
        assert ReversedPipelineSchema(text="a\nb").text == "a<br>b"

    def test_field_without_pipelines_is_untouched(self):
        schema = NoPipelineSchema(text="  raw  ")

        assert schema.text == "  raw  "

    def test_non_string_fields_are_ignored(self):
        class IntSchema(SchemaBase):
            value: int = filtered_str()

        schema = IntSchema(value=5)

        assert schema.value == 5

    def test_duplicate_pipelines_are_deduped(self):
        field_info = DedupedPipelineSchema.model_fields["text"]

        assert field_info.json_schema_extra["pipelines"] == [strip_whitespace, nl2br]
