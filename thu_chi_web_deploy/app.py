import os
import sqlite3
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None


app = Flask(__name__)

# Secret key dùng cho session đăng nhập
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# Mật khẩu đăng nhập web
APP_PASSWORD = os.environ.get("APP_PASSWORD", "123456")

# Database URL: local không có thì dùng SQLite, Render/Neon thì dùng PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL")

# Nếu sau này muốn thêm Gen, vào Render Environment thêm:
# GEN_OPTIONS = Gen 3,Gen 4,Gen 5
GEN_OPTIONS = [
    gen.strip()
    for gen in os.environ.get("GEN_OPTIONS", "Gen 3,Gen 4").split(",")
    if gen.strip()
]


def is_postgres():
    return DATABASE_URL and DATABASE_URL.startswith(("postgres://", "postgresql://"))


def get_db_connection():
    """
    Local: dùng SQLite finance.db
    Render/Neon: dùng PostgreSQL thông qua DATABASE_URL
    """
    if is_postgres():
        if psycopg2 is None:
            raise RuntimeError("psycopg2-binary chưa được cài. Hãy kiểm tra requirements.txt")

        db_url = DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)

    conn = sqlite3.connect("finance.db")
    conn.row_factory = sqlite3.Row
    return conn


def placeholder():
    """
    SQLite dùng ?
    PostgreSQL dùng %s
    """
    return "%s" if is_postgres() else "?"


def column_exists_sqlite(conn, table_name, column_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row["name"] for row in cursor.fetchall()]
    return column_name in columns


