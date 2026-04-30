# URL Shortener (Flask + PostgreSQL)

A simple URL shortener built with Flask and PostgreSQL.

It lets you:
- shorten long URLs into 6-character codes
- redirect short links to original URLs
- track click counts
- view all links and stats on a dashboard page

## Tech Stack

- Python 3
- Flask
- PostgreSQL
- HTML/CSS (Jinja templates)

## Project Structure

```text
url-shortner/
├── app.py
├── static/
│   └── style.css
└── templates/
    ├── index.html
    └── stats.html
```

## Quick Start

### 1) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install flask psycopg[binary]
```

### 3) Run the app

```bash
python app.py
```

The app will be available at:
- `http://127.0.0.1:5000/`

## How It Works

- Submitting a URL on `/` creates a random 6-character short code.
- The mapping is stored in PostgreSQL table `urls`.
- Visiting `/<short_code>` redirects to the original URL and increments `clicks`.
- `/stats` lists all shortened links, click counts, and creation times.

## Routes

- `GET /` - show URL shortener form
- `POST /` - create a new shortened URL
- `GET /stats` - show all links and stats
- `GET /<short_code>` - redirect to original URL

## Configuration

Set `DATABASE_URL` before running:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/url_shortener"
```

- If a URL is entered without `http://` or `https://`, the app prepends `https://`.
- `app.py` calls `init_db()` when started with `python app.py`, so the `urls` table is auto-created if missing.

## Troubleshooting

### `RuntimeError: DATABASE_URL is required`

Set your PostgreSQL connection string first:

Use:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/url_shortener"
```

### Virtual environment not activating

If your environment folder is `venv`:

```bash
source venv/bin/activate
```

If it is `.venv`:

```bash
source .venv/bin/activate
```

## Future Improvements

- custom short codes
- URL validation and duplicate detection
- copy-to-clipboard button
- pagination/search on stats page
- automated tests
- Docker support

