from .base import Roll
from .basic import BasicRoll
from .fate import FateRoll
from .feng_shui import FengShuiRoll
from .star_wars_ffg import StarWarsFFGRoll

ROLL_TYPES: dict[str, type[Roll]] = {
    "basic": BasicRoll,
    "fate": FateRoll,
    "fengshui": FengShuiRoll,
    "starwarsffg": StarWarsFFGRoll,
}


def get_roll(system: str, roll_string: str, **options) -> Roll:
    try:
        roll_cls = ROLL_TYPES[system]
    except KeyError:
        raise ValueError(f"Invalid roll type: {system}")

    roll = roll_cls()
    roll.new_roll(roll_string, **options)
    roll.roll()
    return roll
