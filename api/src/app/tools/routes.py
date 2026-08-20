from typing import Literal

from fastapi import APIRouter

from app.exceptions import ValidationError
from app.helpers.decorators import public
from app.tools.dice import get_roll
from app.tools.dice.basic import BasicRollResult
from app.tools.dice.fate import FateRollResult
from app.tools.dice.feng_shui import FengShuiRollResult
from app.tools.dice.star_wars_ffg import StarWarsFFGRollResult

tools = APIRouter(prefix="/tools")

DiceRollResponse = (
    BasicRollResult | FateRollResult | FengShuiRollResult | StarWarsFFGRollResult
)


@tools.get("/dice", response_model=DiceRollResponse)
@public
def roll_dice(
    system: Literal["basic", "fate", "fengshui", "starwarsffg"],
    roll: str,
    reroll_aces: bool = False,
    modifier: int = 0,
    roll_type: Literal["standard", "fortune", "closed"] = "standard",
):
    try:
        result = get_roll(
            system,
            roll,
            reroll_aces=reroll_aces,
            modifier=modifier,
            roll_type=roll_type,
        ).result
    except ValueError as e:
        raise ValidationError(str(e))
    return result
