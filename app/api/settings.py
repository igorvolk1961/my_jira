"""Настройки приложения (только администратор)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.flash import flash
from app.presentation.render import render
from app.services import settings_service

router = APIRouter()

SETTING_KEY = settings_service.ALLOW_USERS_ASSIGN_SUBTASK_EXECUTORS


@router.api_route("/settings", methods=["GET", "POST"], name="settings_index")
async def settings_index(request: Request, db: Session = Depends(get_db), _user: dict = Depends(require_admin)):
    if request.method == "POST":
        form = await request.form()
        value = "1" if form.get(SETTING_KEY) else "0"
        settings_service.set_setting(db, SETTING_KEY, value)
        flash(request, "Настройки сохранены", "success")
        return RedirectResponse(str(request.url_for("settings_index")), status_code=302)

    enabled = settings_service.get_setting(db, SETTING_KEY, "1") == "1"
    fields = [
        {
            "name": SETTING_KEY,
            "label": "Разрешить пользователям назначать исполнителей на подзадачи",
            "type": "checkbox",
            "checked": enabled,
            "hint": (
                "Если включено — любой пользователь может назначить исполнителем подзадачи любого "
                "сотрудника команды проекта. Если выключено — пользователь может назначить только себя "
                "либо оставить подзадачу без исполнителя."
            ),
        }
    ]
    return render(
        request,
        "pages/form.html",
        db,
        title="Настройки",
        action=str(request.url_for("settings_index")),
        fields=fields,
    )
