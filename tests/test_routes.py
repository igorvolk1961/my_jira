"""Дымовые проверки страниц: списки, детальные, отчёты."""

LIST_PAGES = [
    '/', '/priorities', '/stakeholder_types', '/stakeholders', '/requirement_types',
    '/projects', '/requirements', '/position_types', '/employee_statuses', '/employees',
    '/stage_types', '/stage_statuses', '/project_stages', '/task_statuses', '/task_types',
    '/tasks', '/subtasks', '/task_assignments', '/events', '/interviews', '/database',
]

REPORT_PAGES = [
    '/reports/projects', '/reports/stakeholders', '/reports/employees', '/reports/requirements',
    '/reports/stages', '/reports/tasks', '/reports/subtasks', '/reports/assignments', '/reports/events',
]


def test_list_pages_return_200(client):
    for p in LIST_PAGES:
        assert client.get(p).status_code == 200, p


def test_reports_return_200(client):
    for p in REPORT_PAGES:
        assert client.get(p).status_code == 200, p


def test_create_forms_render(client):
    for p in ['/priorities/create', '/stakeholders/create', '/projects/create',
              '/requirements/create', '/tasks/create', '/subtasks/create',
              '/employees/create', '/interviews/create', '/task_types/create']:
        assert client.get(p).status_code == 200, p


def test_detail_pages_render(seeded):
    for p in ['/projects/1', '/stakeholders/1', '/tasks/1', '/requirements/1', '/employees/1']:
        assert seeded.get(p).status_code == 200, p


def test_details_after_full_seed(client):
    # полный набор: подзадача, сотрудник, назначение, событие, интервью
    client.post('/stakeholders/create', data={'last_name': 'П', 'first_name': 'И', 'type_id': '1', 'priority': '3'})
    client.post('/projects/create', data={'name': 'П', 'priority_id': '1'})
    client.post('/requirements/create', data={'project_id': '1', 'requirement_type_id': '1', 'description': 'R', 'priority_id': '1'})
    client.post('/project_stages/create', data={'project_id': '1', 'stage_type_id': '1', 'status_id': '1'})
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    client.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'S', 'priority_id': '1', 'status_id': '1'})
    client.post('/employees/create', data={'last_name': 'С', 'first_name': 'И', 'position_type_id': '1', 'status_id': '1'})
    client.post('/projects/1/add_employee', data={'employee_id': '1'})
    client.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'task', 'employee_id': '1', 'share': '1.0'})
    client.post('/events/create', data={'description': 'E'})
    client.post('/interviews/create', data={'stakeholder_id': '1', 'scheduled_at': '2026-01-01T10:00'})
    for p in ['/subtasks/1', '/task_assignments/1', '/events/1', '/interviews/1']:
        assert client.get(p).status_code == 200, p
