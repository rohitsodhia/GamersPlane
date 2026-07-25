from app.schema_base import SchemaBase, escape_html, filtered_str, nl2br, strip_whitespace


class TestPipelineFunctions:
    def test_escape_html_escapes_special_characters(self):
        assert escape_html("<script>&") == "&lt;script&gt;&amp;"

    def test_nl2br_replaces_newlines(self):
        assert nl2br("line1\nline2") == "line1<br>line2"

    def test_strip_whitespace_trims_edges(self):
        assert strip_whitespace("  hello  ") == "hello"


class DefaultPipelineSchema(SchemaBase):
    text: str = filtered_str()


class CustomPipelineSchema(SchemaBase):
    text: str = filtered_str(pipelines=[strip_whitespace, escape_html])


class NoPipelineSchema(SchemaBase):
    text: str


class DedupedPipelineSchema(SchemaBase):
    text: str = filtered_str(pipelines=[strip_whitespace, strip_whitespace, nl2br])


class TestApplyPipelines:
    def test_default_pipeline_applies_nl2br_then_strips(self):
        schema = DefaultPipelineSchema(text="  hello\nworld  ")

        assert schema.text == "hello<br>world"

    def test_custom_pipeline_runs_in_declared_order(self):
        schema = CustomPipelineSchema(text="  <b>hi</b>  ")

        assert schema.text == "&lt;b&gt;hi&lt;/b&gt;"

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
