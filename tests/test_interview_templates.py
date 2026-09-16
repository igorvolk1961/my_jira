"""Шаблоны интервью."""

import sqlite3

import main

TEST_DB = "pytest_verify.db"


def _scalar(sql, params=()):
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def test_default_template_seeded(anon_client):
    assert anon_client.get("/interview_templates").status_code == 200
    tid = _scalar("SELECT id FROM interview_template WHERE name='Вопросы Заказчику' AND is_deleted=0")
    assert tid
    assert (
        _scalar("SELECT COUNT(*) FROM interview_template_question WHERE template_id=? AND is_deleted=0", (tid,)) >= 25
    )


def test_interview_from_template_copies_questions(client):
    client.post("/stakeholders/create", data={"last_name": "П", "first_name": "И", "type_id": "1", "priority": "3"})
    tid = _scalar("SELECT id FROM interview_template WHERE name='Вопросы Заказчику' AND is_deleted=0")
    client.post("/interviews/create", data={"stakeholder_id": "1", "template_id": str(tid)})
    iv = _scalar("SELECT id FROM interview WHERE stakeholder_id=1 AND is_deleted=0")
    assert iv
    tpl_count = _scalar("SELECT COUNT(*) FROM interview_template_question WHERE template_id=? AND is_deleted=0", (tid,))
    qa_count = _scalar("SELECT COUNT(*) FROM interview_qa WHERE interview_id=? AND is_deleted=0", (iv,))
    assert qa_count == tpl_count >= 25


def test_template_created_from_interview(client):
    client.post("/stakeholders/create", data={"last_name": "П", "first_name": "И", "type_id": "1", "priority": "3"})
    client.post("/interviews/create", data={"stakeholder_id": "1"})
    iv = _scalar("SELECT id FROM interview WHERE stakeholder_id=1 AND is_deleted=0")
    client.post("/interview_qa/create", data={"interview_id": str(iv), "question": "Q1", "answer": "A1"})
    client.post("/interview_qa/create", data={"interview_id": str(iv), "question": "Q2", "answer": ""})
    client.post(f"/interviews/{iv}/save_as_template", data={"name": "Мой шаблон"})
    tid = _scalar("SELECT id FROM interview_template WHERE name='Мой шаблон' AND is_deleted=0")
    assert tid
    assert _scalar("SELECT COUNT(*) FROM interview_template_question WHERE template_id=? AND is_deleted=0", (tid,)) == 2
    # ответы в шаблон не переносятся
    assert (
        _scalar("SELECT COUNT(*) FROM interview_template_question WHERE template_id=? AND answer IS NOT NULL", (tid,))
        == 0
    )


def test_template_writes_are_admin_only(user_client):
    user_client.post("/interview_templates/create", data={"name": "X"})
    assert _scalar("SELECT COUNT(*) FROM interview_template WHERE name='X'") == 0


def test_interview_qa_inline_edit(client):
    client.post("/stakeholders/create", data={"last_name": "П", "first_name": "И", "type_id": "1", "priority": "3"})
    client.post("/interviews/create", data={"stakeholder_id": "1"})
    client.post("/interview_qa/create", data={"interview_id": "1", "question": "Старый", "answer": "A"})
    html = client.get("/interviews/1").get_data(as_text=True)
    assert "Старый" in html and 'form="qa-1"' in html and "Сохранить" in html
    # правка на месте
    client.post("/interview_qa/edit/1", data={"interview_id": "1", "question": "Новый", "answer": "B2"})
    assert _scalar("SELECT question FROM interview_qa WHERE id=1") == "Новый"
    assert _scalar("SELECT answer FROM interview_qa WHERE id=1") == "B2"


def test_interview_qa_read_only_for_anonymous(anon_client):
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    con.execute("INSERT INTO stakeholder (last_name, first_name, type_id, priority) VALUES ('П', 'И', 1, 3)")
    con.execute("INSERT INTO interview (stakeholder_id) VALUES (1)")
    con.execute("INSERT INTO interview_qa (interview_id, question, answer) VALUES (1, 'Вопрос читателя', 'Ответ')")
    con.commit()
    con.close()
    html = anon_client.get("/interviews/1").get_data(as_text=True)
    assert "Вопрос читателя" in html and "Ответ" in html
    assert 'form="qa-' not in html
