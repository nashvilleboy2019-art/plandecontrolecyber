"""
Plugin : Revue des Droits Opérateurs – KSTAMP (DSO-LOG-03-03)
"""

from app.revue_droits_engine import run_analysis, read_upload_text

SLUG            = "revue_droits_kstamp"
FORM_TEMPLATE   = "plugins/revue_droits_kstamp/form.html"
RESULT_TEMPLATE = "plugins/revue_droits_operateurs/resultats.html"


async def execute(form, config: dict, lir_url: str, lir_key: str, control_date: str) -> dict:
    kstamp_texts = {}
    for site, key in (("MRS1", "kstamp_mrs1"), ("MRS2", "kstamp_mrs2"), ("CLY", "kstamp_cly")):
        f = form.get(key)
        if f and f.filename:
            kstamp_texts[site] = read_upload_text(f)
    if not kstamp_texts:
        raise ValueError("Au moins un fichier KSTAMP est requis (MRS1, MRS2 ou CLY).")
    return run_analysis(kstamp_texts=kstamp_texts, lir_url=lir_url, lir_key=lir_key,
                        control_date=control_date)


def compute_taux(result: dict) -> float:
    resume = result.get("resume", {})
    total  = sum(v.get("total",  0) for k, v in resume.items()
                 if k.startswith("KSTAMP") and k != "total_ecarts")
    ecarts = sum(v.get("ecarts", 0) for k, v in resume.items()
                 if k.startswith("KSTAMP") and k != "total_ecarts")
    if total == 0:
        return 100.0
    return round((total - ecarts) / total * 100, 1)


def build_commentaire(result: dict) -> str:
    resume  = result.get("resume", {})
    nb      = resume.get("total_ecarts", 0)
    date_s  = result.get("control_date", "")
    sites   = [k for k in resume if k.startswith("KSTAMP") and k != "total_ecarts"
               and resume[k].get("ecarts", 0) > 0]
    if nb == 0:
        return f"Revue droits KSTAMP du {date_s} : aucun écart détecté. Tous les accès sont conformes."
    return (f"Revue droits KSTAMP du {date_s} : {nb} écart(s) détecté(s) sur "
            f"{', '.join(sites)}. Voir rapport Excel pour le détail.")
