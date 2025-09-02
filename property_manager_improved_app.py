"""
Property & Contracts Manager — Flask (Single file, polished UI)
- Tailwind + daisyUI (CDN)
- Auth (admin@example.com / admin123)
- Dashboard + Properties CRUD (list, search/filter, add, edit, delete)
- SQLite init runs once (no before_first_request, compatible with Flask ≥3.1)
- Fix for template inheritance via jinja2.DictLoader
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
from jinja2 import DictLoader  # مهم لعلاج TemplateNotFound عند استخدام extends

APP_NAME = "Property & Contracts Manager"
DB_PATH = os.path.join(os.path.dirname(__file__), "property_manager.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY)

# ========= Templates (Tailwind + daisyUI) =========
BASE_HTML = """
<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{{ title or app_name }}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css" rel="stylesheet" />
</head>
<body class="min-h-screen bg-base-200">
  <div class="drawer lg:drawer-open">
    <input id="sidebar" type="checkbox" class="drawer-toggle"/>
    <div class="drawer-content">
      <!-- Topbar -->
      <div class="navbar bg-base-100 shadow">
        <div class="flex-none lg:hidden">
          <label for="sidebar" class="btn btn-ghost btn-square">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
          </label>
        </div>
        <div class="flex-1 px-2">
          <a href="{{ url_for('index') }}" class="font-semibold">{{ app_name }}</a>
        </div>
        <div class="px-4">
          {% if user %}
            <span class="text-sm opacity-70 mr-2">{{ user['email'] }}</span>
            <a class="btn btn-ghost btn-sm" href="{{ url_for('logout') }}">Logout</a>
          {% else %}
            <a class="btn btn-primary btn-sm" href="{{ url_for('login') }}">Login</a>
          {% endif %}
        </div>
      </div>
      <!-- Content -->
      <div class="p-5 lg:p-8">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="max-w-3xl mx-auto space-y-2 mb-4">
              {% for cat, msg in messages %}
                <div class="alert {{ 'alert-warning' if cat=='warning' else 'alert-success' if cat=='success' else 'alert-info' }}">{{ msg }}</div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
      </div>
    </div>
    <div class="drawer-side">
      <label for="sidebar" class="drawer-overlay"></label>
      <ul class="menu p-4 w-72 min-h-full bg-base-100">
        <li class="menu-title">Navigation</li>
        <li><a class="{{ 'active' if active=='dashboard' }}" href="{{ url_for('dashboard') }}">Dashboard</a></li>
        <li><a class="{{ 'active' if active=='properties' }}" href="{{ url_for('properties') }}">Properties</a></li>
      </ul>
    </div>
  </div>
</body>
</html>
"""

# سجّل base.html في مُحمّل القوالب حتى تعمل {% extends 'base.html' %}
app.jinja_loader = DictLoader({
    "base.html": BASE_HTML
})

HOME_HTML = """
{% extends 'base.html' %}
{% block content %}
<div class="max-w-xl mx-auto text-center mt-10">
  <h1 class="text-3xl font-bold mb-2">Welcome to {{ app_name }}</h1>
  <p class="opacity-80">Manage properties, tenants & contracts with ease.</p>
  <div class="mt-6">
    {% if not user %}<a class="btn btn-primary" href="{{ url_for('login') }}">Login</a>{% endif %}
  </div>
</div>
{% endblock %}
"""

LOGIN_HTML = """
{% extends 'base.html' %}
{% block content %}
<div class="max-w-sm mx-auto">
  <div class="card bg-base-100 shadow">
    <div class="card-body">
      <h2 class="card-title">Login</h2>
      <form method="post" class="space-y-3">
        <input class="input input-bordered w-full" name="email" placeholder="Email" value="admin@example.com" />
        <input class="input input-bordered w-full" type="password" name="password" placeholder="Password" value="admin123" />
        <button class="btn btn-primary w-full">Login</button>
      </form>
    </div>
  </div>
</div>
{% endblock %}
"""

DASHBOARD_HTML = """
{% extends 'base.html' %}
{% block content %}
<h1 class="text-2xl font-semibold mb-4">Dashboard</h1>
<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
  <div class="stat bg-base-100 shadow">
    <div class="stat-title">Total Properties</div>
    <div class="stat-value">{{ totals.properties }}</div>
  </div>
  <div class="stat bg-base-100 shadow">
    <div class="stat-title">Vacant</div>
    <div class="stat-value">{{ totals.vacant }}</div>
  </div>
  <div class="stat bg-base-100 shadow">
    <div class="stat-title">Occupied</div>
    <div class="stat-value">{{ totals.occupied }}</div>
  </div>
</div>
{% endblock %}
"""

PROPERTIES_LIST_HTML = """
{% extends 'base.html' %}
{% block content %}
<div class="flex items-center justify-between mb-4">
  <h1 class="text-2xl font-semibold">Properties</h1>
  <a class="btn btn-primary" href="{{ url_for('new_property') }}">Add Property</a>
