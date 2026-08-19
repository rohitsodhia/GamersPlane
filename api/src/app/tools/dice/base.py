from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Die(ABC, Generic[T]):
    def __init__(self, sides: int):
        self.sides = sides

    @abstractmethod
    def roll(self) -> T:
        """Roll the die and return its face value."""


class RollResult(BaseModel):
    pass


class Roll(ABC):
    def __init__(self):
        self.result: RollResult | None = None

    @abstractmethod
    def new_roll(self, roll_string: str, **options) -> None:
        """Parse the roll string and options in preparation for rolling."""

    @abstractmethod
    def roll(self) -> RollResult:
        """Perform the roll, store the result on self.result, and return it."""
