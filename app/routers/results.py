import json
from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Control, ControlResult, ResultHistory, User
from app.utils import (
    get_current_user, log_activity, paginate,
    current_period, periode_label, get_config,
)
from app.templates_config import templates

router = APIRouter(tags=["results"])


def _jira_create_ticket(db, control: Control, result: ControlResult):
    if get_config(db, "jira_enabled", "0") != "1":
        return None
    try:
        import requests as req
        url = get_config(db, "jira_url", "").rstrip("/")
        token = get_config(db, "jira_api_token", "")
        project = get_config(db, "jira_project_key", "")
        email = get_config(db, "jira_user_email", "")
        if not all([url, token, project, email]):
            return None
        payload = {
            "fields": {
                "project": {"key": project},
                "summary": f"[PDC] Non-conformité – {control.reference} – {result.periode_label}",
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [
                        {"type": "text", "text": (
                            f"Contrôle: {control.libelle}\n"
                            f"Période: {result.periode_label}\n"
                            f"Taux: {result.taux_conformite}%\n"
                            f"Commentaire: {result.commentaire or '-'}"
                        )}
                    ]}]
                },
                "issuetype": {"name": "Task"},
            }
        }
        resp = req.post(
            f"{url}/rest/api/3/issue",
            json=payload,
            auth=(email, token),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 201:
            return resp.json().get("key")
    except Exception:
        pass
    return None


@router.get("/results/pending")
async def pending_results(request: Request, db: Session = Depends(get_db), page: int = 1):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    query = (
        db.query(ControlResult)
        .filter(ControlResult.validated == False, ControlResult.taux_conformite.isnot(None))
        .order_by(ControlResult.created_at.desc())
    )
    pag = paginate(query, page)
    return templates.TemplateResponse(request, "results/pending.html", {
        "request": request, "user": user,
        "pagination": pag,
        "flash": request.session.pop("flash", None),
    })


@router.get("/controls/{control_id}/results/new")
async def new_result_form(
    request: Request, control_id: int, db: Session = Depends(get_db),
    annee: int = 0, mois: int = 0,
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    c = db.query(Control).filter(Control.id == control_id).first()
    if not c or c.archived:
        return RedirectResponse("/controls", status_code=302)

    if not annee or not mois:
        annee, mois = current_period(c.frequence)

    existing = db.query(ControlResult).filter(
        ControlResult.control_id == c.id,
        ControlResult.annee == annee,
        ControlResult.mois == mois,
    ).first()

    return templates.TemplateResponse(request, "results/form.html", {
        "request": request, "user": user, "control": c,
        "result": existing,
        "annee": annee, "mois": mois,
        "periode_label_str": periode_label(c.frequence, annee, mois),
        "error": None,
        "jira_enabled": get_config(db, "jira_enabled", "0") == "1",
    })


@router.post("/controls/{control_id}/results/new")
async def submit_result(
    request: Request, control_id: int, db: Session = Depends(get_db),
    annee: int = Form(...), mois: int = Form(...),
    taux_conformite: float = Form(None), statut: str = Form("en_attente"),
    commentaire: str = Form(""), create_jira: str = Form(""),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    c = db.query(Control).filter(Control.id == control_id).first()
    if not c:
        return RedirectResponse("/controls", status_code=302)

    plabel = periode_label(c.frequence, annee, mois)
    existing = db.query(ControlResult).filter(
        ControlResult.control_id == c.id,
        ControlResult.annee == annee,
        ControlResult.mois == mois,
    ).first()

    # Derive statut from taux if not NA
    if statut != "na" and taux_conformite is not None:
        statut = "conforme" if taux_conformite >= c.taux_cible else "non_conforme"

    if existing:
        old = {
            "taux_conformite": existing.taux_conformite,
            "statut": existing.statut,
            "commentaire": existing.commentaire,
        }
        existing.taux_conformite = taux_conformite
        existing.statut = statut
        existing.commentaire = commentaire.strip()
        existing.updated_by_id = user.id
        existing.updated_at = datetime.utcnow()
        if existing.validated:
            existing.validated = False
            existing.validated_by_id = None
            existing.validated_at = None
        db.add(ResultHistory(
            result_id=existing.id, control_id=c.id,
            action="updated", changed_by_id=user.id,
            old_values=json.dumps(old),
            new_values=json.dumps({"taux_conformite": taux_conformite, "statut": statut}),
        ))
        result = existing
    else:
        result = ControlResult(
            control_id=c.id, annee=annee, mois=mois,
            periode_label=plabel, taux_conformite=taux_conformite,
            statut=statut, commentaire=commentaire.strip(),
            created_by_id=user.id, updated_by_id=user.id,
        )
        db.add(result)
        db.flush()
        db.add(ResultHistory(
            result_id=result.id, control_id=c.id,
            action="created", changed_by_id=user.id,
            new_values=json.dumps({"taux_conformite": taux_conformite, "statut": statut}),
        ))

    db.flush()

    # JIRA ticket for non-conformance
    if create_jira == "1" and statut == "non_conforme" and not result.jira_ticket:
        ticket = _jira_create_ticket(db, c, result)
        if ticket:
            result.jira_ticket = ticket

    db.commit()
    log_activity(db, user.id, user.username, "Saisie résultat", "result", result.id, f"{c.reference} – {plabel}")
    request.session["flash"] = f"Résultat enregistré pour {plabel}"
    return RedirectResponse(f"/controls/{c.id}", status_code=302)


@router.post("/controls/{control_id}/results/{result_id}/open-incident")
async def open_incident(
    request: Request, control_id: int, result_id: int, db: Session = Depends(get_db),
    create_jira: str = Form(""),
    incident_ref: str = Form(""),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)

    r = db.query(ControlResult).filter(
        ControlResult.id == result_id, ControlResult.control_id == control_id
    ).first()
    c = db.query(Control).filter(Control.id == control_id).first()

    if r and c:
        r.statut = "incident_en_cours"
        r.updated_by_id = user.id
        r.updated_at = datetime.utcnow()

        if incident_ref.strip():
            r.incident_ref = incident_ref.strip()

        if create_jira == "1" and not r.jira_ticket:
            ticket = _jira_create_ticket(db, c, r)
            if ticket:
                r.jira_ticket = ticket

        db.add(ResultHistory(
            result_id=r.id, control_id=control_id,
            action="incident_opened", changed_by_id=user.id,
        ))
        db.commit()

        ref_info = r.jira_ticket or r.incident_ref or ""
        log_activity(db, user.id, user.username, "Incident ouvert", "result", r.id,
                     f"{c.reference} – {r.periode_label}" + (f" – {ref_info}" if ref_info else ""))
        request.session["flash"] = f"Incident ouvert pour {r.periode_label}" + (
            f" – {ref_info}" if ref_info else ""
        )
    return RedirectResponse(f"/controls/{control_id}", status_code=302)


@router.post("/controls/{control_id}/results/{result_id}/validate")
async def validate_result(request: Request, control_id: int, result_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)
    r = db.query(ControlResult).filter(
        ControlResult.id == result_id, ControlResult.control_id == control_id
    ).first()
    if r:
        r.validated = True
        r.validated_by_id = user.id
        r.validated_at = datetime.utcnow()
        db.add(ResultHistory(
            result_id=r.id, control_id=control_id,
            action="validated", changed_by_id=user.id,
        ))
        db.commit()
        action_label = "Incident clôturé" if r.statut == "incident_en_cours" else "Clôture résultat"
        log_activity(db, user.id, user.username, action_label, "result", r.id, r.periode_label)
        request.session["flash"] = f"Résultat {r.periode_label} clôturé"
    return RedirectResponse(f"/controls/{control_id}", status_code=302)


@router.post("/controls/{control_id}/results/{result_id}/invalidate")
async def invalidate_result(request: Request, control_id: int, result_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)
    r = db.query(ControlResult).filter(
        ControlResult.id == result_id, ControlResult.control_id == control_id
    ).first()
    if r:
        r.validated = False
        r.validated_by_id = None
        r.validated_at = None
        db.add(ResultHistory(
            result_id=r.id, control_id=control_id,
            action="invalidated", changed_by_id=user.id,
        ))
        db.commit()
        request.session["flash"] = f"Validation annulée pour {r.periode_label}"
    return RedirectResponse(f"/controls/{control_id}", status_code=302)


@router.post("/controls/{control_id}/results/{result_id}/update-incident-ref")
async def update_incident_ref(
    request: Request, control_id: int, result_id: int, db: Session = Depends(get_db),
    incident_ref: str = Form(""),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)
    r = db.query(ControlResult).filter(
        ControlResult.id == result_id, ControlResult.control_id == control_id
    ).first()
    if r and incident_ref.strip():
        r.incident_ref = incident_ref.strip()
        db.commit()
        request.session["flash"] = f"Numéro d'incident mis à jour : {r.incident_ref}"
    return RedirectResponse(f"/controls/{control_id}", status_code=302)


@router.post("/results/{result_id}/validate-from-pending")
async def validate_from_pending(request: Request, result_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)
    r = db.query(ControlResult).filter(ControlResult.id == result_id).first()
    if r:
        r.validated = True
        r.validated_by_id = user.id
        r.validated_at = datetime.utcnow()
        db.add(ResultHistory(
            result_id=r.id, control_id=r.control_id,
            action="validated", changed_by_id=user.id,
        ))
        db.commit()
        log_activity(db, user.id, user.username, "Validation résultat", "result", r.id, r.periode_label)
        request.session["flash"] = f"Résultat validé"
    return RedirectResponse("/results/pending", status_code=302)
