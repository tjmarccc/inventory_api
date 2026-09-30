import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models import User


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="john", password="1234"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username="john", password="1234"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(client, username="john", password="1234"):
    register(client, username, password)
    token = login(client, username, password).get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


PRODUCT = {
    "name": "Generator",
    "description": "20KVA generator",
    "price": 20000000,
    "quantity": 5,
    "category": "Electrical",
}


def test_register(client):
    res = register(client)
    assert res.status_code == 201


def test_duplicate_registration(client):
    register(client)
    res = register(client)
    assert res.status_code == 409


def test_login(client):
    register(client)
    res = login(client)
    assert res.status_code == 200
    data = res.get_json()
    assert "access_token" in data and "refresh_token" in data


def test_invalid_login(client):
    register(client)
    res = login(client, password="wrong")
    assert res.status_code == 401


def test_protected_endpoint_without_token(client):
    assert client.post("/products", json=PRODUCT).status_code == 401


def test_invalid_token(client):
    res = client.post(
        "/products", json=PRODUCT, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert res.status_code in (401, 422)


def test_refresh_token(client):
    register(client)
    refresh_token = login(client).get_json()["refresh_token"]
    res = client.post(
        "/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert res.status_code == 200
    assert "access_token" in res.get_json()


def test_create_product(client):
    headers = auth_headers(client)
    res = client.post("/products", json=PRODUCT, headers=headers)
    assert res.status_code == 201
    assert res.get_json()["name"] == "Generator"


def test_product_validation(client):
    headers = auth_headers(client)
    bad = {**PRODUCT, "price": -5}
    assert client.post("/products", json=bad, headers=headers).status_code == 400
    assert (
        client.post("/products", json={"name": "No price"}, headers=headers).status_code
        == 400
    )


def test_search_filter_pagination(client):
    headers = auth_headers(client)
    client.post("/products", json=PRODUCT, headers=headers)
    client.post(
        "/products",
        json={**PRODUCT, "name": "Cable", "category": "Wiring"},
        headers=headers,
    )

    assert client.get("/products?search=generator").get_json()["total"] == 1
    assert client.get("/products?category=Wiring").get_json()["total"] == 1
    page = client.get("/products?page=1&per_page=1").get_json()
    assert len(page["products"]) == 1 and page["pages"] == 2


def test_get_one_and_my_products(client):
    headers = auth_headers(client)
    pid = client.post("/products", json=PRODUCT, headers=headers).get_json()["id"]
    assert client.get(f"/products/{pid}").status_code == 200
    assert client.get("/products/9999").status_code == 404
    mine = client.get("/products/my-products", headers=headers).get_json()
    assert len(mine["products"]) == 1


def test_update_product(client):
    headers = auth_headers(client)
    pid = client.post("/products", json=PRODUCT, headers=headers).get_json()["id"]
    res = client.put(f"/products/{pid}", json={"quantity": 10}, headers=headers)
    assert res.status_code == 200
    assert res.get_json()["quantity"] == 10


def test_delete_product(client):
    headers = auth_headers(client)
    pid = client.post("/products", json=PRODUCT, headers=headers).get_json()["id"]
    assert client.delete(f"/products/{pid}", headers=headers).status_code == 200
    assert client.get(f"/products/{pid}").status_code == 404


def test_ownership_forbidden(client):
    owner = auth_headers(client, "alice", "1234")
    other = auth_headers(client, "bob", "1234")
    pid = client.post("/products", json=PRODUCT, headers=owner).get_json()["id"]
    assert (
        client.put(f"/products/{pid}", json={"quantity": 1}, headers=other).status_code
        == 403
    )
    assert client.delete(f"/products/{pid}", headers=other).status_code == 403


def test_admin_can_manage_any_product(client, app):
    owner = auth_headers(client, "alice", "1234")
    pid = client.post("/products", json=PRODUCT, headers=owner).get_json()["id"]

    register(client, "admin", "1234")
    admin = User.query.filter_by(username="admin").first()
    admin.role = "admin"
    db.session.commit()
    token = login(client, "admin", "1234").get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert (
        client.put(
            f"/products/{pid}", json={"quantity": 99}, headers=headers
        ).status_code
        == 200
    )
    assert client.delete(f"/products/{pid}", headers=headers).status_code == 200


def test_logout_revokes_token(client):
    headers = auth_headers(client)
    assert client.post("/products", json=PRODUCT, headers=headers).status_code == 201
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.post("/products", json=PRODUCT, headers=headers).status_code == 401
