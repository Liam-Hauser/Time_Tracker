"""
database/db.py — SQLAlchemy engine and session factory.
Reads connection details from .env.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

_url = os.getenv("DATABASE_URL") or (
    "postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}".format(
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        name=os.environ["DB_NAME"],
    )
)

engine = create_engine(_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
