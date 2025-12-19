import datetime

from app.main import datetime_msk, allowed_file


def test_datetime_stringify():
    dt = datetime.datetime(2025, 10, 10, 10, 10, 10)
    assert datetime_msk(dt) == "10.10.2025 13:10 (МСК)"

def test_allowed_extensions():
    assert allowed_file("sticker.webp")
    assert not allowed_file("okak.zip")
    assert allowed_file("meow.png")
    assert not allowed_file("hackersky.script.py")