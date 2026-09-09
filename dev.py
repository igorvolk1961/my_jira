"""
Разработка/тестирование на ОТДЕЛЬНОЙ БД.

Никогда не трогает рабочую БД (data/upo_database.db):
  - имя тестовой БД задаётся через env UPO_DATABASE до импорта main,
  - после прогона удаляется только тестовый файл.
Запуск:  .venv/bin/python dev.py
"""

import os
import sys

TEST_DB = 'dev_verify.db'
os.environ['UPO_DATABASE'] = TEST_DB  # до импорта main! -> DEFAULT_DB_NAME = TEST_DB

import main  # noqa: E402
from main import app  # noqa: E402


def smoke():
    main.init_db()
    c = app.test_client()

    # Справочники
    assert c.get('/priorities').status_code == 200
    assert c.get('/position_types').status_code == 200

    # Стейкхолдер + проект (главный стейкхолдер)
    r = c.post('/stakeholders/create', data={
        'last_name': 'Петров', 'first_name': 'Иван', 'position': 'Директор',
        'type_id': '1', 'priority': '5',
    })
    assert r.status_code in (200, 302) and c.get('/stakeholders').get_data(as_text=True).count('Петров') >= 1

    r = c.post('/projects/create', data={
        'name': 'Тестовый проект', 'priority_id': '1', 'main_stakeholder_id': '1',
    })
    assert r.status_code in (200, 302)
    assert 'Стейкхолдеры (1)' in c.get('/projects/1').get_data(as_text=True)

    # Требование -> этап -> задача -> подзадача -> назначение
    c.post('/requirements/create', data={'project_id': '1', 'requirement_type_id': '1',
                                         'description': 'Требование', 'priority_id': '1'})
    c.post('/project_stages/create', data={'project_id': '1', 'stage_type_id': '1', 'status_id': '1'})
    c.post('/tasks/create', data={'requirement_id': '1', 'description': 'Задача', 'stage_id': '1',
                                  'priority_id': '1', 'status_id': '1'})
    c.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'Подзадача',
                                     'priority_id': '1', 'status_id': '1'})
    c.post('/employees/create', data={'last_name': 'Сидоров', 'first_name': 'Иван',
                                      'position_type_id': '1', 'status_id': '1'})
    c.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'task',
                                             'employee_id': '1', 'share': '1.0'})

    # Детальные страницы и переходы по ссылкам
    assert c.get('/projects/1').status_code == 200
    assert c.get('/tasks/1').status_code == 200
    assert c.get('/employees/1').status_code == 200

    # Интервью + вопрос-ответ + экспорт Markdown
    c.post('/interviews/create', data={'stakeholder_id': '1', 'scheduled_at': '2026-01-01T10:00'})
    c.post('/interview_qa/create', data={'interview_id': '1', 'question': 'Вопрос', 'answer': 'Ответ'})
    assert c.get('/interviews/1').status_code == 200
    exp = c.get('/interviews/1/export')
    assert exp.status_code == 200 and exp.headers.get('Content-Type', '').startswith('text/markdown')

    # Отчёты, БД
    for p in ['/reports/projects', '/reports/tasks', '/reports/employees', '/database']:
        assert c.get(p).status_code == 200

    print('OK: проверки пройдены на тестовой БД "%s"' % TEST_DB)


if __name__ == '__main__':
    try:
        smoke()
    except AssertionError as e:
        print('FAIL:', e)
        sys.exit(1)
    finally:
        p = main.db_path_for(TEST_DB)
        for suf in ('', '-wal', '-shm'):
            if os.path.exists(p + suf):
                os.remove(p + suf)
        print('Тестовая БД удалена, рабочая БД не затронута.')
