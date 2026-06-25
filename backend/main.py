from fastapi import FastAPI
from sqlalchemy import text

from backend.db import engine

app = FastAPI(title="NGS Monitor API")


@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
