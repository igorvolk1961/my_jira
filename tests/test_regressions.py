"""Регрессионные тесты по итогам код-ревью (XSS, каскад удаления, стейкхолдеры)."""

import sqlite3

import main


def _scalar(query: str):
    con = sqlite3.connect(main.db_path_for("pytest_verify.db"))
    try:
        return con.execute(query).fetchone()[0]
    finally:
        con.close()


def test_requirement_description_is_escaped(seeded):
    payload = "<script>alert(1)</script>"
    seeded.post(
        "/requirements/edit/1",
        data={
            "project_id": "1",
            "requirement_type_id": "1",
            "description": payload,
            "priority_id": "1",
            "acceptance_criteria": payload,
        },
    )
    for url in ("/requirements", "/requirements/1", "/projects/1"):
        body = seeded.get(url).text
        assert payload not in body, url
        assert "&lt;script&gt;" in body, url


def test_task_delete_soft_deletes_subtasks(seeded):
    seeded.post(
        "/subtasks/create", data={"parent_task_id": "1", "description": "S1", "priority_id": "1", "status_id": "1"}
    )
    parent_id = _scalar("SELECT id FROM subtask WHERE description='S1'")
    seeded.post(
        "/subtasks/create",
        data={
            "parent_task_id": "1",
            "parent_subtask_id": str(parent_id),
            "description": "S1-nested",
            "priority_id": "1",
            "status_id": "1",
        },
    )
    seeded.get("/tasks/delete/1")
    # legacy task_delete: UPDATE subtask SET is_deleted=1 WHERE parent_task_id=<task>
    assert _scalar("SELECT COUNT(*) FROM subtask WHERE description='S1' AND is_deleted=0") == 0
    assert _scalar("SELECT COUNT(*) FROM subtask WHERE description='S1-nested' AND is_deleted=0") == 0


def test_employee_delete_keeps_linked_stakeholder(seeded):
    employee_id = _scalar("SELECT id FROM employee WHERE last_name='Сидоров' AND is_deleted=0")
    seeded.post(
        f"/employees/edit/{employee_id}",
        data={
            "last_name": "Сидоров",
            "first_name": "Иван",
            "position_type_id": "1",
            "status_id": "1",
            "is_stackholder": "1",
        },
    )
    stakeholder_id = _scalar(f"SELECT id FROM stakeholder WHERE employee_id={employee_id} AND is_deleted=0")
    assert stakeholder_id
    seeded.get(f"/employees/delete/{employee_id}")
    assert _scalar(f"SELECT COUNT(*) FROM stakeholder WHERE id={stakeholder_id} AND is_deleted=0") == 1
