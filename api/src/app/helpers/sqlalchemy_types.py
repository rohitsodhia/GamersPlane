from enum import Enum

from sqlalchemy import types


def EnumValueDecorator(enum_class: type[Enum], impl_class):
    class AnonymousEnumDecorator(types.TypeDecorator):
        impl = impl_class
        cache_ok = True

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            return value.value if isinstance(value, Enum) else value

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            return enum_class(value)

    return AnonymousEnumDecorator
