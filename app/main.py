import os
from flask import Flask, redirect, render_template, request, url_for, flash
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from db import db, Card, User, Board

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "CHANGEME" # TODO: Change for production
app.config["TEMPLATES_AUTO_RELOAD"] = True

db.init_app(app)
with app.app_context():
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
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("board"))
        else:
            error = "Логин или пароль не верен!"
    return render_template("login.html", error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            error = "Пожалуйста, заполните все поля."
        elif len(username) < 3:
            error = "Логин должен быть от 3 символов."
        elif len(password) < 8:
            error = "Пароль должен быть минимум 8 символов."
        elif User.query.filter_by(username=username).first():
            error = "Логин уже занят!"
        else:
            password_hash = generate_password_hash(password)
            new_user = User(username=username, password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            flash("Аккаунт создан! Теперь войдите.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", error=error)

@app.route("/board", methods=["GET", "POST"])
@login_required
def board():
    statuses = [
        ("ideas", "Идеи"),
        ("todo", "To Do"),
        ("wip", "В работе"),
        ("done", "Готово")
    ]
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        status = request.form.get("status", "ideas")
        description = request.form.get("description", "")
        if name and status in [s for s, t in statuses]:
            card = Card(
                name=name,
                description=description,
                status=status,
                deadline=None,
                board_id=1
            )
            db.session.add(card)
            db.session.commit()
            flash("Задача добавлена!", "success")
            return redirect(url_for("board"))
    tasks = Card.query.order_by(Card.id.desc()).all()
    return render_template("board.html", tasks=tasks, statuses=statuses)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7007, debug=True)