"""
Plugin : Revue des Droits Opérateurs (DSO-LOG-03) — SACRE + PKI + KSTAMP
Interface standard : FORM_TEMPLATE, RESULT_TEMPLATE, execute(), compute_taux()
"""

from app.revue_droits_engine import run_analysis, read_upload_text

SLUG            = "revue_droits_operateurs"
FORM_TEMPLATE   = "plugins/revue_droits_operateurs/form.html"
RESULT_TEMPLATE = "plugins/revue_droits_operateurs/resultats.html"


async def execute(form, config: dict, db_path: str, control_date: str) -> dict:
    """
    form : starlette FormData contenant sacre_file, pki_file, kstamp_mrs1/mrs2/cly
    """
    sacre_file = form.get("sacre_file")
    pki_file   = form.get("pki_file")
    if not sacre_file or not sacre_file.filename:
        raise ValueError("Le fichier SACRE est requis.")
    if not pki_file or not pki_file.filename:
        raise ValueError("Le fichier PKI est requis.")

    sacre_text = read_upload_text(sacre_file)
    pki_text   = read_upload_text(pki_file)

    kstamp_texts = {}
    for site, key in (("MRS1", "kstamp_mrs1"), ("MRS2", "kstamp_mrs2"), ("CLY", "kstamp_cly")):
        f = form.get(key)
        if f and f.filename:
            kstamp_texts[site] = read_upload_text(f)
    if not kstamp_texts:
        raise ValueError("Au moins un fichier KSTAMP est requis.")

    return run_analysis(sacre_text=sacre_text, pki_text=pki_text,
                        kstamp_texts=kstamp_texts, db_path=db_path,
                        control_date=control_date)


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
