from flask import Flask
from werkzeug.security import generate_password_hash, check_password_hash
import os

from db import db, Card, User, Board

app = Flask(__name__)


app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
db.init_app(app)

with app.app_context():
    db.create_all()


@app.route("/")
def index():
    return "Flask test"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7007, debug=True)
