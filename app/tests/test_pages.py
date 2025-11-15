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
        "/register",
        data={"username": "bob", "password": "verysecure"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert r.headers["Location"].endswith("/board")


# ТЕСТЫ /board


def test_board_requires_auth(client):
    r = client.get("/board", follow_redirects=False)
    assert r.status_code in (302, 303)


def test_add_task_success(client):
    client.post("/register", data={"username": "carol", "password": "verysecure"})
    client.post("/login", data={"username": "carol", "password": "verysecure"})
    r = client.post(
        "/board",
        data={"name": "Task A", "status": "ideas", "description": "desc"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    page = client.get("/board")
    assert page.status_code == 200
    assert b"Task A" in page.data
