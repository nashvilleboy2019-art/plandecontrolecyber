"""
Import du Plan de Contrôle depuis un fichier Excel vers la base de données.

Usage : python seed_from_excel.py [chemin_excel]

Format attendu du fichier Excel (données à partir de la ligne 3) :
  Col 0  : Thématique       — doit correspondre à une entrée de TYPE_COLORS
  Col 1  : Catégorie        — ex. « Entité A », « Entité B »
  Col 3  : Référence        — identifiant unique du contrôle (ex. ACC-001)
  Col 4  : Fréquence        — mensuel / bimestriel / trimestriel / semestriel / annuel
  Col 5  : Indicateur       — libellé du contrôle
  Col 6  : Objectif         — description de la vérification
  Col 7  : Seuils           — taux cible (ex. 95%, 0.95 ou 95)
  Col 8  : Périmètre        — ex. « SMSI », « Global »
  Col 9-20 : Jan → Déc      — résultats mensuels (ratio 0–1, %, ou vide/N/A)

Ligne 1 : titre (ignorée)
Ligne 2 : en-têtes (ignorée)

Renommez ce fichier en seed_from_excel.py et adaptez les constantes ci-dessous.
"""
import sys
import re
import datetime
import datetime as dt
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import Control, ControlResult, ControlType, Category, Perimetre, User
from app.utils import periode_label

# ── À ADAPTER ──────────────────────────────────────────────────────────────
EXCEL_PATH = r"C:\chemin\vers\votre\plan_de_controle.xlsx"
YEAR = 2026

# Thématiques avec leur couleur Tailwind — doit correspondre aux données Excel
TYPE_COLORS = {
    "Alertes":                      "red",
    "Accès logique":                "blue",
    "Accès physique":               "orange",
    "Accès réseaux":                "indigo",
    "Attestation sur l'honneur":    "purple",
    "Audit de configuration":       "teal",
    "Comptes utilisateurs et services": "cyan",
    "Indicateurs":                  "gray",
    "Secrets et données":           "yellow",
}
# ───────────────────────────────────────────────────────────────────────────

FREQ_MAP = {
    "mensuel": "mensuel", "mensuelle": "mensuel",
    "bimestriel": "bimestriel", "bimestrielle": "bimestriel",
    "trimestriel": "trimestriel", "trimestrielle": "trimestriel",
    "semestriel": "semestriel", "semestrielle": "semestriel",
    "annuel": "annuel", "annuelle": "annuel",
}


def parse_taux_cible(seuil) -> float:
    if seuil is None:
        return 100.0
    if isinstance(seuil, (int, float)):
        return 100.0 if seuil <= 1 else float(seuil)
    s = str(seuil)
    m = re.search(r"(\d+)\s*%", s)
    if m:
        return float(m.group(1))
    return 100.0


def cal_month_to_period(freq: str, cal_month: int) -> int:
    """Mois calendaire (1-12) → index de période selon la fréquence."""
    if freq == "mensuel":
        return cal_month
    if freq == "bimestriel":
        return (cal_month + 1) // 2
    if freq == "trimestriel":
        return (cal_month - 1) // 3 + 1
    if freq == "semestriel":
        return 1 if cal_month <= 6 else 2
    return 1  # annuel


def parse_result(val, taux_cible: float):
    """
    Retourne (taux_conformite, statut, skip).
    skip=True  → ne pas créer de résultat (N/A, vide, valeur non normalisable).
    """
    if val is None:
        return None, None, True
    if isinstance(val, (dt.time, dt.datetime)):
        return None, None, True
    if isinstance(val, str):
        return None, None, True

    f = float(val)
    if 0.0 <= f <= 1.0:
        taux = round(f * 100, 1)
        statut = "conforme" if taux >= taux_cible else "non_conforme"
        return taux, statut, False
    if f > 100:
        return None, None, True
    taux = round(f, 1)
    statut = "conforme" if taux >= taux_cible else "non_conforme"
    return taux, statut, False


