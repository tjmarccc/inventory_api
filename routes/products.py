from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from marshmallow import ValidationError

from extensions import db
from models import Product
from schemas import ProductSchema

product_bp = Blueprint("products", __name__)
product_schema = ProductSchema()


def _current_user_id():
    return int(get_jwt_identity())


def _can_modify(product):
    return product.user_id == _current_user_id() or get_jwt().get("role") == "admin"


@product_bp.route("", methods=["GET"], strict_slashes=False)
def get_products():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

    query = Product.query
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    if category:
        query = query.filter(Product.category == category)

    pagination = query.order_by(Product.id).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "products": [p.to_dict() for p in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        }
    ), 200


@product_bp.route("", methods=["POST"], strict_slashes=False)
@jwt_required()
def create_product():
    try:
        data = product_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    product = Product(**data, user_id=_current_user_id())
    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201


@product_bp.route("/my-products", methods=["GET"])
@jwt_required()
def my_products():
    products = Product.query.filter_by(user_id=_current_user_id()).order_by(Product.id).all()
    return jsonify({"products": [p.to_dict() for p in products]}), 200


@product_bp.route("/<int:product_id>", methods=["GET"])
def get_product(product_id):
    product = db.get_or_404(Product, product_id)
    return jsonify(product.to_dict()), 200


@product_bp.route("/<int:product_id>", methods=["PUT"])
@jwt_required()
def update_product(product_id):
    product = db.get_or_404(Product, product_id)
    if not _can_modify(product):
        return jsonify({"message": "Forbidden"}), 403

    try:
        data = product_schema.load(request.get_json(silent=True) or {}, partial=True)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    for key, value in data.items():
        setattr(product, key, value)
    db.session.commit()
    return jsonify(product.to_dict()), 200


@product_bp.route("/<int:product_id>", methods=["DELETE"])
@jwt_required()
def delete_product(product_id):
    product = db.get_or_404(Product, product_id)
    if not _can_modify(product):
        return jsonify({"message": "Forbidden"}), 403

    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Product deleted"}), 200