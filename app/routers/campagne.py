from datetime import date
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Control, ControlResult, User, ResultHistory
from app.utils import (
    get_current_user, log_activity, period_for_cal_month,
    periods_for_year, periode_label,
)
from app.templates_config import templates

router = APIRouter(tags=["campagne"])

MOIS_NOMS = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
             "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


@router.get("/campagne")
async def campagne_mensuelle(
    request: Request, db: Session = Depends(get_db),
    annee: int = 0, mois: int = 0,
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    today = date.today()
    if not annee:
        annee = today.year
    if not mois:
        mois = today.month

    # Navigation
    prev_mois, prev_annee = (mois - 1, annee) if mois > 1 else (12, annee - 1)
    next_mois, next_annee = (mois + 1, annee) if mois < 12 else (1, annee + 1)

    # All active controls
    controls = db.query(Control).filter(Control.archived == False).order_by(Control.reference).all()

    items = []
    for c in controls:
        period_idx = period_for_cal_month(c.frequence, mois)
        if period_idx is None:
            continue  # not due this month

        plabel = periode_label(c.frequence, annee, period_idx)
        result = db.query(ControlResult).filter(
            ControlResult.control_id == c.id,
            ControlResult.annee == annee,
            ControlResult.mois == period_idx,
        ).first()

        items.append({
            "control": c,
            "period_idx": period_idx,
            "periode_label": plabel,
            "result": result,
        })

    # Stats
    total = len(items)
    saisis = sum(1 for i in items if i["result"] and i["result"].taux_conformite is not None)
    clotures = sum(1 for i in items if i["result"] and i["result"].validated)
    en_attente = total - saisis

    auditeurs = db.query(User).filter(User.active == True).order_by(User.nom_complet).all()

    return templates.TemplateResponse(request, "campagne/index.html", {
        "user": user,
        "items": items,
        "annee": annee,
        "mois": mois,
        "mois_nom": MOIS_NOMS[mois],
        "prev_mois": prev_mois, "prev_annee": prev_annee,
        "next_mois": next_mois, "next_annee": next_annee,
        "total": total, "saisis": saisis, "clotures": clotures, "en_attente": en_attente,
        "auditeurs": auditeurs,
        "flash": request.session.pop("flash", None),
    })


@router.post("/campagne/assign")
async def campagne_assign(
    request: Request, db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/campagne", status_code=302)

    form = await request.form()
    control_id = int(form.get("control_id", 0))
    annee = int(form.get("annee", 0))
    period_idx = int(form.get("period_idx", 0))
    assigned_id_raw = form.get("assigned_to_id", "")
    assigned_id = int(assigned_id_raw) if assigned_id_raw else None
    redirect_annee = form.get("redirect_annee", annee)
    redirect_mois = form.get("redirect_mois", 1)

    r = db.query(ControlResult).filter(
        ControlResult.control_id == control_id,
        ControlResult.annee == annee,
        ControlResult.mois == period_idx,
    ).first()

    if not r:
        # Create placeholder if doesn't exist yet
        c = db.query(Control).filter(Control.id == control_id).first()
        if c:
            r = ControlResult(
                control_id=control_id,
                annee=annee,
                mois=period_idx,
                periode_label=periode_label(c.frequence, annee, period_idx),
                statut="en_attente",
                assigned_to_id=assigned_id,
                created_by_id=user.id,
                updated_by_id=user.id,
            )
            db.add(r)
    else:
        r.assigned_to_id = assigned_id

    db.commit()
    return RedirectResponse(f"/campagne?annee={redirect_annee}&mois={redirect_mois}", status_code=302)


@router.get("/controls/{control_id}/plan-year")
async def plan_year_form(
    request: Request, control_id: int, db: Session = Depends(get_db),
    annee: int = 0,
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    c = db.query(Control).filter(Control.id == control_id).first()
    if not c or c.archived:
        return RedirectResponse("/controls", status_code=302)

    if not annee:
        annee = date.today().year

    periods = periods_for_year(c.frequence, annee)
    auditeurs = db.query(User).filter(User.active == True).order_by(User.nom_complet).all()

    # Existing results for this year
    existing = {
        r.mois: r
        for r in db.query(ControlResult).filter(
            ControlResult.control_id == c.id,
            ControlResult.annee == annee,
        ).all()
    }

    plan = []
    for (a, period_idx, label) in periods:
        plan.append({
            "annee": a,
            "mois": period_idx,
            "label": label,
            "result": existing.get(period_idx),
        })

    return templates.TemplateResponse(request, "controls/plan_year.html", {
        "user": user,
        "control": c,
        "annee": annee,
        "plan": plan,
        "auditeurs": auditeurs,
        "flash": request.session.pop("flash", None),
    })


@router.post("/controls/{control_id}/plan-year")
async def plan_year_submit(
    request: Request, control_id: int, db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    c = db.query(Control).filter(Control.id == control_id).first()
    if not c:
        return RedirectResponse("/controls", status_code=302)

    form = await request.form()
    annee = int(form.get("annee", date.today().year))

    created = 0
    updated = 0
    periods = periods_for_year(c.frequence, annee)

    for (a, period_idx, label) in periods:
        field_key = f"assigned_{period_idx}"
        assigned_id_raw = form.get(field_key, "")
        assigned_id = int(assigned_id_raw) if assigned_id_raw else None

        existing = db.query(ControlResult).filter(
            ControlResult.control_id == c.id,
            ControlResult.annee == a,
            ControlResult.mois == period_idx,
        ).first()

        if existing:
            # Only update assignment
            existing.assigned_to_id = assigned_id
            updated += 1
        else:
            r = ControlResult(
                control_id=c.id,
                annee=a,
                mois=period_idx,
                periode_label=label,
                statut="en_attente",
                taux_conformite=None,
                assigned_to_id=assigned_id,
                created_by_id=user.id,
                updated_by_id=user.id,
            )
            db.add(r)
            db.flush()
            db.add(ResultHistory(
                result_id=r.id, control_id=c.id,
                action="planned", changed_by_id=user.id,
            ))
            created += 1

    db.commit()
    log_activity(db, user.id, user.username, "Planification annuelle", "control", c.id,
                 f"{c.reference} – {annee} ({created} créés, {updated} mis à jour)")

    request.session["flash"] = f"Campagne {annee} planifiée : {created} période(s) créée(s), {updated} mise(s) à jour."
    return RedirectResponse(f"/controls/{control_id}/plan-year?annee={annee}", status_code=302)
