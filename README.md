# Highest Tasks

Веб-приложение на Flask, которое помогает небольшим командам вести задачи по методике канбан: создавайте доски, карточки, назначайте исполнителей и объединяйтесь в группы. Проект ориентирован на запуск в Docker.

## Основные возможности

- регистрация, авторизация и личный профиль с аватаром;
- создание неограниченного числа досок и карточек задач;
- создание и управление задачами, назначение выполняющего задачу, дедлайнов и пр.;
- распределение пользователей по группам и совместная работа с досками;

## Требования

- Python 3.10+;
- PostgreSQL (используется в docker-compose);
- pip зависимости описаны в `app/requirements.txt`;
- для пересборки документации нужен `pydoctor`;
- Docker для быстрого запуска всей инфраструктуры.

## Конфигурация

Создайте `.env` в корне, опираясь на `env.example`:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=ChangeMeInProd!
POSTGRES_DB=highesttasks
APP_SECRET_KEY=ChangeMeInProd!
UPLOAD_FOLDER=static/uploads
```

## Запуск

### В Docker

```bash
docker compose up --build -d
```

После запуска БД приложение станет доступно на `http://localhost:7007`.

## Тесты

Все тесты запускаются из корня командой:

```bash
python3 -m pytest
```

pytest использует конфигурацию из `pytest.ini` и директорию `app/tests`.

## Документация

HTML-документация находится в `docs/index.html`. Чтобы пересобрать её из docstring:

```bash
python3 -m venv .venv
.venv/bin/pip install -r docs/requirements.txt 
.venv/bin/pydoctor \
  --project-name "Highest Tasks" \
  --docformat google \
  --html-output docs \
  app/main.py app/db.py
```

## Структура репозитория

```
app/            исходный код Flask-приложения и тесты
docs/           готовая HTML-документация (Pydoctor)
static/         общие статические файлы и загрузки пользователей
docker-compose.yml
README.md
```
