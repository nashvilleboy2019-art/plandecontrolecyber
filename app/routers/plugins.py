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

from fastapi import APIRouter, Request, Depends, UploadFile, File, Form
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Control, ControlPlugin, ControlResult, PluginRun, ResultHistory
from app.utils import get_current_user, get_config, log_activity, periode_label
from app.templates_config import templates
from app.plugins import get_plugin, all_plugins

router = APIRouter(tags=["plugins"])

PLUGIN_DIR = os.path.join("static", "uploads", "plugin_runs")
os.makedirs(PLUGIN_DIR, exist_ok=True)

DEFAULT_DB = r"C:\Users\Romain\Project\BaseLIR\data\baselir.db"


def _db_path(db: Session) -> str:
    return get_config(db, "baselir_path", DEFAULT_DB)


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

    return templates.TemplateResponse(request, "admin/plugins.html", {
        "user":         user,
        "plugins":      all_plugins(),
        "associations": associations,
        "controls":     controls,
        "associated_control_ids": associated_control_ids,
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
    annee:        int = Form(...),
    mois:         int = Form(...),
    control_date: str = Form(""),
    sacre_file:   UploadFile = File(...),
    pki_file:     UploadFile = File(...),
    kstamp_mrs1:  UploadFile = File(None),
    kstamp_mrs2:  UploadFile = File(None),
    kstamp_cly:   UploadFile = File(None),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    control = db.query(Control).filter(Control.id == control_id).first()
    if not control or not control.plugin or not control.plugin.active:
        return RedirectResponse(f"/controls/{control_id}", status_code=302)

    cp   = control.plugin
    meta = get_plugin(cp.plugin_slug)
    mod  = _load_module(cp.plugin_slug)

    if not control_date:
        control_date = date.today().strftime("%Y-%m-%d")

    # Validation : au moins 1 fichier KSTAMP
    kstamp_provided = any(
        f and f.filename for f in (kstamp_mrs1, kstamp_mrs2, kstamp_cly)
    )
    if not kstamp_provided:
        request.session["plugin_run_error"] = "Au moins un fichier KSTAMP est requis."
        return RedirectResponse(
            f"/plugin/controls/{control_id}/lancer?annee={annee}&mois={mois}",
            status_code=302
        )

    files = {
        "sacre_file":  sacre_file,
        "pki_file":    pki_file,
        "kstamp_mrs1": kstamp_mrs1,
        "kstamp_mrs2": kstamp_mrs2,
        "kstamp_cly":  kstamp_cly,
    }

    try:
        result = await mod.execute(files, {}, _db_path(db), control_date)
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
        f"Résultat enregistré : {taux}% — Vous pouvez maintenant clôturer la période."
    )
    return RedirectResponse(f"/controls/{control.id}", status_code=302)


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
