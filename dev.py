"""
Разработка/тестирование на ОТДЕЛЬНОЙ БД.

Никогда не трогает рабочую БД (data/upo_database.db):
  - имя тестовой БД задаётся через env UPO_DATABASE до импорта main,
  - после прогона удаляется только тестовый файл.
Запуск:  .venv/bin/python dev.py
"""

import os
import shutil
import sqlite3
import sys

TEST_DB = 'dev_verify.db'
os.environ['UPO_DATABASE'] = TEST_DB  # до импорта main! -> DEFAULT_DB_NAME = TEST_DB
os.environ['UPO_AUDIO_DIR'] = os.path.join('data', 'dev_verify_audio')  # изоляция аудио теста

import main  # noqa: E402
from main import app  # noqa: E402


def smoke():
    main.init_db()
    c = app.test_client()
    c.post('/login', data={'login': 'admin', 'password': '12345'})

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
                                  'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
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

    # Шаблоны интервью: предзаполненный, интервью по шаблону, шаблон из интервью
    assert c.get('/interview_templates').status_code == 200
    tpl_id = None
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    row = con.execute("SELECT id FROM interview_template WHERE name='Вопросы Заказчику' AND is_deleted=0").fetchone()
    tpl_id = row[0] if row else None
    tpl_q = con.execute("SELECT COUNT(*) FROM interview_template_question WHERE template_id=? AND is_deleted=0",
                        (tpl_id,)).fetchone()[0] if tpl_id else 0
    con.close()
    assert tpl_id and tpl_q >= 25
    c.post('/interviews/create', data={'stakeholder_id': '1', 'template_id': str(tpl_id)})
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    iv_id = con.execute("SELECT id FROM interview ORDER BY id DESC LIMIT 1").fetchone()[0]
    copied = con.execute("SELECT COUNT(*) FROM interview_qa WHERE interview_id=? AND is_deleted=0", (iv_id,)).fetchone()[0]
    con.close()
    assert copied == tpl_q
    c.post('/interviews/1/save_as_template', data={'name': 'Шаблон из smoke'})
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    made = con.execute("SELECT COUNT(*) FROM interview_template WHERE name='Шаблон из smoke' AND is_deleted=0").fetchone()[0]
    con.close()
    assert made == 1

    # Аудио + транскрипт с посегментными таймкодами
    import io
    r = c.post('/interviews/1/audio', data={'file': (io.BytesIO(b'RIFFfake'), 'rec.wav')},
               content_type='multipart/form-data')
    assert r.status_code in (200, 302)
    assert 'rec.wav' in c.get('/interviews/1').get_data(as_text=True)
    assert c.get('/interviews/audio/1').status_code == 200

    # Транскрипт: сегменты создаём напрямую (импорт SRT/VTT/TXT из UI убран)
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    con.execute("INSERT INTO transcript_segment (interview_id, start_ms, end_ms, text) VALUES (1, 1000, 4000, 'Hello')")
    con.execute("INSERT INTO transcript_segment (interview_id, start_ms, end_ms, text) VALUES (1, 5000, 7500, 'World')")
    con.commit()
    con.close()
    html = c.get('/interviews/1').get_data(as_text=True)
    assert 'Hello' in html and 'World' in html and '00:01' in html and '00:05' in html

    # пакетное редактирование транскрипта одной отправкой
    assert c.get('/interviews/1/transcript/edit').status_code == 200
    c.post('/interviews/1/transcript/save', data={
        'text_1': 'Hello edited', 'speaker_1': 'Интервьюер',
        'text_2': 'World', 'speaker_2': ''})
    html = c.get('/interviews/1').get_data(as_text=True)
    assert 'Hello edited' in html and 'Интервьюер' in html

    # /transcribe не должен падать (движок может быть недоступен, аудио — фиктивное)
    r = c.post('/interviews/1/transcribe', data={}, follow_redirects=True)
    assert r.status_code == 200

    # Отчёты, БД
    for p in ['/reports/projects', '/reports/tasks', '/reports/employees', '/database']:
        assert c.get(p).status_code == 200

    # Копирование БД (без автоматического удаления данных)
    copy_path = main.db_path_for('dev_copy.db')
    assert c.post('/database/copy', data={'source': TEST_DB, 'name': 'dev_copy'}).status_code in (200, 302)
    assert os.path.exists(copy_path)
    con = sqlite3.connect(copy_path)
    assert con.execute("SELECT COUNT(*) FROM project").fetchone()[0] >= 1
    assert con.execute("SELECT COUNT(*) FROM app_user WHERE is_deleted=0").fetchone()[0] >= 1
    con.close()
    for suffix in ('', '-wal', '-shm'):
        if os.path.exists(copy_path + suffix):
            os.remove(copy_path + suffix)

    # Аутентификация, роли, аудит, чат, настройки, разделы
    assert c.get('/chat').status_code == 200
    assert c.get('/audit').status_code == 200
    assert c.get('/settings').status_code == 200
    assert c.get('/tasks_admin').status_code == 200
    for tab in ('unassigned', 'not_accepted', 'overdue'):
        assert c.get('/tasks_admin?tab=' + tab).status_code == 200
    r = c.post('/register', data={'login': 'dev_user', 'password': 'pw', 'last_name': 'Дев',
                                  'first_name': 'Юзер', 'middle_name': 'Тест'})
    assert r.status_code in (200, 302)
    c.get('/logout')
    c.post('/login', data={'login': 'dev_user', 'password': 'pw'})
    assert c.get('/my_tasks').status_code == 200
    c.post('/chat/post', data={'text': 'сообщение из smoke'})
    assert 'сообщение из smoke' in c.get('/chat').get_data(as_text=True)
    assert c.get('/tasks_admin').status_code == 302  # пользователю нельзя
    c.get('/logout')
    c.post('/login', data={'login': 'admin', 'password': '12345'})
    assert 'task_create' in c.get('/audit').get_data(as_text=True)

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
        shutil.rmtree(main.AUDIO_DIR, ignore_errors=True)
        print('Тестовая БД удалена, рабочая БД не затронута.')
