import random
import re

from .base import Die, Roll, RollResult

DICE_FACES: dict[str, list[str]] = {
    "ability": [
        "",
        "success",
        "success",
        "advantage",
        "success_success",
        "success_advantage",
        "advantage_advantage",
    ],
    "proficiency": [
        "",
        "success",
        "success",
        "advantage",
        "success_success",
        "success_success",
        "success_advantage",
        "success_advantage",
        "success_advantage",
        "advantage_advantage",
        "advantage_advantage",
        "triumph",
    ],
    "boost": [
        "",
        "",
        "success",
        "advantage",
        "success_advantage",
        "advantage_advantage",
    ],
    "difficulty": [
        "",
        "failure",
        "threat",
        "threat",
        "threat",
        "failure_failure",
        "failure_threat",
        "threat_threat",
    ],
    "challenge": [
        "",
        "failure",
        "failure",
        "threat",
        "threat",
        "failure_failure",
        "failure_failure",
        "failure_threat",
        "failure_threat",
        "threat_threat",
        "threat_threat",
        "despair",
    ],
    "setback": ["", "", "failure", "failure", "threat", "threat"],
    "force": [
        "whiteDot",
        "whiteDot",
        "whiteDot_whiteDot",
        "whiteDot_whiteDot",
        "whiteDot_whiteDot",
        "blackDot",
        "blackDot",
        "blackDot",
        "blackDot",
        "blackDot",
        "blackDot",
        "blackDot_blackDot",
    ],
}

DIE_SHORTHAND = {
    "a": "ability",
    "p": "proficiency",
    "b": "boost",
    "d": "difficulty",
    "c": "challenge",
    "s": "setback",
    "f": "force",
}

ICON_KEYS = [
    "success",
    "advantage",
    "triumph",
    "failure",
    "threat",
    "despair",
    "whiteDot",
    "blackDot",
]


class StarWarsFFGDie(Die[str]):
    def __init__(self, die_type: str):
        if die_type not in DICE_FACES:
            raise ValueError(f"Invalid die type: {die_type}")
        super().__init__(len(DICE_FACES[die_type]))
        self.die_type = die_type

    def roll(self) -> str:
        return DICE_FACES[self.die_type][random.randint(0, self.sides - 1)]


class StarWarsFFGRollTerm(RollResult):
    die: str
    result: str


class StarWarsFFGRollResult(RollResult):
    rolls: list[StarWarsFFGRollTerm]
    totals: dict[str, int]
    net_success: int
    net_advantage: int


class StarWarsFFGRoll(Roll):
    def __init__(self):
        super().__init__()
        self._dice_names: list[str] = []
        self._dice: dict[str, StarWarsFFGDie] = {}

    def new_roll(self, roll_string: str, **options) -> None:
        self._dice_names = []
        self._dice = {}
        for token in re.findall(r"\w+", roll_string):
            die_type = token.lower()
            if len(die_type) == 1 and die_type in DIE_SHORTHAND:
                die_type = DIE_SHORTHAND[die_type]
            elif die_type not in DIE_SHORTHAND.values():
                continue
            self._dice_names.append(die_type)
            self._dice.setdefault(die_type, StarWarsFFGDie(die_type))

    def roll(self) -> StarWarsFFGRollResult:
        totals = dict.fromkeys(ICON_KEYS, 0)
        rolls = []
        for die_type in self._dice_names:
            result = self._dice[die_type].roll()
            rolls.append(StarWarsFFGRollTerm(die=die_type, result=result))
            if result:
                for icon in result.split("_"):
                    totals[icon] += 1

        self.result = StarWarsFFGRollResult(
            rolls=rolls,
            totals=totals,
            net_success=(totals["success"] + totals["triumph"])
            - (totals["failure"] + totals["despair"]),
            net_advantage=totals["advantage"] - totals["threat"],
        )
        return self.result
