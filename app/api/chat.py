"""Чат."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_user
from app.flash import flash
from app.presentation.render import render
from app.services import chat_service

router = APIRouter()


@router.get("/chat", name="chat_index")
def chat_index(request: Request, db: Session = Depends(get_db)):
    messages = chat_service.list_messages(db)
    return render(request, "pages/chat.html", db, title="Чат", messages=messages)


@router.post("/chat/post", name="chat_post")
async def chat_post(request: Request, db: Session = Depends(get_db), user: dict = Depends(require_user)):
    form = await request.form()
    error = chat_service.post_message(db, user, str(form.get("text") or ""))
    if error:
        flash(request, error, "error")
    return RedirectResponse(str(request.url_for("chat_index")), status_code=302)
