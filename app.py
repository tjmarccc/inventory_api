from flask import Flask, jsonify
from config import Config
from extensions import db, jwt, migrate
from models import TokenBlocklist
from routes.auth import auth_bp
from routes.products import product_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    @jwt.token_in_blocklist_loader
    def is_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        return (
            db.session.query(TokenBlocklist.id).filter_by(jti=jti).first() is not None
        )

    @jwt.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        return jsonify({"message": "Token has been revoked"}), 401

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return jsonify({"message": "Token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify({"message": "Invalid token", "detail": reason}), 401

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify({"message": "Authorization token required"}), 401

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(product_bp, url_prefix="/products")

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"message": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"message": "Method not allowed"}), 405

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"message": "Internal server error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
