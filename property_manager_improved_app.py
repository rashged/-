
"""
Improved Property & Contracts Manager — Single-file Flask App (Deploy-Ready)
Minimal working version for Render (uses SQLite, simple HTML).
"""
from __future__ import annotations
import os, sqlite3
from datetime import datetime
from functools import wraps
from typing import Optional
from flask import Flask, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

APP_NAME = "Property & Contracts Manager"
DB_PATH = os.path.join(os.path.dirname(__file__), "property_manager.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            status TEXT DEFAULT 'vacant',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    # default admin
    cur = c.execute("SELECT COUNT(*) AS n FROM users")
    if cur.fetchone()["n"] == 0:
        c.execute("INSERT INTO users (email, password_hash, role, created_at) VALUES (?,?,?,?)",
                  ("admin@example.com", generate_password_hash("admin123"), "admin", datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()

def current_user() -> Optional[sqlite3.Row]:
    uid = session.get("user_id")
    if not uid: return None
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return row

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please log in first.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    user = current_user()
    if user: return redirect(url_for("dashboard"))
    return "<h1>Welcome to Property Manager</h1><p><a href='/login'>Login</a></p>"

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if row and check_password_hash(row["password_hash"], password):
            session["user_id"] = row["id"]
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "warning")
    return """
    <h2>Login</h2>
    <form method="post">
      <input name="email" placeholder="Email" value="admin@example.com"><br>
      <input type="password" name="password" placeholder="Password" value="admin123"><br>
      <button>Login</button>
    </form>
    """

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    count_props = conn.execute("SELECT COUNT(*) AS c FROM properties").fetchone()["c"]
    conn.close()
    return f"<h1>Dashboard</h1><p>Total properties: {count_props}</p><p><a href='/logout'>Logout</a></p>"

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.before_first_request
def setup():
    init_db()

if __name__ == '__main__':
    init_db()
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
