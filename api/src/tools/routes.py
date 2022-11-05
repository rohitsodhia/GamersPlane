from flask import Blueprint, request

from common.response import response

tools = Blueprint("tools", __name__, url_prefix="/tools")


@tools.route("/dice", methods=["GET"])
def roll_dice():
    pass
