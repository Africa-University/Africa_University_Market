import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-this")

    SQLALCHEMY_DATABASE_URI = "sqlite:///market.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False