"""
Property & Contracts Manager — Flask (Single file, polished UI with fallback CSS)
- Tailwind + daisyUI (CDN) + Internal fallback CSS
- Auth (admin@example.com / admin123)
- Dashboard + Properties CRUD
- SQLite auto init (Flask ≥3.1 compatible)
"""

from __future__ import annotations
import os, sqlite3
from datetime import datetime
from functools import wraps
from typing import Optional

from flask import (
    Flask, request, redirect, url_for, session, flash, render_template_string
)
from werkzeug.security import generate_password_hash, check_password_hash
from jinja2 import DictLoader

APP_NAME = "Property & Contracts Manager"
DB_PATH = os.path.join(os.path.dirname(__file__), "property_manager.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY)

# ========= Templates =========
BASE_HTML = """
<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{{ title or app_name }}</title>

  <!-- Tailwind CDN -->
  <script src="https://cdn.tailwindcss.com"></script>

  <!-- daisyUI main CDN -->
  <link href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css" rel="stylesheet" />

  <!-- daisyUI alternate CDN -->
  <link rel="preconnect" href="https://unpkg.com">
  <link rel="alternate stylesheet" id="daisyui-alt" href="https://unpkg.com/daisyui@4.12.10/dist/full.min.css" disabled>

  <script>
    // if main CDN fails, enable alternate
    window.addEventListener('load', () => {
      const hasDaisy = [...document.styleSheets].some(s => (s.href||'').includes('daisyui'));
      if (!hasDaisy) {
        const alt = document.getElementById('daisyui-alt');
        if (alt) alt.disabled = false;
      }
    });
  </script>

  <!-- fallback CSS if all CDNs blocked -->
  <style>
    body {font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:#f7f9fb; margin:0;}
    .navbar {background:#fff; border-bottom:1px solid #eee; padding:10px 20px;}
    .card {background:#fff; border:1px solid #eee; border-radius:12px; padding:16px; margin:10px 0;}
    .btn {display:inline-block; padding:8px 14px; border-radius:10px; border:1px solid #ddd; background:#f1f1f1; text-decoration:none;}
    .btn-primary {background:#3b82f6; color:#fff; border-color:#3b82f6;}
    .menu a.active {font-weight:600;}
    table {width:100%; border-collapse:collapse;}
    th,td {border:1px solid #eee; padding:8px;}
  </style>
</head>
<body class="min-h-screen">
  <div class="navbar">
    <span style="font-weight:bold">{{ app_name }}</span>
    <span style="float:right">
      {% if user %}
        {{ user['email'] }} | <a class="btn" href="{{ url_for('logout') }}">Logout</a>
      {% else %}
        <a class="btn btn-primary" href="{{ url_for('login') }}">Login</a>
      {% endif %}
    </span>
  </div>
  <div class="p-6">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div>
          {% for cat, msg in messages %}
            <div class="card">{{ msg }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
  </div>
</body>
</html>
"""

app.jinja_loader = DictLoader({"base.html": BASE_HTML})

HOME_HTML = """
{% extends 'base.html' %}
{% block content %}
<h1 class="text-3xl font-bold mb-4">Welcome to {{ app_name }}</h1>
<p class="opacity-80">Manage properties, tenants & contracts with ease.</p>
{% if not user %}
  <div class="mt-4"><a class="btn btn-primary" href="{{ url_for('login') }}">Login</a></div>
{% endif %}
{% endblock %}
"""

LOGIN_HTML = """
{% extends 'base.html' %}
{% block content %}
<div class="card max-w-md mx-auto">
  <h2 class="text-xl font-semibold mb-2">Login</h2>
  <form method="post" class="space-y-3">
    <input class="input input-bordered w-full" name="email" placeholder="Email" value="admin@example.com"/>
    <input class="input input-bordered w-full" type="password" name="password" placeholder="Password" value="admin123"/>
    <button class="btn btn-primary w-full">Login</button>
  </form>
</div>
{% endblock %}
"""

DASHBOARD_HTML = """
{% extends 'base.html' %}
{% block content %}
<h1 class="text-2xl font-semibold mb-4">Dashboard</h1>
<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
  <div class="card">Total Properties: {{ totals.properties }}</div>
  <div class="card">Vacant: {{ totals.vacant }}</div>
  <div class="card">Occupied: {{ totals.occupied }}</div>
</div>
{% endblock %}
"""

PROPERTIES_LIST_HTML = """
{% extends 'base.html' %}
{% block content %}
<div class="flex justify-between mb-3">
  <h1 class="text-2xl font-semibold">Properties</h1>
  <a class="btn btn-primary" href="{{ url_for('new_property') }}">Add Property</a>
</div>
<form method="get" class="flex gap-2 mb-3">
  <input class="input input-bordered" name="q" value="{{ q or '' }}" placeholder="Search by name/address"/>
  <select name="status" class="select select-bordered">
    <option value="">All</option>
    <option value="vacant" {{ 'selected' if status=='vacant' else '' }}>Vacant</option>
    <option value="occupied" {{ 'selected' if status=='occupied' else '' }}>Occupied</option>
  </select>
  <button class="btn">Filter</button>
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Address</th><th>Status</th><th></th></tr></thead>
  <tbody>
  {% for p in rows %}
    <tr>
      <td>{{ p['name'] }}</td>
      <td>{{ p['address'] or '-' }}</td>
      <td>{{ p['status'] }}</td>
      <td>
        <a class="btn btn-sm" href="{{ url_for('edit_property', pid=p['id']) }}">Edit</a>
        <a class="btn btn-sm" href="{{ url_for('delete_property', pid=p['id']) }}" onclick="return confirm('Delete property?')">Delete</a>
      </td>
    </tr>
  {% else %}
    <tr><td colspan="4">No properties found.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
"""

PROPERTY_FORM_HTML = """
{% extends 'base.html' %}
{% block content %}
<h1 class="text-xl mb-3">{{ 'Edit' if p else 'New' }} Property</h1>
<form method="post" class="grid gap-3 max-w-lg">
  <input class="input input-bordered" name="name" placeholder="Name" value="{{ p['name'] if p else '' }}" required/>
  <input class="input input-bordered" name="address" placeholder="Address" value="{{ p['address'] if p else '' }}"/>
  <select class="select select-bordered" name="status">
    <option value="vacant" {{ 'selected' if p and p['status']=='vacant' else '' }}>Vacant</option>
    <option value="occupied" {{ 'selected' if p and p['status']=='occupied' else '' }}>Occupied</option>
  </select>
  <div class="flex gap-2">
    <button class="btn btn-primary">Save</button>
    <a class="btn" href="{{ url_for('properties') }}">Cancel</a>
  </div>
</form>
{% endblock %}
"""

# ========= DB =========
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        status TEXT DEFAULT 'vacant',
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        c.execute("INSERT INTO users (email,password_hash,role,created_at) VALUES (?,?,?,?)",
                  ("admin@example.com", generate_password_hash("admin123"), "admin", datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()

try: init_db()
except Exception as e: print("DB init error:", e)

# ========= Auth =========
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

# ========= Routes =========
@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template_string(HOME_HTML, app_name=APP_NAME, user=None, title="Home", active=None)

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
    return render_template_string(LOGIN_HTML, app_name=APP_NAME, user=None, title="Login", active=None)

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    totals = {
        "properties": conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0],
        "vacant": conn.execute("SELECT COUNT(*) FROM properties WHERE status='vacant'").fetchone()[0],
        "occupied": conn.execute("SELECT COUNT(*) FROM properties WHERE status='occupied'").fetchone()[0],
    }
    conn.close()
    return render_template_string(DASHBOARD_HTML, app_name=APP_NAME, user=current_user(),
                                  title="Dashboard", active="dashboard", totals=totals)

@app.route("/properties")
@login_required
def properties():
    q = request.args.get("q","").strip()
    status = request.args.get("status","").strip()
    sql, params = "SELECT * FROM properties WHERE 1=1", []
    if q:
        sql += " AND (name LIKE ? OR address LIKE ?)"
        like = f"%{q}%"; params += [like, like]
    if status:
        sql += " AND status=?"; params.append(status)
    sql += " ORDER BY created_at DESC"
    conn = get_db(); rows = conn.execute(sql, params).fetchall(); conn.close()
    return render_template_string(PROPERTIES_LIST_HTML, app_name=APP_NAME, user=current_user(),
                                  title="Properties", active="properties", rows=rows, q=q, status=status)

@app.route("/properties/new", methods=["GET","POST"])
@login_required
def new_property():
    if request.method == "POST":
        conn = get_db()
        conn.execute("INSERT INTO properties (name,address,status,created_at) VALUES (?,?,?,?)",
                     (request.form["name"], request.form.get("address"), request.form.get("status","vacant"),
                      datetime.utcnow().isoformat()))
        conn.commit(); conn.close()
        flash("Property added.", "success")
        return redirect(url_for("properties"))
    return render_template_string(PROPERTY_FORM_HTML, app_name=APP_NAME, user=current_user(),
                                  title="New Property", active="properties", p=None)

@app.route("/properties/<int:pid>/edit", methods=["GET","POST"])
@login_required
def edit_property(pid):
    conn = get_db(); p = conn.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone()
    if not p: conn.close(); flash("Property not found.", "warning"); return redirect(url_for("properties"))
    if request.method == "POST":
        conn.execute("UPDATE properties SET name=?, address=?, status=? WHERE id=?",
                     (request.form["name"], request.form.get("address"), request.form.get("status","vacant"), pid))
        conn.commit(); conn.close()
        flash("Property updated.", "success")
        return redirect(url_for("properties"))
    conn.close()
    return render_template_string(PROPERTY_FORM_HTML, app_name=APP_NAME, user=current_user(),
                                  title="Edit Property", active="properties", p=p)

@app.route("/properties/<int:pid>/delete")
@login_required
def delete_property(pid):
    conn = get_db(); conn.execute("DELETE FROM properties WHERE id=?", (pid,)); conn.commit(); conn.close()
    flash("Property deleted.", "info")
    return redirect(url_for("properties"))

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.context_processor
def inject_base():
    return {"app_name": APP_NAME, "user": current_user(), "active": request.endpoint}

# ========= Entry =========
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)



