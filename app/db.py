"""Описание моделей БД для Highest Tasks."""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()
"""Глобальный объект SQLAlchemy для работы с приложением."""


class User(db.Model, UserMixin):
    """Модель пользователя с профилем и доступом к доскам."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # логин должен быть уникальным
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # поля личного кабинета
    full_name = db.Column(db.String(128), default="")
    bio = db.Column(db.String(512), default="")
    avatar_url = db.Column(db.String(255), default="")  # /static/uploads/...
    boards = db.relationship("Board", back_populates="owner", cascade="all, delete-orphan")

    groups = relationship("Group", secondary="group_memberships", back_populates="users")

    # хелперы пароля (опционально, чтобы не повторять вью-функции)
    def set_password(self, password: str) -> None:
        """Сохраняет хеш пароля пользователя.

        Args:
            password: Пароль в открытом виде.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Проверяет пароль пользователя.

        Args:
            password: Пароль в открытом виде.

        Returns:
            True, если пароль верен.
        """
        return check_password_hash(self.password_hash, password)


class Group(db.Model):
    """Группа пользователей, объединённых для совместной работы."""

    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    users = relationship("User", secondary="group_memberships", back_populates="groups")
    boards = db.relationship("Board", back_populates="owner_group")


class GroupMembership(db.Model):
    """Связующая таблица между пользователями и группами."""

    __tablename__ = "group_memberships"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)


class Board(db.Model):
    """Модель доски задач, принадлежащей пользователю или группе."""

    __tablename__ = "boards"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    owner = db.relationship("User", back_populates="boards")
    owner_group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)
    owner_group = db.relationship("Group", back_populates="boards")
    cards = db.relationship("Card", back_populates="board", cascade="all, delete-orphan")


class Card(db.Model):
    """Карточка задачи, принадлежащая конкретной доске."""

    __tablename__ = "cards"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    task_creator = db.Column(db.String(128), nullable=False, default="")
    task_assignee = db.Column(db.String(128), nullable=False, default="")
    task_description = db.Column(db.Text, default="")
    deadline = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # статусы: ideas, todo, wip, done
    status = db.Column(db.String(20), nullable=False, default="ideas")

    board_id = db.Column(db.Integer, db.ForeignKey("boards.id"), nullable=False)
    board = db.relationship("Board", back_populates="cards")
