"""
Plugin : Revue des Droits Opérateurs – SACRE (DSO-LOG-03-01)
"""

from app.revue_droits_engine import run_analysis, read_upload_text

SLUG            = "revue_droits_sacre"
FORM_TEMPLATE   = "plugins/revue_droits_sacre/form.html"
RESULT_TEMPLATE = "plugins/revue_droits_operateurs/resultats.html"


async def execute(form, config: dict, lir_url: str, lir_key: str, control_date: str) -> dict:
    sacre_file = form.get("sacre_file")
    if not sacre_file or not sacre_file.filename:
        raise ValueError("Le fichier SACRE est requis.")
    sacre_text = read_upload_text(sacre_file)
    return run_analysis(sacre_text=sacre_text, lir_url=lir_url, lir_key=lir_key,
                        control_date=control_date)


def compute_taux(result: dict) -> float:
    sacre = result.get("resume", {}).get("SACRE", {})
    total  = sacre.get("total", 0)
    ecarts = sacre.get("ecarts", 0)
    if total == 0:
        return 100.0
    return round((total - ecarts) / total * 100, 1)


def build_commentaire(result: dict) -> str:
    sacre  = result.get("resume", {}).get("SACRE", {})
    nb     = sacre.get("ecarts", 0)
    date_s = result.get("control_date", "")
    if nb == 0:
        return f"Revue droits SACRE du {date_s} : aucun écart détecté. Tous les accès sont conformes."
    return f"Revue droits SACRE du {date_s} : {nb} écart(s) détecté(s). Voir rapport Excel pour le détail."
