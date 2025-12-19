import re
from random import randint


def test_pages_render(client):
    assert client.get("/").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200


def test_register_success_redirect(client):
    r = client.post(
        "/register",
        data={"username": "alice", "password": "verysecure"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert r.headers["Location"].endswith("/login")


def test_login_success_redirect(client):
    r = client.post(
        "/register",
        data={"username": "bob", "password": "verysecure"},
        follow_redirects=False,
    )
    r = client.post(
        "/login",
        data={"username": "bob", "password": "verysecure"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert r.headers["Location"].endswith("/boards")


def test_board_requires_auth(client):
    r = client.get("/boards", follow_redirects=False)
    assert r.status_code in (302, 303)


def test_create_board_and_task_success(client):
    username = "carol" + str(randint(100, 200))
    client.post("/register", data={"username": username, "password": "verysecure"})
    client.post("/login", data={"username": username, "password": "verysecure"})
    r = client.post(
        "/boards",
        data={"name": "my board"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    board_id = int(re.findall(rb"href=\"/board/(\d+)", r.data)[0])

    r = client.post(
        f"/board/{board_id}",
        data={"name": "Crazy Task"},
        follow_redirects=True
    )
    assert r.status_code == 200
    assert b"Crazy Task" in r.data