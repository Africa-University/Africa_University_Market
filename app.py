from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="customer")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == "admin"


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Please log in to access that page.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def role_required(required_role):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if g.user is None:
                flash("Please log in to access that page.", "warning")
                return redirect(url_for("login"))
            if g.user.role != required_role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped_view
    return decorator


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        if User.query.filter_by(role="admin").first() is None:
            default_admin = User(
                fullname="Africa University Admin",
                email="admin@africau.edu",
                role="admin",
            )
            default_admin.set_password("Admin123!")
            db.session.add(default_admin)
            db.session.commit()
            print("Created default admin user: admin@africau.edu / Admin123! (change this password immediately)")
        print("Database tables created successfully (SQLite ready)")

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        if user_id is None:
            g.user = None
        else:
            g.user = User.query.get(user_id)

    return app


app = create_app()

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not fullname or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first() is not None:
            flash("That email is already registered.", "danger")
            return render_template("auth/register.html")

        new_user = User(fullname=fullname, email=email, role="customer")
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("auth/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        session.clear()
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["user_name"] = user.fullname

        flash("You are now logged in.", "success")
        return redirect(url_for("home"))

    return render_template("auth/login.html")


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/admin_login.html")

        if user.role != "admin":
            flash("Admin login required. Please use a regular account login.", "danger")
            return render_template("auth/admin_login.html")

        session.clear()
        session["user_id"] = user.id
        session["user_role"] = user.role
        session["user_name"] = user.fullname

        flash("Admin login successful.", "success")
        return redirect(url_for("admin"))

    return render_template("auth/admin_login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/admin")
@role_required("admin")
def admin():
    return render_template("admin.html")


@app.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403


if __name__ == "__main__":
    app.run(debug=True)
