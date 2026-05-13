"""
Plugin : Revue des Droits Opérateurs (DSO-LOG-03)
Interface standard : FORM_TEMPLATE, RESULT_TEMPLATE, execute(), compute_taux()
"""

from fastapi import UploadFile

from app.revue_droits_engine import run_analysis

SLUG            = "revue_droits_operateurs"
FORM_TEMPLATE   = "plugins/revue_droits_operateurs/form.html"
RESULT_TEMPLATE = "plugins/revue_droits_operateurs/resultats.html"


def _read_text(upload: UploadFile) -> str:
    raw = upload.file.read()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


async def execute(files: dict, config: dict, db_path: str, control_date: str) -> dict:
    """
    files : {
        "sacre_file": UploadFile,
        "pki_file":   UploadFile,
        "kstamp_mrs1": UploadFile | None,
        "kstamp_mrs2": UploadFile | None,
        "kstamp_cly":  UploadFile | None,
    }
    Retourne le dict résultat de run_analysis() (sans excel_bytes).
    """
    sacre_text = _read_text(files["sacre_file"])
    pki_text   = _read_text(files["pki_file"])

    kstamp_texts = {}
    for site, key in (("MRS1", "kstamp_mrs1"), ("MRS2", "kstamp_mrs2"), ("CLY", "kstamp_cly")):
        f = files.get(key)
        if f and f.filename:
            kstamp_texts[site] = _read_text(f)

    return run_analysis(sacre_text, pki_text, kstamp_texts, db_path, control_date)


def compute_taux(result: dict) -> float:
    """Calcule le taux de conformité global depuis le résumé."""
    resume = result.get("resume", {})
    total   = sum(v.get("total",   0) for k, v in resume.items() if k != "total_ecarts")
    ecarts  = sum(v.get("ecarts",  0) for k, v in resume.items() if k != "total_ecarts")
    if total == 0:
        return 100.0
    return round((total - ecarts) / total * 100, 1)


def build_commentaire(result: dict) -> str:
    """Génère un commentaire automatique synthétique."""
    resume = result.get("resume", {})
    nb     = resume.get("total_ecarts", 0)
    date   = result.get("control_date", "")
    if nb == 0:
        return f"Revue droits opérateurs du {date} : aucun écart détecté. Tous les accès sont conformes."
    systems = [k for k, v in resume.items() if k != "total_ecarts" and v.get("ecarts", 0) > 0]
    return (
        f"Revue droits opérateurs du {date} : {nb} écart(s) détecté(s) sur "
        f"{', '.join(systems)}. Voir rapport Excel pour le détail."
    )
