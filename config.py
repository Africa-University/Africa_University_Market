class Config:
    # Security key for sessions
    SECRET_KEY = "dev-key"

    # SQLite database (local file)
    SQLALCHEMY_DATABASE_URI = "sqlite:///market.db"

    # Disable tracking for performance
    SQLALCHEMY_TRACK_MODIFICATIONS = False