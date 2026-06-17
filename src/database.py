import os
import sqlite3
from contextlib import closing


def get_db_connection():
    is_vercel = os.environ.get('VERCEL') == '1' or 'VERCEL' in os.environ
    if is_vercel:
        db_path = '/tmp/artifacts/database.db'
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    else:
        db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'artifacts', 'database.db')
        try:
            parent_dir = os.path.dirname(db_path)
            os.makedirs(parent_dir, exist_ok=True)
            test_file = os.path.join(parent_dir, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except Exception:
            # Read-only filesystem, fallback to /tmp
            db_path = '/tmp/artifacts/database.db'
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn


def create_signup_schema(connection):
    columns = [col[1] for col in connection.execute("PRAGMA table_info(signups)").fetchall()]
    
    if not columns:
        # Fresh setup
        connection.executescript("""
        CREATE TABLE signups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            signup_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
    elif 'name' in columns:
        # Needs migration
        connection.executescript("""
        CREATE TABLE signups_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            signup_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO signups_new (id, email, signup_time) SELECT id, email, signup_time FROM signups;
        DROP TABLE signups;
        ALTER TABLE signups_new RENAME TO signups;
        """)


def insert_signup(email):
    with closing(get_db_connection()) as connection:
        with connection:
            connection.execute(
                "INSERT INTO signups (email) VALUES (?)",
                (email,)
            )


def get_signups():
    with closing(get_db_connection()) as connection:
        signups = connection.execute("SELECT id, email, signup_time FROM signups").fetchall()
        
    return [
        {
            'id': signup['id'],
            'email': signup['email'],
            'signup_time': signup['signup_time']
        } for signup in signups
    ]
