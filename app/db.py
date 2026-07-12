import sqlite3
import os
import bcrypt

DB_PATH = "data/catalog.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Режим WAL дозволяє читати БД під час її запису
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        category            TEXT DEFAULT 'Загальне',
        name                TEXT NOT NULL,
        version             TEXT DEFAULT '',
        status              TEXT DEFAULT 'В процесі',
        tags                TEXT DEFAULT '',
        description         TEXT,
        links               TEXT,
        ratings             TEXT,
        opinion             TEXT,
        install_instructions TEXT,
        icon_file           TEXT DEFAULT ''
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS tab_order (
        category   TEXT PRIMARY KEY,
        sort_index INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role          TEXT DEFAULT 'viewer',
        permissions   TEXT DEFAULT '{}',
        default_lang  TEXT DEFAULT 'uk'
    )''')

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        hashed = bcrypt.hashpw(b"admin", bcrypt.gensalt())
        c.execute(
            "INSERT INTO users (username, password_hash, role, default_lang) VALUES (?, ?, ?, ?)",
            ("admin", hashed.decode(), "admin", "uk")
        )

    conn.commit()
    conn.close()
