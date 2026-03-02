import sqlite3


def get_db_connection():
    conn = sqlite3.connect('./artifacts/database.db')
    conn.row_factory = sqlite3.Row
    return conn


def create_signup_schema(connection):
    schema_signup = """
    CREATE TABLE IF NOT EXISTS signups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        agree INTEGER NOT NULL,
        signup_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    connection.executescript(schema_signup)


def insert_signup(name, email, agree):
    connection = get_db_connection()
    connection.execute(
        "INSERT INTO signups (name, email, agree) VALUES (?, ?, ?)",
        (name, email, int(agree))
    )
    connection.commit()
    connection.close()


def get_signups():
    connection = get_db_connection()
    signups = connection.execute("SELECT name, email, agree FROM signups").fetchall()
    connection.close()
    return [
        {
            'name': signup['name'],
            'email': signup['email'],
            'agree': bool(signup['agree'])
        } for signup in signups
    ]
