from functools import reduce
from typing import Any, Callable, List, Optional, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic.config import JsonDict
from pydantic.fields import FieldInfo


def escape_html(v: str) -> str:
    import html

    return html.escape(v)


def nl2br(v: str) -> str:
    return v.replace("\n", "<br>")


def strip_whitespace(v: str) -> str:
    return v.strip()


PipelineMap = List[Callable[[str], str]]
DEFAULT_PIPELINES = [nl2br, strip_whitespace]


def filtered_str(
    pipelines: Optional[PipelineMap] = None,
    **kwargs: Any,
) -> Any:
    if pipelines is None:
        pipelines = DEFAULT_PIPELINES
    pipelines = list(dict.fromkeys(pipelines))
    return Field(
        default=kwargs.get("default"),
        json_schema_extra=cast(JsonDict, {"pipelines": pipelines}),
        **kwargs,
    )


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="after")
    @classmethod
    def apply_pipelines(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, str):
            return value

        field_info: Optional[FieldInfo] = cls.model_fields.get(info.field_name or "")
        if not field_info or not isinstance(field_info.json_schema_extra, dict):
            return value

        if "pipelines" not in field_info.json_schema_extra:
            return value

        pipelines = field_info.json_schema_extra.get("pipelines")
        pipelines = cast(list[Callable], pipelines)

        if not isinstance(pipelines, list):
            return value

        return reduce(lambda val, f: f(val), pipelines, value)
