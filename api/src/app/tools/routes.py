from flask import Blueprint

tools = Blueprint("tools", __name__, url_prefix="/tools")


@tools.route("/dice", methods=["GET"])
def roll_dice():
    pass
