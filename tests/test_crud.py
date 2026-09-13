"""CRUD по справочникам и основным сущностям."""


def test_priority_crud(client):
    client.post('/priorities/create', data={'name': 'Критичный', 'weight': '5'})
    assert 'Критичный' in client.get('/priorities').get_data(as_text=True)
    client.post('/priorities/edit/1', data={'name': 'Очень низкий', 'weight': '1'})
    assert 'Очень низкий' in client.get('/priorities').get_data(as_text=True)


def test_task_type_crud(client):
    client.post('/task_types/create', data={'name': 'Рефакторинг'})
    assert 'Рефакторинг' in client.get('/task_types').get_data(as_text=True)
    client.post('/task_types/edit/1', data={'name': 'Новый функционал X'})
    assert 'Новый функционал X' in client.get('/task_types').get_data(as_text=True)


def test_stakeholder_crud(client):
    client.post('/stakeholders/create', data={'last_name': 'Иванов', 'first_name': 'И', 'type_id': '1', 'priority': '3'})
    assert 'Иванов' in client.get('/stakeholders').get_data(as_text=True)
    client.post('/stakeholders/edit/1', data={'last_name': 'Иванов2', 'first_name': 'И', 'type_id': '1', 'priority': '3'})
    assert 'Иванов2' in client.get('/stakeholders').get_data(as_text=True)
    client.get('/stakeholders/delete/1')
    assert 'Иванов2' not in client.get('/stakeholders').get_data(as_text=True)


def test_project_requirement_stage_task_flow(client):
    client.post('/projects/create', data={'name': 'Проект X', 'priority_id': '1'})
    client.post('/requirements/create', data={'project_id': '1', 'requirement_type_id': '1', 'description': 'Req', 'priority_id': '1'})
    client.post('/project_stages/create', data={'project_id': '1', 'stage_type_id': '1', 'status_id': '1'})
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'Task', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    html = client.get('/projects/1').get_data(as_text=True)
    assert 'Проект X' in html and 'Требования (1)' in html and 'Этапы (1)' in html


def test_subtask_edit_delete(client):
    client.post('/projects/create', data={'name': 'P', 'priority_id': '1'})
    client.post('/requirements/create', data={'project_id': '1', 'requirement_type_id': '1', 'description': 'R', 'priority_id': '1'})
    client.post('/project_stages/create', data={'project_id': '1', 'stage_type_id': '1', 'status_id': '1'})
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T', 'stage_id': '1', 'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    client.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'S', 'priority_id': '1', 'status_id': '1'})
    assert 'S' in client.get('/subtasks').get_data(as_text=True)
    client.post('/subtasks/edit/1', data={'parent_task_id': '1', 'description': 'S2', 'priority_id': '1', 'status_id': '1'})
    assert 'S2' in client.get('/subtasks').get_data(as_text=True)


def test_employee_crud(client):
    client.post('/employees/create', data={'last_name': 'Сидоров', 'first_name': 'И', 'position_type_id': '1', 'status_id': '1'})
    assert 'Сидоров' in client.get('/employees').get_data(as_text=True)
    client.post('/employees/edit/1', data={'last_name': 'Сидоров2', 'first_name': 'И', 'position_type_id': '1', 'status_id': '1'})
    assert 'Сидоров2' in client.get('/employees').get_data(as_text=True)


def test_event_crud(client):
    client.post('/events/create', data={'description': 'Форс-мажор', 'decision': 'Решили'})
    assert 'Форс-мажор' in client.get('/events').get_data(as_text=True)
