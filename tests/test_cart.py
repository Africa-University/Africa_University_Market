import unittest

from app import app, db, User, ensure_default_admin
from models import Category, Product, Order


class CartFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            category = Category(name="Vegetables")
            db.session.add(category)
            db.session.commit()

            product = Product(
                name="Tomatoes",
                price=5.99,
                stock=10,
                description="Fresh tomatoes from the farm",
                category_id=category.id,
            )
            db.session.add(product)
            db.session.commit()
            self.product_id = product.id

    def test_add_update_and_checkout_flow(self):
        add_response = self.client.post(
            f"/cart/add/{self.product_id}",
            data={"quantity": 2, "next": "/products"},
            follow_redirects=True,
        )
        self.assertEqual(add_response.status_code, 200)

        with self.client.session_transaction() as session:
            self.assertEqual(len(session["cart"]), 1)
            self.assertEqual(session["cart"][0]["quantity"], 2)

        update_response = self.client.post(
            f"/cart/update/{self.product_id}",
            data={"delta": 1},
            follow_redirects=True,
        )
        self.assertEqual(update_response.status_code, 200)

        with self.client.session_transaction() as session:
            self.assertEqual(session["cart"][0]["quantity"], 3)

        checkout_response = self.client.post("/checkout", follow_redirects=True)
        self.assertEqual(checkout_response.status_code, 200)

        with self.client.session_transaction() as session:
            self.assertEqual(session.get("cart"), [])
            self.assertIn("last_receipt", session)
            self.assertEqual(session["last_receipt"]["total"], 17.97)

        self.assertIn("Receipt", checkout_response.get_data(as_text=True))

    def test_checkout_creates_order_record(self):
        self.client.post(
            f"/cart/add/{self.product_id}",
            data={"quantity": 1, "next": "/products"},
            follow_redirects=True,
        )

        self.client.post("/checkout", follow_redirects=True)

        with self.app.app_context():
            order = Order.query.first()
            self.assertIsNotNone(order)
            self.assertEqual(order.status, "Pending")
            self.assertEqual(order.total, 5.99)
            self.assertEqual(len(order.items), 1)
            self.assertEqual(order.items[0].product_name, "Tomatoes")

    def test_admin_can_delete_product(self):
        with self.app.app_context():
            admin = User(
                fullname="Admin User",
                email="admin-test@example.com",
                role="admin",
            )
            admin.set_password("secret123")
            db.session.add(admin)
            db.session.commit()

            product = Product.query.get(self.product_id)
            self.assertIsNotNone(product)

            with self.client.session_transaction() as session:
                session["user_id"] = admin.id
                session["user_role"] = admin.role
                session["user_name"] = admin.fullname

        response = self.client.post(f"/admin/products/{self.product_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertIsNone(Product.query.get(self.product_id))

    def test_admin_can_edit_product(self):
        with self.app.app_context():
            admin = User(
                fullname="Admin User",
                email="admin-edit@example.com",
                role="admin",
            )
            admin.set_password("secret123")
            db.session.add(admin)
            db.session.commit()

            with self.client.session_transaction() as session:
                session["user_id"] = admin.id
                session["user_role"] = admin.role
                session["user_name"] = admin.fullname

        response = self.client.post(
            f"/admin/products/{self.product_id}/edit",
            data={
                "name": "Updated Tomatoes",
                "description": "Fresh updated tomatoes",
                "price": "7.99",
                "category_id": 1,
                "stock": "12",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            product = Product.query.get(self.product_id)
            self.assertEqual(product.name, "Updated Tomatoes")
            self.assertEqual(product.stock, 12)
            self.assertEqual(product.price, 7.99)

    def test_currency_selector_updates_session(self):
        response = self.client.get("/set-currency/USD", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session:
            self.assertEqual(session["currency"], "USD")

    def test_currency_preference_survives_login(self):
        with self.app.app_context():
            user = User(
                fullname="Test Customer",
                email="customer@example.com",
                role="customer",
            )
            user.set_password("secret123")
            db.session.add(user)
            db.session.commit()

        with self.client.session_transaction() as session:
            session["currency"] = "USD"

        response = self.client.post(
            "/login",
            data={"email": "customer@example.com", "password": "secret123"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session:
            self.assertEqual(session.get("currency"), "USD")

    def test_default_admin_credentials_are_bootstrapped(self):
        with self.app.app_context():
            other_admin = User(
                fullname="Other Admin",
                email="other-admin@example.com",
                role="admin",
            )
            other_admin.set_password("another-pass")
            db.session.add(other_admin)
            db.session.commit()

            ensure_default_admin()

            default_admin = User.query.filter_by(email="admin@africau.edu").first()
            self.assertIsNotNone(default_admin)
            self.assertEqual(default_admin.role, "admin")
            self.assertTrue(default_admin.check_password("Admin123!"))

    def test_admin_can_add_product_with_stock(self):
        with self.app.app_context():
            admin = User(
                fullname="Admin User",
                email="admin-add@example.com",
                role="admin",
            )
            admin.set_password("secret123")
            db.session.add(admin)
            db.session.commit()

            with self.client.session_transaction() as session:
                session["user_id"] = admin.id
                session["user_role"] = admin.role
                session["user_name"] = admin.fullname

        response = self.client.post(
            "/admin/products/add",
            data={
                "name": "Fresh Maize",
                "description": "Sweet maize from the orchard",
                "price": "9.99",
                "stock": "15",
                "category_id": "1",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            product = Product.query.filter_by(name="Fresh Maize").first()
            self.assertIsNotNone(product)
            self.assertEqual(product.stock, 15)
            self.assertEqual(product.category_id, 1)

    def test_receipt_download_returns_pdf(self):
        with self.client.session_transaction() as session:
            session["last_receipt"] = {
                "order_number": "AU-TEST-RECEIPT",
                "date": "Today",
                "customer": "Test Customer",
                "email": "test@example.com",
                "line_items": [{"name": "Tomatoes", "quantity": 1, "subtotal": 5.99}],
                "total": 5.99,
                "payment_method": "Cash on pickup",
            }

        response = self.client.get("/receipt/download")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn(b"%PDF", response.data)

    def test_receipt_pdf_uses_selected_currency_symbol(self):
        with self.client.session_transaction() as session:
            session["currency"] = "USD"
            session["last_receipt"] = {
                "order_number": "AU-USD-RECEIPT",
                "date": "Today",
                "customer": "Test Customer",
                "email": "test@example.com",
                "line_items": [{"name": "Tomatoes", "quantity": 1, "subtotal": 5.99}],
                "total": 5.99,
                "payment_method": "Cash on pickup",
            }

        response = self.client.get("/receipt/download")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"$5.99", response.data)


if __name__ == "__main__":
    unittest.main()
