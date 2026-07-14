from datetime import datetime, timezone
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    g,
    abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, Product, Category
import os

from werkzeug.utils import secure_filename

# =========================
# USER MODEL
# =========================
class User(db.Model):
    __tablename__ = "users"

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


# =========================
# DECORATORS
# =========================
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


# =========================
# APP FACTORY
# =========================
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

        # Create default admin if one does not exist
        if User.query.filter_by(role="admin").first() is None:
            admin = User(
                fullname="Africa University Admin",
                email="admin@africau.edu",
                role="admin"
            )
            admin.set_password("Admin123!")

            db.session.add(admin)
            db.session.commit()

            print(
                "Default Admin Created:"
                " admin@africau.edu / Admin123!"
            )

        # Create default categories if none exist
        if Category.query.count() == 0:
            default_categories = [
                "Grains & Cereals",
                "Vegetables",
                "Fruits",
                "Dairy & Eggs",
                "Meat & Poultry",
                "Herbs & Spices",
                "Honey & Preserves",
                "Seeds & Seedlings"
            ]
            for cat_name in default_categories:
                db.session.add(Category(name=cat_name))
            db.session.commit()
            print("Default categories created.")

        print("SQLite database initialized successfully.")

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")

        if user_id is None:
            g.user = None
        else:
            g.user = User.query.get(user_id)

    return app


app = create_app()
import os

app.config["UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "static/uploads"
)


def get_cart_items():
    cart_entries = session.get("cart", [])
    items = []

    for entry in cart_entries:
        product = Product.query.get(entry.get("product_id"))
        if product is None:
            continue

        items.append({
            "id": product.id,
            "product_id": product.id,
            "name": product.name,
            "price": float(product.price),
            "quantity": entry.get("quantity", 1),
            "image": product.image,
            "stock": product.stock,
        })

    return items


@app.context_processor
def inject_cart():
    cart_items = get_cart_items()
    cart_total = sum(item["price"] * item["quantity"] for item in cart_items)
    return dict(global_cart=cart_items, global_cart_total=cart_total)

# =========================
# ROUTES
# =========================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/products")
def products():
    products = Product.query.all()
    return render_template("products.html", products=products)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("product_detail.html", product=product)

@app.route("/cart")
def cart():
    return render_template("cart.html", cart=get_cart_items())


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)

    if product.stock <= 0:
        flash("This product is currently out of stock.", "warning")
        return redirect(request.form.get("next") or url_for("products"))

    quantity = int(request.form.get("quantity", 1) or 1)
    quantity = max(1, quantity)

    if product.stock > 0 and quantity > product.stock:
        quantity = product.stock

    cart = session.get("cart", [])
    found = False

    for item in cart:
        if item.get("product_id") == product_id:
            item["quantity"] += quantity
            if product.stock > 0 and item["quantity"] > product.stock:
                item["quantity"] = product.stock
            found = True
            break

    if not found:
        cart.append({"product_id": product_id, "quantity": quantity})

    session["cart"] = cart
    flash(f"{product.name} added to your cart.", "success")
    return redirect(request.form.get("next") or url_for("cart"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    delta = int(request.form.get("delta", 0) or 0)
    cart = session.get("cart", [])
    updated_cart = []

    for item in cart:
        if item.get("product_id") != product_id:
            updated_cart.append(item)
            continue

        new_quantity = item.get("quantity", 1) + delta
        if new_quantity > 0:
            product = Product.query.get(product_id)
            if product is not None and product.stock > 0 and new_quantity > product.stock:
                new_quantity = product.stock
            updated_cart.append({"product_id": product_id, "quantity": new_quantity})

    session["cart"] = updated_cart
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart = session.get("cart", [])
    session["cart"] = [item for item in cart if item.get("product_id") != product_id]
    flash("Item removed from your cart.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["POST"])
def checkout():
    cart_items = get_cart_items()

    if not cart_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart"))

    total = round(sum(item["price"] * item["quantity"] for item in cart_items), 2)
    receipt = {
        "order_number": f"AU-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "date": datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p"),
        "customer": g.user.fullname if g.user else "Guest Customer",
        "email": g.user.email if g.user else "",
        "line_items": [
            {
                "name": item["name"],
                "quantity": item["quantity"],
                "price": round(float(item["price"]), 2),
                "subtotal": round(float(item["price"] * item["quantity"]), 2),
            }
            for item in cart_items
        ],
        "total": total,
        "payment_method": "Cash on pickup",
    }

    session["cart"] = []
    session["last_receipt"] = receipt
    flash(f"Checkout completed successfully. Receipt #{receipt['order_number']} is ready.", "success")
    return redirect(url_for("receipt"))


@app.route("/receipt")
def receipt():
    receipt_data = session.get("last_receipt")
    if not receipt_data:
        flash("No receipt available yet.", "info")
        return redirect(url_for("home"))
    return render_template("receipt.html", receipt=receipt_data)


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

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return render_template("auth/register.html")

        user = User(
            fullname=fullname,
            email=email,
            role="customer"
        )

        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("Registration successful.", "success")
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

        flash("Logged in successfully.", "success")
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
            flash("Admin account required.", "danger")
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
    flash("Logged out successfully.", "info")
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
    return render_template("403.html"),403

@app.route("/admin/products/add", methods=["GET", "POST"])
@role_required("admin")
def add_product():

    categories = Category.query.all()

    if request.method == "POST":

        name = request.form.get("name")
        description = request.form.get("description")
        price = request.form.get("price")
        category_id = request.form.get("category_id")

        image_file = request.files.get("image")

        image_name = None

        if image_file and image_file.filename:

            image_name = secure_filename(
                image_file.filename
            )

            image_file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_name
                )
            )

        product = Product(
            name=name,
            description=description,
            price=float(price),
            image=image_name,
            category_id=category_id
        )

        db.session.add(product)
        db.session.commit()

        flash("Product added successfully.", "success")

        return redirect(url_for("admin"))

    return render_template(
        "admin/add_product.html",
        categories=categories
    )



# =========================
# RUN APPLICATION
# =========================
if __name__ == "__main__":
    app.run(debug=True)
