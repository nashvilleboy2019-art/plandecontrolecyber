import os
import shutil
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppConfig
from app.utils import get_current_user, get_config, set_config, log_activity
from app.templates_config import templates
from app import theme_cache

router = APIRouter(prefix="/settings", tags=["settings"])

LOGO_DIR = "static/uploads"
ALLOWED_LOGO_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}


@router.get("")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    cfg = {r.key: r.value for r in db.query(AppConfig).all()}
    return templates.TemplateResponse(request, "settings/index.html", {
        "request": request, "user": user, "cfg": cfg,
        "palettes": theme_cache.PALETTES,
        "flash": request.session.pop("flash", None),
    })


@router.post("/general")
async def save_general(
    request: Request, db: Session = Depends(get_db),
    company_name: str = Form(""), alert_warning_days: int = Form(7),
    alert_danger_days: int = Form(0),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    set_config(db, "company_name", company_name.strip())
    set_config(db, "alert_warning_days", str(alert_warning_days))
    set_config(db, "alert_danger_days", str(alert_danger_days))
    log_activity(db, user.id, user.username, "Modification paramètres généraux")
    request.session["flash"] = "Paramètres généraux sauvegardés"
    return RedirectResponse("/settings", status_code=302)


@router.post("/theme")
async def save_theme(
    request: Request, db: Session = Depends(get_db),
    theme_primary: str = Form("indigo"), theme_secondary: str = Form("slate"),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    set_config(db, "theme_primary", theme_primary)
    set_config(db, "theme_secondary", theme_secondary)
    theme_cache.set_theme(theme_primary, theme_secondary)
    request.session["flash"] = "Thème appliqué"
    return RedirectResponse("/settings", status_code=302)


@router.post("/logo")
async def upload_logo(
    request: Request, db: Session = Depends(get_db),
    logo: UploadFile = File(...),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    ext = os.path.splitext(logo.filename)[1].lower()
    if ext not in ALLOWED_LOGO_EXTS:
        request.session["flash"] = "Format non supporté (png, jpg, svg, webp)"
        return RedirectResponse("/settings", status_code=302)
    dest = os.path.join(LOGO_DIR, f"logo{ext}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(logo.file, f)
    set_config(db, "logo_ext", ext)
    request.session["flash"] = "Logo uploadé"
    return RedirectResponse("/settings", status_code=302)


@router.post("/logo/delete")
async def delete_logo(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    ext = get_config(db, "logo_ext", "")
    if ext:
        try:
            os.remove(os.path.join(LOGO_DIR, f"logo{ext}"))
        except FileNotFoundError:
            pass
    set_config(db, "logo_ext", "")
    request.session["flash"] = "Logo supprimé"
    return RedirectResponse("/settings", status_code=302)


@router.post("/ldap")
async def save_ldap(
    request: Request, db: Session = Depends(get_db),
    ldap_enabled: str = Form("0"),
    ldap_server: str = Form(""), ldap_port: int = Form(389),
    ldap_domain: str = Form(""), ldap_tls: str = Form("0"),
    ldap_base_dn: str = Form(""), ldap_allowed_ou: str = Form(""),
    ldap_allowed_group: str = Form(""), ldap_default_role: str = Form("auditeur"),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    for key, val in {
        "ldap_enabled": ldap_enabled, "ldap_server": ldap_server,
        "ldap_port": str(ldap_port), "ldap_domain": ldap_domain,
        "ldap_tls": ldap_tls, "ldap_base_dn": ldap_base_dn,
        "ldap_allowed_ou": ldap_allowed_ou, "ldap_allowed_group": ldap_allowed_group,
        "ldap_default_role": ldap_default_role,
    }.items():
        set_config(db, key, val)
    log_activity(db, user.id, user.username, "Modification config LDAP")
    request.session["flash"] = "Configuration LDAP sauvegardée"
    return RedirectResponse("/settings", status_code=302)


@router.get("/ldap/test")
async def test_ldap(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    try:
        from ldap3 import Server, Connection, Tls
        import ssl
        server_addr = get_config(db, "ldap_server", "")
        port = int(get_config(db, "ldap_port", "389"))
        use_tls = get_config(db, "ldap_tls", "0") == "1"
        tls = Tls(validate=ssl.CERT_NONE) if use_tls else None
        srv = Server(server_addr, port=port, tls=tls, get_info=None, connect_timeout=5)
        conn = Connection(srv)
        conn.open()
        request.session["flash"] = f"Connexion LDAP réussie vers {server_addr}:{port}"
    except Exception as e:
        request.session["flash"] = f"Échec connexion LDAP : {e}"
    return RedirectResponse("/settings", status_code=302)


@router.post("/jira")
async def save_jira(
    request: Request, db: Session = Depends(get_db),
    jira_enabled: str = Form("0"),
    jira_url: str = Form(""), jira_api_token: str = Form(""),
    jira_project_key: str = Form(""), jira_user_email: str = Form(""),
):
    user = get_current_user(request, db)
    if not user or user.role != "responsable":
        return RedirectResponse("/dashboard", status_code=302)
    for key, val in {
        "jira_enabled": jira_enabled, "jira_url": jira_url,
        "jira_api_token": jira_api_token, "jira_project_key": jira_project_key,
        "jira_user_email": jira_user_email,
    }.items():
        set_config(db, key, val)
    log_activity(db, user.id, user.username, "Modification config JIRA")
    request.session["flash"] = "Configuration JIRA sauvegardée"
    return RedirectResponse("/settings", status_code=302)
