from enum import Enum

from sqlalchemy.types import TypeDecorator, TypeEngine


class LabelEnum(Enum):
    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, *args):
        self.label = args[1]
        self.full_value = args


class LabelEnumType(TypeDecorator):
    """Stores a LabelEnum member as its raw `.value` and reads it back as the enum member."""

    cache_ok = True
    impl = TypeEngine

    def __init__(self, enum_class, impl, **kwargs):
        super().__init__(**kwargs)
        self.enum_class = enum_class
        self._underlying = impl() if isinstance(impl, type) else impl

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(self._underlying)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value.value if isinstance(value, self.enum_class) else value

    def process_result_value(self, value, dialect):
        return None if value is None else self.enum_class(value)


# from enum import Enum


# class Status(Enum):
#     # Arguments: value, label
#     ACTIVE = (1, "Active Status")
#     INACTIVE = (0, "Inactive Status")

#     def __new__(cls, value, label):
#         member = object.__new__(cls)
#         member._value_ = value
#         member.label = label
#         return member

#     # Optional: override __str__ for a clean printout of the label
#     def __str__(self):
#         return self.label


# # Accessing the custom label attribute and other properties
# print(f"Status: {Status.ACTIVE.name}")
# print(f"Value: {Status.ACTIVE.value}")
# print(f"Custom Label: {Status.ACTIVE.label}")
# print(f"String representation: {str(Status.ACTIVE)}")
