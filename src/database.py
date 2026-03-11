import os
import sqlite3
from contextlib import closing


def get_db_connection():
    db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'artifacts', 'database.db')
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn


def create_signup_schema(connection):
    schema_signup = """
    CREATE TABLE IF NOT EXISTS signups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        agree INTEGER NOT NULL,
        n10as_message TEXT,
        mp3_filename TEXT,
        signup_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    connection.executescript(schema_signup)
    
    try:
        connection.execute("ALTER TABLE signups ADD COLUMN n10as_message TEXT;")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' not in str(e).lower():
            print(f"Error adding n10as_message column: {e}")
    
    try:
        connection.execute("ALTER TABLE signups ADD COLUMN mp3_filename TEXT;")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' not in str(e).lower():
            print(f"Error adding mp3_filename column: {e}")


def insert_signup(name, email, agree=1, n10as_message=None, mp3_filename=None):
    with closing(get_db_connection()) as connection:
        with connection:
            connection.execute(
                "INSERT INTO signups (name, email, agree, n10as_message, mp3_filename) VALUES (?, ?, ?, ?, ?)",
                (name, email, int(agree), n10as_message, mp3_filename)
            )


def get_signups():
    with closing(get_db_connection()) as connection:
        signups = connection.execute("SELECT name, email, agree, n10as_message, mp3_filename FROM signups").fetchall()
        
    return [
        {
            'name': signup['name'],
            'email': signup['email'],
            'agree': bool(signup['agree']),
            'n10as_message': signup['n10as_message'],
            'mp3_filename': signup['mp3_filename']
        } for signup in signups
    ]
