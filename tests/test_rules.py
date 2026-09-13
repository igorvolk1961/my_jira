"""Проверка бизнес-правил: обязательные поля, загрузка ≤100%, один исполнитель подзадачи,
поглощение родителя подзадачей, каскадное удаление, идемпотентность справочников."""

import sqlite3

import main

TEST_DB = 'pytest_verify.db'


def _q(sql, params=()):
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _scalar(sql, params=()):
    rows = _q(sql, params)
    return rows[0][0] if rows else None


def _mk_project(client):
    client.post('/stakeholders/create', data={'last_name': 'S', 'first_name': 'S', 'type_id': '1', 'priority': '3'})
    client.post('/projects/create', data={'name': 'P', 'priority_id': '1'})
    client.post('/requirements/create', data={'project_id': '1', 'requirement_type_id': '1', 'description': 'R', 'priority_id': '1'})
    client.post('/project_stages/create', data={'project_id': '1', 'stage_type_id': '1', 'status_id': '1'})
    client.post('/employees/create', data={'last_name': 'E', 'first_name': 'E', 'position_type_id': '1', 'status_id': '1'})
    client.post('/projects/1/add_employee', data={'employee_id': '1'})


def test_task_requires_stage_requirement_and_type(client):
    client.post('/stakeholders/create', data={'last_name': 'S', 'first_name': 'S', 'type_id': '1', 'priority': '3'})
    client.post('/projects/create', data={'name': 'P', 'priority_id': '1'})
    client.post('/requirements/create', data={'project_id': '1', 'requirement_type_id': '1', 'description': 'R', 'priority_id': '1'})
    client.post('/project_stages/create', data={'project_id': '1', 'stage_type_id': '1', 'status_id': '1'})
    # без типа
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T', 'stage_id': '1', 'priority_id': '1', 'status_id': '1'})
    # без требования
    client.post('/tasks/create', data={'description': 'T', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    # без этапа
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    assert _scalar('SELECT COUNT(*) FROM task') == 0
    # с полным набором
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    assert _scalar('SELECT COUNT(*) FROM task') == 1


def test_one_executor_per_subtask(client):
    _mk_project(client)
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    client.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'S', 'priority_id': '1', 'status_id': '1'})
    client.post('/employees/create', data={'last_name': 'E2', 'first_name': 'E', 'position_type_id': '1', 'status_id': '1'})
    client.post('/projects/1/add_employee', data={'employee_id': '2'})
    client.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'subtask', 'employee_id': '1', 'share': '1.0'})
    client.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'subtask', 'employee_id': '2', 'share': '1.0'})
    rows = _q("SELECT employee_id FROM task_assignment WHERE task_id=1 AND task_kind='subtask' AND is_deleted=0")
    assert len(rows) == 1
    assert rows[0]['employee_id'] == 2  # замена


def test_employee_load_not_over_100(client):
    _mk_project(client)
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T1', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T2', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    client.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'task', 'employee_id': '1', 'share': '1.0'})
    client.post('/task_assignments/create', data={'task_id': '2', 'task_kind': 'task', 'employee_id': '1', 'share': '0.5'})
    total = _scalar("SELECT COALESCE(SUM(share),0) FROM task_assignment WHERE employee_id=1 AND is_deleted=0")
    assert round(total, 2) <= 1.0
    # вторая задача не создана
    assert _scalar('SELECT COUNT(*) FROM task_assignment WHERE task_id=2') == 0


def test_subtask_covers_parent_load(client):
    _mk_project(client)
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    client.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'S', 'priority_id': '1', 'status_id': '1'})
    client.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'task', 'employee_id': '1', 'share': '1.0'})
    # назначение на подзадачу разрешено (она покрывает родителя)
    client.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'subtask', 'employee_id': '1', 'share': '1.0'})
    # эффективная загрузка = 100% (не 200%)
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    con.row_factory = sqlite3.Row
    covered = main._covered_for_employee(con, 1)
    rows = con.execute("SELECT task_id, task_kind, share FROM task_assignment WHERE employee_id=1 AND is_deleted=0").fetchall()
    con.close()
    eff = sum(r['share'] for r in rows if (r['task_kind'], r['task_id']) not in covered)
    assert round(eff, 2) == 1.0


def test_cascade_task_delete(client):
    _mk_project(client)
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    client.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'S', 'priority_id': '1', 'status_id': '1'})
    client.get('/tasks/delete/1')
    assert _scalar('SELECT COUNT(*) FROM task WHERE id=1 AND is_deleted=0') == 0
    assert _scalar('SELECT COUNT(*) FROM subtask WHERE parent_task_id=1 AND is_deleted=0') == 0


def test_task_type_seeded_and_idempotent(client):
    assert _scalar('SELECT COUNT(*) FROM task_type WHERE is_deleted=0') == 6
    main.init_db()  # повторный запуск не должен дублировать
    assert _scalar('SELECT COUNT(*) FROM task_type') == 6
    assert _scalar("SELECT COUNT(*) FROM task_type WHERE name='Код-ревью'") == 1
