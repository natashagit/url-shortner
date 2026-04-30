import os
import random
import string
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from flask import Flask, redirect, render_template, request

app = Flask(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required. Example: "
        "postgresql://user:password@localhost:5432/url_shortener"
    )

# Accept SQLAlchemy-style URLs if provided by mistake.
if DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def get_db_connection():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS urls (
                    id BIGSERIAL PRIMARY KEY,
                    original_url TEXT NOT NULL,
                    short_code VARCHAR(6) NOT NULL UNIQUE,
                    clicks INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            # Harden defaults for pre-existing tables created with older schema versions.
            cur.execute("ALTER TABLE urls ALTER COLUMN clicks SET DEFAULT 0")
            cur.execute("ALTER TABLE urls ALTER COLUMN created_at SET DEFAULT NOW()")
            conn.commit()


def generate_short_code(length=6):
    # Build a pool of letters and digits (62 possible characters)
    characters = string.ascii_letters + string.digits
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            while True:
                # Generate a random 6-character code
                code = "".join(random.choices(characters, k=length))
                # Check if this code already exists in the database
                cur.execute("SELECT id FROM urls WHERE short_code = %s", (code,))
                existing = cur.fetchone()
                # If the code is unique, return it
                if not existing:
                    return code


@app.route('/', methods=['GET', 'POST'])
def index():
    short_url = None
    if request.method == 'POST':
        # Get the URL from the form and clean up whitespace
        original_url = request.form.get('original_url', '').strip()
        if original_url:
            # Auto-add https:// if the user didn't include a scheme
            if not original_url.startswith(('http://', 'https://')):
                original_url = 'https://' + original_url
            # Generate a unique short code and save the mapping
            short_code = generate_short_code()
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO urls (original_url, short_code, clicks, created_at) "
                        "VALUES (%s, %s, %s, NOW())",
                        (original_url, short_code, 0),
                    )
                    conn.commit()
            # Build the full shortened URL
            short_url = request.host_url + short_code
    return render_template('index.html', short_url=short_url)

@app.route('/stats')
def stats():
    # Fetch all URLs, newest first
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT short_code, original_url, clicks, created_at "
                "FROM urls ORDER BY created_at DESC"
            )
            urls = cur.fetchall()
    return render_template('stats.html', urls=urls)

@app.route('/<short_code>')
def redirect_url(short_code):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT original_url FROM urls WHERE short_code = %s",
                (short_code,),
            )
            url_data = cur.fetchone()
            if url_data:
                # Increment the click counter for this short code
                cur.execute(
                    "UPDATE urls SET clicks = clicks + 1 WHERE short_code = %s",
                    (short_code,),
                )
                conn.commit()
                return redirect(url_data["original_url"])
    return 'URL not found', 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True)