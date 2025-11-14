from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user

import os

from db import db, Card, User, Board

app = Flask(__name__)


app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "CHANGEME"  # TODO: Change this key later

db.init_app(app)

with app.app_context():  # TODO: Create tables only if they does not exist
    db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("board"))
        else:
            return render_template("login.html", error="Логин или пароль не верен!")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username and password:
            user = User.query.filter_by(username=username).first()
            if user:
                return render_template("register.html", error="Логин уже занят!")
            password_hash = generate_password_hash(password)
            new_user = User(username=username, password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for("login"))


@app.route("/board", methods=["GET", "POST"])
def board():
    return "Board logic will be here"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7007, debug=True)
