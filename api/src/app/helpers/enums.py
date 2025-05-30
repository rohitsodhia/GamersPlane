from enum import Enum


class LabelEnum(Enum):
    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, *args):
        self.label = args[1]
        self.full_value = args
