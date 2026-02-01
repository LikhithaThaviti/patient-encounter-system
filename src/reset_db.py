from sqlalchemy import text

from src.database import engine

with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS likhitha_appointments"))
    conn.execute(text("DROP TABLE IF EXISTS likhitha_patients"))
    conn.execute(text("DROP TABLE IF EXISTS likhitha_doctors"))

print("All tables dropped successfully.")
