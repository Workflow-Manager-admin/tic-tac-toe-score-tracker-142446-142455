import os
from sqlmodel import SQLModel, Session, create_engine

# All required DB creds come from env variables set in deployment
MYSQL_URL = os.getenv("MYSQL_URL")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")

# Construct SQLAlchemy connection string
DB_URI = f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_URL}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

engine = create_engine(DB_URI, echo=True, pool_pre_ping=True)


# PUBLIC_INTERFACE
def get_session():
    """Yields a new session for DB usage."""
    with Session(engine) as session:
        yield session


# PUBLIC_INTERFACE
def create_db_and_tables():
    """Creates tables (if missing) in database."""
    SQLModel.metadata.create_all(engine)
