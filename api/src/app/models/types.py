import json

from pydantic import BaseModel
from sqlalchemy.types import JSON, TypeDecorator


class ClassWrappedJSON(TypeDecorator):
    impl = JSON

    cache_ok = True

    def __init__(self, container: type[BaseModel], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.container = container

    def process_bind_param(self, value: BaseModel | None, dialect) -> str | None:
        if value is not None:
            return value.model_dump_json()

    def process_result_value(self, value: str | None, dialect) -> BaseModel | None:
        if value is not None:
            return self.container(**json.loads(value))
        return self.container()
