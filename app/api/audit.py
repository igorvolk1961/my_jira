"""Журнал аудита: HTTP-контроллер (только администратор)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.presentation import audit_views
from app.presentation.render import render
from app.services import audit_service

router = APIRouter()


@router.get("/audit", name="audit_index", dependencies=[Depends(require_admin)])
def audit_index(request: Request, db: Session = Depends(get_db)):
    data = audit_service.audit_data(db, request.query_params)
    return render(
        request,
        "pages/content.html",
        db,
        title="Аудит",
        content=audit_views.content(request, data),
    )
