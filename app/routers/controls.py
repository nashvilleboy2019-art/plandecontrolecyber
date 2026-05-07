import json
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Control, ControlHistory, ControlType, Category, Perimetre, User
from app.utils import get_current_user, log_activity, get_alert_status, paginate
from app.templates_config import templates

router = APIRouter(prefix="/controls", tags=["controls"])


def _snapshot(c: Control) -> dict:
    return {
        "reference": c.reference, "libelle": c.libelle, "indicateur": c.indicateur,
        "objectif": c.objectif, "frequence": c.frequence, "type_id": c.type_id,
        "category_id": c.category_id, "perimetre_id": c.perimetre_id,
        "taux_cible": c.taux_cible, "responsable_id": c.responsable_id,
    }


@router.get("")
async def list_controls(
    request: Request, db: Session = Depends(get_db),
    q: str = "", type_id: int = 0, category_id: int = 0,
    perimetre_id: int = 0, frequence: str = "", archived: str = "0",
    page: int = 1,
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    query = db.query(Control)
    if archived == "1":
        query = query.filter(Control.archived == True)
    else:
        query = query.filter(Control.archived == False)
    if q:
        query = query.filter(
            Control.reference.ilike(f"%{q}%") | Control.libelle.ilike(f"%{q}%")
        )
    if type_id:
        query = query.filter(Control.type_id == type_id)
    if category_id:
        query = query.filter(Control.category_id == category_id)
    if perimetre_id:
        query = query.filter(Control.perimetre_id == perimetre_id)
    if frequence:
        query = query.filter(Control.frequence == frequence)

    query = query.order_by(Control.reference)
    pag = paginate(query, page)

    # Compute alert status for each control
    controls_with_status = []
    for c in pag["rows"]:
        controls_with_status.append({
            "control": c,
            "alert": get_alert_status(c, db),
            "last_result": c.results[0] if c.results else None,
        })

    return templates.TemplateResponse(request, "controls/list.html", {
        "request": request, "user": user,
        "controls_with_status": controls_with_status,
        "pagination": pag,
        "types": db.query(ControlType).filter(ControlType.active == True).order_by(ControlType.ordre).all(),
        "categories": db.query(Category).filter(Category.active == True).order_by(Category.ordre).all(),
        "perimetres": db.query(Perimetre).filter(Perimetre.active == True).order_by(Perimetre.ordre).all(),
        "filters": {"q": q, "type_id": type_id, "category_id": category_id,
                    "perimetre_id": perimetre_id, "frequence": frequence, "archived": archived},
    })


@router.get("/new")
async def new_control_form(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.role != "responsable":
        return RedirectResponse("/controls", status_code=302)
    return templates.TemplateResponse(request, "controls/form.html", {
        "request": request, "user": user, "control": None,
        "types": db.query(ControlType).filter(ControlType.active == True).order_by(ControlType.ordre).all(),
        "categories": db.query(Category).filter(Category.active == True).order_by(Category.ordre).all(),
        "perimetres": db.query(Perimetre).filter(Perimetre.active == True).order_by(Perimetre.ordre).all(),
        "responsables": db.query(User).filter(User.active == True).order_by(User.nom_complet).all(),
        "error": None,
    })


@router.post("/new")
async def create_control(
    request: Request, db: Session = Depends(get_db),
    reference: str = Form(...), libelle: str = Form(...),
    indicateur: str = Form(""), objectif: str = Form(""),
    guide_url: str = Form(""),
    frequence: str = Form(...), type_id: int = Form(0),
    category_id: int = Form(0), perimetre_id: int = Form(0),
    taux_cible: float = Form(100.0), responsable_id: int = Form(0),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)

    if db.query(Control).filter(Control.reference == reference.strip().upper()).first():
        return templates.TemplateResponse(request, "controls/form.html", {
            "request": request, "user": user, "control": None,
            "types": db.query(ControlType).filter(ControlType.active == True).all(),
            "categories": db.query(Category).filter(Category.active == True).all(),
            "perimetres": db.query(Perimetre).filter(Perimetre.active == True).all(),
            "responsables": db.query(User).filter(User.active == True).all(),
            "error": f"La référence «{reference.strip().upper()}» existe déjà.",
        })

    c = Control(
        reference=reference.strip().upper(),
        libelle=libelle.strip(),
        indicateur=indicateur.strip(),
        objectif=objectif.strip(),
        guide_url=guide_url.strip() or None,
        frequence=frequence,
        type_id=type_id or None,
        category_id=category_id or None,
        perimetre_id=perimetre_id or None,
        taux_cible=taux_cible,
        responsable_id=responsable_id or None,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    db.add(c)
    db.flush()
    db.add(ControlHistory(
        control_id=c.id, action="created", changed_by_id=user.id,
        new_values=json.dumps(_snapshot(c)),
    ))
    db.commit()
    log_activity(db, user.id, user.username, "Création contrôle", "control", c.id, c.reference)
    return RedirectResponse(f"/controls/{c.id}", status_code=302)


@router.get("/{control_id}")
async def control_detail(request: Request, control_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    c = db.query(Control).filter(Control.id == control_id).first()
    if not c:
        return RedirectResponse("/controls", status_code=302)
    from app.utils import get_config
    return templates.TemplateResponse(request, "controls/detail.html", {
        "request": request, "user": user, "control": c,
        "alert": get_alert_status(c, db),
        "flash": request.session.pop("flash", None),
        "jira_enabled": get_config(db, "jira_enabled", "0") == "1",
    })


@router.get("/{control_id}/edit")
async def edit_control_form(request: Request, control_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    c = db.query(Control).filter(Control.id == control_id).first()
    if not c:
        return RedirectResponse("/controls", status_code=302)
    return templates.TemplateResponse(request, "controls/form.html", {
        "request": request, "user": user, "control": c,
        "types": db.query(ControlType).filter(ControlType.active == True).order_by(ControlType.ordre).all(),
        "categories": db.query(Category).filter(Category.active == True).order_by(Category.ordre).all(),
        "perimetres": db.query(Perimetre).filter(Perimetre.active == True).order_by(Perimetre.ordre).all(),
        "responsables": db.query(User).filter(User.active == True).order_by(User.nom_complet).all(),
        "error": None,
    })


@router.post("/{control_id}/edit")
async def update_control(
    request: Request, control_id: int, db: Session = Depends(get_db),
    libelle: str = Form(...), indicateur: str = Form(""), objectif: str = Form(""),
    guide_url: str = Form(""),
    frequence: str = Form(...), type_id: int = Form(0),
    category_id: int = Form(0), perimetre_id: int = Form(0),
    taux_cible: float = Form(100.0), responsable_id: int = Form(0),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    c = db.query(Control).filter(Control.id == control_id).first()
    if not c:
        return RedirectResponse("/controls", status_code=302)

    old = _snapshot(c)
    c.libelle = libelle.strip()
    c.indicateur = indicateur.strip()
    c.objectif = objectif.strip()
    c.guide_url = guide_url.strip() or None
    c.frequence = frequence
    c.type_id = type_id or None
    c.category_id = category_id or None
    c.perimetre_id = perimetre_id or None
    c.taux_cible = taux_cible
    c.responsable_id = responsable_id or None
    c.updated_by_id = user.id
    c.updated_at = datetime.utcnow()

    db.add(ControlHistory(
        control_id=c.id, action="updated", changed_by_id=user.id,
        old_values=json.dumps(old), new_values=json.dumps(_snapshot(c)),
    ))
    db.commit()
    log_activity(db, user.id, user.username, "Modification contrôle", "control", c.id, c.reference)
    return RedirectResponse(f"/controls/{c.id}", status_code=302)


@router.post("/{control_id}/archive")
async def archive_control(request: Request, control_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)
    c = db.query(Control).filter(Control.id == control_id).first()
    if c and not c.archived:
        c.archived = True
        c.archived_at = datetime.utcnow()
        c.archived_by_id = user.id
        db.add(ControlHistory(control_id=c.id, action="archived", changed_by_id=user.id))
        db.commit()
        log_activity(db, user.id, user.username, "Archivage contrôle", "control", c.id, c.reference)
    return RedirectResponse("/controls", status_code=302)


@router.post("/{control_id}/restore")
async def restore_control(request: Request, control_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/login", status_code=302)
    c = db.query(Control).filter(Control.id == control_id).first()
    if c and c.archived:
        c.archived = False
        c.archived_at = None
        c.archived_by_id = None
        db.add(ControlHistory(control_id=c.id, action="restored", changed_by_id=user.id))
        db.commit()
        log_activity(db, user.id, user.username, "Restauration contrôle", "control", c.id, c.reference)
    return RedirectResponse(f"/controls/{control_id}", status_code=302)


@router.get("/{control_id}/history")
async def control_history(request: Request, control_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    c = db.query(Control).filter(Control.id == control_id).first()
    if not c:
        return RedirectResponse("/controls", status_code=302)
    return templates.TemplateResponse(request, "controls/history.html", {
        "request": request, "user": user, "control": c,
    })
