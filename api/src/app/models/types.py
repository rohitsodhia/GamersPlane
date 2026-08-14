from pydantic import BaseModel
from sqlalchemy.types import JSON, TypeDecorator


class ClassWrappedJSON(TypeDecorator):
    impl = JSON

    cache_ok = True

    def __init__(self, container: type[BaseModel], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.container = container

    def process_bind_param(self, value: BaseModel | None, dialect) -> dict | None:
        if value is not None:
            return value.model_dump(mode="json")

    def process_result_value(self, value: dict | None, dialect) -> BaseModel | None:
        if value is not None:
            return self.container(**value)
        return self.container()
