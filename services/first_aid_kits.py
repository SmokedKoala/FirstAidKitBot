from datetime import date

from db import connect_to_db


def _row_to_first_aid_kit(row):
    if row is None:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "created_at": row[2],
    }


def _row_to_first_aid_kit_medicine(row):
    if row is None:
        return None
    return {
        "id": row[0],
        "first_aid_kit_id": row[1],
        "name": row[2],
        "number_of_drugs": row[3],
        "expiration_date": row[4],
        "description": row[5],
    }


def create_first_aid_kit(title, user_ids):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO first_aid_kits (title)
                VALUES (%s)
                RETURNING id, title, created_at
                """,
                (title,),
            )
            first_aid_kit = _row_to_first_aid_kit(cursor.fetchone())

            if user_ids:
                cursor.executemany(
                    """
                    INSERT INTO user_first_aid_kits (user_id, first_aid_kit_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    [(user_id, first_aid_kit["id"]) for user_id in user_ids],
                )

            return first_aid_kit


def add_medicine_to_first_aid_kit(
    first_aid_kit_id,
    name,
    number_of_drugs,
    expiration_date: date,
    description,
):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO first_aid_kit_medicines (
                    first_aid_kit_id,
                    name,
                    number_of_drugs,
                    expiration_date,
                    description
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, first_aid_kit_id, name, number_of_drugs, expiration_date, description
                """,
                (
                    first_aid_kit_id,
                    name,
                    number_of_drugs,
                    expiration_date,
                    description,
                ),
            )
            return _row_to_first_aid_kit_medicine(cursor.fetchone())


def get_first_aid_kit_by_id(first_aid_kit_id):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, created_at FROM first_aid_kits WHERE id = %s",
                (first_aid_kit_id,),
            )
            return _row_to_first_aid_kit(cursor.fetchone())


def list_first_aid_kits_for_user(user_id: int):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT fak.id, fak.title, fak.created_at
                FROM first_aid_kits fak
                INNER JOIN user_first_aid_kits ufak
                    ON ufak.first_aid_kit_id = fak.id
                WHERE ufak.user_id = %s
                ORDER BY fak.id
                """,
                (user_id,),
            )
            return [_row_to_first_aid_kit(row) for row in cursor.fetchall()]


def users_exist(user_ids):
    if not user_ids:
        return True
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE id = ANY(%s)",
                (user_ids,),
            )
            found_ids = {row[0] for row in cursor.fetchall()}
            return all(user_id in found_ids for user_id in user_ids)

