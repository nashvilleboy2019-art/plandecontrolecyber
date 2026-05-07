from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ActivityLog
from app.utils import get_current_user, paginate
from app.templates_config import templates

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
async def activity_log(request: Request, db: Session = Depends(get_db), page: int = 1):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    query = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc())
    pag = paginate(query, page, per_page=50)
    return templates.TemplateResponse(request, "activity/list.html", {
        "request": request, "user": user, "pagination": pag,
    })
