"""Веб-приложение Highest Tasks на Flask."""

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
"""LoginManager, отвечающий за авторизацию пользователей."""

UPLOAD_FOLDER = os.path.join("static", "uploads")
"""Каталог для сохранения загруженных файлов."""

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
"""Набор допустимых расширений для файлов пользователя."""


class UserFacingError(Exception):
    """Исключение, отображаемое пользователю."""


class ApiError(UserFacingError):
    """Исключение для API-запросов с кодом ответа."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def ensure(condition: bool, message: str) -> None:
    """Поднимает UserFacingError, если условие ложно."""
    if not condition:
        raise UserFacingError(message)


def ensure_api(condition: bool, message: str, status_code: int = 400) -> None:
    """Поднимает ApiError, если условие ложно."""
    if not condition:
        raise ApiError(message, status_code)


def allowed_file(filename: str) -> bool:
    """Проверяет допустимость расширения загружаемого файла.

    Args:
        filename: Имя файла, полученное от клиента.

    Returns:
        True, если расширение входит в ALLOWED_EXTENSIONS, иначе False.
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def create_app():
    """Создаёт и настраивает экземпляр Flask-приложения.

    Returns:
        Инициализированное приложение с подключённой БД и LoginManager.
    """
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
"""Глобальный экземпляр Flask-приложения."""

MSK_OFFSET = timedelta(hours=3)
"""Смещение по времени относительно UTC для МСК."""


def datetime_msk(value):
    """Форматирует дату-время в строку с МСК.

    Args:
        value: Исходное UTC-время.

    Returns:
        Строка с человеком-понятным форматом или пустая строка, если значение не задано.
    """
    if not value:
        return ""
    local = value + MSK_OFFSET
    return local.strftime("%d.%m.%Y %H:%M (МСК)")


def datetime_msk_input(value):
    """Готовит дату-время для предварительного заполнения HTML-поля в МСК.

    Args:
        value: Исходное UTC-время.

    Returns:
        Строка в формате ДД.ММ.ГГГГ ЧЧ:ММ или пустая строка.
    """
    if not value:
        return ""
    local = value + MSK_OFFSET
    local = local.replace(second=0, microsecond=0)
    return local.strftime("%d.%m.%Y %H:%M")


app.jinja_env.filters["datetime_msk"] = datetime_msk
app.jinja_env.filters["datetime_msk_input"] = datetime_msk_input


@login_manager.user_loader
def load_user(user_id):
    """Загружает пользователя по идентификатору для Flask-Login.

    Args:
        user_id: Идентификатор пользователя из сессии.

    Returns:
        Объект пользователя или None, если не найден.
    """
    return db.session.get(User, int(user_id))


@app.route("/")
def index():
    """Отображает лендинг или домашнюю страницу для авторизованных пользователей."""
    if current_user.is_authenticated:
        return render_template("home_authenticated.html")
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Авторизует пользователя и перенаправляет к списку досок."""
    error = None
    if request.method == "POST":
        try:
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            ensure(username and password, "Пожалуйста, заполните логин и пароль.")
            user = User.query.filter_by(username=username).first()
            ensure(user and check_password_hash(user.password_hash, password), "Логин или пароль не верен!")
            login_user(user)
            return redirect(url_for("boards"))
        except UserFacingError as exc:
            error = str(exc)
    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    """Завершает сессию и возвращает пользователя на страницу входа."""
    logout_user()
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Создаёт нового пользователя после проверки входных данных."""
    error = None
    if request.method == "POST":
        try:
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            ensure(username and password, "Пожалуйста, заполните все поля.")
            ensure(len(username) >= 3, "Логин должен быть от 3 символов.")
            ensure(len(password) >= 8, "Пароль должен быть минимум 8 символов.")
            ensure(not User.query.filter_by(username=username).first(), "Логин уже занят!")
            password_hash = generate_password_hash(password)
            new_user = User(username=username, password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            flash("Аккаунт создан! Теперь войдите.", "success")
            return redirect(url_for("login"))
        except UserFacingError as exc:
            error = str(exc)
    return render_template("register.html", error=error)


@app.route("/boards", methods=["GET", "POST"])
@login_required
def boards():
    """Возвращает список досок пользователя или создаёт новую доску."""
    error = None
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            ensure(name, "Введите название доски.")
            b = Board(name=name, owner_id=current_user.id)
            db.session.add(b)
            db.session.commit()
            flash("Доска создана", "success")
            return redirect(url_for("boards"))
        except UserFacingError as exc:
            error = str(exc)
    user_boards = (
        Board.query.filter_by(owner_id=current_user.id).order_by(Board.id.desc()).all()
    )
    for grp in current_user.groups:
        for brd in grp.boards:
            if brd not in user_boards:
                user_boards.append(brd)
    return render_template("boards.html", boards=user_boards, error=error)


@app.route("/board/<int:board_id>", methods=["GET", "POST"])
@login_required
def board(board_id):
    """Отображает доску и обрабатывает создание карточек.

    Args:
        board_id: Идентификатор доски.
    """
    board = Board.query.filter_by(id=board_id).first_or_404()
    try:
        has_group_access = (
            board.owner_group is not None and current_user in board.owner_group.users
        )
        ensure(current_user == board.owner or has_group_access, "У вас нет доступа к этой доске")
    except UserFacingError as exc:
        flash(str(exc), "error")
        return redirect(url_for("boards"))

    statuses = [
        ("ideas", "Идеи"),
        ("todo", "To Do"),
        ("wip", "В работе"),
        ("done", "Готово"),
    ]
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            status = request.form.get("status", "ideas")
            task_creator = request.form.get(
                "task_creator", current_user.username or ""
            ).strip()
            task_assignee = request.form.get("task_assignee", "").strip()
            task_description = request.form.get("task_description")
            if task_description is None:
                task_description = request.form.get("description", "")
            task_description = task_description.strip()
            if not task_creator:
                task_creator = current_user.username or ""
            ensure(name, "Название задачи не может быть пустым.")
            ensure(status in [s for s, _ in statuses], "Неверный статус задачи.")
            card = Card(
                name=name,
                task_creator=task_creator,
                task_assignee=task_assignee,
                task_description=task_description,
                status=status,
                deadline=None,
                board_id=board.id,
                created_at=datetime.utcnow() + MSK_OFFSET,
            )
            db.session.add(card)
            db.session.commit()
            flash("Задача добавлена!", "success")
            return redirect(url_for("board", board_id=board.id))
        except UserFacingError as exc:
            flash(str(exc), "error")
    tasks = Card.query.filter_by(board_id=board.id).order_by(Card.id.desc()).all()
    available_groups = current_user.groups
    return render_template(
        "board.html",
        tasks=tasks,
        statuses=statuses,
        board=board,
        available_groups=available_groups,
    )


@app.route("/board/remove_group", methods=["POST"])
@login_required
def remove_board_from_group():
    """Удаляет связь доски с группой."""
    board_id = request.form.get("board_id")
    board = Board.query.filter_by(id=board_id).first_or_404()

    try:
        ensure(board.owner_group is not None, "Доска не принадлежит группе.")
        ensure(current_user in board.owner_group.users, "У вас нет прав на изменение этой группы")
        ensure(current_user == board.owner, "Только владелец доски может менять группу")
    except UserFacingError as exc:
        flash(str(exc), "error")
        return redirect(url_for("board", board_id=board_id))

    board.owner_group = None
    db.session.commit()
    flash("Доска удалена из группы", "info")

    return redirect(url_for("board", board_id=board_id))


@app.route("/board/add_group", methods=["POST"])
@login_required
def add_board_to_group():
    """Привязывает доску к выбранной группе."""
    board_id = request.form.get("board_id")
    group_id = request.form.get("group_id")
    board = Board.query.filter_by(id=board_id).first_or_404()
    group = Group.query.filter_by(id=group_id).first_or_404()

    try:
        ensure(current_user in group.users, "У вас нет прав на изменение этой группы")
        ensure(current_user == board.owner, "Только владелец доски может менять группу")
    except UserFacingError as exc:
        flash(str(exc), "error")
        return redirect(url_for("board", board_id=board_id))

    board.owner_group = group
    db.session.commit()
    flash("Доска добавлена в группу", "success")

    return redirect(url_for("board", board_id=board_id))


@app.route("/board/<int:board_id>/card/<int:card_id>", methods=["GET", "POST"])
@login_required
def card_detail(board_id, card_id):
    """Отображает карточку и позволяет обновить описание и дедлайн.

    Args:
        board_id: Идентификатор доски.
        card_id: Идентификатор карточки.
    """
    board = Board.query.filter_by(id=board_id, owner_id=current_user.id).first_or_404()
    card = Card.query.filter_by(board_id=board.id, id=card_id).first_or_404()

    error = None
    form_description = None
    form_deadline = None

    if request.method == "POST":
        try:
            form_description = request.form.get("task_description", "").strip()
            form_deadline = request.form.get("deadline", "").strip()
            new_deadline = None
            if form_deadline:
                try:
                    deadline_local = datetime.strptime(form_deadline, "%d.%m.%Y %H:%M")
                    new_deadline = deadline_local - MSK_OFFSET
                except ValueError as exc:
                    raise UserFacingError(
                        "Неверный формат даты/времени дедлайна. Используйте ДД.ММ.ГГГГ ЧЧ:ММ."
                    ) from exc

            card.task_description = form_description
            card.deadline = new_deadline
            db.session.commit()
            flash("Задача обновлена", "success")
            return redirect(url_for("card_detail", board_id=board.id, card_id=card.id))
        except UserFacingError as exc:
            error = str(exc)

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
    """Показывает профиль текущего пользователя."""
    return render_template("profile.html")


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    """Позволяет редактировать профиль и загружать аватар."""
    error = None
    if request.method == "POST":
        try:
            full_name = request.form.get("full_name", "").strip()
            bio = request.form.get("bio", "").strip()

            current_user.full_name = full_name
            current_user.bio = bio

            file = request.files.get("avatar")
            if file and file.filename:
                ensure(
                    allowed_file(file.filename),
                    "Неверный формат файла. Разрешены: png, jpg, jpeg, gif, webp.",
                )
                fname = secure_filename(file.filename)
                name, ext = os.path.splitext(fname)
                final_name = f"{current_user.id}_{name}{ext}"
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], final_name)
                file.save(save_path)
                current_user.avatar_url = f"/{save_path.replace(os.sep, '/')}"

            db.session.commit()
            flash("Профиль обновлён", "success")
            return redirect(url_for("profile"))
        except UserFacingError as exc:
            error = str(exc)

    return render_template("profile_edit.html", error=error)


