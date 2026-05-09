# Plan de Contrôle Cyber

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-local-003B57?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/licence-MIT-green)

Application de gestion du plan de contrôle cybersécurité — suivi des contrôles, saisie des résultats, gestion des incidents, tableau de bord de conformité.

Déploiement local Windows ou Docker, aucune dépendance cloud.

---

## Aperçu

| Tableau de bord — Vue annuelle | Vue mensuelle |
|:---:|:---:|
| ![Dashboard](static/screenshots/dashboard.png) | ![Vue mensuelle](static/screenshots/dashboard_mensuel.png) |

| Cockpit Indicateurs | Liste des contrôles |
|:---:|:---:|
| ![Indicateurs](static/screenshots/dashboard_indicateurs.png) | ![Contrôles](static/screenshots/controls_list.png) |

| Campagne mensuelle | Administration |
|:---:|:---:|
| ![Campagne](static/screenshots/campagne.png) | ![Admin](static/screenshots/admin.png) |

---

## Fonctionnalités

- **Référentiel de contrôles** — création et gestion des contrôles avec référence, libellé, indicateur, objectif, fréquence, taux cible et lien vers le guide/procédure
- **Campagne mensuelle** — vue des contrôles à réaliser pour le mois en cours, avec assignation des auditeurs par le responsable
- **Planification annuelle** — création en masse de toutes les périodes d'un contrôle pour l'année, avec assignation par période
- **Saisie des résultats** — formulaire de saisie du taux de conformité par période, statut automatique (conforme / non conforme / NA)
- **Workflow incident** — ouverture d'un incident depuis un résultat non conforme (avec ou sans ticket JIRA), suivi de l'état (en cours / résolu / clôturé)
- **Clôtures en attente** — file de validation des résultats soumis par les auditeurs
- **Tableau de bord** — trois onglets : *Vue annuelle* (KPIs, graphiques, top 10 contrôles les moins performants), *Vue mensuelle* (heatmap thématique × mois, top 10 du mois courant), *Indicateurs* (cockpit exécutif cyber avec cartes groupées par domaine, tendance et mini-graphiques)
- **Journal d'activité** — toutes les actions tracées avec lien direct vers la ressource
- **Gestion des référentiels** — thématiques, catégories (entités) et périmètres configurables depuis l'administration
- **Authentification LDAP / SSO** — connexion via Active Directory avec création automatique des comptes, filtrage par OU et groupe AD, fallback local
- **Intégration JIRA** — création automatique de tickets sur non-conformance (API JIRA Cloud v3)
- **Historique** — historique détaillé des modifications sur chaque contrôle et chaque résultat
- **Archivage** — les contrôles archivés sont masqués mais conservent leur historique
- **Thème couleurs** — personnalisation de la couleur principale depuis les paramètres
- **Logo société** — personnalisation depuis les paramètres
- **Export Excel** — export du tableau de bord (résumé, conformité par thématique, tendance mensuelle, liste des contrôles)
- **Guide intégré** — accessible sur `/guide`

## Rôles

| Action | Auditeur | Responsable |
|---|:---:|:---:|
| Consulter les contrôles et résultats | ✓ | ✓ |
| Saisir un résultat | ✓ | ✓ |
| Modifier un contrôle | ✓ | ✓ |
| Créer un contrôle | — | ✓ |
| Planifier l'année / assigner auditeurs | — | ✓ |
| Clôturer / rouvrir un résultat | — | ✓ |
| Ouvrir / résoudre un incident | — | ✓ |
| Journal d'activité | ✓ | ✓ |
| Tableau de bord | ✓ | ✓ |
| Gestion des utilisateurs | — | ✓ |
| Paramètres (logo, thème, JIRA) | — | ✓ |
| Administration (thématiques, catégories, périmètres) | — | ✓ |
| Archiver un contrôle | — | ✓ |

## Stack technique

- **Backend** : Python 3.10+ · FastAPI · SQLAlchemy 2 · SQLite
- **Frontend** : Jinja2 · Tailwind CSS (CDN JIT) · Alpine.js v3 · Chart.js 4
- **Auth** : sessions Starlette · bcrypt · ldap3 (LDAP/AD, optionnel)
- **Export** : openpyxl (Excel)
- **Incidents** : requests (JIRA REST API v3, optionnel)

## Installation

### Mode classique (Windows / Linux)

**Prérequis** : Python 3.10 ou supérieur, avec `pip` dans le PATH.

```bash
pip install -r requirements.txt
python run.py
```

