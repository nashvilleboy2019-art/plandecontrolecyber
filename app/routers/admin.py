from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ControlType, Category, Perimetre, Control
from app.utils import get_current_user, log_activity
from app.templates_config import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_resp(request, db):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return None, RedirectResponse("/dashboard", status_code=302)
    return user, None


@router.get("")
async def admin_index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "admin/index.html", {
        "request": request, "user": user,
        "types": db.query(ControlType).order_by(ControlType.ordre).all(),
        "categories": db.query(Category).order_by(Category.ordre).all(),
        "perimetres": db.query(Perimetre).order_by(Perimetre.ordre).all(),
        "flash": request.session.pop("flash", None),
    })


# ── Control Types ────────────────────────────────────────────────────────────

@router.post("/types/add")
async def add_type(
    request: Request, db: Session = Depends(get_db),
    label: str = Form(...), color: str = Form("blue"),
):
    user, redir = _require_resp(request, db)
    if redir:
        return redir
    if not db.query(ControlType).filter(ControlType.label == label.strip()).first():
        max_ordre = db.query(ControlType).count()
        db.add(ControlType(label=label.strip(), color=color, ordre=max_ordre))
        db.commit()
        log_activity(db, user.id, user.username, "Ajout thématique", "type", None, label)
        request.session["flash"] = f"Thématique «{label}» ajoutée"
    return RedirectResponse("/admin", status_code=302)


@router.post("/types/{type_id}/edit")
async def edit_type(
    request: Request, type_id: int, db: Session = Depends(get_db),
    label: str = Form(...), color: str = Form("blue"), active: str = Form("1"),
):
    user, redir = _require_resp(request, db)
    if redir:
        return redir
    t = db.query(ControlType).filter(ControlType.id == type_id).first()
    if t:
        t.label = label.strip()
        t.color = color
        t.active = active == "1"
        db.commit()
        request.session["flash"] = f"Thématique «{t.label}» modifiée"
    return RedirectResponse("/admin", status_code=302)


@router.post("/types/{type_id}/delete")
async def delete_type(request: Request, type_id: int, db: Session = Depends(get_db)):
    user, redir = _require_resp(request, db)
    if redir:
        return redir
    t = db.query(ControlType).filter(ControlType.id == type_id).first()
    if t:
        db.query(Control).filter(Control.type_id == t.id).update({"type_id": None})
        label = t.label
        db.delete(t)
        db.commit()
        log_activity(db, user.id, user.username, "Suppression thématique", "type", None, label)
        request.session["flash"] = f"Thématique «{label}» supprimée"
    return RedirectResponse("/admin", status_code=302)


# ── Categories ───────────────────────────────────────────────────────────────

@router.post("/categories/add")
async def add_category(
    request: Request, db: Session = Depends(get_db),
    label: str = Form(...), description: str = Form(""),
):
    user, redir = _require_resp(request, db)
    if redir:
        return redir
    if not db.query(Category).filter(Category.label == label.strip()).first():
        db.add(Category(label=label.strip(), description=description.strip(), ordre=db.query(Category).count()))
        db.commit()
        request.session["flash"] = f"Catégorie «{label}» ajoutée"
    return RedirectResponse("/admin", status_code=302)


@router.post("/categories/{cat_id}/edit")
async def edit_category(
    request: Request, cat_id: int, db: Session = Depends(get_db),
    label: str = Form(...), description: str = Form(""), active: str = Form("1"),
):
    user, redir = _require_resp(request, db)
    if redir:
        return redir
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if cat:
        cat.label = label.strip()
        cat.description = description.strip()
        cat.active = active == "1"
        db.commit()
        request.session["flash"] = f"Catégorie «{cat.label}» modifiée"
    return RedirectResponse("/admin", status_code=302)


@router.post("/categories/{cat_id}/delete")
async def delete_category(request: Request, cat_id: int, db: Session = Depends(get_db)):
    user, redir = _require_resp(request, db)
    if redir:
        return redir
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if cat:
        db.query(Control).filter(Control.category_id == cat.id).update({"category_id": None})
        label = cat.label
        db.delete(cat)
        db.commit()
        log_activity(db, user.id, user.username, "Suppression catégorie", "category", None, label)
        request.session["flash"] = f"Catégorie «{label}» supprimée"
    return RedirectResponse("/admin", status_code=302)


# ── Perimetres ───────────────────────────────────────────────────────────────

@router.post("/perimetres/add")
async def add_perimetre(
    request: Request, db: Session = Depends(get_db),
    label: str = Form(...), description: str = Form(""),
):
    user, redir = _require_resp(request, db)
    if redir:
        return redir
    if not db.query(Perimetre).filter(Perimetre.label == label.strip()).first():
        db.add(Perimetre(label=label.strip(), description=description.strip(), ordre=db.query(Perimetre).count()))
        db.commit()
        request.session["flash"] = f"Périmètre «{label}» ajouté"
    return RedirectResponse("/admin", status_code=302)


@router.post("/perimetres/{per_id}/edit")
async def edit_perimetre(
    request: Request, per_id: int, db: Session = Depends(get_db),
    label: str = Form(...), description: str = Form(""), active: str = Form("1"),
):
    user, redir = _require_resp(request, db)
    if redir:
        return redir
    p = db.query(Perimetre).filter(Perimetre.id == per_id).first()
    if p:
        p.label = label.strip()
        p.description = description.strip()
        p.active = active == "1"
        db.commit()
        request.session["flash"] = f"Périmètre «{p.label}» modifié"
    return RedirectResponse("/admin", status_code=302)


@router.post("/perimetres/{per_id}/delete")
async def delete_perimetre(request: Request, per_id: int, db: Session = Depends(get_db)):
    user, redir = _require_resp(request, db)
    if redir:
        return redir
    p = db.query(Perimetre).filter(Perimetre.id == per_id).first()
    if p:
        db.query(Control).filter(Control.perimetre_id == p.id).update({"perimetre_id": None})
        label = p.label
        db.delete(p)
        db.commit()
        log_activity(db, user.id, user.username, "Suppression périmètre", "perimetre", None, label)
        request.session["flash"] = f"Périmètre «{label}» supprimé"
    return RedirectResponse("/admin", status_code=302)
