import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import SessionLocal
from app.models import AppConfig
from app import theme_cache

from app.routers import controls, results, dashboard, admin, users, activity, settings as settings_router, campagne

app = FastAPI(title="Plan de Contrôle Cyber")

SECRET_KEY = os.environ.get("PDC_SECRET_KEY", "pdc-secret-key-change-in-production")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(controls.router)
app.include_router(results.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(activity.router)
app.include_router(settings_router.router)
app.include_router(campagne.router)


@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        primary = db.query(AppConfig).filter(AppConfig.key == "theme_primary").first()
        secondary = db.query(AppConfig).filter(AppConfig.key == "theme_secondary").first()
        theme_cache.set_theme(
            primary.value if primary else "indigo",
            secondary.value if secondary else "slate",
        )
    finally:
        db.close()


@app.get("/")
def root():
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/login")
async def login_page(request: Request):
    from app.templates_config import templates
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        cfg = db.query(AppConfig).filter(AppConfig.key == "company_name").first()
        logo = db.query(AppConfig).filter(AppConfig.key == "logo_ext").first()
        ldap_cfg = db.query(AppConfig).filter(AppConfig.key == "ldap_enabled").first()
        return templates.TemplateResponse(request, "login.html", {            "company_name": cfg.value if cfg else "Plan de Contrôle Cyber",
            "logo_ext": logo.value if logo else "",
            "ldap_enabled": (ldap_cfg.value == "1") if ldap_cfg else False,
            "error": request.session.pop("login_error", None),
        })
    finally:
        db.close()


@app.post("/login")
async def login_post(request: Request):
    from app.auth import authenticate
    from app.database import SessionLocal
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    db = SessionLocal()
    try:
        user = authenticate(username, password, db)
        if user:
            request.session["user_id"] = user.id
            request.session["username"] = user.username
            request.session["role"] = user.role
            return RedirectResponse("/dashboard", status_code=302)
        request.session["login_error"] = "Identifiants incorrects"
        return RedirectResponse("/login", status_code=302)
    finally:
        db.close()


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@app.get("/guide")
async def guide_page(request: Request):
    from app.templates_config import templates
    return templates.TemplateResponse(request, "guide.html", {})
