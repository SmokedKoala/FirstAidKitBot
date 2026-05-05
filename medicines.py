from db import connect_to_db


def _row_to_medicine(row):
    if row is None:
        return None
    return {
        "id": row[0],
        "ean13_code": row[1],
        "medicine_name": row[2],
    }


def list_medicines(limit=100, offset=0):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, ean13_code, medicine_name
                FROM medicines
                ORDER BY id
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            return [_row_to_medicine(row) for row in cursor.fetchall()]


def get_medicine_by_ean13(ean13_code):
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, ean13_code, medicine_name
                FROM medicines
                WHERE ean13_code = %s
                LIMIT 1
                """,
                (ean13_code,),
            )
            return _row_to_medicine(cursor.fetchone())
