"""
Plugin : Revue des Droits Opérateurs – PKI (DSO-LOG-03-02)
"""

from app.revue_droits_engine import run_analysis, read_upload_text

SLUG            = "revue_droits_pki"
FORM_TEMPLATE   = "plugins/revue_droits_pki/form.html"
RESULT_TEMPLATE = "plugins/revue_droits_operateurs/resultats.html"


async def execute(form, config: dict, lir_url: str, lir_key: str, control_date: str) -> dict:
    pki_file = form.get("pki_file")
    if not pki_file or not pki_file.filename:
        raise ValueError("Le fichier PKI est requis.")
    pki_text = read_upload_text(pki_file)
    return run_analysis(pki_text=pki_text, lir_url=lir_url, lir_key=lir_key,
                        control_date=control_date)


def compute_taux(result: dict) -> float:
    pki    = result.get("resume", {}).get("PKI", {})
    total  = pki.get("total", 0)
    ecarts = pki.get("ecarts", 0)
    if total == 0:
        return 100.0
    return round((total - ecarts) / total * 100, 1)


def build_commentaire(result: dict) -> str:
    pki    = result.get("resume", {}).get("PKI", {})
    nb     = pki.get("ecarts", 0)
    date_s = result.get("control_date", "")
    if nb == 0:
        return f"Revue droits PKI du {date_s} : aucun écart détecté. Tous les accès sont conformes."
    return f"Revue droits PKI du {date_s} : {nb} écart(s) détecté(s). Voir rapport Excel pour le détail."
