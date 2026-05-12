"""
Debug de connexion EasyVista — à lancer depuis la racine du projet.
Usage : python debug_easyvista.py
"""
import sys
import json
import base64
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ────────────────────────────────────────────────────────────────────
# Lus depuis la base de données de l'application
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.utils import get_config

db = SessionLocal()
URL     = get_config(db, "ev_url", "").rstrip("/")
ACCOUNT = get_config(db, "ev_account", "")
LOGIN   = get_config(db, "ev_login", "")
TOKEN   = get_config(db, "ev_token", "")
db.close()

# ── Helpers ───────────────────────────────────────────────────────────────────
SEP = "─" * 60

def print_response(label, resp):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(SEP)
    print(f"  Status  : {resp.status_code} {resp.reason}")
    print(f"  URL     : {resp.url}")
    print("  Headers envoyés :")
    for k, v in resp.request.headers.items():
        # masquer partiellement le token
        if k.lower() == "authorization":
            parts = v.split(" ", 1)
            if len(parts) == 2:
                masked = parts[1][:8] + "…" + parts[1][-4:] if len(parts[1]) > 12 else "***"
                v = f"{parts[0]} {masked}"
        print(f"    {k}: {v}")
    print("  Réponse :")
    try:
        print(json.dumps(resp.json(), indent=4, ensure_ascii=False))
    except Exception:
        print(f"  (non-JSON) {resp.text[:500]}")

# ── Vérification config ───────────────────────────────────────────────────────
print(SEP)
print("  Config lue depuis la base")
print(SEP)
print(f"  URL     : {URL or '(vide)'}")
print(f"  Account : {ACCOUNT or '(vide)'}")
print(f"  Login   : {LOGIN or '(vide)'}")
print(f"  Token   : {TOKEN[:8] + '…' + TOKEN[-4:] if len(TOKEN) > 12 else '(vide)' }")

if not all([URL, ACCOUNT, LOGIN, TOKEN]):
    print("\n  ⚠ Config incomplète — renseignez les paramètres EasyVista dans l'application.")
    sys.exit(1)

target = f"{URL}/api/v1/{ACCOUNT}/requests"
print(f"\n  Endpoint : {target}")

# ── Test 1 : Bearer token ─────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("  TEST 1 — Bearer token (Authorization: Bearer <token>)")
try:
    r = requests.get(
        target,
        params={"max_rows": 1},
        headers={"Accept": "application/json", "Authorization": f"Bearer {TOKEN}"},
        timeout=10,
        verify=False,
    )
    print_response("Bearer token → GET /requests", r)
except Exception as e:
    print(f"\n  ERREUR réseau : {e}")

# ── Test 2 : Basic Auth ───────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("  TEST 2 — Basic Auth (login:token)")
try:
    r = requests.get(
        target,
        params={"max_rows": 1},
        headers={"Accept": "application/json"},
        auth=(LOGIN, TOKEN),
        timeout=10,
        verify=False,
    )
    print_response("Basic Auth → GET /requests", r)
except Exception as e:
    print(f"\n  ERREUR réseau : {e}")

# ── Test 3 : création ticket factice ─────────────────────────────────────────
print(f"\n{'='*60}")
print("  TEST 3 — POST /requests (création ticket de test — annulable)")
print("  Voulez-vous tester la création d'un ticket ? (o/n) ", end="")
answer = input().strip().lower()
if answer == "o":
    catalog = input("  Code catalogue (ex. DSO_CTRL_CNFRMT_ERR_REF) : ").strip()
    payload = {
        "requests": [{
            "Catalog_Code": catalog,
            "Title": "TEST PDC – debug connexion",
            "Description": "Ticket de test créé par debug_easyvista.py — peut être supprimé.",
            "External_reference": "PDC-DEBUG",
        }]
    }
    print(f"\n  Payload envoyé :\n{json.dumps(payload, indent=4, ensure_ascii=False)}")
    print("  (timeout 30s — le serveur EasyVista peut être lent sur POST)")
    post_ok = False
    try:
        rpost = requests.post(
            target,
            json=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
            timeout=30,
            verify=False,
        )
        print_response("Bearer token → POST /requests", rpost)
        post_ok = rpost.status_code == 201
    except Exception as e:
        print(f"\n  ERREUR réseau : {e}")
    if not post_ok:
        print(f"\n  Bearer POST n'a pas abouti, essai Basic Auth…")
        try:
            rpost2 = requests.post(
                target,
                json=payload,
                headers={"Content-Type": "application/json"},
                auth=(LOGIN, TOKEN),
                timeout=30,
                verify=False,
            )
            print_response("Basic Auth → POST /requests", rpost2)
        except Exception as e:
            print(f"\n  ERREUR réseau : {e}")
else:
    print("  Test POST ignoré.")

print(f"\n{'='*60}\n")
