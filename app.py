from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import sqlite3
from pathlib import Path

# Only used when the app is deployed with PostgreSQL, for example on Render.
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "finance.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()
USE_POSTGRES = bool(DATABASE_URL)
PLACEHOLDER = "%s" if USE_POSTGRES else "?"


def normalize_database_url(url):
    """Render normally gives postgresql://, but this also supports postgres://."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def get_db_connection():
    """Create a database connection.

    Local machine: SQLite finance.db
    Render/hosting: PostgreSQL when DATABASE_URL is provided
    """
    if USE_POSTGRES:
        if psycopg2 is None:
            raise RuntimeError("psycopg2-binary is required when using DATABASE_URL.")
        return psycopg2.connect(
            normalize_database_url(DATABASE_URL),
            cursor_factory=RealDictCursor,
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def execute_db(sql, params=()):
    """Run INSERT/UPDATE/DELETE/CREATE statements."""
    conn = get_db_connection()
    try:
        if USE_POSTGRES:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        else:
            conn.execute(sql, params)
            conn.commit()
    finally:
        conn.close()


def fetch_all(sql, params=()):
    """Fetch many rows."""
    conn = get_db_connection()
    try:
        if USE_POSTGRES:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def fetch_one(sql, params=()):
    """Fetch one row."""
    conn = get_db_connection()
    try:
        if USE_POSTGRES:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def init_db():
    """Create tables if they do not exist."""
    if USE_POSTGRES:
        income_table_sql = """
            CREATE TABLE IF NOT EXISTS incomes (
                id SERIAL PRIMARY KEY,
                person TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK(amount >= 0),
                description TEXT NOT NULL,
                date TEXT NOT NULL
            )
        """
        expense_table_sql = """
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                person TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK(amount >= 0),
                description TEXT NOT NULL,
                date TEXT NOT NULL
            )
        """
    else:
        income_table_sql = """
            CREATE TABLE IF NOT EXISTS incomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK(amount >= 0),
                description TEXT NOT NULL,
                date TEXT NOT NULL
            )
        """
        expense_table_sql = """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK(amount >= 0),
                description TEXT NOT NULL,
                date TEXT NOT NULL
            )
        """

    execute_db(income_table_sql)
    execute_db(expense_table_sql)


def format_vnd(value):
    """Format number into Vietnamese currency style."""
    try:
        value = int(value or 0)
    except (TypeError, ValueError):
        value = 0
    return f"{value:,.0f} VND"


app.jinja_env.filters["vnd"] = format_vnd


def validate_form(person, amount, description, date):
    """Validate input data from form."""
    if not person or not amount or not description or not date:
        return False, "Vui lòng nhập đầy đủ thông tin."

    try:
        amount = int(amount)
    except ValueError:
        return False, "Số tiền phải là số hợp lệ."

    if amount < 0:
        return False, "Số tiền không được là số âm."

    return True, amount


@app.before_request
def require_login():
    """Protect the public website with a simple password when APP_PASSWORD is set."""
    if not APP_PASSWORD:
        return None

    allowed_endpoints = {"login", "static"}
    if request.endpoint in allowed_endpoints:
        return None

    if session.get("logged_in"):
        return None

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not APP_PASSWORD:
        return redirect(url_for("overview"))

    if request.method == "POST":
        password = request.form.get("password", "")
        if password == APP_PASSWORD:
            session["logged_in"] = True
            flash("Đăng nhập thành công!", "success")
            return redirect(url_for("overview"))
        flash("Sai mật khẩu, vui lòng thử lại.", "danger")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Đã đăng xuất.", "success")
    return redirect(url_for("login"))


@app.route("/")
def home():
    return redirect(url_for("overview"))


@app.route("/income", methods=["GET", "POST"])
def income():
    if request.method == "POST":
        person = request.form.get("person", "").strip()
        amount = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()

        is_valid, result = validate_form(person, amount, description, date)
        if not is_valid:
            flash(result, "danger")
        else:
            execute_db(
                f"INSERT INTO incomes (person, amount, description, date) VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
                (person, result, description, date),
            )
            flash("Đã thêm khoản tiền vào thành công!", "success")
            return redirect(url_for("income"))

    incomes = fetch_all("SELECT * FROM incomes ORDER BY date DESC, id DESC")
    return render_template("income.html", incomes=incomes)


@app.route("/expense", methods=["GET", "POST"])
def expense():
    if request.method == "POST":
        person = request.form.get("person", "").strip()
        amount = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()

        is_valid, result = validate_form(person, amount, description, date)
        if not is_valid:
            flash(result, "danger")
        else:
            execute_db(
                f"INSERT INTO expenses (person, amount, description, date) VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
                (person, result, description, date),
            )
            flash("Đã thêm khoản tiền ra thành công!", "success")
            return redirect(url_for("expense"))

    expenses = fetch_all("SELECT * FROM expenses ORDER BY date DESC, id DESC")
    return render_template("expense.html", expenses=expenses)


@app.route("/overview")
def overview():
    incomes = fetch_all("SELECT * FROM incomes ORDER BY date DESC, id DESC")
    expenses = fetch_all("SELECT * FROM expenses ORDER BY date DESC, id DESC")

    total_income_row = fetch_one("SELECT COALESCE(SUM(amount), 0) AS total FROM incomes")
    total_expense_row = fetch_one("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses")

    total_income = total_income_row["total"] if total_income_row else 0
    total_expense = total_expense_row["total"] if total_expense_row else 0
    remaining = total_income - total_expense

    return render_template(
        "overview.html",
        incomes=incomes,
        expenses=expenses,
        total_income=total_income,
        total_expense=total_expense,
        remaining=remaining,
    )


@app.route("/delete-income/<int:item_id>", methods=["POST"])
def delete_income(item_id):
    execute_db(f"DELETE FROM incomes WHERE id = {PLACEHOLDER}", (item_id,))
    flash("Đã xóa khoản tiền vào.", "success")
    return redirect(request.referrer or url_for("income"))


@app.route("/delete-expense/<int:item_id>", methods=["POST"])
def delete_expense(item_id):
    execute_db(f"DELETE FROM expenses WHERE id = {PLACEHOLDER}", (item_id,))
    flash("Đã xóa khoản tiền ra.", "success")
    return redirect(request.referrer or url_for("expense"))


# Important for deployment: gunicorn imports app.py but does not run the block below.
# Therefore, initialize the database when the module is imported.
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
