from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import base64
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from face_engine import process_attendance, register_user, load_database

app = Flask(__name__)
app.secret_key = "change_this_to_a_random_secret"

# Admin credentials (CHANGE!)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = generate_password_hash("admin123")

# Ensure folders exist
os.makedirs("static/uploads/image_data", exist_ok=True)
os.makedirs("static/uploads/captures", exist_ok=True)

load_database()

# ---------------- AUTH DECORATOR ----------------
def admin_required(f):
    def wrapped(*args, **kwargs):
        if "admin_logged_in" not in session:
            flash("Please login as admin first", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    wrapped.__name__ = f.__name__
    return wrapped

# ---------------- PUBLIC ------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/capture', methods=['POST'])
def capture():
    data = request.form.get("image")
    if not data:
        flash("No image captured", "danger")
        return redirect(url_for("index"))

    header, encoded = data.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    fname = f"static/uploads/captures/{int(datetime.now().timestamp())}.jpg"

    with open(fname, "wb") as f:
        f.write(img_bytes)

    result, name = process_attendance(fname)
    return render_template("result.html", result=result, name=name)

# ---------------- ADMIN LOGIN/LOGOUT ------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()

        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["admin_logged_in"] = True
            flash("Logged in successfully", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid username or password", "danger")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html")

@app.route('/admin/logout')
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logged out", "success")
    return redirect(url_for("admin_login"))

# ---------------- ADMIN DASHBOARD ------------------------

@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route('/admin/records')
@admin_required
def admin_records():
    csv_path = "user_verifications.csv"
    rows = []

    if os.path.exists(csv_path):
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)

    return render_template("admin_records.html", rows=rows)

@app.route('/admin/register', methods=['GET', 'POST'])
@admin_required
def admin_register():
    if request.method == "POST":
        name = request.form.get("name").strip()
        image_data = request.form.get("image")

        if not name or not image_data:
            flash("Name & image required", "danger")
            return redirect(url_for("admin_register"))

        header, encoded = image_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)

        safe_name = "".join(c for c in name if c.isalnum()).strip()
        file_path = f"static/uploads/image_data/{safe_name}.jpg"

        with open(file_path, "wb") as f:
            f.write(img_bytes)

        register_user(file_path)
        flash("Employee registered successfully!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_register.html")

# ---------------- RUN APP ------------------------

if __name__ == "__main__":
    app.run(debug=True)
