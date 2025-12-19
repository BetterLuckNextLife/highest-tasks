import os
from datetime import datetime, timedelta
from flask import Flask, redirect, render_template, request, url_for, flash, jsonify
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
    from db import db, Card, User, Board, Group
except ImportError as exc:
    from app.db import db, Card, User, Board, Group

login_manager = LoginManager()

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


@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("home_authenticated.html")
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
    user_boards = Board.query.filter_by(owner_id=current_user.id).order_by(Board.id.desc()).all()
    for grp in current_user.groups:
        for brd in grp.boards:
            if brd not in user_boards:
                user_boards.append(brd)
    return render_template("boards.html", boards=user_boards, error=error)


@app.route("/board/<int:board_id>", methods=["GET", "POST"])
@login_required
def board(board_id):
    # доступ только к своей доске
    board = Board.query.filter_by(id=board_id).first_or_404()
    if current_user != board.owner and (board.owner_group is None or current_user not in board.owner_group.users):
        flash("У вас нет доступа к этой доске", "error")
        return redirect(url_for("boards"))

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
    available_groups = current_user.groups
    return render_template(
        "board.html",
        tasks=tasks,
        statuses=statuses,
        board=board,
        available_groups=available_groups
    )


@app.route("/board/remove_group", methods=["POST"])
@login_required
def remove_board_from_group():
    board_id = request.form.get("board_id")
    board = Board.query.filter_by(id=board_id).first_or_404()

    if current_user not in board.owner_group.users or current_user != board.owner:
        flash("У вас нет прав на изменение этой группы", "error")
        return redirect(url_for("board", board_id=board_id))

    board.owner_group = None
    db.session.commit()
    flash("Доска удалена из группы", "info")

    return redirect(url_for("board", board_id=board_id))


@app.route("/board/add_group", methods=["POST"])
@login_required
def add_board_to_group():
    board_id = request.form.get("board_id")
    group_id = request.form.get("group_id")
    board = Board.query.filter_by(id=board_id).first_or_404()
    group = Group.query.filter_by(id=group_id).first_or_404()

    if current_user not in group.users or current_user != board.owner:
        flash("У вас нет прав на изменение этой группы", "error")
        return redirect(url_for("board", board_id=board_id))

    board.owner_group = group
    db.session.commit()
    flash("Доска добавлена в группу", "success")

    return redirect(url_for("board", board_id=board_id))


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


@app.route("/groups", methods=["GET", "POST"])
@login_required
def groups():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            new_group = Group(name=name)
            new_group.users.append(current_user)
            db.session.add(new_group)
            db.session.commit()
            flash("Группа создана", "success")
            return redirect(url_for("groups"))
    cur_groups = current_user.groups
    return render_template("groups.html", groups=cur_groups)


@app.route("/group/<int:group_id>", methods=["GET", "POST"])
@login_required
def group_detail(group_id):
    grp = Group.query.filter_by(id=group_id).first_or_404()
    if request.method == "POST":
        user_id = request.form.get("user_id")
        user = User.query.filter_by(id=user_id).first()
        if user and user not in grp.users:
            grp.users.append(user)
            db.session.commit()
            flash("Пользователь добавлен в группу", "success")
            return redirect(url_for("group_detail", group_id=group_id))
    all_users = User.query.all()
    return render_template("group_details.html", group=grp, all_users=all_users)


@app.route("/group/delete", methods=["POST"])
@login_required
def remove_user_from_group():
    group_id = request.form.get("group_id")
    user_id = request.form.get("user_id")
    grp = Group.query.filter_by(id=group_id).first_or_404()
    user = User.query.filter_by(id=user_id).first()
    if current_user not in grp.users:
        flash("У вас нет прав на изменение этой группы", "error")
        return redirect(url_for("groups"))
    if current_user == user:
        flash("Вы не можете удалить себя из группы", "error")
        return redirect(url_for("group_detail", group_id=group_id))
    if user and user in grp.users:
        grp.users.remove(user)
        db.session.commit()
        flash("Пользователь удалён из группы", "info")
    return redirect(url_for("group_detail", group_id=group_id))


@app.route("/card/move", methods=["POST"])
@login_required
def move_card():
    data = None
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    if not data:
        return jsonify({"error": "No data provided"}), 400

    card_id = data.get("card_id")
    new_status = data.get("new_status")
    if not card_id or not new_status:
        return jsonify({"error": "card_id and new_status are required"}), 400

    try:
        card_id_int = int(card_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid card_id"}), 400

    card = Card.query.filter_by(id=card_id_int).first()
    if not card:
        return jsonify({"error": "Card not found"}), 404

    board = Board.query.filter_by(id=card.board_id).first()
    if not board:
        return jsonify({"error": "Board not found"}), 404

    if current_user != board.owner and (board.owner_group is None or current_user not in board.owner_group.users):
        return jsonify({"error": "Permission denied"}), 403

    valid_statuses = {"ideas", "todo", "wip", "done"}
    if new_status not in valid_statuses:
        return jsonify({"error": "Invalid status"}), 400

    card.status = new_status
    db.session.commit()
    return jsonify({"ok": True, "card_id": card.id, "new_status": card.status}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7007, debug=True)
