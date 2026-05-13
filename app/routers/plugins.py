"""
Router du système de plugins d'automatisation.

Routes admin    : /admin/plugins
Routes exécution: /plugin/controls/{control_id}/...
Routes résultats: /plugin/run/{run_id}/...
"""

import importlib
import json
import os
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Control, ControlPlugin, ControlResult, PluginRun, ResultHistory, AppConfig
from app.utils import get_current_user, get_config, log_activity, periode_label
from app.templates_config import templates
from app.plugins import get_plugin, all_plugins

router = APIRouter(tags=["plugins"])

PLUGIN_DIR = os.path.join("static", "uploads", "plugin_runs")
os.makedirs(PLUGIN_DIR, exist_ok=True)

def _lir_cfg(db: Session) -> tuple[str, str]:
    url = get_config(db, "baselir_url", "http://localhost:8001")
    key = get_config(db, "baselir_api_key", "")
    return url, key


def _load_module(slug: str):
    meta = get_plugin(slug)
    if not meta:
        return None
    return importlib.import_module(meta["module"])


# ── Admin : gestion des associations plugin ↔ contrôle ────────────────────────

@router.get("/admin/plugins")
async def admin_plugins(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)

    associations = db.query(ControlPlugin).all()
    associated_control_ids = {a.control_id for a in associations}
    controls = (db.query(Control)
                .filter(Control.archived == False)
                .order_by(Control.reference)
                .all())

    lir_url, lir_key = _lir_cfg(db)

    return templates.TemplateResponse(request, "admin/plugins.html", {
        "user":         user,
        "plugins":      all_plugins(),
        "associations": associations,
        "controls":     controls,
        "associated_control_ids": associated_control_ids,
        "lir_url":      lir_url,
        "lir_key":      lir_key,
        "flash":        request.session.pop("flash", None),
        "error":        request.session.pop("plugin_error", None),
    })


