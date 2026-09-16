"""Аутентификация: вход, выход, регистрация."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.flash import flash
from app.presentation.render import render
from app.security import safe_next
from app.services import auth_service

router = APIRouter()

_LOGIN_FIELDS = [
    {"name": "login", "label": "Логин", "type": "text", "required": True, "value": ""},
    {"name": "password", "label": "Пароль", "type": "password", "required": True, "value": ""},
]

_REGISTER_FIELDS = [
    {"name": "login", "label": "Логин", "type": "text", "required": True, "value": ""},
    {"name": "password", "label": "Пароль", "type": "password", "required": True, "value": ""},
    {"name": "last_name", "label": "Фамилия", "type": "text", "required": True, "value": ""},
    {"name": "first_name", "label": "Имя", "type": "text", "required": True, "value": ""},
    {"name": "middle_name", "label": "Отчество", "type": "text", "required": True, "value": ""},
]


@router.api_route("/login", methods=["GET", "POST"], name="login")
async def login(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = await request.form()
        login_name = str(form.get("login") or "").strip()
        password = str(form.get("password") or "")
        user = auth_service.authenticate(db, login_name, password)
        if user is not None:
            request.session["user_id"] = user.id
            flash(request, "Вы вошли в систему", "success")
            target = safe_next(request.session.pop("next", None), str(request.url_for("index")))
            return RedirectResponse(target, status_code=302)
        flash(request, "Неверный логин или пароль", "error")

    return render(
        request,
        "pages/form.html",
        db,
        title="Вход",
        action=str(request.url_for("login")),
        fields=_LOGIN_FIELDS,
        submit_label="Войти",
        alt_url=str(request.url_for("register")),
        alt_label="Регистрация",
    )


@router.get("/logout", name="logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    flash(request, "Вы вышли из системы", "success")
    return RedirectResponse(str(request.url_for("index")), status_code=302)


@router.api_route("/register", methods=["GET", "POST"], name="register")
async def register(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = await request.form()
        values = {
            "login": str(form.get("login") or "").strip(),
            "password": str(form.get("password") or ""),
            "last_name": str(form.get("last_name") or "").strip(),
            "first_name": str(form.get("first_name") or "").strip(),
            "middle_name": str(form.get("middle_name") or "").strip(),
        }
        user, error = auth_service.register(db, **values)
        if user is None:
            flash(request, error, "error")
            return RedirectResponse(str(request.url_for("register")), status_code=302)
        flash(request, "Регистрация завершена — войдите с новыми учётными данными", "success")
        return RedirectResponse(str(request.url_for("login")), status_code=302)

    return render(
        request,
        "pages/form.html",
        db,
        title="Регистрация",
        action=str(request.url_for("register")),
        fields=_REGISTER_FIELDS,
        submit_label="Зарегистрироваться",
        back_url=str(request.url_for("login")),
    )
