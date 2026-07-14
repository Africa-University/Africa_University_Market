import unittest

from app import app, db
from models import Category, Product


class CartFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            category = Category(name="Test Category")
            db.session.add(category)
            db.session.commit()

            product = Product(
                name="Test Product",
                price=5.99,
                stock=10,
                description="A sample test product",
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


if __name__ == "__main__":
    unittest.main()
