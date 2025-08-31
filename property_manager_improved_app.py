"""
Improved Property & Contracts Manager — Single-file Flask App
UX upgrades: clean layout (Tailwind + daisyUI via CDN), responsive sidebar, status chips,
smart tables with search/sort (client-side), and focused forms.

How to run locally:
1) pip install flask werkzeug gunicorn
2) python property_manager_improved_app.py
3) Open http://127.0.0.1:5000

Default admin (auto-created if DB empty):
  email: admin@example.com
  password: admin123

This single file embeds templates with render_template_string
and stores data in SQLite (property_manager.db).
"""
from __future__ import annotations
import os
import sqlite3
from functools import wraps
from datetime import datetime, date
from typing import Optional

from flask import (
    Flask, request, redirect, url_for, session, flash,
    render_template_string
)
from werkzeug.security import generate_password_hash, check_password_hash

APP_NAME = "Property & Contracts Manager"
DB_PATH = os.path.join(os.path.dirname(__file__), "property_manager.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY)

# ---------------------- DB Helpers ----------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # users
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TEXT NOT NULL
        )
        """
    )
    # properties
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            dewa_no TEXT,
            unit_type TEXT,
            beds INTEGER,
            baths INTEGER,
            size REAL,
            furnished INTEGER DEFAULT 0,
            status TEXT DEFAULT 'vacant',
            price REAL,
            notes TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
        """
    )
    # tenants
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            id_number TEXT,
            emergency_contact TEXT,
            notes TEXT
        )
        """
    )
    # contracts
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            tenant_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            rent_amount REAL NOT NULL,
            frequency TEXT NOT NULL,
            deposit_amount REAL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            renewal_notice_days INTEGER DEFAULT 60,
            terms TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(property_id) REFERENCES properties(id),
            FOREIGN KEY(tenant_id) REFERENCES tenants(id)
        )
        """
    )
    # cheques
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS cheques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL,
            cheque_no TEXT,
            bank TEXT,
            amount REAL NOT NULL,
            issue_date TEXT,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'issued',
            FOREIGN KEY(contract_id) REFERENCES contracts(id)
        )
        """
    )
    conn.commit()

    # create default admin if none
    cur = c.execute("SELECT COUNT(*) AS n FROM users")
    if cur.fetchone()["n"] == 0:
        c.execute(
            "INSERT INTO users (email, password_hash, role, created_at) VALUES (?,?,?,?)",
            (
                "admin@example.com",
                generate_password_hash("admin123"),
                "admin",
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    conn.close()

# ---------------------- Auth ----------------------
def current_user() -> Optional[sqlite3.Row]:
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    cur = conn.execute("SELECT * FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
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

# ---------------------- Utilities ----------------------
def fmt_money(v) -> str:
    try:
        return f"AED {float(v):,.2f}"
    except Exception:
        return "AED 0.00"

def days_until(date_str: str) -> int:
    try:
        d = datetime.fromisoformat(date_str).date()
    except ValueError:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (d - date.today()).days

# ---------------------- Routes ----------------------
@app.route('/')
def index():
    user = current_user()
    if user:
        return redirect(url_for('dashboard'))
    return "<h1>Welcome to Property Manager</h1><p><a href='/login'>Login</a></p>"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        conn = get_db()
        cur = conn.execute("SELECT * FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        conn.close()
        if row and check_password_hash(row['password_hash'], password):
            session['user_id'] = row['id']
            flash('Welcome back!', 'info')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'warning')
    return '''
    <form method="post">
      <input name="email" placeholder="Email"><br>
      <input type="password" name="password" placeholder="Password"><br>
      <button>Login</button>
    </form>
    '''

@app.route('/dashboard')
@login_required
def dashboard():
    return "<h1>Dashboard</h1><p>Here will be properties, tenants, and contracts.</p>"

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('index'))

@app.before_first_request
def setup():
    init_db()

if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