@router.post("/admin/plugins/associate")
async def admin_plugins_associate(
    request: Request, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    plugin_slug = form.get("plugin_slug", "").strip()
    control_id  = int(form.get("control_id", 0))

    if not get_plugin(plugin_slug):
        request.session["plugin_error"] = "Plugin inconnu."
        return RedirectResponse("/admin/plugins", status_code=302)

    control = db.query(Control).filter(Control.id == control_id).first()
    if not control:
        request.session["plugin_error"] = "Contrôle introuvable."
        return RedirectResponse("/admin/plugins", status_code=302)

    # Retirer l'association existante du contrôle cible (s'il y en a une)
    existing = db.query(ControlPlugin).filter(ControlPlugin.control_id == control_id).first()
    if existing:
        existing.plugin_slug = plugin_slug
        existing.active = True
    else:
        db.add(ControlPlugin(control_id=control_id, plugin_slug=plugin_slug, active=True))

    db.commit()
    log_activity(db, user.id, user.username, "Plugin associé", "control", control_id,
                 f"{plugin_slug} → {control.reference}")
    request.session["flash"] = f"Plugin « {get_plugin(plugin_slug)['name']} » associé à {control.reference}."
    return RedirectResponse("/admin/plugins", status_code=302)


@router.get("/admin/plugins/baselir-config")
async def baselir_config_get(request: Request):
    return RedirectResponse("/admin/plugins", status_code=302)


@router.post("/admin/plugins/baselir-config")
async def save_baselir_config(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    for key, value in (("baselir_url", form.get("baselir_url", "").strip()),
                       ("baselir_api_key", form.get("baselir_api_key", "").strip())):
        cfg = db.query(AppConfig).filter(AppConfig.key == key).first()
        if cfg:
            cfg.value = value
        else:
            db.add(AppConfig(key=key, value=value))
    db.commit()
    request.session["flash"] = "Configuration BaseLIR sauvegardée."
    return RedirectResponse("/admin/plugins", status_code=302)


@router.post("/admin/plugins/{cp_id}/toggle")
async def admin_plugins_toggle(
    request: Request, cp_id: int, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)

    cp = db.query(ControlPlugin).filter(ControlPlugin.id == cp_id).first()
    if cp:
        cp.active = not cp.active
        db.commit()
        state = "activé" if cp.active else "désactivé"
        request.session["flash"] = f"Plugin {state}."
    return RedirectResponse("/admin/plugins", status_code=302)


@router.post("/admin/plugins/{cp_id}/delete")
async def admin_plugins_delete(
    request: Request, cp_id: int, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)

    cp = db.query(ControlPlugin).filter(ControlPlugin.id == cp_id).first()
    if cp:
        db.delete(cp)
        db.commit()
        request.session["flash"] = "Association supprimée."
    return RedirectResponse("/admin/plugins", status_code=302)


# ── Lancement du plugin ────────────────────────────────────────────────────────

@router.get("/plugin/controls/{control_id}/lancer")
async def plugin_lancer(
    request: Request, control_id: int,
    annee: int = 0, mois: int = 0,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    control = db.query(Control).filter(Control.id == control_id).first()
    if not control or not control.plugin or not control.plugin.active:
        return RedirectResponse(f"/controls/{control_id}", status_code=302)

    cp = control.plugin
    meta = get_plugin(cp.plugin_slug)

    if not annee:
        annee = date.today().year
    if not mois:
        mois = date.today().month

    plabel = periode_label(control.frequence, annee, mois)

    # Dernier run pour cette période (s'il existe)
    last_run = (db.query(PluginRun)
                .filter(PluginRun.control_plugin_id == cp.id,
                        PluginRun.annee == annee,
                        PluginRun.mois == mois)
                .order_by(PluginRun.run_at.desc())
                .first())

    return templates.TemplateResponse(request, meta["form_template"], {
        "user":         user,
        "control":      control,
        "cp":           cp,
        "plugin":       meta,
        "annee":        annee,
        "mois":         mois,
        "periode_label": plabel,
        "today":        date.today().strftime("%Y-%m-%d"),
        "last_run":     last_run,
        "error":        request.session.pop("plugin_run_error", None),
        "flash":        request.session.pop("flash", None),
    })


@router.post("/plugin/controls/{control_id}/executer")
async def plugin_executer(
    request: Request, control_id: int,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    control = db.query(Control).filter(Control.id == control_id).first()
    if not control or not control.plugin or not control.plugin.active:
        return RedirectResponse(f"/controls/{control_id}", status_code=302)

    form = await request.form()
    annee        = int(form.get("annee", 0))
    mois         = int(form.get("mois", 0))
    control_date = form.get("control_date", "") or date.today().strftime("%Y-%m-%d")

    cp   = control.plugin
    meta = get_plugin(cp.plugin_slug)
    mod  = _load_module(cp.plugin_slug)

    lir_url, lir_key = _lir_cfg(db)
    try:
        result = await mod.execute(form, {}, lir_url, lir_key, control_date)
    except Exception as e:
        request.session["plugin_run_error"] = f"Erreur d'analyse : {e}"
        return RedirectResponse(
            f"/plugin/controls/{control_id}/lancer?annee={annee}&mois={mois}",
            status_code=302
        )

    # Sauvegarde Excel + JSON
    run_id     = str(uuid.uuid4())
    excel_path = os.path.join(PLUGIN_DIR, f"report_{run_id}.xlsx")
    json_path  = os.path.join(PLUGIN_DIR, f"results_{run_id}.json")

    with open(excel_path, "wb") as f:
        f.write(result.pop("excel_bytes"))

    def _serial(obj):
        if isinstance(obj, set):
            return sorted(obj)
        raise TypeError(type(obj))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, default=_serial)

    taux_auto   = mod.compute_taux(result)
    commentaire = mod.build_commentaire(result)

    run = PluginRun(
        control_plugin_id=cp.id,
        annee=annee,
        mois=mois,
        plugin_slug=cp.plugin_slug,
        control_date=control_date,
        status="done",
        result_json_path=json_path,
        excel_path=excel_path,
        taux_conformite=taux_auto,
        commentaire_auto=commentaire,
        run_by_id=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    log_activity(db, user.id, user.username,
                 "Plugin exécuté", "plugin_run", run.id,
                 f"{meta['name']} — {control.reference} {annee}/{mois}")

    return RedirectResponse(f"/plugin/run/{run.id}", status_code=302)


# ── Résultats ──────────────────────────────────────────────────────────────────

@router.get("/plugin/run/{run_id}")
async def plugin_run_view(
    request: Request, run_id: int, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    run = db.query(PluginRun).filter(PluginRun.id == run_id).first()
    if not run:
        return RedirectResponse("/controls", status_code=302)

    cp      = run.control_plugin
    control = cp.control
    meta    = get_plugin(run.plugin_slug)

    if not os.path.exists(run.result_json_path or ""):
        request.session["flash"] = "Fichier de résultats introuvable."
        return RedirectResponse(f"/controls/{control.id}", status_code=302)

    with open(run.result_json_path, encoding="utf-8") as f:
        data = json.load(f)

    plabel = periode_label(control.frequence, run.annee, run.mois)

    return templates.TemplateResponse(request, meta["result_template"], {
        "user":          user,
        "run":           run,
        "control":       control,
        "plugin":        meta,
        "data":          data,
        "periode_label": plabel,
        "flash":         request.session.pop("flash", None),
    })


# ── Validation ────────────────────────────────────────────────────────────────

@router.post("/plugin/run/{run_id}/valider")
async def plugin_run_valider(
    request: Request, run_id: int, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    run = db.query(PluginRun).filter(PluginRun.id == run_id).first()
    if not run:
        return RedirectResponse("/controls", status_code=302)

    form = await request.form()
    taux        = float(form.get("taux_conformite", run.taux_conformite or 0))
    commentaire = form.get("commentaire", run.commentaire_auto or "").strip()
    notes       = form.get("notes", "").strip()

    cp      = run.control_plugin
    control = cp.control

    # Calcul statut
    if taux >= 100:
        statut = "conforme"
    elif taux >= 70:
        statut = "non_conforme"
    else:
        statut = "non_conforme"

    plabel = periode_label(control.frequence, run.annee, run.mois)

    # Upsert ControlResult
    cr = (db.query(ControlResult)
          .filter(ControlResult.control_id == control.id,
                  ControlResult.annee == run.annee,
                  ControlResult.mois  == run.mois)
          .first())

    is_new = cr is None
    if is_new:
        cr = ControlResult(
            control_id=control.id,
            annee=run.annee,
            mois=run.mois,
            periode_label=plabel,
            created_by_id=user.id,
        )
        db.add(cr)
        db.flush()

    cr.taux_conformite = taux
    cr.statut          = statut
    cr.commentaire     = commentaire
    cr.updated_by_id   = user.id
    cr.updated_at      = datetime.utcnow()
    cr.validated       = False  # laisse la clôture à l'auditeur

    db.add(ResultHistory(
        result_id=cr.id, control_id=control.id,
        action="created" if is_new else "updated",
        changed_by_id=user.id,
    ))

    # Marquer le run comme validé
    run.status         = "validated"
    run.notes          = notes
    run.validated_by_id = user.id
    run.validated_at   = datetime.utcnow()

    db.commit()

    log_activity(db, user.id, user.username,
                 "Résultat plugin enregistré", "control_result", cr.id,
                 f"{control.reference} {run.annee}/{run.mois} — taux {taux}%")

    request.session["flash"] = (
        f"Résultat enregistré : {taux}% — Vérifiez et clôturez ci-dessous."
    )
    return RedirectResponse(
        f"/controls/{control.id}/results/new?annee={run.annee}&mois={run.mois}",
        status_code=302
    )


# ── Téléchargement Excel ──────────────────────────────────────────────────────

@router.get("/plugin/run/{run_id}/telecharger")
async def plugin_run_download(
    request: Request, run_id: int, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    run = db.query(PluginRun).filter(PluginRun.id == run_id).first()
    if not run or not run.excel_path or not os.path.exists(run.excel_path):
        request.session["flash"] = "Rapport introuvable."
        return RedirectResponse("/controls", status_code=302)

    ctrl_date = run.control_date or date.today().strftime("%Y-%m-%d")
    filename  = f"{ctrl_date}-Revue-Droits-Operateurs.xlsx"

    def _iter():
        with open(run.excel_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        _iter(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Correction inline des écarts ──────────────────────────────────────────────

@router.post("/plugin/run/{run_id}/ecart/{idx}/override")
async def ecart_override(
    request: Request, run_id: int, idx: int, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "Non autorisé"}, status_code=401)

    run = db.query(PluginRun).filter(PluginRun.id == run_id).first()
    if not run or not os.path.exists(run.result_json_path or ""):
        return JSONResponse({"error": "Run introuvable"}, status_code=404)

    body   = await request.json()
    action = body.get("action", "")  # "ignore" | "reset"

    with open(run.result_json_path, encoding="utf-8") as f:
        data = json.load(f)

    ecarts = data.get("ecarts", [])
    if idx < 0 or idx >= len(ecarts):
        return JSONResponse({"error": "Index invalide"}, status_code=400)

    if action == "reset":
        ecarts[idx].pop("_override", None)
    else:
        ecarts[idx]["_override"] = action

    def _serial(obj):
        if isinstance(obj, set):
            return sorted(obj)
        raise TypeError(type(obj))

    with open(run.result_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=_serial)

    return JSONResponse({"ok": True})


# ── Envoi de tickets EasyVista pour les écarts sélectionnés ───────────────────

@router.post("/plugin/run/{run_id}/tickets")
async def create_ev_tickets(
    request: Request, run_id: int, db: Session = Depends(get_db)
):
    import urllib3, requests as _req
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "Non autorisé"}, status_code=401)

    run = db.query(PluginRun).filter(PluginRun.id == run_id).first()
    if not run or not os.path.exists(run.result_json_path or ""):
        return JSONResponse({"error": "Run introuvable"}, status_code=404)

    if get_config(db, "ev_enabled", "0") != "1":
        return JSONResponse({"error": "EasyVista non activé — activez-le dans Paramètres → EasyVista"}, status_code=503)

    ev_url     = get_config(db, "ev_url", "").rstrip("/")
    ev_account = get_config(db, "ev_account", "")
    ev_login   = get_config(db, "ev_login", "")
    ev_token   = get_config(db, "ev_token", "")

    body         = await request.json()
    indices      = body.get("indices", [])
    catalog_code = body.get("catalog_code", "").strip()

    if not all([ev_url, ev_account, ev_token, catalog_code]):
        return JSONResponse({"error": "Configuration EasyVista incomplète (URL / compte / token / code catalogue)"}, status_code=503)

    with open(run.result_json_path, encoding="utf-8") as f:
        data = json.load(f)

    ecarts  = data.get("ecarts", [])
    control = run.control_plugin.control
    y, m    = run.annee, f"{run.mois:02d}"
    requestor_mail = get_config(db, "ev_requestor_mail", "")

    results = []
    for idx in indices:
        if not (0 <= idx < len(ecarts)):
            continue
        ecart = ecarts[idx]
        if ecart.get("_override") == "ignore":
            continue
        if ecart.get("_ticket_ev"):
            results.append({"idx": idx, "ticket": ecart["_ticket_ev"], "status": "existing"})
            continue

        title = (f"[CONTROLE] {y}.{m}-Revue Droits Opérateurs - {ecart['name']}")
        description = (
            f"Contrôle : {control.reference} – {control.libelle}\n"
            f"Période  : {y}/{m}\n"
            f"Système  : {ecart['systeme']}\n"
            f"Nom      : {ecart['name']}\n"
            f"Détail   : {ecart['detail']}\n"
            f"Statut   : {ecart['status']}\n"
        )
        entry = {
            "Catalog_Code": catalog_code,
            "Title":        title,
            "Description":  description,
            "External_reference": f"PDC-RUN-{run_id}-{idx}",
        }
        if requestor_mail:
            entry["Requestor_Mail"] = requestor_mail

        try:
            resp = _req.post(
                f"{ev_url}/api/v1/{ev_account}/requests",
                json={"requests": [entry]},
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {ev_token}"},
                timeout=60, verify=False,
            )
            if resp.status_code == 201:
                href       = resp.json().get("HREF", "")
                ticket_num = href.rstrip("/").split("/")[-1] if href else str(resp.status_code)
                ecart["_ticket_ev"] = ticket_num
                results.append({"idx": idx, "ticket": ticket_num, "status": "created"})
            else:
                results.append({"idx": idx, "error": f"HTTP {resp.status_code}", "status": "error"})
        except Exception as e:
            results.append({"idx": idx, "error": str(e), "status": "error"})

    def _serial(obj):
        if isinstance(obj, set):
            return sorted(obj)
        raise TypeError(type(obj))

    with open(run.result_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=_serial)

    created = sum(1 for r in results if r["status"] == "created")
    log_activity(db, user.id, user.username, "Tickets EV créés", "plugin_run", run_id,
                 f"{created} ticket(s) — {control.reference} {y}/{m}")

    return JSONResponse({"results": results, "created": created})
