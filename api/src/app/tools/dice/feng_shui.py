from .base import Roll, RollResult
from .basic import BasicDie


class FengShuiRollResult(RollResult):
    type: str
    action_value: int
    positive: list[int]
    negative: list[int]
    extra: int | None = None
    total: int


class FengShuiRoll(Roll):
    VALID_TYPES = {"standard", "fortune", "closed"}

    def __init__(self):
        super().__init__()
        self.die = BasicDie(6)
        self.action_value = 0
        self.type = "standard"

    def new_roll(
        self, roll_string: str, roll_type: str = "standard", **options
    ) -> None:
        if roll_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid feng shui roll type: {roll_type}")
        self.action_value = max(0, int(roll_string))
        self.type = roll_type

    def roll(self) -> FengShuiRollResult:
        positive: list[int] = []
        negative: list[int] = []
        extra = None

        if self.type in ("standard", "fortune"):
            value = self.die.roll()
            positive.append(value)
            while value == 6:
                value = self.die.roll()
                positive.append(value)

            value = self.die.roll()
            negative.append(value)
            while value == 6:
                value = self.die.roll()
                negative.append(value)

            if self.type == "fortune":
                extra = self.die.roll()
        else:  # closed
            positive.append(self.die.roll())
            negative.append(self.die.roll())

        total = self.action_value + sum(positive) - sum(negative) + (extra or 0)
        self.result = FengShuiRollResult(
            type=self.type,
            action_value=self.action_value,
            positive=positive,
            negative=negative,
            extra=extra,
            total=total,
        )
        return self.result
