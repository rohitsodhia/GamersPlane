from flask import Blueprint

characters = Blueprint("characters", __name__)


@characters.route("/", methods=["POST"])
def create_character():
    pass
