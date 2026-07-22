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
    abort,
    make_response,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, Product, Category, Order, OrderItem
import os
from io import BytesIO

from werkzeug.utils import secure_filename

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
except ImportError:
    colors = None
    letter = None
    inch = None
    canvas = None
    ImageReader = None

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


def ensure_default_admin():
    admin = User.query.filter_by(email="admin@africau.edu").first()

    if admin is None:
        admin = User(
            fullname="Africa University Admin",
            email="admin@africau.edu",
            role="admin",
        )
        db.session.add(admin)

    if admin.role != "admin":
        admin.role = "admin"

    if not admin.password_hash or not admin.check_password("Admin123!"):
        admin.set_password("Admin123!")

    db.session.commit()
    return admin


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
        

        ensure_default_admin()
        print(
            "Default Admin Ready:"
            " admin@africau.edu / Admin123!"
        )

        # Create default categories if none exist
        if Category.query.count() == 0:
            default_categories = [
                "Poultry",
                "Pig Production",
                
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
    "static","uploads"
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
    currency = session.get("currency", "USD")
    currency_info = {
        "ZAR": {"code": "ZAR", "symbol": "R", "label": "South African Rand"},
        "USD": {"code": "USD", "symbol": "$", "label": "US Dollar"},
        "EUR": {"code": "EUR", "symbol": "€", "label": "Euro"},
    }.get(currency, {"code": currency, "symbol": currency, "label": currency})

    return dict(
        global_cart=cart_items,
        global_cart_total=cart_total,
        selected_currency=currency,
        currency_info=currency_info,
    )

# =========================
# ROUTES
# =========================
@app.route("/")
def home():

    featured_products = Product.query.limit(6).all()

    return render_template(
        "index.html",
        featured_products=featured_products
    )

@app.route("/products")
def products():

    category_name = request.args.get("category")


    if category_name:

        category = Category.query.filter_by(
            name=category_name
        ).first()


        if category:

            products = Product.query.filter_by(
                category_id=category.id
            ).all()

        else:

            products = []


    else:

        products = Product.query.all()



    return render_template(
        "products.html",
        products=products
    )


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")
        
        if not name or not email or not message:
            flash("Please fill in all required fields.", "danger")
        else:
            flash("Thank you for contacting us! Your message has been received.", "success")
            return redirect(url_for("contact"))
            
    return render_template("contact.html")

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

    if product.stock > 0 and quantity > p