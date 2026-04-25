from db import connect_to_db


def _row_to_user(row):
    if row is None:
        return None
    return {
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "created_at": row[3],
    }


def create_user(username, email):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (username, email)
                VALUES (%s, %s)
                RETURNING *
                """,
                (username, email),
            )
            return _row_to_user(cursor.fetchone())


def get_user_by_id(user_id):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return _row_to_user(cursor.fetchone())


def get_user_by_username(username):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            return _row_to_user(cursor.fetchone())


def get_user_by_email(email):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            return _row_to_user(cursor.fetchone())


def list_users(limit=100, offset=0):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM users
                ORDER BY id
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            return [_row_to_user(row) for row in cursor.fetchall()]


def update_user(user_id, username=None, email=None):
    updates = []
    params = []

    if username is not None:
        updates.append("username = %s")
        params.append(username)
    if email is not None:
        updates.append("email = %s")
        params.append(email)

    if not updates:
        raise ValueError("At least one field must be provided for update.")

    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING *"

    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, tuple(params))
            return _row_to_user(cursor.fetchone())


def delete_user(user_id):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
            return cursor.fetchone() is not None
