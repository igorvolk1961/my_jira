"""Артефакты СА, текущий проект и роль «Системный аналитик»."""

import sqlite3

import main

TEST_DB = "pytest_verify.db"

ARTIFACT_KEYS = [
    "vision",
    "glossary",
    "stakeholders",
    "personas",
    "user_stories",
    "use_cases",
    "functional_requirements",
    "nonfunctional_requirements",
    "bpmn",
    "state_machines",
    "data_model",
    "prototype",
    "backlog",
    "risks",
]


def _scalar(sql, params=()):
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def _exec(sql, params=()):
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    try:
        con.execute(sql, params)
        con.commit()
    finally:
        con.close()


def _register(client, login="user1", password="pw"):
    client.post(
        "/register",
        data={"login": login, "password": password, "last_name": "И", "first_name": "И", "middle_name": "И"},
    )
    return _scalar("SELECT employee_id FROM app_user WHERE login=?", (login,))


def test_all_artifact_pages_render(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    for key in ARTIFACT_KEYS:
        r = client.get(f"/artifacts/{key}")
        assert r.status_code == 200, key


def test_artifact_pages_render_without_projects(anon_client):
    for key in ARTIFACT_KEYS:
        assert anon_client.get(f"/artifacts/{key}").status_code == 200, key
    assert anon_client.get("/artifacts/nope").status_code == 302


def test_document_artifact_edit_and_render(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    r = client.post("/artifacts/vision/edit", data={"content": "# Видение\n\n| a | b |\n|---|---|\n| 1 | 2 |"})
    assert r.status_code == 302
    html = client.get("/artifacts/vision").get_data(as_text=True)
    assert "<h1>Видение</h1>" in html and "<table>" in html
    # очистка
    client.get("/artifacts/vision/clear")
    assert "Артефакт не заполнен" in client.get("/artifacts/vision").get_data(as_text=True)


def test_document_artifact_edit_requires_analyst_or_admin(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    emp = _register(client, "u1")
    # обычный пользователь не может
    other = main.test_client()
    other.post("/login", data={"login": "u1", "password": "pw"})
    other.post("/artifacts/vision/edit", data={"content": "X"})
    assert _scalar("SELECT COUNT(*) FROM project_artifact WHERE artifact_key='vision'") == 0
    # аноним не может и перенаправляется на вход
    anon = main.test_client()
    r = anon.post("/artifacts/vision/edit", data={"content": "X"})
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    # системный аналитик может
    analyst_pos = _scalar("SELECT id FROM position_type WHERE name='Системный аналитик'")
    _exec("UPDATE employee SET position_type_id=? WHERE id=?", (analyst_pos, emp))
    _exec("UPDATE app_user SET is_analyst=1 WHERE login='u1'")
    other.post("/artifacts/vision/edit", data={"content": "Y"})
    assert _scalar("SELECT content FROM project_artifact WHERE artifact_key='vision'") == "Y"


BPMN_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">'
    '<bpmn:process id="Process_1" isExecutable="false"/></bpmn:definitions>'
)


def test_bpmn_artifact_edit_and_view(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    # пустой артефакт
    empty = client.get("/artifacts/bpmn").get_data(as_text=True)
    assert "Диаграмма BPMN не заполнена" in empty
    # сохранение XML модельером
    r = client.post("/artifacts/bpmn/edit", data={"content": BPMN_XML})
    assert r.status_code == 302
    assert _scalar("SELECT content FROM project_artifact WHERE artifact_key='bpmn'") == BPMN_XML
    # просмотр в bpmn-js
    view = client.get("/artifacts/bpmn").get_data(as_text=True)
    assert "bpmn-canvas" in view and "Process_1" in view and "bpmn-navigated-viewer" in view
    # страница редактирования подключает модельер
    edit = client.get("/artifacts/bpmn/edit").get_data(as_text=True)
    assert "bpmn-modeler.production.min.js" in edit and "bpmn-canvas" in edit
    # очистка
    client.get("/artifacts/bpmn/clear")
    assert "Диаграмма BPMN не заполнена" in client.get("/artifacts/bpmn").get_data(as_text=True)


def test_user_stories_flat_sections_and_markdown(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    client.post("/artifacts/user_stories/sections/create", data={"name": "Требования"})
    sec = _scalar("SELECT id FROM user_story_section WHERE name='Требования'")
    # «Как» — тип стейкхолдера
    type_id = _scalar("SELECT id FROM stakeholder_type WHERE is_deleted=0 ORDER BY id LIMIT 1")
    type_name = _scalar("SELECT name FROM stakeholder_type WHERE id=?", (type_id,))
    r = client.post(
        "/artifacts/user_stories/create",
        data={
            "identifier": "US-42",
            "section_id": str(sec),
            "stakeholder_type_id": str(type_id),
            "want": "видеть отчёт",
            "benefit": "контролировать сроки",
        },
    )
    assert r.status_code == 302
    assert _scalar("SELECT identifier FROM user_story WHERE project_id=1") == "US-42"
    body = client.get("/artifacts/user_stories").get_data(as_text=True)
    # не таблица: без заголовков, с метками полей
    assert "<thead" not in body
    assert 'class="us-section"' in body and "Требования" in body
    for label in ("ID", "Как", "Я хочу", "Чтобы"):
        assert f">{label}<" in body, label
    # все поля истории в один ряд, ввод большого текста — через textarea
    assert '<textarea name="identifier"' in body
    assert '<textarea name="want"' in body and '<textarea name="benefit"' in body
    assert "display:flex" in body and "resize:vertical" in body
    # нет выбора раздела в строке истории и нет подразделов
    assert '<select name="section_id"' not in body
    assert 'name="parent_id"' not in body
    # одна кнопка добавления истории на раздел и одна — добавления раздела (внизу)
    assert body.count("+ следующая история") == 1
    assert body.count(">+ раздел<") == 1
    # поддержка перетаскивания
    assert 'class="us-drag"' in body and 'data-us-kind="section"' in body and 'data-us-kind="story"' in body
    assert 'data-reorder-url="/artifacts/user_stories/reorder"' in body
    # кнопки «Показать текст»/«Скачать» в шапке, текст скрыт; область прокрутки
    assert "Показать текст" in body and ">Скачать<" in body
    assert 'id="us-text"' in body and 'id="us-text-src"' in body
    assert "overflow-y:auto" in body
    # плоский markdown по разделу
    assert "## Требования" in body and f"- **US-42**: Как {type_name}" in body
    assert "### " not in body
    # автоидентификатор продолжает нумерацию
    client.post("/artifacts/user_stories/create", data={"want": "w", "benefit": "b"})
    assert _scalar("SELECT identifier FROM user_story WHERE id=2") == "US-43"
    # правка идентификатора
    sid = _scalar("SELECT id FROM user_story WHERE identifier='US-42'")
    client.post(f"/artifacts/user_stories/edit/{sid}", data={"identifier": "US-1", "want": "W", "benefit": "B"})
    assert _scalar("SELECT identifier FROM user_story WHERE id=?", (sid,)) == "US-1"
    # переименование раздела: ссылка рядом с «Удалить», правка на месте
    assert 'class="us-rename"' in body and f'data-edit-url="/artifacts/user_stories/sections/edit/{sec}"' in body
    client.post(f"/artifacts/user_stories/sections/edit/{sec}", data={"name": "Требования 2"})
    assert _scalar("SELECT name FROM user_story_section WHERE id=?", (sec,)) == "Требования 2"
    client.post(f"/artifacts/user_stories/sections/edit/{sec}", data={"name": "Требования"})
    # непустой раздел не удаляется, пустой — удаляется
    client.get(f"/artifacts/user_stories/sections/delete/{sec}")
    assert _scalar("SELECT is_deleted FROM user_story_section WHERE id=?", (sec,)) == 0
    client.post("/artifacts/user_stories/sections/create", data={"name": "Пустой"})
    empty = _scalar("SELECT id FROM user_story_section WHERE name='Пустой'")
    client.get(f"/artifacts/user_stories/sections/delete/{empty}")
    assert _scalar("SELECT is_deleted FROM user_story_section WHERE id=?", (empty,)) == 1
    # удаление истории
    client.get(f"/artifacts/user_stories/delete/{sid}")
    assert _scalar("SELECT is_deleted FROM user_story WHERE id=?", (sid,)) == 1


def test_user_stories_reorder(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    client.post("/artifacts/user_stories/sections/create", data={"name": "A"})
    client.post("/artifacts/user_stories/sections/create", data={"name": "B"})
    a = _scalar("SELECT id FROM user_story_section WHERE name='A'")
    b = _scalar("SELECT id FROM user_story_section WHERE name='B'")
    client.post("/artifacts/user_stories/create", data={"want": "1", "benefit": "x", "section_id": str(a)})
    client.post("/artifacts/user_stories/create", data={"want": "2", "benefit": "y", "section_id": str(b)})
    s1 = _scalar("SELECT id FROM user_story WHERE want='1'")
    s2 = _scalar("SELECT id FROM user_story WHERE want='2'")
    # меняем порядок разделов и переносим историю в другой раздел
    r = client.post(
        "/artifacts/user_stories/reorder",
        json={"sections": [b, a], "stories": [{"id": s2, "section_id": b}, {"id": s1, "section_id": b}]},
    )
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert _scalar("SELECT position FROM user_story_section WHERE id=?", (b,)) == 0
    assert _scalar("SELECT position FROM user_story_section WHERE id=?", (a,)) == 1
    assert _scalar("SELECT section_id FROM user_story WHERE id=?", (s1,)) == b
    assert _scalar("SELECT position FROM user_story WHERE id=?", (s1,)) == 1


def test_user_stories_requires_analyst_or_admin(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    _register(client, "u7")
    other = main.test_client()
    other.post("/login", data={"login": "u7", "password": "pw"})
    other.post("/artifacts/user_stories/create", data={"role": "r", "want": "w", "benefit": "b"})
    assert _scalar("SELECT COUNT(*) FROM user_story") == 0
    r = other.post("/artifacts/user_stories/reorder", json={"sections": [], "stories": []})
    assert r.status_code == 302


def test_empty_artifact_hint_respects_rights(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    # администратор видит кнопку и подсказку про неё
    admin_body = client.get("/artifacts/bpmn").get_data(as_text=True)
    assert "/artifacts/bpmn/edit" in admin_body and "Нажмите «Изменить»" in admin_body
    # аноним не видит кнопку и получает подсказку про вход
    client.get("/logout")
    anon_body = client.get("/artifacts/bpmn").get_data(as_text=True)
    assert "/artifacts/bpmn/edit" not in anon_body
    assert "войдите в систему" in anon_body


def test_bpmn_static_assets_available(client):
    for path in (
        "/static/bpmn/bpmn-modeler.production.min.js",
        "/static/bpmn/bpmn-navigated-viewer.production.min.js",
        "/static/bpmn/assets/bpmn-js.css",
        "/static/bpmn/assets/diagram-js.css",
        "/static/bpmn/assets/bpmn-font/css/bpmn-embedded.css",
    ):
        assert client.get(path).status_code == 200, path


def test_bpmn_edit_requires_analyst_or_admin(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    _register(client, "u9")
    other = main.test_client()
    other.post("/login", data={"login": "u9", "password": "pw"})
    r = other.post("/artifacts/bpmn/edit", data={"content": BPMN_XML})
    assert r.status_code == 302
    assert _scalar("SELECT COUNT(*) FROM project_artifact WHERE artifact_key='bpmn'") == 0


def test_requirements_next_is_escaped(client):
    r = client.get("/requirements/create?next=%22%3E%3Cscript%3Ealert(1)%3C/script%3E")
    body = r.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


def test_nonfunctional_requirement_types_crud(client):
    client.post("/nonfunctional_requirement_types/create", data={"name": "Тест-НФТ"})
    assert "Тест-НФТ" in client.get("/nonfunctional_requirement_types").get_data(as_text=True)
    tid = _scalar("SELECT id FROM nonfunctional_requirement_type WHERE name='Тест-НФТ'")
    client.post(f"/nonfunctional_requirement_types/edit/{tid}", data={"name": "Тест-НФТ-2"})
    assert "Тест-НФТ-2" in client.get("/nonfunctional_requirement_types").get_data(as_text=True)
    client.get(f"/nonfunctional_requirement_types/delete/{tid}")
    assert "Тест-НФТ-2" not in client.get("/nonfunctional_requirement_types").get_data(as_text=True)


def test_nfr_type_used_on_nonfunctional_artifact(client):
    client.post("/projects/create", data={"name": "П", "priority_id": "1"})
    nfr_id = _scalar("SELECT id FROM nonfunctional_requirement_type WHERE name='Производительность'")
    nfr_req_type = _scalar("SELECT id FROM requirement_type WHERE name='Нефункциональное требование'")
    client.post(
        "/requirements/create",
        data={
            "project_id": "1",
            "requirement_type_id": str(nfr_req_type),
            "nfr_type_id": str(nfr_id),
            "description": "Отклик < 1с",
            "priority_id": "1",
        },
    )
    body = client.get("/artifacts/nonfunctional_requirements").get_data(as_text=True)
    assert "Тип НФТ" in body and "Производительность" in body and "Отклик" in body
    # селект типа НФТ берётся из нового справочника
    form = client.get("/requirements/create").get_data(as_text=True)
    assert 'name="nfr_type_id"' in form and "Производительность" in form
    # тип НФТ виден в карточке требования
    assert "Производительность" in client.get("/requirements/1").get_data(as_text=True)


def test_current_project_switch(client):
    client.post("/projects/create", data={"name": "Первый", "priority_id": "1"})
    client.post("/projects/create", data={"name": "Второй", "priority_id": "1"})
    r = client.get("/current-project/2?next=/artifacts/vision")
    assert r.status_code == 302
    body = client.get("/artifacts/vision").get_data(as_text=True)
    assert "Второй" in body
