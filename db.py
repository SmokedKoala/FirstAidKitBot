import psycopg2

def connect_to_db():
    conn = psycopg2.connect(
        host="localhost",
        database="firstaidkitbot",
        user="postgres",
        password="1234567890"
    )
    return conn
    
def get_user_by_id(user_id):
    conn = connect_to_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user
    
def get_user_by_username(username):
    conn = connect_to_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()
    return user
    
def get_user_by_email(email):
    conn = connect_to_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    conn.close()
    return user