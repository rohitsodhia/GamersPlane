import random
import re

from .base import Die, Roll, RollResult

TERM_RE = re.compile(
    r"(?P<sign>[+-]?)(?:(?P<count>\d*)d(?P<sides>\d+)(?:(?P<keep>[hl])(?P<keep_count>\d+))?|(?P<mod>\d+))",
    re.IGNORECASE,
)


class BasicDie(Die[int]):
    def __init__(self, sides: int):
        if sides < 2:
            raise ValueError(f"Invalid die sides: {sides}")
        super().__init__(min(sides, 1000))

    def roll(self) -> int:
        return random.randint(1, self.sides)


class BasicDiceTerm(RollResult):
    count: int
    sides: int
    sign: int
    keep_high: bool | None = None
    keep_count: int | None = None
    rolls: list[int | list[int]] = []
    dropped: list[int] = []
    subtotal: int = 0


class BasicRollGroup(RollResult):
    expression: str
    terms: list[BasicDiceTerm]
    modifier: int = 0
    total: int = 0


class BasicRollResult(RollResult):
    groups: list[BasicRollGroup]
    total: int


class BasicRoll(Roll):
    def __init__(self):
        super().__init__()
        self.reroll_aces = False
        self._groups: list[BasicRollGroup] = []
        self._dice: dict[int, BasicDie] = {}

    def new_roll(self, roll_string: str, reroll_aces: bool = False, **options) -> None:
        self.reroll_aces = reroll_aces
        self._groups = []
        self._dice = {}

        for expression in roll_string.replace(" ", "").split(","):
            if not expression:
                continue

            terms: list[BasicDiceTerm] = []
            modifier = 0
            for match in TERM_RE.finditer(expression):
                sign = -1 if match.group("sign") == "-" else 1
                if match.group("sides") is not None:
                    sides = int(match.group("sides"))
                    count = int(match.group("count")) if match.group("count") else 1
                    if count < 1:
                        raise ValueError(f"Invalid dice count: {count}")
                    keep = match.group("keep")
                    keep_count = (
                        int(match.group("keep_count"))
                        if match.group("keep_count")
                        else None
                    )
                    terms.append(
                        BasicDiceTerm(
                            count=count,
                            sides=sides,
                            sign=sign,
                            keep_high=(keep.lower() == "h") if keep else None,
                            keep_count=keep_count,
                        )
                    )
                    self._dice.setdefault(sides, BasicDie(sides))
                elif match.group("mod") is not None:
                    modifier += sign * int(match.group("mod"))

            if terms or modifier:
                self._groups.append(
                    BasicRollGroup(
                        expression=expression, terms=terms, modifier=modifier
                    )
                )

    def roll(self) -> BasicRollResult:
        for group in self._groups:
            group.total = 0
            for term in group.terms:
                die = self._dice[term.sides]
                rolls: list[int | list[int]] = []
                for _ in range(term.count):
                    value = die.roll()
                    if self.reroll_aces and value == term.sides and value > 1:
                        chain = [value]
                        while value == term.sides:
                            value = die.roll()
                            chain.append(value)
                        rolls.append(chain)
                    else:
                        rolls.append(value)
                term.rolls = rolls

                values = [sum(r) if isinstance(r, list) else r for r in rolls]
                drop_count = (
                    max(0, term.count - term.keep_count)
                    if term.keep_count is not None
                    else 0
                )
                order = sorted(
                    range(len(values)),
                    key=lambda i: values[i],
                    reverse=not term.keep_high,
                )
                term.dropped = order[:drop_count]

                term.subtotal = term.sign * sum(
                    val for i, val in enumerate(values) if i not in term.dropped
                )
                group.total += term.subtotal
            group.total += group.modifier

        total = sum(group.total for group in self._groups)
        self.result = BasicRollResult(groups=self._groups, total=total)
        return self.result
