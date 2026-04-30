import os
from contextlib import contextmanager
import uuid

import psycopg
import redis
from psycopg.rows import dict_row
from flask import Flask, redirect, render_template, request

app = Flask(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
_redis_client = None

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required. Example: "
        "postgresql://user:password@localhost:5432/url_shortener"
    )

# Accept SQLAlchemy-style URLs if provided by mistake.
if DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)


def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not REDIS_URL:
        return None
    try:
        _redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except redis.RedisError:
        return None


def cache_key(short_code: str) -> str:
    return f"url:{short_code}"


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
                    short_code VARCHAR(16) NOT NULL UNIQUE,
                    clicks INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            # Harden defaults for pre-existing tables created with older schema versions.
            cur.execute("ALTER TABLE urls ALTER COLUMN clicks SET DEFAULT 0")
            cur.execute("ALTER TABLE urls ALTER COLUMN created_at SET DEFAULT NOW()")
            cur.execute("ALTER TABLE urls ALTER COLUMN short_code TYPE VARCHAR(16)")
            conn.commit()


def encode_base62(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if value == 0:
        return alphabet[0]

    parts = []
    while value > 0:
        value, remainder = divmod(value, 62)
        parts.append(alphabet[remainder])
    return "".join(reversed(parts))


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
            # Generate a short code from the row id using Base62 encoding.
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Keep placeholder below VARCHAR(16) limit.
                    placeholder_code = f"t{uuid.uuid4().hex[:12]}"
                    cur.execute(
                        "INSERT INTO urls (original_url, short_code, clicks, created_at) "
                        "VALUES (%s, %s, %s, NOW()) RETURNING id",
                        (original_url, placeholder_code, 0),
                    )
                    new_id = cur.fetchone()["id"]
                    short_code = encode_base62(new_id)
                    cur.execute(
                        "UPDATE urls SET short_code = %s WHERE id = %s",
                        (short_code, new_id),
                    )
                    conn.commit()
            redis_client = get_redis_client()
            if redis_client:
                try:
                    redis_client.setex(cache_key(short_code), CACHE_TTL_SECONDS, original_url)
                except redis.RedisError:
                    pass
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
    redis_client = get_redis_client()
    cached_url = None
    if redis_client:
        try:
            cached_url = redis_client.get(cache_key(short_code))
        except redis.RedisError:
            cached_url = None

    if cached_url:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Keep click tracking durable in PostgreSQL.
                cur.execute(
                    "UPDATE urls SET clicks = clicks + 1 WHERE short_code = %s",
                    (short_code,),
                )
                conn.commit()
        return redirect(cached_url)

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
                if redis_client:
                    try:
                        redis_client.setex(
                            cache_key(short_code),
                            CACHE_TTL_SECONDS,
                            url_data["original_url"],
                        )
                    except redis.RedisError:
                        pass
                return redirect(url_data["original_url"])
    return 'URL not found', 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True)