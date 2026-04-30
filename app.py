from flask import Flask, render_template, request, redirect
import sqlite3
import string
import random

app = Flask(__name__)
DATABASE = 'urls.db'


def get_db_connection():
    # Connect to the SQLite database file
    conn = sqlite3.connect(DATABASE)
    # Allow accessing columns by name instead of index
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Create the urls table if it doesn't already exist
    conn.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            short_code TEXT NOT NULL UNIQUE,
            clicks INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Save the changes and close the connection
    conn.commit()
    conn.close()
    
def generate_short_code(length=6):
    # Build a pool of letters and digits (62 possible characters)
    characters = string.ascii_letters + string.digits
    conn = get_db_connection()
    while True:
        # Generate a random 6-character code
        code = ''.join(random.choices(characters, k=length))
        # Check if this code already exists in the database
        existing = conn.execute(
            'SELECT id FROM urls WHERE short_code = ?', (code,)
        ).fetchone()
        # If the code is unique, return it
        if not existing:
            conn.close()
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
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO urls (original_url, short_code) VALUES (?, ?)',
                (original_url, short_code)
            )
            conn.commit()
            conn.close()
            # Build the full shortened URL
            short_url = request.host_url + short_code
    return render_template('index.html', short_url=short_url)

@app.route('/stats')
def stats():
    # Fetch all URLs, newest first
    conn = get_db_connection()
    urls = conn.execute(
        'SELECT short_code, original_url, clicks, created_at FROM urls ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return render_template('stats.html', urls=urls)

@app.route('/<short_code>')
def redirect_url(short_code):
    conn = get_db_connection()
    url_data = conn.execute(
        'SELECT original_url FROM urls WHERE short_code = ?', (short_code,)
    ).fetchone()
    if url_data:
        # Increment the click counter for this short code
        conn.execute(
            'UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?',
            (short_code,)
        )
        conn.commit()
        conn.close()
        return redirect(url_data['original_url'])
    conn.close()
    return 'URL not found', 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True)