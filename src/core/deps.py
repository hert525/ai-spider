"""Dependencies for FastAPI."""
from src.core.database import db

async def get_database():
    return db
