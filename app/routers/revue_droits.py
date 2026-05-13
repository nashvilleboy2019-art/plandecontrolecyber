import json
import os
import uuid
from datetime import date

from fastapi import APIRouter, Request, Depends, UploadFile, File, Form
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppConfig
from app.utils import get_current_user, get_config, log_activity
from app.templates_config import templates
from app.revue_droits_engine import run_analysis

router = APIRouter(tags=["revue_droits"])

UPLOAD_DIR = os.path.join("static", "uploads", "revue_droits")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DEFAULT_DB = r"C:\Users\Romain\Project\BaseLIR\data\baselir.db"


def _db_path(db: Session) -> str:
    return get_config(db, "baselir_path", DEFAULT_DB)


# ── Page upload ───────────────────────────────────────────────────────────────

@router.get("/revue-droits")
async def revue_droits_index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "revue_droits/index.html", {
        "user":  user,
        "today": date.today().strftime("%Y-%m-%d"),
        "flash": request.session.pop("flash", None),
        "error": request.session.pop("revue_error", None),
    })


# ── Analyse ───────────────────────────────────────────────────────────────────

@router.post("/revue-droits/analyser")
async def revue_droits_analyser(
    request: Request,
    db: Session = Depends(get_db),
    sacre_file:      UploadFile = File(...),
    pki_file:        UploadFile = File(...),
    kstamp_mrs1:     UploadFile = File(None),
    kstamp_mrs2:     UploadFile = File(None),
    kstamp_cly:      UploadFile = File(None),
    control_date:    str        = Form(""),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # Validation : au moins 1 fichier KSTAMP
    kstamp_files = {
        "MRS1": kstamp_mrs1,
        "MRS2": kstamp_mrs2,
        "CLY":  kstamp_cly,
    }
    kstamp_provided = {k: v for k, v in kstamp_files.items()
                       if v and v.filename}
    if not kstamp_provided:
        request.session["revue_error"] = "Au moins un fichier KSTAMP est requis."
        return RedirectResponse("/revue-droits", status_code=302)

    # Lecture des fichiers uploadés
    def _read_text(upload: UploadFile) -> str:
        raw = upload.file.read()
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    sacre_text = _read_text(sacre_file)
    pki_text   = _read_text(pki_file)
    kstamp_texts = {site: _read_text(f) for site, f in kstamp_provided.items()}

    if not control_date:
        control_date = date.today().strftime("%Y-%m-%d")

    db_path = _db_path(db)

    try:
        result = run_analysis(sacre_text, pki_text, kstamp_texts, db_path, control_date)
    except Exception as e:
        request.session["revue_error"] = f"Erreur d'analyse : {e}"
        return RedirectResponse("/revue-droits", status_code=302)

    # Sauvegarde du rapport Excel et des données JSON
    run_id = str(uuid.uuid4())
    excel_path = os.path.join(UPLOAD_DIR, f"report_{run_id}.xlsx")
    json_path  = os.path.join(UPLOAD_DIR, f"results_{run_id}.json")

    with open(excel_path, "wb") as f:
        f.write(result.pop("excel_bytes"))

    # Sérialisation JSON — convertit les sets en listes
    def _jsonify(obj):
        if isinstance(obj, set):
            return sorted(obj)
        raise TypeError(f"Not serializable: {type(obj)}")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, default=_jsonify)

    log_activity(db, user.id, user.username,
                 "Revue droits opérateurs", "revue_droits", run_id,
                 f"Date: {control_date} — {result['resume']['total_ecarts']} écart(s)")

    return RedirectResponse(f"/revue-droits/resultats/{run_id}", status_code=302)


# ── Page résultats ────────────────────────────────────────────────────────────

@router.get("/revue-droits/resultats/{run_id}")
async def revue_droits_resultats(
    request: Request, run_id: str, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    json_path = os.path.join(UPLOAD_DIR, f"results_{run_id}.json")
    if not os.path.exists(json_path):
        request.session["revue_error"] = "Résultats introuvables (session expirée ?)."
        return RedirectResponse("/revue-droits", status_code=302)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    return templates.TemplateResponse(request, "revue_droits/resultats.html", {
        "user":    user,
        "run_id":  run_id,
        "data":    data,
        "flash":   request.session.pop("flash", None),
    })


# ── Téléchargement Excel ──────────────────────────────────────────────────────

@router.get("/revue-droits/telecharger/{run_id}")
async def revue_droits_download(
    request: Request, run_id: str, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    excel_path = os.path.join(UPLOAD_DIR, f"report_{run_id}.xlsx")
    if not os.path.exists(excel_path):
        request.session["revue_error"] = "Rapport introuvable."
        return RedirectResponse("/revue-droits", status_code=302)

    # Lire la date depuis le JSON pour nommer le fichier proprement
    json_path = os.path.join(UPLOAD_DIR, f"results_{run_id}.json")
    ctrl_date = date.today().strftime("%Y-%m-%d")
    if os.path.exists(json_path):
        with open(json_path, encoding="utf-8") as f:
            ctrl_date = json.load(f).get("control_date", ctrl_date)

    filename = f"{ctrl_date}-Revue-Droits-Operateurs.xlsx"

    def _iter():
        with open(excel_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        _iter(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
