import os
from datetime import datetime, timedelta
from flask import Flask, redirect, render_template, request, url_for, flash
from flask_login import (
    LoginManager,
    login_required,
    login_user,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from db import db, Card, User, Board
except ImportError as exc:
    from app.db import db, Card, User, Board


login_manager = LoginManager()

# ---------- uploads config ----------
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("APP_SECRET_KEY")

    # ensure upload dir
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    login_manager.init_app(app)
    login_manager.login_view = "login"
    return app


app = create_app()


MSK_OFFSET = timedelta(hours=3)


def datetime_msk(value):
    if not value:
        return ""
    local = value + MSK_OFFSET
    return local.strftime("%d.%m.%Y %H:%M (МСК)")


def datetime_msk_input(value):
    if not value:
        return ""
    local = value + MSK_OFFSET
    local = local.replace(second=0, microsecond=0)
    return local.strftime("%d.%m.%Y %H:%M")


app.jinja_env.filters["datetime_msk"] = datetime_msk
app.jinja_env.filters["datetime_msk_input"] = datetime_msk_input


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------- HOME ---------------------
@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("home_authenticated.html")
    return render_template("index.html")


# ------------------------------------------------


# --------------------- AUTH ---------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("boards"))  # после входа идём к списку досок
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


# ------------------------------------------------


# --------------------- BOARDS (multi) ---------------------
@app.route("/boards", methods=["GET", "POST"])
@login_required
def boards():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            error = "Введите название доски."
        else:
            # ВНИМАНИЕ: требуется поле owner_id в модели Board
            b = Board(name=name, owner_id=current_user.id)
            db.session.add(b)
            db.session.commit()
            flash("Доска создана", "success")
            return redirect(url_for("boards"))
    user_boards = (
        Board.query.filter_by(owner_id=current_user.id).order_by(Board.id.desc()).all()
    )
    return render_template("boards.html", boards=user_boards, error=error)


@app.route("/board/<int:board_id>", methods=["GET", "POST"])
@login_required
def board(board_id):
    # доступ только к своей доске
    board = Board.query.filter_by(id=board_id, owner_id=current_user.id).first_or_404()

    statuses = [
        ("ideas", "Идеи"),
        ("todo", "To Do"),
        ("wip", "В работе"),
        ("done", "Готово"),
    ]
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        status = request.form.get("status", "ideas")
        task_creator = request.form.get("task_creator", current_user.username or "").strip()
        task_assignee = request.form.get("task_assignee", "").strip()
        task_description = request.form.get("task_description")
        if task_description is None:
            task_description = request.form.get("description", "")
        task_description = task_description.strip()
        if not task_creator:
            task_creator = current_user.username or ""
        if name and status in [s for s, _ in statuses]:
            card = Card(
                name=name,
                task_creator=task_creator,
                task_assignee=task_assignee,
                task_description=task_description,
                status=status,
                deadline=None,
                board_id=board.id,
                created_at=datetime.utcnow(),
            )
            db.session.add(card)
            db.session.commit()
            flash("Задача добавлена!", "success")
            return redirect(url_for("board", board_id=board.id))
    tasks = Card.query.filter_by(board_id=board.id).order_by(Card.id.desc()).all()
    return render_template("board.html", tasks=tasks, statuses=statuses, board=board)


@app.route("/board/<int:board_id>/card/<int:card_id>", methods=["GET", "POST"])
@login_required
def card_detail(board_id, card_id):
    board = Board.query.filter_by(id=board_id, owner_id=current_user.id).first_or_404()
    card = Card.query.filter_by(board_id=board.id, id=card_id).first_or_404()

    error = None
    form_description = None
    form_deadline = None

    if request.method == "POST":
        form_description = request.form.get("task_description", "").strip()
        form_deadline = request.form.get("deadline", "").strip()
        new_deadline = None
        if form_deadline:
            try:
                deadline_local = datetime.strptime(form_deadline, "%d.%m.%Y %H:%M")
                new_deadline = deadline_local - MSK_OFFSET
            except ValueError:
                error = "Неверный формат даты/времени дедлайна. Используйте ДД.ММ.ГГГГ ЧЧ:ММ."

        if not error:
            card.task_description = form_description
            card.deadline = new_deadline
            db.session.commit()
            flash("Задача обновлена", "success")
            return redirect(url_for("card_detail", board_id=board.id, card_id=card.id))

    return render_template(
        "card_detail.html",
        board=board,
        card=card,
        error=error,
        form_description=form_description,
        form_deadline=form_deadline,
    )


# ----------------------------------------------------------


# --------------------- PROFILE ---------------------
@app.route("/profile", methods=["GET"])
@login_required
def profile():
    return render_template("profile.html")


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    error = None
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        bio = request.form.get("bio", "").strip()

        current_user.full_name = full_name
        current_user.bio = bio

        file = request.files.get("avatar")
        if file and file.filename:
            if not allowed_file(file.filename):
                error = "Неверный формат файла. Разрешены: png, jpg, jpeg, gif, webp."
            else:
                fname = secure_filename(file.filename)
                name, ext = os.path.splitext(fname)
                final_name = f"{current_user.id}_{name}{ext}"
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], final_name)
                file.save(save_path)
                current_user.avatar_url = f"/{save_path.replace(os.sep, '/')}"

        if not error:
            db.session.commit()
            flash("Профиль обновлён", "success")
            return redirect(url_for("profile"))

    return render_template("profile_edit.html", error=error)


# --------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7007, debug=True)