Ouvrir [http://127.0.0.1:8002](http://127.0.0.1:8002)

Le port peut être modifié via la variable d'environnement `PDC_PORT`.

### Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `PDC_HOST` | `0.0.0.0` | Interface d'écoute |
| `PDC_PORT` | `8002` | Port |
| `PDC_RELOAD` | `false` | Rechargement automatique (développement) |

### Données de démarrage

Au premier lancement, l'application crée automatiquement :
- Les comptes par défaut
- Les catégories **Entité 1** et **Entité 2**
- Les périmètres **SMSI** et **Tous**

Pour charger des contrôles de démonstration :

```bash
python seed_controls.py
```

Pour importer un plan de contrôle réel depuis un fichier Excel :

```bash
# 1. Copier le template et l'adapter
cp seed_from_excel.example.py seed_from_excel.py

# 2. Éditer seed_from_excel.py : renseigner EXCEL_PATH, YEAR et TYPE_COLORS

# 3. Lancer l'import
python seed_from_excel.py [chemin_vers_le_fichier.xlsx]
```

Le script lit les colonnes Thématique, Catégorie, Référence, Fréquence, Indicateur, Objectif, Seuils, Périmètre et les 12 colonnes mensuelles (Jan → Déc). Il crée ou met à jour les contrôles par référence (upsert) et importe les résultats en ignorant les cases vides, N/A et les valeurs brutes supérieures à 100.

> `seed_from_excel.py` est dans `.gitignore` — votre fichier de production avec les chemins et données réels ne sera jamais commité.

## Comptes par défaut

À changer après la première connexion (Paramètres → Utilisateurs).

| Compte | Mot de passe | Rôle |
|---|---|---|
| `admin` | `erwanbogosse2026` | responsable |
| `auditeur` | `audit123` | auditeur |

## Structure

```
plandecontrole/
├── run.py                        # point d'entrée + migrations idempotentes
├── requirements.txt
├── seed_controls.py              # données de démonstration (15 contrôles)
├── seed_from_excel.example.py    # template d'import Excel (à copier en seed_from_excel.py)
├── app/
│   ├── main.py                   # application FastAPI, montage des routeurs
│   ├── models.py                 # ORM : Control, ControlResult, User, History…
│   ├── auth.py                   # bcrypt, création données par défaut
│   ├── database.py               # engine SQLite, SessionLocal
│   ├── utils.py                  # helpers : périodes, alertes, pagination
│   ├── templates_config.py       # Jinja2 + fonctions globales (get_theme…)
│   ├── theme_cache.py            # cache thème couleurs
│   └── routers/
│       ├── controls.py           # CRUD contrôles, archivage, historique
│       ├── results.py            # saisie résultats, incidents, validations
│       ├── dashboard.py          # stats, export Excel
│       ├── campagne.py           # campagne mensuelle, planification annuelle
│       ├── admin.py              # thématiques, catégories, périmètres
│       ├── users.py              # gestion comptes
│       ├── activity.py           # journal d'activité
│       └── settings.py           # logo, thème, JIRA
├── app/templates/
│   ├── base.html                 # layout, navbar, flash messages
│   ├── dashboard.html
│   ├── guide.html
│   ├── login.html
│   ├── controls/
│   │   ├── list.html             # liste avec filtres
│   │   ├── detail.html           # fiche contrôle + tableau résultats
│   │   ├── form.html             # création / modification
│   │   ├── plan_year.html        # planification annuelle
│   │   └── history.html
│   ├── results/
│   │   ├── form.html             # saisie résultat
│   │   └── pending.html          # clôtures en attente
│   ├── campagne/index.html
│   ├── admin/index.html
│   ├── users/
│   ├── activity/list.html
│   └── settings/index.html
└── data/                         # plandecontrole.db (généré au démarrage)
```

## Fréquences supportées

| Fréquence | Périodes par an | Exemples de labels |
|---|:---:|---|
| Mensuel | 12 | Jan 2026, Fév 2026… |
| Bimestriel | 6 | Bim1 2026, Bim2 2026… |
| Trimestriel | 4 | T1 2026, T2 2026… |
| Semestriel | 2 | S1 2026, S2 2026 |
| Annuel | 1 | 2026 |

## Workflow incident

```
non_conforme
    ├─→ [Ouvrir incident] → incident_en_cours
    │       └─→ [Incident résolu] → clôturé (validated = true)
    └─→ [Clôturer quand même] → clôturé (validated = true)
```

Un incident peut être lié à :
- Un **numéro d'incident** saisi manuellement (éditable après ouverture)
- Un **ticket JIRA** créé automatiquement via l'API (si JIRA configuré dans les paramètres)

## Intégration JIRA

Depuis **Paramètres → JIRA**, configurer :
- URL de l'instance JIRA (`https://xxx.atlassian.net`)
- E-mail utilisateur et token API
- Clé du projet JIRA

Lors de l'ouverture d'un incident, cocher "Pousser un ticket JIRA" pour créer automatiquement un ticket avec le détail du contrôle non conforme.

## Authentification LDAP / SSO

Depuis **Paramètres → LDAP / SSO**, configurer :

| Champ | Description |
|---|---|
| Serveur LDAP | Adresse du contrôleur de domaine (ex. `ad.entreprise.local`) |
| Port | 389 (LDAP) ou 636 (LDAPS) |
| Domaine | Domaine Windows (ex. `entreprise.local`) |
| Base DN | Optionnel — déduit du domaine si vide |
| Restreindre à l'OU | Optionnel — filtre par unité organisationnelle |
| Groupe requis | Optionnel — filtre par appartenance à un groupe AD |
| Rôle par défaut | Rôle attribué à la création automatique du compte (`auditeur` ou `responsable`) |
| TLS / SSL | Activer pour LDAPS (port 636) |

**Fonctionnement** : l'authentification LDAP est tentée en premier ; le compte local sert de fallback. Lors de la première connexion LDAP, un compte est créé automatiquement. Le bouton **Tester la connexion** vérifie l'accessibilité du serveur.

> Le compte `admin` local reste toujours fonctionnel même si LDAP est activé.

## Licence

Distribué sous licence [MIT](LICENSE) — libre d'utilisation, de modification et de redistribution.
