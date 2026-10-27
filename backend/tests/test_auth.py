from app.security import login_throttle
from tests.conftest import PASSWORD


def test_protected_endpoints_require_login(anon_client):
    assert anon_client.get("/api/plants").status_code == 401
    assert anon_client.post("/api/plants", json={"name": "X"}).status_code == 401


def test_health_is_public(anon_client):
    response = anon_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_login_sets_httponly_cookie(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_cookie_flags(db, anon_client):
    from app.models import User
    from app.security import hash_password

    db.add(User(username="admin", password_hash=hash_password(PASSWORD)))
    db.commit()
    response = anon_client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie


def test_mutation_without_csrf_token_is_rejected(client):
    token = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/plants", json={"name": "X"}).status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert client.post("/api/plants", json={"name": "X"}).status_code == 201


def test_wrong_password_and_throttle(db, anon_client):
    from app.models import User
    from app.security import hash_password

    login_throttle.reset("testclient")
    db.add(User(username="admin", password_hash=hash_password(PASSWORD)))
    db.commit()
    for _ in range(5):
        assert anon_client.post("/api/auth/login", json={"username": "admin", "password": "sbagliata"}).status_code == 401
    assert anon_client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD}).status_code == 429
    login_throttle.reset("testclient")


def test_password_is_stored_hashed(db, client):
    from app.models import User

    user = db.query(User).one()
    assert PASSWORD not in user.password_hash
    assert user.password_hash.startswith("$argon2")


def test_logout_invalidates_session(client):
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_change_password(client):
    response = client.post(
        "/api/auth/password", json={"current_password": PASSWORD, "new_password": "nuova-password-lunga"}
    )
    assert response.status_code == 204
    bad = client.post("/api/auth/password", json={"current_password": "x", "new_password": "altra-password-lunga"})
    assert bad.status_code == 400
