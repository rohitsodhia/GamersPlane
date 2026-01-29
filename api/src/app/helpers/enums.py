from enum import Enum


class LabelEnum(Enum):
    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, *args):
        self.label = args[1]
        self.full_value = args


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
