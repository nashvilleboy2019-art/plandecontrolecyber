from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.auth import hash_password
from app.utils import get_current_user, log_activity
from app.templates_config import templates

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    users = db.query(User).order_by(User.username).all()
    return templates.TemplateResponse(request, "users/list.html", {
        "request": request, "user": user, "users": users,
        "flash": request.session.pop("flash", None),
    })


@router.get("/new")
async def new_user_form(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "users/form.html", {
        "request": request, "user": user, "edit_user": None, "error": None,
    })


@router.post("/new")
async def create_user(
    request: Request, db: Session = Depends(get_db),
    username: str = Form(...), password: str = Form(...),
    role: str = Form("auditeur"), email: str = Form(""), nom_complet: str = Form(""),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    if db.query(User).filter(User.username == username.strip().lower()).first():
        return templates.TemplateResponse(request, "users/form.html", {
            "request": request, "user": user, "edit_user": None,
            "error": f"L'utilisateur «{username}» existe déjà.",
        })
    new_u = User(
        username=username.strip().lower(),
        password_hash=hash_password(password),
        role=role,
        email=email.strip(),
        nom_complet=nom_complet.strip(),
    )
    db.add(new_u)
    db.commit()
    log_activity(db, user.id, user.username, "Création utilisateur", "user", new_u.id, new_u.username)
    request.session["flash"] = f"Utilisateur «{new_u.username}» créé"
    return RedirectResponse("/users", status_code=302)


@router.get("/{user_id}/edit")
async def edit_user_form(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    edit_user = db.query(User).filter(User.id == user_id).first()
    if not edit_user:
        return RedirectResponse("/users", status_code=302)
    return templates.TemplateResponse(request, "users/form.html", {
        "request": request, "user": user, "edit_user": edit_user, "error": None,
    })


@router.post("/{user_id}/edit")
async def update_user(
    request: Request, user_id: int, db: Session = Depends(get_db),
    role: str = Form("auditeur"), email: str = Form(""),
    nom_complet: str = Form(""), password: str = Form(""),
    active: str = Form("1"),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    edit_user = db.query(User).filter(User.id == user_id).first()
    if not edit_user:
        return RedirectResponse("/users", status_code=302)
    edit_user.role = role
    edit_user.email = email.strip()
    edit_user.nom_complet = nom_complet.strip()
    edit_user.active = active == "1"
    if password.strip():
        edit_user.password_hash = hash_password(password.strip())
    db.commit()
    log_activity(db, user.id, user.username, "Modification utilisateur", "user", edit_user.id, edit_user.username)
    request.session["flash"] = f"Utilisateur «{edit_user.username}» modifié"
    return RedirectResponse("/users", status_code=302)


@router.post("/{user_id}/delete")
async def delete_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    if user_id == user.id:
        request.session["flash"] = "Impossible de supprimer votre propre compte"
        return RedirectResponse("/users", status_code=302)
    edit_user = db.query(User).filter(User.id == user_id).first()
    if edit_user:
        edit_user.active = False
        db.commit()
        log_activity(db, user.id, user.username, "Désactivation utilisateur", "user", edit_user.id, edit_user.username)
        request.session["flash"] = f"Utilisateur «{edit_user.username}» désactivé"
    return RedirectResponse("/users", status_code=302)
