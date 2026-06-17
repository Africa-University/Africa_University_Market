from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<Product {self.name}>"

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        print("Database tables created successfully (SQLite ready)")

    @app.route("/")
    def home():
        return "Africa University Market Running with Database Ready"

    @app.route("/health")
    def health():
        return {"status": "running"}

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)