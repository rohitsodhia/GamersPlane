from flask import Blueprint, request

from helpers.response import response

tools = Blueprint("tools", __name__)


@tools.route("/dice", methods=["GET"])
def roll_dice():
    pass
