import sqlite3


def get_db_connection():
    conn = sqlite3.connect('./artifacts/database.db')
    conn.row_factory = sqlite3.Row
    return conn


def create_email_schema(connection):
    schema_email = """
    CREATE TABLE EMAILZ (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        EMAIL TEXT NOT NULL,
        EMAILTIME TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    connection.executescript(schema_email)


def insert_to_email_schema(email):
    connection = get_db_connection()
    connection.execute("INSERT INTO EMAILZ VALUES (NULL, ?, CURRENT_TIMESTAMP)", (email, ))
    connection.commit()
    connection.close()


def get_signups():
    connection = get_db_connection()
    signups = connection.execute("SELECT EMAIL FROM EMAILZ").fetchall()
    connection.close()
    return [{'email': signup['EMAIL']} for signup in signups]
