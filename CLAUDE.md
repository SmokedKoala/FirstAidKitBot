# FirstAidKitBot — Справка для Claude

## Что делает проект

Telegram-бот + REST API для управления домашними аптечками. Принимает фото штрихкода (EAN-13), распознаёт код через pyzbar/OpenCV и запрашивает справочник Medum.ru — возвращает данные о товарах и регистрационных удостоверениях. Хранит пользователей, аптечки и лекарства в PostgreSQL.

## Запуск

```bash
python app.py          # API :8000 + Telegram-бот (если задан токен)
python migrate.py      # применить SQL-миграции перед первым запуском
```

Переменные окружения задаются в `private.properties` (не в Git, шаблон — `private.properties.example`):

```properties
HOST=127.0.0.1
PORT=8000
TELEGRAM_BOT_TOKEN=...
```

На Windows использовать `http://127.0.0.1:PORT` (не `localhost` — возможны сбои IPv6).

## Архитектура

```
app.py                    # точка входа: Uvicorn + lifespan бота
endpoints/
  api.py                  # FastAPI-маршруты
  telegram_bot.py         # обработчики команд Telegram
services/
  users.py / medicines.py / first_aid_kits.py / scan_service.py
db/connection.py          # пул подключений PostgreSQL (psycopg2)
scan.py                   # pyzbar-декодирование + парсинг Medum.ru
migration_control.py      # контроль SQL-миграций (таблица schema_migrations)
migrations/*.sql          # версионированные DDL-скрипты (NNN__name.sql)
```

## API-эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | `{"status":"ok"}` |
| GET | `/docs` | Swagger UI |
| POST | `/scan` | `multipart/form-data`, поле `file` — изображение |
| POST | `/first-aid-kits` | `{"title": "...", "user_ids": [...]}` |
| POST | `/first-aid-kits/{id}/medicines` | добавить лекарство в аптечку |

## Команды Telegram-бота

| Команда | Описание |
|---------|----------|
| `/start` | Справка |
| `/create_first_aid_kit <название>` | Создать аптечку |
| `/my_first_aid_kits` | Список аптечек пользователя |
| `/rename_first_aid_kit <id> <новое название>` | Переименовать аптечку |
| `/delete_first_aid_kit <id>` | Удалить аптечку (с подтверждением через кнопки) |

## Зависимости

`opencv-python`, `pyzbar` (нужны DLL ZBar на Windows), `fastapi`, `uvicorn`, `python-telegram-bot>=22.7`, `psycopg2-binary`, `requests`, `beautifulsoup4`, `numpy`

## Добавление миграции

1. Создать `migrations/NNN__описание.sql`
2. Добавить DDL/DML
3. `python migrate.py`

## Docker

```bash
docker build -t firstaidkitbot .
docker run --rm -p 8080:8000 -e HOST=0.0.0.0 firstaidkitbot
```

## Важные ограничения

- Medum.ru запрашивается **только для EAN-13**; другие форматы распознаются, но не ищутся.
- Не кешировать и не перепродавать данные Medum.ru (Terms of Service).
- Не запускать два экземпляра бота с одним токеном — Telegram разрешает только один polling.
- Если ранее настраивался webhook — удалить через `deleteWebhook` перед polling.