def run(excel_path: str = EXCEL_PATH):
    import openpyxl
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
    data = [r for r in all_rows[2:] if any(c is not None for c in r)]

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        admin_id = admin.id if admin else None

        # 1. Thématiques
        type_map = {}
        for i, (label, color) in enumerate(TYPE_COLORS.items()):
            t = db.query(ControlType).filter(ControlType.label == label).first()
            if not t:
                t = ControlType(label=label, color=color, ordre=i, active=True)
                db.add(t)
                db.flush()
                print(f"  [+] Thématique : {label}")
            type_map[label] = t.id

        # 2. Catégories (créées à la volée depuis les données)
        cat_map = {}
        cat_labels = sorted({str(r[1]).strip() for r in data if r[1]})
        for i, label in enumerate(cat_labels):
            c = db.query(Category).filter(Category.label == label).first()
            if not c:
                c = Category(label=label, ordre=i, active=True)
                db.add(c)
                db.flush()
                print(f"  [+] Catégorie : {label}")
            cat_map[label] = c.id

        # 3. Périmètres (créés à la volée depuis les données)
        perim_map = {}
        perim_labels = sorted({str(r[8]).strip() for r in data if r[8]})
        for i, label in enumerate(perim_labels):
            p = db.query(Perimetre).filter(Perimetre.label == label).first()
            if not p:
                p = Perimetre(label=label, ordre=i, active=True)
                db.add(p)
                db.flush()
                print(f"  [+] Périmètre : {label}")
            perim_map[label] = p.id

        db.commit()

        # 4. Contrôles et résultats
        ctrl_created = ctrl_updated = 0
        res_created = res_skipped = 0

        for row in data:
            theme_label = (str(row[0]).strip() if row[0] else "")
            cat_label   = (str(row[1]).strip() if row[1] else "")
            ref         = (str(row[3]).strip() if row[3] else "")
            freq_raw    = (str(row[4]).strip() if row[4] else "")
            indicateur  = (str(row[5]).strip() if row[5] else None)
            objectif    = (str(row[6]).strip() if row[6] else None)
            seuil       = row[7]
            perim_label = (str(row[8]).strip() if row[8] else "")
            monthly     = row[9:21]  # Jan → Déc

            if not ref or ref == "None":
                continue

            freq = FREQ_MAP.get(freq_raw.lower(), "mensuel")
            taux_cible = parse_taux_cible(seuil)
            libelle = indicateur[:400] if indicateur else ref

            ctrl = db.query(Control).filter(Control.reference == ref).first()
            if not ctrl:
                ctrl = Control(
                    reference=ref, libelle=libelle, indicateur=indicateur,
                    objectif=objectif, frequence=freq, taux_cible=taux_cible,
                    type_id=type_map.get(theme_label),
                    category_id=cat_map.get(cat_label),
                    perimetre_id=perim_map.get(perim_label),
                    responsable_id=admin_id, created_by_id=admin_id,
                )
                db.add(ctrl)
                db.flush()
                ctrl_created += 1
            else:
                ctrl.libelle = libelle
                ctrl.indicateur = indicateur
                ctrl.objectif = objectif
                ctrl.frequence = freq
                ctrl.taux_cible = taux_cible
                ctrl.type_id = type_map.get(theme_label)
                ctrl.category_id = cat_map.get(cat_label)
                ctrl.perimetre_id = perim_map.get(perim_label)
                db.flush()
                ctrl_updated += 1

            periods_done: set[int] = set()
            for cal_month, val in enumerate(monthly, start=1):
                taux, statut, skip = parse_result(val, taux_cible)
                if skip:
                    continue
                period_idx = cal_month_to_period(freq, cal_month)
                if period_idx in periods_done:
                    res_skipped += 1
                    continue
                periods_done.add(period_idx)
                existing = db.query(ControlResult).filter(
                    ControlResult.control_id == ctrl.id,
                    ControlResult.annee == YEAR,
                    ControlResult.mois == period_idx,
                ).first()
                if existing:
                    res_skipped += 1
                    continue
                plabel = periode_label(freq, YEAR, period_idx)
                res = ControlResult(
                    control_id=ctrl.id, annee=YEAR, mois=period_idx,
                    periode_label=plabel, taux_conformite=taux, statut=statut,
                    validated=True, validated_by_id=admin_id,
                    validated_at=datetime.datetime.utcnow(), created_by_id=admin_id,
                )
                db.add(res)
                res_created += 1

        db.commit()

        print(f"\n{'─' * 40}")
        print(f"Contrôles créés   : {ctrl_created}")
        print(f"Contrôles mis à j.: {ctrl_updated}")
        print(f"Résultats créés   : {res_created}")
        print(f"Résultats ignorés : {res_skipped}")
        print(f"{'─' * 40}")
        print("Import terminé.")

    except Exception as e:
        db.rollback()
        print(f"\n[ERREUR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else EXCEL_PATH
    print(f"Import depuis : {path}\n")
    run(path)
