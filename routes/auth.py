from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from marshmallow import ValidationError

from extensions import db
from models import TokenBlocklist, User
from schemas import UserSchema

auth_bp = Blueprint("auth", __name__)
user_schema = UserSchema()


def _access_token_for(user):
    return create_access_token(identity=str(user.id), additional_claims={"role": user.role})


@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = user_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"message": "Username already exists"}), 409

    user = User(username=data["username"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User registered successfully", "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = user_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
        return jsonify({"message": "Invalid username or password"}), 401

    return jsonify(
        {
            "access_token": _access_token_for(user),
            "refresh_token": create_refresh_token(identity=str(user.id)),
        }
    ), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify({"message": "User not found"}), 404
    return jsonify({"access_token": _access_token_for(user)}), 200


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    db.session.add(TokenBlocklist(jti=jti))
    db.session.commit()
    return jsonify({"message": "Successfully logged out"}), 200