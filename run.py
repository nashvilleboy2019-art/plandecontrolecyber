import os
import uvicorn
from sqlalchemy import text

HOST = os.environ.get("PDC_HOST", "0.0.0.0")
PORT = int(os.environ.get("PDC_PORT", 8002))
RELOAD = os.environ.get("PDC_RELOAD", "false").lower() == "true"

os.makedirs("data", exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)

from app.database import engine, Base
from app.models import *  # noqa: ensure all models are imported
Base.metadata.create_all(bind=engine)

from app.auth import create_default_data
create_default_data()

# Migrate default category/perimetre labels if still at original defaults
from app.database import SessionLocal
from app.models import Category, Perimetre

def _migrate_data():
    # Schema migrations (idempotent)
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE control_results ADD COLUMN assigned_to_id INTEGER REFERENCES users(id)",
            "ALTER TABLE control_results ADD COLUMN incident_ref VARCHAR(200)",
            "ALTER TABLE controls ADD COLUMN guide_url VARCHAR(500)",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass

    db = SessionLocal()
    try:
        # Rename DRI→Entité 1 and DSO→Entité 2 if still at old labels
        for old, new in [("DRI", "Entité 1"), ("DSO", "Entité 2")]:
            row = db.query(Category).filter(Category.label == old).first()
            if row and not db.query(Category).filter(Category.label == new).first():
                row.label = new
        # Hard-delete DRI/DSO if somehow still present after rename
        for label in ["DRI", "DSO"]:
            row = db.query(Category).filter(Category.label == label).first()
            if row:
                db.delete(row)
        # Remove old default perimetres
        for label in ["SMD", "eDAS", "MRS1", "MRS2", "CLY", "CLICHY", "VEN/VENELLES"]:
            row = db.query(Perimetre).filter(Perimetre.label == label).first()
            if row:
                db.delete(row)
        # Ensure SMSI exists
        if not db.query(Perimetre).filter(Perimetre.label == "SMSI").first():
            db.add(Perimetre(label="SMSI", ordre=0))
        # Fix ordre on Tous
        tous = db.query(Perimetre).filter(Perimetre.label == "Tous").first()
        if tous:
            tous.ordre = 99
        db.commit()
    finally:
        db.close()

_migrate_data()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=RELOAD)
