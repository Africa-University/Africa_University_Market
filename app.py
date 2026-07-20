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
    return render_template("index.html")

@app.route("/products")
def products():
    products = Product.query.all()
    return render_template("products.html", products=products)

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

    order = Order(
        order_number=receipt["order_number"],
        customer_name=receipt["customer"],
        customer_email=receipt["email"],
        payment_method=receipt["payment_method"],
        total=total,
    )
    db.session.add(order)
    db.session.flush()

    for item in cart_items:
        product = Product.query.get(item["product_id"])
        if product is None:
            continue

        db.session.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            quantity=item["quantity"],
            unit_price=float(item["price"]),
            subtotal=round(float(item["price"]) * item["quantity"], 2),
        ))

    db.session.commit()

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


@app.route("/receipt/download")
def download_receipt():
    receipt_data = session.get("last_receipt")
    if not receipt_data:
        receipt_data = {
            "order_number": "AU-TEST-RECEIPT",
            "date": datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p"),
            "customer": "Guest Customer",
            "email": "",
            "line_items": [],
            "total": 0.0,
            "payment_method": "Cash on pickup",
        }

    currency = session.get("currency", "USD")
    currency_info = {
        "ZAR": {"code": "ZAR", "symbol": "R", "label": "South African Rand"},
        "USD": {"code": "USD", "symbol": "$", "label": "US Dollar"},
        "EUR": {"code": "EUR", "symbol": "€", "label": "Euro"},
    }.get(currency, {"code": currency, "symbol": currency, "label": currency})
    currency_symbol = currency_info["symbol"]

    if canvas is not None and colors is not None and letter is not None and inch is not None and ImageReader is not None:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter, pageCompression=0)
        width, height = letter

        logo_path = os.path.join(app.root_path, "static", "images", "logo.png")
        try:
            if os.path.exists(logo_path):
                logo = ImageReader(logo_path)
                pdf.drawImage(logo, (width / 2) - 1.15 * inch, height - 1.35 * inch, width=2.3 * inch, height=0.95 * inch, mask='auto')
        except Exception:
            pass

        pdf.setFillColor(colors.HexColor("#cc0000"))
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(width / 2, height - 1.95 * inch, "Africa University Market")
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(colors.HexColor("#666666"))
        pdf.drawCentredString(width / 2, height - 2.25 * inch, "Official Purchase Receipt")

        pdf.setStrokeColor(colors.HexColor("#d8d8d8"))
        pdf.line(0.75 * inch, height - 2.55 * inch, width - 0.75 * inch, height - 2.55 * inch)

        pdf.setFillColor(colors.HexColor("#111111"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(0.75 * inch, height - 3.05 * inch, "Receipt Details")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(0.75 * inch, height - 3.35 * inch, f"Order number: {receipt_data.get('order_number', 'Unknown')}")
        pdf.drawString(0.75 * inch, height - 3.6 * inch, f"Date: {receipt_data.get('date', '')}")
        pdf.drawString(0.75 * inch, height - 3.85 * inch, f"Customer: {receipt_data.get('customer', '')}")
        pdf.drawString(0.75 * inch, height - 4.1 * inch, f"Email: {receipt_data.get('email', '')}")
        pdf.drawString(0.75 * inch, height - 4.35 * inch, f"Payment method: {receipt_data.get('payment_method', 'Cash on pickup')}")

        pdf.setFillColor(colors.HexColor("#cc0000"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(0.75 * inch, height - 4.95 * inch, "Items")

        y = height - 5.35 * inch
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(colors.HexColor("#222222"))
        for item in receipt_data.get("line_items", []):
            item_name = item.get("name", "")
            quantity = item.get("quantity", 0)
            subtotal = item.get("subtotal", 0)
            pdf.drawString(0.75 * inch, y, f"{item_name} x{quantity}")
            pdf.drawRightString(width - 0.75 * inch, y, f"{currency_symbol}{subtotal:.2f}")
            y -= 0.28 * inch

        if not receipt_data.get("line_items"):
            pdf.drawString(0.75 * inch, y, "No items recorded")
            y -= 0.28 * inch

        pdf.setStrokeColor(colors.HexColor("#d8d8d8"))
        pdf.line(0.75 * inch, y - 0.2 * inch, width - 0.75 * inch, y - 0.2 * inch)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(0.75 * inch, y - 0.6 * inch, "Total paid")
        pdf.drawRightString(width - 0.75 * inch, y - 0.6 * inch, f"{currency_symbol}{receipt_data.get('total', 0):.2f}")

        pdf.setFillColor(colors.HexColor("#cc0000"))
        pdf.setFont("Helvetica-Oblique", 9)
        pdf.drawCentredString(width / 2, 0.55 * inch, "Thank you for shopping with Africa University Market")

        pdf.showPage()
        pdf.save()
        response = make_response(buffer.getvalue())
    else:
        receipt_lines = [
            f"Receipt: {receipt_data.get('order_number', 'Unknown')}",
            f"Date: {receipt_data.get('date', '')}",
            f"Customer: {receipt_data.get('customer', '')}",
            f"Email: {receipt_data.get('email', '')}",
            f"Payment method: {receipt_data.get('payment_method', 'Cash on pickup')}",
            "Items:",
        ]

        for item in receipt_data.get("line_items", []):
            receipt_lines.append(f"- {item.get('name', '')} x{item.get('quantity', 0)}: {currency_symbol}{item.get('subtotal', 0):.2f}")

        receipt_lines.append(f"Total: {currency_symbol}{receipt_data.get('total', 0):.2f}")
        receipt_text = " ".join(line for line in receipt_lines if line)
        escaped_receipt_text = receipt_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        content = (
            f"BT /F1 12 Tf 72 720 Td ({escaped_receipt_text}) Tj ET"
        )
        object_payloads = [
            "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
            "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
            "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
            f"4 0 obj\n<< /Length {len(content.encode('latin-1', 'replace'))} >>\nstream\n{content}\nendstream\nendobj\n",
            "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        ]

        pdf_bytes = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for payload in object_payloads:
            offsets.append(len(pdf_bytes))
            pdf_bytes.extend(payload.encode("latin-1", "replace"))

        xref_offset = len(pdf_bytes)
        pdf_bytes.extend(f"xref\n0 {len(object_payloads) + 1}\n".encode("latin-1", "replace"))
        pdf_bytes.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf_bytes.extend(f"{offset:010d} 00000 n \n".encode("latin-1", "replace"))
        pdf_bytes.extend(
            f"trailer\n<< /Size {len(object_payloads) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1", "replace")
        )

        response = make_response(bytes(pdf_bytes))
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        f"attachment; filename={receipt_data.get('order_number', 'receipt').replace(' ', '_')}.pdf"
    )
    return response


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
        preferred_currency = session.get("currency", "USD")

        if email == "admin@africau.edu":
            ensure_default_admin()

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        session.clear()
        session["currency"] = preferred_currency
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
        preferred_currency = session.get("currency", "USD")

        if email == "admin@africau.edu":
            ensure_default_admin()

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/admin_login.html")

        if user.role != "admin":
            flash("Admin account required.", "danger")
            return render_template("auth/admin_login.html")

        session.clear()
        session["currency"] = preferred_currency
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


@app.route("/set-currency/<currency_code>")
def set_currency(currency_code):
    allowed = ["ZAR", "USD", "EUR"]
    currency_code = currency_code.upper()
    if currency_code not in allowed:
        currency_code = "ZAR"

    session["currency"] = currency_code
    flash(f"Currency switched to {currency_code}.", "info")
    return redirect(request.referrer or url_for("home"))


@app.route("/admin")
@role_required("admin")
def admin():
    products = Product.query.order_by(Product.id.desc()).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    pending_orders = Order.query.filter_by(status="Pending").count()
    completed_orders = Order.query.filter_by(status="Completed").count()
    return render_template(
        "admin.html",
        products=products,
        orders=orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
    )


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@role_required("admin")
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status", "").strip()
    valid_statuses = ["Pending", "Processing", "Completed", "Cancelled"]

    if new_status not in valid_statuses:
        flash("Please select a valid order status.", "warning")
        return redirect(url_for("admin"))

    order.status = new_status
    db.session.commit()
    flash(f"Order {order.order_number} updated to {new_status}.", "success")
    return redirect(url_for("admin"))


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
        stock = request.form.get("stock", "0")
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
            stock=max(0, int(stock or 0)),
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


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.all()

    if request.method == "POST":
        product.name = request.form.get("name", "").strip() or product.name
        product.description = request.form.get("description", "")
        product.price = float(request.form.get("price", product.price) or product.price)
        product.category_id = request.form.get("category_id")
        product.stock = int(request.form.get("stock", product.stock) or product.stock)

        image_file = request.files.get("image")
        if image_file and image_file.filename:
            image_name = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_name))
            product.image = image_name

        db.session.commit()
        flash("Product updated successfully.", "success")
        return redirect(url_for("admin"))

    return render_template("admin/edit_product.html", product=product, categories=categories)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@role_required("admin")
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted successfully.", "success")
    return redirect(url_for("admin"))


# =========================
# RUN APPLICATION
# =========================
if __name__ == "__main__":
    port=int(os.environ.get("PORT", 5000 )) 
    app.run(host="0.0.0.0", port=port, debug=False)

