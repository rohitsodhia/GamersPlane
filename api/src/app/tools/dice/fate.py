import random

from .base import Roll, RollResult

MAX_DICE = 100


class FateRollResult(RollResult):
    rolls: list[int]
    modifier: int
    positive: int
    blank: int
    negative: int
    total: int


class FateRoll(Roll):
    def __init__(self):
        super().__init__()
        self.num_dice = 0
        self.modifier = 0

    def new_roll(self, roll_string: str, modifier: int = 0, **options) -> None:
        num_dice = int(roll_string)
        if num_dice < 1 or num_dice > MAX_DICE:
            raise ValueError(f"Invalid dice count: {num_dice}")
        self.num_dice = num_dice
        self.modifier = modifier

    def roll(self) -> FateRollResult:
        rolls = [random.randint(1, 3) - 2 for _ in range(self.num_dice)]
        self.result = FateRollResult(
            rolls=rolls,
            modifier=self.modifier,
            positive=rolls.count(1),
            blank=rolls.count(0),
            negative=rolls.count(-1),
            total=sum(rolls) + self.modifier,
        )
        return self.result