</div>
<div class="card bg-base-100 shadow">
  <div class="card-body">
    <form method="get" class="flex gap-2 mb-3">
      <input class="input input-bordered w-full" name="q" value="{{ q or '' }}" placeholder="Search by name/address"/>
      <select name="status" class="select select-bordered">
        <option value="">All</option>
        <option value="vacant" {{ 'selected' if status=='vacant' else '' }}>Vacant</option>
        <option value="occupied" {{ 'selected' if status=='occupied' else '' }}>Occupied</option>
      </select>
      <button class="btn">Filter</button>
    </form>
    <div class="overflow-x-auto">
      <table class="table">
        <thead><tr><th>Name</th><th>Address</th><th>Status</th><th></th></tr></thead>
        <tbody>
        {% for p in rows %}
          <tr>
            <td class="font-medium">{{ p['name'] }}</td>
            <td class="opacity-80">{{ p['address'] or '-' }}</td>
            <td>
              <span class="badge {{ 'badge-ghost' if p['status']=='vacant' else 'badge-success' }}">{{ p['status'] }}</span>
            </td>
            <td class="text-right">
              <a class="btn btn-sm" href="{{ url_for('edit_property', pid=p['id']) }}">Edit</a>
              <a class="btn btn-sm btn-outline" href="{{ url_for('delete_property', pid=p['id']) }}" onclick="return confirm('Delete property?')">Delete</a>
            </td>
          </tr>
        {% else %}
          <tr><td colspan="4" class="opacity-70">No properties found.</td></tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endblock %}
"""

PROPERTY_FORM_HTML = """
{% extends 'base.html' %}
{% block content %}
<h1 class="text-2xl font-semibold mb-4">{{ 'Edit' if p else 'New' }} Property</h1>
<form method="post" class="grid md:grid-cols-2 gap-4 max-w-3xl">
  <input class="input input-bordered" name="name" placeholder="Name" value="{{ p['name'] if p else '' }}" required />
  <input class="input input-bordered" name="address" placeholder="Address" value="{{ p['address'] if p else '' }}" />
  <select class="select select-bordered" name="status">
    <option value="vacant" {{ 'selected' if p and p['status']=='vacant' else '' }}>Vacant</option>
    <option value="occupied" {{ 'selected' if p and p['status']=='occupied' else '' }}>Occupied</option>
  </select>
  <div class="md:col-span-2 flex gap-2">
    <button class="btn btn-primary">Save</button>
    <a class="btn" href="{{ url_for('properties') }}">Cancel</a>
  </div>
</form>
{% endblock %}
"""

# ========= DB helpers =========
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
    # seed admin
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        c.execute(
            "INSERT INTO users (email, password_hash, role, created_at) VALUES (?,?,?,?)",
            ("admin@example.com", generate_password_hash("admin123"), "admin", datetime.utcnow().isoformat())
        )
        conn.commit()
    conn.close()

# init once (works under Gunicorn too)
try:
    init_db()
except Exception as e:
    print("DB init error:", e)

# ========= Auth =========
def current_user() -> Optional[sqlite3.Row]:
    uid = session.get("user_id")
    if not uid:
        return None
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
    return render_template_string(DASHBOARD_HTML, app_name=APP_NAME, user=current_user(), title="Dashboard",
                                  active="dashboard", totals=totals)

# ---- Properties CRUD ----
@app.route("/properties")
@login_required
def properties():
    q = request.args.get("q","").strip()
    status = request.args.get("status","").strip()
    sql = "SELECT * FROM properties WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR address LIKE ?)"
        like = f"%{q}%"
        params += [like, like]
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template_string(PROPERTIES_LIST_HTML, app_name=APP_NAME, user=current_user(),
                                  title="Properties", active="properties", rows=rows, q=q, status=status)

@app.route("/properties/new", methods=["GET","POST"])
@login_required
def new_property():
    if request.method == "POST":
        conn = get_db()
        conn.execute(
            "INSERT INTO properties (name,address,status,created_at) VALUES (?,?,?,?)",
            (request.form["name"], request.form.get("address"), request.form.get("status","vacant"),
             datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        flash("Property added.", "success")
        return redirect(url_for("properties"))
    return render_template_string(PROPERTY_FORM_HTML, app_name=APP_NAME, user=current_user(),
                                  title="New Property", active="properties", p=None)

@app.route("/properties/<int:pid>/edit", methods=["GET","POST"])
@login_required
def edit_property(pid):
    conn = get_db()
    p = conn.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone()
    if not p:
        conn.close()
        flash("Property not found.", "warning")
        return redirect(url_for("properties"))
    if request.method == "POST":
        conn.execute(
            "UPDATE properties SET name=?, address=?, status=? WHERE id=?",
            (request.form["name"], request.form.get("address"), request.form.get("status","vacant"), pid)
        )
        conn.commit()
        conn.close()
        flash("Property updated.", "success")
        return redirect(url_for("properties"))
    conn.close()
    return render_template_string(PROPERTY_FORM_HTML, app_name=APP_NAME, user=current_user(),
                                  title="Edit Property", active="properties", p=p)

@app.route("/properties/<int:pid>/delete")
@login_required
def delete_property(pid):
    conn = get_db()
    conn.execute("DELETE FROM properties WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Property deleted.", "info")
    return redirect(url_for("properties"))

# ========= Context (to provide 'user' & 'active') =========
@app.context_processor
def inject_base():
    return {"app_name": APP_NAME, "user": current_user(), "active": request.endpoint}

# ========= Entry =========
if __name__ == "__main__":
    # Safe to call init_db again
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)


