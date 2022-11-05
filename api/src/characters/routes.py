from flask import Blueprint, request

from common.response import response

characters = Blueprint("characters", __name__)


@characters.route("/", methods=["POST"])
def create_character():
    pass
