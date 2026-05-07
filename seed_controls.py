"""
Données de démonstration — 15 contrôles fictifs.
Exécuter : python seed_controls.py
"""
import os
os.makedirs("data", exist_ok=True)

from app.database import engine, Base, SessionLocal
from app.models import *  # noqa
Base.metadata.create_all(bind=engine)

from app.auth import create_default_data
create_default_data()

db = SessionLocal()


def get_or_none(model, label):
    return db.query(model).filter(model.label == label).first()


def get_user(username):
    return db.query(User).filter(User.username == username).first()


t_acces   = get_or_none(ControlType, "Gestion des accès")
t_surv    = get_or_none(ControlType, "Surveillance et détection")
t_cont    = get_or_none(ControlType, "Continuité et sauvegarde")
t_vuln    = get_or_none(ControlType, "Gestion des vulnérabilités")
t_conf    = get_or_none(ControlType, "Conformité et audit")

cat_a = get_or_none(Category, "Entité A")
cat_b = get_or_none(Category, "Entité B")

peri_si  = get_or_none(Perimetre, "Périmètre SI")
peri_all = get_or_none(Perimetre, "Global")

admin = get_user("admin")

CONTROLS = [
    # ── Gestion des accès ────────────────────────────────────────────────────
    {
        "reference": "ACC-001",
        "libelle": "Revue trimestrielle des droits d'accès",
        "indicateur": "Comptes revus et validés / total comptes actifs",
        "objectif": "S'assurer que tous les droits d'accès sont à jour et justifiés",
        "frequence": "trimestriel",
        "type": t_acces, "category": cat_a, "perimetre": peri_si,
        "taux_cible": 95.0,
    },
    {
        "reference": "ACC-002",
        "libelle": "Contrôle des comptes à privilèges",
        "indicateur": "Comptes admin justifiés / total comptes admin actifs",
        "objectif": "Recenser et valider tous les comptes administrateurs",
        "frequence": "mensuel",
        "type": t_acces, "category": cat_a, "perimetre": peri_si,
        "taux_cible": 100.0,
    },
    {
        "reference": "ACC-003",
        "libelle": "Revue des accès aux applications critiques",
        "indicateur": "Accès applicatifs validés / total accès applicatifs",
        "objectif": "Vérifier que l'accès aux applications sensibles est justifié",
        "frequence": "semestriel",
        "type": t_acces, "category": cat_b, "perimetre": peri_all,
        "taux_cible": 90.0,
    },
    # ── Surveillance et détection ────────────────────────────────────────────
    {
        "reference": "DET-001",
        "libelle": "Vérification des alertes SIEM",
        "indicateur": "Alertes traitées dans le délai / alertes reçues",
        "objectif": "Assurer le traitement de toutes les alertes dans les délais définis",
        "frequence": "mensuel",
        "type": t_surv, "category": cat_a, "perimetre": peri_si,
        "taux_cible": 95.0,
    },
    {
        "reference": "DET-002",
        "libelle": "Test de détection d'intrusion",
        "indicateur": "Tentatives détectées / tentatives simulées",
        "objectif": "Valider la capacité de détection des outils IDS/IPS",
        "frequence": "trimestriel",
        "type": t_surv, "category": cat_a, "perimetre": peri_si,
        "taux_cible": 80.0,
    },
    {
        "reference": "DET-003",
        "libelle": "Analyse des logs d'authentification",
        "indicateur": "Anomalies traitées / anomalies détectées",
        "objectif": "Détecter et traiter toute tentative d'authentification anormale",
        "frequence": "mensuel",
        "type": t_surv, "category": cat_b, "perimetre": peri_all,
        "taux_cible": 90.0,
    },
    # ── Continuité et sauvegarde ─────────────────────────────────────────────
    {
        "reference": "SAU-001",
        "libelle": "Contrôle des sauvegardes",
        "indicateur": "Sauvegardes réussies / sauvegardes planifiées",
        "objectif": "Garantir l'exécution complète des sauvegardes planifiées",
        "frequence": "mensuel",
        "type": t_cont, "category": cat_a, "perimetre": peri_si,
        "taux_cible": 100.0,
    },
    {
        "reference": "SAU-002",
        "libelle": "Test de restauration des données",
        "indicateur": "Restaurations réussies / restaurations testées",
        "objectif": "Valider la capacité de restauration des sauvegardes",
        "frequence": "trimestriel",
        "type": t_cont, "category": cat_b, "perimetre": peri_all,
        "taux_cible": 90.0,
    },
    {
        "reference": "SAU-003",
        "libelle": "Vérification du plan de continuité d'activité",
        "indicateur": "Points de contrôle PCA validés / points de contrôle totaux",
        "objectif": "S'assurer de la mise à jour et de l'opérabilité du PCA",
        "frequence": "semestriel",
        "type": t_cont, "category": cat_a, "perimetre": peri_all,
        "taux_cible": 90.0,
    },
    # ── Gestion des vulnérabilités ───────────────────────────────────────────
    {
        "reference": "VUL-001",
        "libelle": "Scan de vulnérabilités des systèmes exposés",
        "indicateur": "Vulnérabilités critiques corrigées / vulnérabilités critiques détectées",
        "objectif": "Maintenir un niveau de risque acceptable sur les systèmes exposés",
        "frequence": "mensuel",
        "type": t_vuln, "category": cat_a, "perimetre": peri_si,
        "taux_cible": 85.0,
    },
    {
        "reference": "VUL-002",
        "libelle": "Application des correctifs de sécurité critiques",
        "indicateur": "Correctifs critiques appliqués sous 30 j / correctifs critiques publiés",
        "objectif": "Appliquer les correctifs critiques dans un délai de 30 jours",
        "frequence": "mensuel",
        "type": t_vuln, "category": cat_b, "perimetre": peri_all,
        "taux_cible": 95.0,
    },
    {
        "reference": "VUL-003",
        "libelle": "Revue de configuration des serveurs",
        "indicateur": "Serveurs conformes baseline / total serveurs audités",
        "objectif": "Vérifier la conformité des configurations aux politiques internes",
        "frequence": "trimestriel",
        "type": t_vuln, "category": cat_a, "perimetre": peri_si,
        "taux_cible": 85.0,
    },
    # ── Conformité et audit ──────────────────────────────────────────────────
    {
        "reference": "CON-001",
        "libelle": "Audit de conformité réglementaire",
        "indicateur": "Exigences réglementaires respectées / exigences applicables",
        "objectif": "S'assurer du respect des obligations réglementaires en vigueur",
        "frequence": "semestriel",
        "type": t_conf, "category": cat_a, "perimetre": peri_all,
        "taux_cible": 90.0,
    },
    {
        "reference": "CON-002",
        "libelle": "Contrôle de la politique de mots de passe",
        "indicateur": "Comptes respectant la politique / total comptes actifs",
        "objectif": "Garantir l'application de la politique de mots de passe",
        "frequence": "trimestriel",
        "type": t_conf, "category": cat_b, "perimetre": peri_si,
        "taux_cible": 100.0,
    },
    {
        "reference": "CON-003",
        "libelle": "Sensibilisation et formation des utilisateurs",
        "indicateur": "Utilisateurs formés / total utilisateurs",
        "objectif": "Former l'ensemble des collaborateurs aux bonnes pratiques cyber",
        "frequence": "annuel",
        "type": t_conf, "category": cat_b, "perimetre": peri_all,
        "taux_cible": 90.0,
    },
]

created = 0
skipped = 0
for data in CONTROLS:
    if db.query(Control).filter(Control.reference == data["reference"]).first():
        skipped += 1
        continue
    c = Control(
        reference=data["reference"],
        libelle=data["libelle"],
        indicateur=data.get("indicateur", ""),
        objectif=data.get("objectif", ""),
        frequence=data["frequence"],
        type_id=data["type"].id if data["type"] else None,
        category_id=data["category"].id if data["category"] else None,
        perimetre_id=data["perimetre"].id if data["perimetre"] else None,
        taux_cible=data.get("taux_cible", 100.0),
        responsable_id=admin.id if admin else None,
        created_by_id=admin.id if admin else None,
        updated_by_id=admin.id if admin else None,
    )
    db.add(c)
    created += 1

db.commit()
db.close()
print(f"Done : {created} contrôles créés, {skipped} déjà existants.")
