from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.models import ActivityLog, AppConfig, User


# ── Auth helpers ────────────────────────────────────────────────────────────

def require_login(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return request.session


def get_current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_responsable(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.role != "responsable":
        raise HTTPException(status_code=403, detail="Accès réservé aux responsables")
    return user


# ── Activity log ────────────────────────────────────────────────────────────

def log_activity(db: Session, user_id: int, username: str, action: str,
                 resource: str = None, resource_id: int = None, details: str = None):
    db.add(ActivityLog(
        user_id=user_id, username=username, action=action,
        resource=resource, resource_id=resource_id, details=details,
    ))
    db.commit()


# ── App config ──────────────────────────────────────────────────────────────

def get_config(db: Session, key: str, default=None):
    row = db.query(AppConfig).filter(AppConfig.key == key).first()
    return row.value if row else default


def set_config(db: Session, key: str, value: str):
    row = db.query(AppConfig).filter(AppConfig.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppConfig(key=key, value=value))
    db.commit()


# ── Frequency helpers ───────────────────────────────────────────────────────

FREQ_LABELS = {
    "mensuel": "Mensuel",
    "bimestriel": "Bimestriel",
    "trimestriel": "Trimestriel",
    "semestriel": "Semestriel",
    "annuel": "Annuel",
}

MOIS_LABELS = ["", "Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
               "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]


def periode_label(frequence: str, annee: int, mois: int) -> str:
    if frequence == "mensuel":
        return f"{MOIS_LABELS[mois]} {annee}"
    if frequence == "bimestriel":
        return f"B{mois} {annee}"
    if frequence == "trimestriel":
        return f"T{mois} {annee}"
    if frequence == "semestriel":
        return f"S{mois} {annee}"
    return str(annee)


def current_period(frequence: str, ref: date = None) -> tuple[int, int]:
    """Return (annee, mois/period-index) for the current expected period."""
    ref = ref or date.today()
    if frequence == "mensuel":
        return ref.year, ref.month
    if frequence == "bimestriel":
        return ref.year, (ref.month - 1) // 2 + 1
    if frequence == "trimestriel":
        return ref.year, (ref.month - 1) // 3 + 1
    if frequence == "semestriel":
        return ref.year, 1 if ref.month <= 6 else 2
    return ref.year, 1  # annuel


def next_due_date(frequence: str, annee: int, mois: int) -> date:
    """Return the start date of the next period after (annee, mois)."""
    if frequence == "mensuel":
        d = date(annee, mois, 1)
        return (d + relativedelta(months=1))
    if frequence == "bimestriel":
        start_month = (mois - 1) * 2 + 1
        d = date(annee, start_month, 1)
        return d + relativedelta(months=2)
    if frequence == "trimestriel":
        start_month = (mois - 1) * 3 + 1
        d = date(annee, start_month, 1)
        return d + relativedelta(months=3)
    if frequence == "semestriel":
        start_month = 1 if mois == 1 else 7
        d = date(annee, start_month, 1)
        return d + relativedelta(months=6)
    return date(annee + 1, 1, 1)


def get_alert_status(control, db: Session) -> str:
    """Return 'ok' | 'warning' | 'danger' | 'unknown'."""
    warning_days = int(get_config(db, "alert_warning_days", "7"))

    latest = next((r for r in control.results if r.taux_conformite is not None), None)
    if not latest:
        # No result yet — check control age
        created = control.created_at.date() if control.created_at else date.today()
        due = next_due_date(control.frequence, created.year, 1)
        delta = (date.today() - due).days
        if delta > 0:
            return "danger"
        if delta > -warning_days:
            return "warning"
        return "unknown"

    due = next_due_date(control.frequence, latest.annee, latest.mois)
    delta = (date.today() - due).days
    if delta > 0:
        return "danger"
    if delta > -warning_days:
        return "warning"
    return "ok"


def periods_for_year(frequence: str, annee: int) -> list:
    """Return all (annee, period_index, label) for the given year and frequency."""
    if frequence == "mensuel":
        return [(annee, m, periode_label(frequence, annee, m)) for m in range(1, 13)]
    if frequence == "bimestriel":
        return [(annee, p, periode_label(frequence, annee, p)) for p in range(1, 7)]
    if frequence == "trimestriel":
        return [(annee, p, periode_label(frequence, annee, p)) for p in range(1, 5)]
    if frequence == "semestriel":
        return [(annee, p, periode_label(frequence, annee, p)) for p in range(1, 3)]
    return [(annee, 1, str(annee))]


def period_for_cal_month(frequence: str, cal_month: int):
    """Return period index if the frequence starts a new period in cal_month, else None."""
    if frequence == "mensuel":
        return cal_month
    if frequence == "bimestriel":
        return (cal_month + 1) // 2 if cal_month % 2 == 1 else None
    if frequence == "trimestriel":
        return ((cal_month - 1) // 3 + 1) if cal_month in (1, 4, 7, 10) else None
    if frequence == "semestriel":
        return 1 if cal_month == 1 else (2 if cal_month == 7 else None)
    return 1 if cal_month == 1 else None  # annuel


def compliance_color(rate) -> str:
    if rate is None:
        return "gray"
    if rate >= 90:
        return "green"
    if rate >= 70:
        return "yellow"
    return "red"


# ── Pagination ──────────────────────────────────────────────────────────────

def paginate(query, page: int, per_page: int = 20):
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "rows": items,   # named "rows" not "items" to avoid dict.items() collision in Jinja2
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }
