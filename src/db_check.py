from sqlalchemy import text

from src.database import engine

with engine.connect() as conn:
    db = conn.execute(text("SELECT DATABASE()")).scalar_one()
    print("Connected Database:", db)

    tables = conn.execute(text("SHOW TABLES")).all()
    print("Tables:", [t[0] for t in tables])
