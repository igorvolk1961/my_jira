"""Интервью, аудио, транскрипт, комментарии, управление БД."""

import io
import os
import sqlite3

import main

TEST_DB = "pytest_verify.db"


def _mk_interview(client):
    client.post("/stakeholders/create", data={"last_name": "S", "first_name": "S", "type_id": "1", "priority": "3"})
    client.post("/interviews/create", data={"stakeholder_id": "1", "scheduled_at": "2026-01-01T10:00"})


def test_interview_qa_and_export(client):
    _mk_interview(client)
    client.post("/interview_qa/create", data={"interview_id": "1", "question": "Вопрос", "answer": "Ответ"})
    html = client.get("/interviews/1").get_data(as_text=True)
    assert "Вопрос" in html and "Ответ" in html
    exp = client.get("/interviews/1/export")
    assert exp.status_code == 200 and exp.headers["Content-Type"].startswith("text/markdown")


def test_audio_upload_and_serve(client):
    _mk_interview(client)
    r = client.post("/interviews/1/audio", files={"file": ("rec.wav", io.BytesIO(b"RIFFfake"), "audio/wav")})
    assert r.status_code in (200, 302)
    assert "rec.wav" in client.get("/interviews/1").get_data(as_text=True)
    assert client.get("/interviews/audio/1").status_code == 200
    assert client.get("/interviews/audio/1/download").status_code == 200


def test_transcript_batch_edit_save_and_delete(client):
    _mk_interview(client)
    # Сегменты создаём напрямую в БД (импорт SRT/VTT/TXT удалён из UI и маршрутов)
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    con.execute("INSERT INTO transcript_segment (interview_id, start_ms, end_ms, text) VALUES (1, 1000, 4000, 'Hello')")
    con.execute("INSERT INTO transcript_segment (interview_id, start_ms, end_ms, text) VALUES (1, 5000, 7500, 'World')")
    con.commit()
    con.close()
    html = client.get("/interviews/1").get_data(as_text=True)
    assert "Hello" in html and "World" in html and "00:01" in html and "00:05" in html
    # страница редактирования транскрипта — одна форма на все сегменты
    assert client.get("/interviews/1/transcript/edit").status_code == 200
    # пакетное сохранение всех сегментов одной отправкой
    r = client.post(
        "/interviews/1/transcript/save",
        data={
            "text_1": "Hello edited",
            "speaker_1": "Интервьюер",
            "text_2": "World edited",
            "speaker_2": "Стейкхолдер",
        },
        follow_redirects=True,
    )
    html = r.get_data(as_text=True)
    assert "Hello edited" in html and "Интервьюер" in html
    assert "World edited" in html and "Стейкхолдер" in html
    # удаление одного сегмента
    client.get("/interviews/1/segment/2/delete")
    assert "World edited" not in client.get("/interviews/1").get_data(as_text=True)


def test_transcribe_endpoint_does_not_crash(client):
    _mk_interview(client)
    client.post("/interviews/1/audio", files={"file": ("rec.wav", io.BytesIO(b"RIFFfake"), "audio/wav")})
    # движок может быть установлен или нет, аудио фиктивное — эндпоинт не должен падать (500)
    r = client.post("/interviews/1/transcribe", data={}, follow_redirects=True)
    assert r.status_code == 200
    assert "Интервью" in r.get_data(as_text=True)


def test_comments_on_task(client):
    client.post("/stakeholders/create", data={"last_name": "S", "first_name": "S", "type_id": "1", "priority": "3"})
    client.post("/projects/create", data={"name": "P", "priority_id": "1"})
    client.post(
        "/requirements/create",
        data={"project_id": "1", "requirement_type_id": "1", "description": "R", "priority_id": "1"},
    )
    client.post("/project_stages/create", data={"project_id": "1", "stage_type_id": "1", "status_id": "1"})
    client.post(
        "/tasks/create",
        data={
            "requirement_id": "1",
            "description": "T",
            "stage_id": "1",
            "task_type_id": "1",
            "priority_id": "1",
            "status_id": "1",
        },
    )
    client.post("/comments/create", data={"entity_type": "task", "entity_id": "1", "text": "Первый"})
    html = client.get("/tasks/1").get_data(as_text=True)
    assert "Первый" in html and "admin" in html


def test_database_create_switch_delete(client):
    name = "pytest_game2.db"
    path = main.db_path_for(name)
    try:
        client.post("/database/create", data={"name": "pytest_game2"})
        assert os.path.exists(path)
        assert client.get("/database").status_code == 200
        assert client.get("/database/use/" + name).status_code in (200, 302)
        assert client.get("/database/delete/" + name).status_code in (200, 302)
        assert not os.path.exists(path)
    finally:
        for suf in ("", "-wal", "-shm"):
            if os.path.exists(path + suf):
                os.remove(path + suf)
