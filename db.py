import os

import psycopg2


def connect_to_db():
    """
    Connect to PostgreSQL using DATABASE_URL if provided, otherwise
    fall back to PG* env vars suitable for local/Docker setups.
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        database=os.environ.get("PGDATABASE", "firstaidkitbot"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", "postgres"),
    )


def get_user_by_id(user_id):
    # Backward-compatible import path; prefer users.get_user_by_id.
    from users import get_user_by_id as _get_user_by_id

    return _get_user_by_id(user_id)


def create_user(username, email):
    # Backward-compatible import path; prefer users.create_user.
    from users import create_user as _create_user

    return _create_user(username, email)


def get_user_by_username(username):
    # Backward-compatible import path; prefer users.get_user_by_username.
    from users import get_user_by_username as _get_user_by_username

    return _get_user_by_username(username)


def get_user_by_email(email):
    # Backward-compatible import path; prefer users.get_user_by_email.
    from users import get_user_by_email as _get_user_by_email

    return _get_user_by_email(email)


def list_users(limit=100, offset=0):
    # Backward-compatible import path; prefer users.list_users.
    from users import list_users as _list_users

    return _list_users(limit=limit, offset=offset)


def update_user(user_id, username=None, email=None):
    # Backward-compatible import path; prefer users.update_user.
    from users import update_user as _update_user

    return _update_user(user_id=user_id, username=username, email=email)


def delete_user(user_id):
    # Backward-compatible import path; prefer users.delete_user.
    from users import delete_user as _delete_user

    return _delete_user(user_id)