@app.route("/groups", methods=["GET", "POST"])
@login_required
def groups():
    """Список групп пользователя и создание новой группы."""
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            ensure(name, "Введите название группы.")
            new_group = Group(name=name)
            new_group.users.append(current_user)
            db.session.add(new_group)
            db.session.commit()
            flash("Группа создана", "success")
            return redirect(url_for("groups"))
        except UserFacingError as exc:
            flash(str(exc), "error")
    cur_groups = current_user.groups
    return render_template("groups.html", groups=cur_groups)


@app.route("/group/<int:group_id>", methods=["GET", "POST"])
@login_required
def group_detail(group_id):
    """Показывает состав группы и добавляет участников.

    Args:
        group_id: Идентификатор группы.
    """
    grp = Group.query.filter_by(id=group_id).first_or_404()
    if request.method == "POST":
        try:
            user_id = request.form.get("user_id")
            user = User.query.filter_by(id=user_id).first()
            ensure(user is not None, "Пользователь не найден.")
            ensure(user not in grp.users, "Пользователь уже в группе.")
            grp.users.append(user)
            db.session.commit()
            flash("Пользователь добавлен в группу", "success")
            return redirect(url_for("group_detail", group_id=group_id))
        except UserFacingError as exc:
            flash(str(exc), "error")
    all_users = User.query.all()
    return render_template("group_details.html", group=grp, all_users=all_users)


@app.route("/group/delete", methods=["POST"])
@login_required
def remove_user_from_group():
    """Удаляет пользователя из группы, если есть права."""
    group_id = request.form.get("group_id")
    user_id = request.form.get("user_id")
    grp = Group.query.filter_by(id=group_id).first_or_404()
    user = User.query.filter_by(id=user_id).first()
    try:
        ensure(current_user in grp.users, "У вас нет прав на изменение этой группы")
        ensure(current_user != user, "Вы не можете удалить себя из группы")
        ensure(user is not None and user in grp.users, "Пользователь уже удалён из группы")
        grp.users.remove(user)
        db.session.commit()
        flash("Пользователь удалён из группы", "info")
    except UserFacingError as exc:
        flash(str(exc), "error")
        if current_user not in grp.users:
            return redirect(url_for("groups"))
        return redirect(url_for("group_detail", group_id=group_id))
    return redirect(url_for("group_detail", group_id=group_id))


@app.route("/card/move", methods=["POST"])
@login_required
def move_card():
    """Обрабатывает перенос карточки между колонками через JSON-запрос."""
    data = None
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        ensure_api(data, "No data provided")

        card_id = data.get("card_id")
        new_status = data.get("new_status")
        ensure_api(card_id and new_status, "card_id and new_status are required")

        try:
            card_id_int = int(card_id)
        except (ValueError, TypeError) as exc:
            raise ApiError("Invalid card_id") from exc

        card = Card.query.filter_by(id=card_id_int).first()
        ensure_api(card is not None, "Card not found", status_code=404)

        board = Board.query.filter_by(id=card.board_id).first()
        ensure_api(board is not None, "Board not found", status_code=404)

        has_group_access = (
            board.owner_group is not None and current_user in board.owner_group.users
        )
        ensure_api(
            current_user == board.owner or has_group_access,
            "Permission denied",
            status_code=403,
        )

        valid_statuses = {"ideas", "todo", "wip", "done"}
        ensure_api(new_status in valid_statuses, "Invalid status")

        card.status = new_status
        db.session.commit()
        return jsonify({"ok": True, "card_id": card.id, "new_status": card.status}), 200
    except ApiError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7007, debug=True)
