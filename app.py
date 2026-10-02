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
from sqlalchemy import or_
from config import Config
from models import db, User, Product, Category, Order, OrderItem
import os
from io import BytesIO

from werkzeug.utils import secure_filename
from uuid import uuid4

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
# =========================
# AUTHENTICATION ROUTES
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form.get("fullname")
        email = request.form.get("email")
        phone = request.form.get("phone")
        address = request.form.get("address")
        password = request.form.get("password")


        existing_user = User.query.filter_by(
            email=email
        ).first()


        if existing_user:
            flash(
                "Email already registered.",
                "danger"
            )
            return redirect(
                url_for("register")
            )


        user = User(
            fullname=fullname,
            email=email,
            phone=phone,
            address=address,
            role="customer"
        )


        user.set_password(password)

        db.session.add(user)
        db.session.commit()


        flash(
            "Registration successful. Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )


    return render_template(
        "auth/register.html"
    )



@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")


        user = User.query.filter_by(
            email=email
        ).first()


        if user and user.check_password(password):

            session["user_id"] = user.id


            flash(
                "Login successful.",
                "success"
            )

            return redirect(
                url_for("home")
            )


        flash(
            "Invalid email or password.",
            "danger"
        )


    return render_template(
        "auth/login.html"
    )



@app.route("/logout")
def logout():

    session.clear()

    flash(
        "Logged out successfully.",
        "success"
    )

    return redirect(
        url_for("home")
    )



@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")


        admin = User.query.filter_by(
            email=email,
            role="admin"
        ).first()


        if admin and admin.check_password(password):

            session["user_id"] = admin.id

            return redirect(
                url_for("admin_dashboard")
            )


        flash(
            "Invalid admin details.",
            "danger"
        )


    return render_template(
        "auth/admin_login.html"
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

@app.route("/categories")
def categories():
    categories = Category.query.all()

    return render_template(
        "categories.html",
        categories=categories
    )

@app.route("/products")
def products():
    category_name = request.args.get("category")
    search_query = (request.args.get("q") or "").strip()
    products_query = Product.query
    if category_name:
        category = Category.query.filter_by(
            name=category_name
        ).first()
        if category:
            products_query = products_query.filter_by(category_id=category.id)
        else:
            products_query = products_query.filter_by(category_id=-1)

    if search_query:
        search_pattern = f"%{search_query}%"
        products_query = products_query.filter(
            or_(Product.name.ilike(search_pattern), Product.description.ilike(search_pattern))
        )

    products = products_query.order_by(Product.name).all()
    categories = Category.query.order_by(Category.name).all()

    return render_template(
        "products.html",
        products=products,
        categories=categories,
        selected_category=category_name,
        search_query=search_query,
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

    if product.stock >= quantity:
        cart = session.get("cart", [])

        for item in cart:
            if item["product_id"] == product_id:
                item["quantity"] += quantity
                break
        else:
            cart.append({
                "product_id": product_id,
                "quantity": quantity
            })

        session["cart"] = cart
        flash(f"Added {quantity} x {product.name} to your cart.", "success")

    return redirect(url_for("cart"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    cart = session.get("cart", [])
    delta = int(request.form.get("delta", 0) or 0)
    product = db.session.get(Product, product_id)

    for entry in cart:
        if entry.get("product_id") == product_id:
            new_quantity = entry.get("quantity", 1) + delta
            if new_quantity <= 0:
                cart.remove(entry)
            elif product is not None:
                entry["quantity"] = min(new_quantity, product.stock)
            break

    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    session["cart"] = [
        entry for entry in session.get("cart", [])
        if entry.get("product_id") != product_id
    ]
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["POST"])
def checkout():
    cart_items = get_cart_items()
    if not cart_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("products"))

    for item in cart_items:
        product = db.session.get(Product, item["product_id"])
        if product is None or product.stock < item["quantity"]:
            flash(f"There is not enough stock available for {item['name']}.", "warning")
            return redirect(url_for("cart"))

    customer_name = g.user.fullname if g.user else (request.form.get("name") or "Guest Customer")
    customer_email = g.user.email if g.user else (request.form.get("email") or "")
    total = sum(item["price"] * item["quantity"] for item in cart_items)
    order = Order(
        order_number=f"AU-{uuid4().hex[:10].upper()}",
        customer_name=customer_name,
        customer_email=customer_email,
        payment_method="Cash on pickup",
        total=total,
    )
    db.session.add(order)
    db.session.flush()

    line_items = []
    for item in cart_items:
        product = db.session.get(Product, item["product_id"])
        subtotal = item["price"] * item["quantity"]
        product.stock -= item["quantity"]
        db.session.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            quantity=item["quantity"],
            unit_price=item["price"],
            subtotal=subtotal,
        ))
        line_items.append({
            "name": item["name"],
            "quantity": item["quantity"],
            "subtotal": subtotal,
        })

    db.session.commit()
    receipt = {
        "order_number": order.order_number,
        "date": datetime.now(timezone.utc).strftime("%b %d, %Y %I:%M %p UTC"),
        "customer": customer_name,
        "email": customer_email,
        "line_items": line_items,
        "total": total,
        "payment_method": order.payment_method,
    }
    session["last_receipt"] = receipt
    session["cart"] = []
    return render_template("receipt.html", receipt=receipt)


@app.route("/set-currency/<currency_code>")
def set_currency(currency_code):
    currency_code = currency_code.upper()
    if currency_code not in {"ZAR", "USD", "EUR"}:
        abort(404)
    session["currency"] = currency_code
    return redirect(request.referrer or url_for("home"))


@app.route("/receipt/download")
def download_receipt():
    receipt = session.get("last_receipt")
    if not receipt:
        abort(404)
    if canvas is None or letter is None:
        abort(503)

    currency_code = session.get("currency", "USD")
    currency_symbol = {"ZAR": "R", "USD": "$", "EUR": "EUR "}.get(currency_code, "$")
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=letter, pageCompression=0)
    page_width, page_height = letter
    y_position = page_height - inch
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(inch, y_position, "Africa University Farm Receipt")
    y_position -= 0.4 * inch
    pdf.setFont("Helvetica", 11)
    pdf.drawString(inch, y_position, f"Order: {receipt['order_number']}")
    y_position -= 0.25 * inch
    pdf.drawString(inch, y_position, f"Date: {receipt['date']}")
    y_position -= 0.25 * inch
    pdf.drawString(inch, y_position, f"Customer: {receipt['customer']}")
    y_position -= 0.4 * inch

    for item in receipt["line_items"]:
        label = f"{item['name']} x{item['quantity']}"
        amount = f"{currency_symbol}{item['subtotal']:.2f}"
        pdf.drawString(inch, y_position, label[:70])
        pdf.drawRightString(page_width - inch, y_position, amount)
        y_position -= 0.25 * inch

    y_position -= 0.15 * inch
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(inch, y_position, "Total due on pickup")
    pdf.drawRightString(page_width - inch, y_position, f"{currency_symbol}{receipt['total']:.2f}")
    pdf.save()
    pdf_buffer.seek(0)
    response = make_response(pdf_buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=africa-university-receipt.pdf"
    return response

# =========================
# ADMIN DASHBOARD
# =========================

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    products = Product.query.all()
    orders = Order.query.all()
    return render_template(
        "admin/dashboard.html",
        products=products,
        orders=orders,
        pending_orders=sum(order.status == "Pending" for order in orders),
        completed_orders=sum(order.status == "Completed" for order in orders),
    )

def save_product_image(upload):
    if upload is None or not upload.filename:
        return None

    filename = secure_filename(upload.filename)
    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("Use a JPG, PNG, or WebP image.")

    image_name = f"{uuid4().hex}{extension}"
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    upload.save(os.path.join(app.config["UPLOAD_FOLDER"], image_name))
    return image_name


def apply_product_form(product):
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()

    try:
        price = float(request.form.get("price", ""))
        stock = int(request.form.get("stock", ""))
        category_id = int(request.form.get("category_id", ""))
    except (TypeError, ValueError):
        flash("Enter a valid price, stock quantity, and category.", "danger")
        return False

    category = db.session.get(Category, category_id)
    if not name or price < 0 or stock < 0 or category is None:
        flash("Complete all required product fields with valid values.", "danger")
        return False

    try:
        image_name = save_product_image(request.files.get("image"))
    except ValueError as error:
        flash(str(error), "danger")
        return False

    product.name = name
    product.description = description
    product.price = price
    product.stock = stock
    product.category_id = category.id
    if image_name:
        product.image = image_name
    return True


@app.route("/admin/products/add", methods=["GET", "POST"])
@app.route("/admin/add-product", methods=["GET", "POST"])
@role_required("admin")
def add_product():
    categories = Category.query.all()
    if request.method == "POST":
        product = Product()
        if apply_product_form(product):
            db.session.add(product)
            db.session.commit()
            flash("Product added successfully.", "success")
            return redirect(url_for("admin_dashboard"))

        return render_template("admin/add_product.html", categories=categories), 400

    return render_template(
        "admin/add_product.html",
        categories=categories
    )


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@app.route("/admin/edit-product/<int:product_id>", methods=["GET", "POST"])
@role_required("admin")
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.all()

    if request.method == "POST":
        if apply_product_form(product):
            db.session.commit()
            flash("Product updated successfully.", "success")
            return redirect(url_for("admin_dashboard"))
        return render_template(
            "admin/edit_product.html", product=product, categories=categories
        ), 400

    return render_template(
        "admin/edit_product.html", product=product, categories=categories
    )


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@app.route("/admin/delete-product/<int:product_id>", methods=["POST"])
@role_required("admin")
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if OrderItem.query.filter_by(product_id=product.id).first():
        flash("This product is part of an order and cannot be deleted.", "warning")
        return redirect(url_for("admin_dashboard"))

    image_path = (
        os.path.join(app.config["UPLOAD_FOLDER"], product.image)
        if product.image else None
    )
    db.session.delete(product)
    db.session.commit()

    if image_path and os.path.isfile(image_path):
        os.remove(image_path)

    flash("Product removed from the catalog.", "success")
    return redirect(url_for("admin_dashboard"))
# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":
    app.run(debug=True)