def init_db():
    """
    Tạo bảng nếu chưa có.
    Nếu bảng cũ chưa có cột generation thì tự thêm cột generation.
    Data cũ sẽ được đưa vào 'Chưa phân loại'.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incomes (
                id SERIAL PRIMARY KEY,
                generation TEXT DEFAULT 'Chưa phân loại',
                person TEXT NOT NULL,
                amount BIGINT NOT NULL,
                description TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                generation TEXT DEFAULT 'Chưa phân loại',
                person TEXT NOT NULL,
                amount BIGINT NOT NULL,
                description TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            "ALTER TABLE incomes ADD COLUMN IF NOT EXISTS generation TEXT DEFAULT 'Chưa phân loại'"
        )
        cursor.execute(
            "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS generation TEXT DEFAULT 'Chưa phân loại'"
        )

        cursor.execute(
            "UPDATE incomes SET generation = 'Chưa phân loại' WHERE generation IS NULL OR generation = ''"
        )
        cursor.execute(
            "UPDATE expenses SET generation = 'Chưa phân loại' WHERE generation IS NULL OR generation = ''"
        )

    else:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation TEXT DEFAULT 'Chưa phân loại',
                person TEXT NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation TEXT DEFAULT 'Chưa phân loại',
                person TEXT NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if not column_exists_sqlite(conn, "incomes", "generation"):
            cursor.execute(
                "ALTER TABLE incomes ADD COLUMN generation TEXT DEFAULT 'Chưa phân loại'"
            )

        if not column_exists_sqlite(conn, "expenses", "generation"):
            cursor.execute(
                "ALTER TABLE expenses ADD COLUMN generation TEXT DEFAULT 'Chưa phân loại'"
            )

        cursor.execute(
            "UPDATE incomes SET generation = 'Chưa phân loại' WHERE generation IS NULL OR generation = ''"
        )
        cursor.execute(
            "UPDATE expenses SET generation = 'Chưa phân loại' WHERE generation IS NULL OR generation = ''"
        )

    conn.commit()
    conn.close()


@app.template_filter("vnd")
def format_vnd(value):
    try:
        return f"{int(value):,} VND"
    except (ValueError, TypeError):
        return "0 VND"


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper


def generation_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))

        if not session.get("selected_gen"):
            return redirect(url_for("select_generation"))

        return func(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if not session.get("selected_gen"):
        return redirect(url_for("select_generation"))

    return redirect(url_for("overview"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if password == APP_PASSWORD:
            session["logged_in"] = True
            flash("Đăng nhập thành công.", "success")
            return redirect(url_for("select_generation"))

        flash("Mật khẩu không đúng. Vui lòng thử lại.", "danger")

    return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("Đã đăng xuất.", "info")
    return redirect(url_for("login"))


@app.route("/select-generation", methods=["GET", "POST"])
@login_required
def select_generation():
    if request.method == "POST":
        selected_gen = request.form.get("generation", "").strip()

        if selected_gen not in GEN_OPTIONS:
            flash("Vui lòng chọn Gen hợp lệ.", "danger")
            return redirect(url_for("select_generation"))

        session["selected_gen"] = selected_gen
        flash(f"Đang truy cập quỹ {selected_gen}.", "success")
        return redirect(url_for("overview"))

    return render_template("select_generation.html", gen_options=GEN_OPTIONS)


@app.route("/change-generation")
@login_required
def change_generation():
    session.pop("selected_gen", None)
    return redirect(url_for("select_generation"))


@app.route("/overview")
@generation_required
def overview():
    selected_gen = session["selected_gen"]
    ph = placeholder()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS total FROM incomes WHERE generation = {ph}",
        (selected_gen,),
    )
    total_income = cursor.fetchone()["total"] or 0

    cursor.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE generation = {ph}",
        (selected_gen,),
    )
    total_expense = cursor.fetchone()["total"] or 0

    remaining = int(total_income) - int(total_expense)

    cursor.execute(
        f"""
        SELECT id, generation, person, amount, description, date, created_at
        FROM incomes
        WHERE generation = {ph}
        ORDER BY date DESC, id DESC
        """,
        (selected_gen,),
    )
    incomes = cursor.fetchall()

    cursor.execute(
        f"""
        SELECT id, generation, person, amount, description, date, created_at
        FROM expenses
        WHERE generation = {ph}
        ORDER BY date DESC, id DESC
        """,
        (selected_gen,),
    )
    expenses = cursor.fetchall()

    conn.close()

    return render_template(
        "overview.html",
        selected_gen=selected_gen,
        total_income=total_income,
        total_expense=total_expense,
        remaining=remaining,
        incomes=incomes,
        expenses=expenses,
    )


@app.route("/income", methods=["GET", "POST"])
@generation_required
def income():
    selected_gen = session["selected_gen"]
    ph = placeholder()

    if request.method == "POST":
        person = request.form.get("person", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()

        if not person or not amount_raw or not description or not date:
            flash("Vui lòng nhập đầy đủ thông tin.", "danger")
            return redirect(url_for("income"))

        try:
            amount = int(float(amount_raw))
        except ValueError:
            flash("Số tiền không hợp lệ.", "danger")
            return redirect(url_for("income"))

        if amount < 0:
            flash("Số tiền không được âm.", "danger")
            return redirect(url_for("income"))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"""
            INSERT INTO incomes (generation, person, amount, description, date)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (selected_gen, person, amount, description, date),
        )

        conn.commit()
        conn.close()

        flash(f"Đã thêm khoản tiền vào cho {selected_gen}.", "success")
        return redirect(url_for("income"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"""
        SELECT id, generation, person, amount, description, date, created_at
        FROM incomes
        WHERE generation = {ph}
        ORDER BY date DESC, id DESC
        """,
        (selected_gen,),
    )
    incomes = cursor.fetchall()

    conn.close()

    return render_template("income.html", incomes=incomes, selected_gen=selected_gen)


@app.route("/expense", methods=["GET", "POST"])
@generation_required
def expense():
    selected_gen = session["selected_gen"]
    ph = placeholder()

    if request.method == "POST":
        person = request.form.get("person", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()

        if not person or not amount_raw or not description or not date:
            flash("Vui lòng nhập đầy đủ thông tin.", "danger")
            return redirect(url_for("expense"))

        try:
            amount = int(float(amount_raw))
        except ValueError:
            flash("Số tiền không hợp lệ.", "danger")
            return redirect(url_for("expense"))

        if amount < 0:
            flash("Số tiền không được âm.", "danger")
            return redirect(url_for("expense"))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"""
            INSERT INTO expenses (generation, person, amount, description, date)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (selected_gen, person, amount, description, date),
        )

        conn.commit()
        conn.close()

        flash(f"Đã thêm khoản tiền ra cho {selected_gen}.", "success")
        return redirect(url_for("expense"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"""
        SELECT id, generation, person, amount, description, date, created_at
        FROM expenses
        WHERE generation = {ph}
        ORDER BY date DESC, id DESC
        """,
        (selected_gen,),
    )
    expenses = cursor.fetchall()

    conn.close()

    return render_template("expense.html", expenses=expenses, selected_gen=selected_gen)


@app.route("/delete-income/<int:item_id>", methods=["POST"])
@generation_required
def delete_income(item_id):
    selected_gen = session["selected_gen"]
    ph = placeholder()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"DELETE FROM incomes WHERE id = {ph} AND generation = {ph}",
        (item_id, selected_gen),
    )

    conn.commit()
    conn.close()

    flash("Đã xóa khoản tiền vào.", "success")
    return redirect(request.referrer or url_for("income"))


@app.route("/delete-expense/<int:item_id>", methods=["POST"])
@generation_required
def delete_expense(item_id):
    selected_gen = session["selected_gen"]
    ph = placeholder()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"DELETE FROM expenses WHERE id = {ph} AND generation = {ph}",
        (item_id, selected_gen),
    )

    conn.commit()
    conn.close()

    flash("Đã xóa khoản tiền ra.", "success")
    return redirect(request.referrer or url_for("expense"))


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
