"""
Учебный проектный офис (УПО) - приложение для управления проектами, 
задачами и персоналом.
Для ролевых игр на курсах системных аналитиков
"""

from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify, session, send_file
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime, date
from io import BytesIO
import html
import json
import os
import re
import shutil

app = Flask(__name__)
app.secret_key = os.environ.get('UPO_SECRET_KEY', 'upo_secret_key_2026')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, 'data')
DEFAULT_DB_NAME = os.environ.get('UPO_DATABASE', 'upo_database.db')
AUDIO_DIR = os.environ.get('UPO_AUDIO_DIR', os.path.join(DATABASE_DIR, 'audio'))
os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

def db_path_for(name):
    return os.path.join(DATABASE_DIR, name)

def current_db_name():
    return session.get('db_name', DEFAULT_DB_NAME)

# ==================== ИНИЦИАЛИЗАЦИЯ БД ====================

def get_db():
    db = sqlite3.connect(db_path_for(current_db_name()))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def backup_db(path=None):
    """Создаёт резервную копию существующей (уже инициализированной) БД в data/backups/."""
    path = path or db_path_for(DEFAULT_DB_NAME)
    if not os.path.exists(path):
        return
    try:
        con = sqlite3.connect(path)
        has = con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='priority'").fetchone()[0]
        con.close()
        if not has:
            return
        bdir = os.path.join(DATABASE_DIR, 'backups')
        os.makedirs(bdir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = os.path.join(bdir, f'{os.path.basename(path)}_{ts}.db')
        shutil.copy2(path, dest)
        for old in sorted(os.listdir(bdir)):
            if len(os.listdir(bdir)) > 20:
                os.remove(os.path.join(bdir, old))
    except Exception:
        pass

def init_db(path=None):
    """Создание таблиц и начальное заполнение справочников"""
    backup_db(path)
    db = sqlite3.connect(path or db_path_for(DEFAULT_DB_NAME))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    
    # Создание таблиц
    db.executescript('''
        -- Приоритеты
        CREATE TABLE IF NOT EXISTS priority (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            weight INTEGER NOT NULL CHECK(weight BETWEEN 1 AND 5),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Типы стейкхолдеров
        CREATE TABLE IF NOT EXISTS stakeholder_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            influence_priority INTEGER NOT NULL CHECK(influence_priority BETWEEN 1 AND 5),
            interest_priority INTEGER NOT NULL CHECK(interest_priority BETWEEN 1 AND 5),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Стейкхолдеры
        CREATE TABLE IF NOT EXISTS stakeholder (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            type_id INTEGER NOT NULL REFERENCES stakeholder_type(id),
            position TEXT,
            priority INTEGER NOT NULL DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
            employee_id INTEGER REFERENCES employee(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Типы требований
        CREATE TABLE IF NOT EXISTS requirement_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Проекты
        CREATE TABLE IF NOT EXISTS project (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            main_stakeholder_id INTEGER REFERENCES stakeholder(id),
            cost REAL,
            mvp_deadline DATE,
            deadline DATE,
            priority_id INTEGER NOT NULL REFERENCES priority(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Требования
        CREATE TABLE IF NOT EXISTS requirement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
            stakeholder_id INTEGER REFERENCES stakeholder(id),
            requirement_type_id INTEGER NOT NULL REFERENCES requirement_type(id),
            description TEXT NOT NULL,
            priority_id INTEGER NOT NULL REFERENCES priority(id),
            acceptance_criteria TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Типы должностей
        CREATE TABLE IF NOT EXISTS position_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Статусы сотрудников
        CREATE TABLE IF NOT EXISTS employee_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_available INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Сотрудники
        CREATE TABLE IF NOT EXISTS employee (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            position_type_id INTEGER NOT NULL REFERENCES position_type(id),
            status_id INTEGER NOT NULL REFERENCES employee_status(id),
            subordinates_total INTEGER NOT NULL DEFAULT 0,
            subordinates_available INTEGER NOT NULL DEFAULT 0,
            is_stackholder INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Типы этапов проекта
        CREATE TABLE IF NOT EXISTS project_stage_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Статусы этапов проекта
        CREATE TABLE IF NOT EXISTS project_stage_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Этапы проекта
        CREATE TABLE IF NOT EXISTS project_stage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
            stage_type_id INTEGER NOT NULL REFERENCES project_stage_type(id),
            status_id INTEGER NOT NULL REFERENCES project_stage_status(id),
            planned_end DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Статусы задач
        CREATE TABLE IF NOT EXISTS task_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );

        -- Типы задач
        CREATE TABLE IF NOT EXISTS task_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Задачи
        CREATE TABLE IF NOT EXISTS task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_id INTEGER REFERENCES requirement(id) ON DELETE SET NULL,
            description TEXT NOT NULL,
            stage_id INTEGER REFERENCES project_stage(id),
            task_type_id INTEGER REFERENCES task_type(id),
            priority_id INTEGER NOT NULL REFERENCES priority(id),
            deadline DATE,
            status_id INTEGER NOT NULL REFERENCES task_status(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Подзадачи
        CREATE TABLE IF NOT EXISTS subtask (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_task_id INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
            parent_subtask_id INTEGER REFERENCES subtask(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            stage_id INTEGER REFERENCES project_stage(id),
            priority_id INTEGER NOT NULL REFERENCES priority(id),
            deadline DATE,
            status_id INTEGER NOT NULL REFERENCES task_status(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Назначения задач
        CREATE TABLE IF NOT EXISTS task_assignment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            task_kind TEXT NOT NULL CHECK(task_kind IN ('task','subtask')),
            employee_id INTEGER NOT NULL REFERENCES employee(id),
            share REAL NOT NULL CHECK(share BETWEEN 0 AND 1),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0,
            UNIQUE(task_id, task_kind, employee_id)
        );
        
        -- События
        CREATE TABLE IF NOT EXISTS event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            description TEXT NOT NULL,
            decision TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Стейкхолдеры проекта (явная связь проект <-> стейкхолдер)
        CREATE TABLE IF NOT EXISTS project_stakeholder (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
            stakeholder_id INTEGER NOT NULL REFERENCES stakeholder(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0,
            UNIQUE(project_id, stakeholder_id)
        );

        -- Исполнители проекта (явная связь проект <-> сотрудник)
        CREATE TABLE IF NOT EXISTS project_employee (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
            employee_id INTEGER NOT NULL REFERENCES employee(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0,
            UNIQUE(project_id, employee_id)
        );

        -- Комментарии к задачам и подзадачам
        CREATE TABLE IF NOT EXISTS comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('task', 'subtask')),
            entity_id INTEGER NOT NULL,
            author TEXT,
            text TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );

        -- Интервью стейкхолдеров
        CREATE TABLE IF NOT EXISTS interview (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stakeholder_id INTEGER NOT NULL REFERENCES stakeholder(id),
            scheduled_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        
        -- Вопросы и ответы в интервью
        CREATE TABLE IF NOT EXISTS interview_qa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interview_id INTEGER NOT NULL REFERENCES interview(id) ON DELETE CASCADE,
            question TEXT NOT NULL,
            answer TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );

        -- Аудиозаписи интервью (диктофон/загрузка/экспорт из Buzz)
        CREATE TABLE IF NOT EXISTS interview_audio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interview_id INTEGER NOT NULL REFERENCES interview(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            original_name TEXT,
            mime TEXT,
            duration_ms INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );

        -- Транскрипт интервью по сегментам (посегментные таймкоды + метка спикера)
        CREATE TABLE IF NOT EXISTS transcript_segment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interview_id INTEGER NOT NULL REFERENCES interview(id) ON DELETE CASCADE,
            audio_id INTEGER REFERENCES interview_audio(id),
            start_ms INTEGER NOT NULL DEFAULT 0,
            end_ms INTEGER NOT NULL DEFAULT 0,
            speaker TEXT,
            text TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_seg_interview ON transcript_segment(interview_id, start_ms);
    ''')
    
    # Миграции для существующих БД (добавление новых колонок)
    scols = [r[1] for r in db.execute("PRAGMA table_info(stakeholder)").fetchall()]
    if 'employee_id' not in scols:
        db.execute("ALTER TABLE stakeholder ADD COLUMN employee_id INTEGER REFERENCES employee(id)")
    ecols = [r[1] for r in db.execute("PRAGMA table_info(employee)").fetchall()]
    if 'is_stackholder' not in ecols:
        db.execute("ALTER TABLE employee ADD COLUMN is_stackholder INTEGER NOT NULL DEFAULT 0")
    subcols = [r[1] for r in db.execute("PRAGMA table_info(subtask)").fetchall()]
    if 'parent_subtask_id' not in subcols:
        db.execute("ALTER TABLE subtask ADD COLUMN parent_subtask_id INTEGER REFERENCES subtask(id)")
    tcols = [r[1] for r in db.execute("PRAGMA table_info(task)").fetchall()]
    if 'task_type_id' not in tcols:
        db.execute("ALTER TABLE task ADD COLUMN task_type_id INTEGER REFERENCES task_type(id)")
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_one_executor_per_subtask ON task_assignment(task_id) WHERE task_kind='subtask' AND is_deleted=0")
    except sqlite3.IntegrityError:
        pass

    # Типы задач: отдельное наполнение (для существующих БД, где основные справочники уже есть)
    for ttype in ('Новый функционал', 'Исправление ошибки', 'Улучшение',
                  'Документирование', 'Тестирование', 'Код-ревью'):
        db.execute("INSERT OR IGNORE INTO task_type (name) VALUES (?)", (ttype,))
    db.commit()
    
    # Начальное заполнение справочников
    if db.execute("SELECT COUNT(*) FROM priority").fetchone()[0] == 0:
        priorities = [
            ('Низкий', 1), ('Ниже среднего', 2), ('Средний', 3),
            ('Выше среднего', 4), ('Высокий', 5)
        ]
        db.executemany("INSERT INTO priority (name, weight) VALUES (?, ?)", priorities)
        
        stakeholder_types = [
            ('Инвестор', 5, 3), ('Бизнес-заказчик', 5, 5),
            ('Конечный пользователь', 2, 5), ('Разработчик', 3, 4),
            ('Ответственный за безопасность', 4, 3),
            ('Юрист / комплаенс', 4, 2), ('Эксплуатация / поддержка', 3, 4)
        ]
        db.executemany("INSERT INTO stakeholder_type (name, influence_priority, interest_priority) VALUES (?, ?, ?)",
                      stakeholder_types)
        
        req_types = ['Бизнес-требование', 'Пользовательское требование',
                    'Функциональное требование', 'Нефункциональное требование']
        db.executemany("INSERT INTO requirement_type (name) VALUES (?)", [(t,) for t in req_types])
        
        stage_types = [
            ('Инициация', 1), ('Анализ', 2), ('Проектирование', 3),
            ('Разработка', 4), ('Тестирование', 5), ('Внедрение', 6), ('Закрытие', 7)
        ]
        db.executemany("INSERT INTO project_stage_type (name, sort_order) VALUES (?, ?)", stage_types)
        
        stage_statuses = [
            ('Не начат', 'gray'), ('В работе', 'blue'), ('На паузе', 'yellow'),
            ('Завершён', 'green'), ('Отменён', 'red')
        ]
        db.executemany("INSERT INTO project_stage_status (name, color) VALUES (?, ?)", stage_statuses)
        
        position_types = [
            'Системный аналитик', 'Архитектор', 'Начальник тех. отдела',
            'Юрист', 'Ведущий бэкендер', 'Ведущий фронтендер',
            'QA-инженер', 'DevOps', 'Аналитик данных',
            'Менеджер проекта', 'Дизайнер', 'Специалист по информационной безопасности'
        ]
        db.executemany("INSERT INTO position_type (name) VALUES (?)", [(p,) for p in position_types])
        
        emp_statuses = [
            ('Работает', 1), ('В командировке', 0), ('Болеет', 0),
            ('В отпуске', 0), ('Уволен', 0)
        ]
        db.executemany("INSERT INTO employee_status (name, is_available) VALUES (?, ?)", emp_statuses)
        
        task_statuses = [
            ('Новая', 'gray'), ('В работе', 'blue'), ('На проверке', 'yellow'),
            ('Выполнена', 'green'), ('Отменена', 'red'), ('Заблокирована', 'orange')
        ]
        db.executemany("INSERT INTO task_status (name, color) VALUES (?, ?)", task_statuses)
        
        db.commit()
    
    db.close()

# ==================== СИНХРОНИЗАЦИЯ «СОТРУДНИК <-> СТЕЙКХОЛДЕР-РАЗРАБОТЧИК» ====================

def _developer_type_id(db):
    row = db.execute("SELECT id FROM stakeholder_type WHERE lower(name)=lower('Разработчик') AND is_deleted=0").fetchone()
    if row:
        return row[0]
    cur = db.execute("INSERT INTO stakeholder_type (name, influence_priority, interest_priority) VALUES (?, ?, ?)",
                     ('Разработчик', 3, 3))
    return cur.lastrowid

def _employee_position_name(db, employee):
    row = db.execute("SELECT name FROM position_type WHERE id=?", (employee['position_type_id'],)).fetchone()
    return row[0] if row else None

def _reset_employee_stackholder_if_unlinked(db, eid):
    if not eid:
        return
    cnt = db.execute("SELECT COUNT(*) FROM stakeholder WHERE employee_id=? AND is_deleted=0", (eid,)).fetchone()[0]
    if cnt == 0:
        db.execute("UPDATE employee SET is_stackholder=0 WHERE id=? AND is_deleted=0", (eid,))

def sync_stakeholder_for_employee(db, eid, active):
    """Синхронизирует связанного стейкхолдера-«разработчика» с флагом is_stackholder сотрудника.
    Вызывается только из обработчиков сотрудника; не вызывает другие обработчики (нет рекурсии)."""
    emp = db.execute("SELECT * FROM employee WHERE id=? AND is_deleted=0", (eid,)).fetchone()
    if not emp:
        return
    linked = db.execute("SELECT id FROM stakeholder WHERE employee_id=? AND is_deleted=0", (eid,)).fetchall()
    if active:
        pos = _employee_position_name(db, emp)
        if linked:
            for ex in linked:
                db.execute("""UPDATE stakeholder SET last_name=?, first_name=?, middle_name=?, position=?, type_id=?,
                              updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                           (emp['last_name'], emp['first_name'], emp['middle_name'], pos, _developer_type_id(db), ex['id']))
        else:
            db.execute("""INSERT INTO stakeholder (last_name, first_name, middle_name, type_id, position, priority, employee_id)
                          VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       (emp['last_name'], emp['first_name'], emp['middle_name'],
                        _developer_type_id(db), pos, 3, eid))
    else:
        for ex in linked:
            db.execute("UPDATE stakeholder SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (ex['id'],))

def _subtask_ancestors(db, sid):
    """Предки подзадачи: (родительская задача, цепочка родительских подзадач)."""
    res = []
    cur = db.execute("SELECT parent_task_id, parent_subtask_id FROM subtask WHERE id=? AND is_deleted=0", (sid,)).fetchone()
    if not cur:
        return res
    res.append(('task', cur['parent_task_id']))
    p = cur['parent_subtask_id']
    while p:
        res.append(('subtask', p))
        pc = db.execute("SELECT parent_subtask_id FROM subtask WHERE id=? AND is_deleted=0", (p,)).fetchone()
        p = pc['parent_subtask_id'] if pc else None
    return res

def _covered_for_employee(db, emp_id):
    """Позиции (kind, id), где сотрудник занят в подзадаче, поэтому его занятость в предке не учитывается."""
    covered = set()
    for r in db.execute("SELECT task_id FROM task_assignment WHERE employee_id=? AND task_kind='subtask' AND is_deleted=0", (emp_id,)):
        for anc in _subtask_ancestors(db, r['task_id']):
            covered.add(anc)
    return covered

def _employee_effective_load(db, emp_id, exclude_assignment_id=0):
    covered = _covered_for_employee(db, emp_id)
    rows = db.execute("SELECT task_id, task_kind, share FROM task_assignment WHERE employee_id=? AND is_deleted=0 AND id<>?",
                      (emp_id, exclude_assignment_id)).fetchall()
    return sum(r['share'] for r in rows if (r['task_kind'], r['task_id']) not in covered)

def _projected_load_after(db, emp_id, kind, task_id, new_share, exclude_assignment_id=0):
    """Загрузка после добавления назначения: если новое — подзадача, её предки исключаются (подзадача покрывает родителя).
    Уже перекрытые предки существующих подзадач тоже исключаются."""
    anc = set(_subtask_ancestors(db, task_id)) if kind == 'subtask' else set()
    rows = db.execute("SELECT task_id, task_kind, share FROM task_assignment WHERE employee_id=? AND is_deleted=0 AND id<>?",
                      (emp_id, exclude_assignment_id)).fetchall()
    cov = _covered_for_employee(db, emp_id)
    total = sum(r['share'] for r in rows
                if (r['task_kind'], r['task_id']) not in anc and (r['task_kind'], r['task_id']) not in cov)
    return total + new_share

def _employee_load_excluding(db, emp_id, exclude_assignment_id=0):
    return db.execute("SELECT COALESCE(SUM(share),0) FROM task_assignment WHERE employee_id=? AND is_deleted=0 AND id<>?",
                      (emp_id, exclude_assignment_id)).fetchone()[0]


def fmt_timecode(ms):
    if not ms:
        return '00:00'
    s = ms // 1000
    return f'{s // 60:02d}:{s % 60:02d}'

def _entity_project_id(db, etype, eid):
    if etype == 'task':
        r = db.execute("SELECT COALESCE(ps.project_id, r.project_id) pid FROM task t LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE t.id=? AND t.is_deleted=0", (eid,)).fetchone()
    else:
        r = db.execute("SELECT COALESCE(ps.project_id, r.project_id) pid FROM subtask s JOIN task t ON s.parent_task_id=t.id LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE s.id=? AND s.is_deleted=0", (eid,)).fetchone()
    return r[0] if r and r[0] else None

def _entity_comments(db, etype, eid):
    return db.execute("SELECT * FROM comment WHERE entity_type=? AND entity_id=? AND is_deleted=0 ORDER BY created_at DESC, id DESC", (etype, eid)).fetchall()

def _last_comment(db, etype, eid):
    return db.execute("SELECT * FROM comment WHERE entity_type=? AND entity_id=? AND is_deleted=0 ORDER BY created_at DESC, id DESC LIMIT 1", (etype, eid)).fetchone()

def _comments_html(db, etype, eid, origin):
    last = _last_comment(db, etype, eid)
    add = f'<a href="{url_for("comment_create", entity_type=etype, entity_id=eid, origin=origin)}" class="btn btn-primary">+ Комментарий</a>'
    if last:
        top = (f'<div class="comment"><strong>{html.escape(last["author"] or "—")}</strong> · '
               f'{html.escape(str(last["created_at"]))}<br>{html.escape(last["text"])}</div>')
    else:
        top = '<div class="muted">Комментариев нет</div>'
    return f'<div class="comments"><div class="comment-note">Последний комментарий:</div>{top} {add}</div>'

def _soft_delete_subtask_tree(db, root_id):
    to_delete = db.execute("SELECT id FROM subtask WHERE id=? AND is_deleted=0", (root_id,)).fetchall()
    ids = [r[0] for r in to_delete]
    frontier = list(ids)
    while frontier:
        ph = ','.join('?' * len(frontier))
        kids = db.execute(f"SELECT id FROM subtask WHERE parent_subtask_id IN ({ph}) AND is_deleted=0", tuple(frontier)).fetchall()
        frontier = [r[0] for r in kids]
        ids.extend(frontier)
    if ids:
        ph = ','.join('?' * len(ids))
        db.execute(f"UPDATE subtask SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id IN ({ph})", tuple(ids))

def _project_employee_options(db):
    """Опции сотрудников проекта с должностью и текущей загруженностью (сумма долей)."""
    proj_emp = {}
    for row in db.execute("""
        SELECT pe.project_id, e.id, e.last_name, e.first_name, pt.name pos,
               COALESCE((SELECT SUM(ta.share) FROM task_assignment ta WHERE ta.employee_id=e.id AND ta.is_deleted=0),0) load
        FROM project_employee pe
        JOIN employee e ON pe.employee_id=e.id
        JOIN position_type pt ON e.position_type_id=pt.id
        WHERE pe.is_deleted=0 AND e.is_deleted=0 ORDER BY e.last_name
    """):
        proj_emp.setdefault(row['project_id'], []).append(
            f'<option value="{row["id"]}">{row["last_name"]} {row["first_name"]} — {row["pos"]} (загрузка {int(row["load"] * 100)}%)</option>')
    return proj_emp

# ==================== БАЗОВЫЙ ШАБЛОН ====================

BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - УПО</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { background: #2c3e50; color: white; padding: 20px; margin-bottom: 20px; }
        .header h1 { font-size: 24px; }
        .nav { background: #34495e; padding: 10px; margin-bottom: 20px; }
        .nav a { color: white; text-decoration: none; padding: 8px 15px; margin-right: 10px; display: inline-block; }
        .nav a:hover { background: #4a6278; border-radius: 4px; }
        .nav .dropdown { position: relative; display: inline-block; }
        .nav .dropbtn { color: white; text-decoration: none; padding: 8px 15px; margin-right: 10px; display: inline-block; cursor: pointer; }
        .nav .dropdown:hover .dropbtn { background: #4a6278; border-radius: 4px; }
        .nav .dropdown-content { display: none; position: absolute; top: 100%; left: 0; background: #34495e; min-width: 210px; box-shadow: 0 8px 16px rgba(0,0,0,0.25); z-index: 1000; border-radius: 4px; }
        .nav .dropdown:hover .dropdown-content { display: block; }
        .nav .dropdown-content a { display: block; padding: 10px 15px; margin-right: 0; border-radius: 0; }
        .nav .dropdown-content a:hover { background: #4a6278; }
        .card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow-x: auto; }
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
        .btn-primary { background: #3498db; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-warning { background: #f39c12; color: white; }
        .btn:hover { opacity: 0.9; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #ecf0f1; font-weight: bold; }
        tr:hover { background: #f8f9fa; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;
        }
        .form-group textarea { min-height: 100px; }
        .flash { padding: 10px; margin: 10px 0; border-radius: 4px; }
        .flash-success { background: #d4edda; color: #155724; }
        .flash-error { background: #f8d7da; color: #721c24; }
        .badge { padding: 4px 8px; border-radius: 12px; font-size: 12px; color: white; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-card h3 { font-size: 14px; color: #7f8c8d; margin-bottom: 10px; }
        .stat-card .value { font-size: 32px; font-weight: bold; color: #2c3e50; }
        .tabs { border-bottom: 2px solid #34495e; margin-bottom: 15px; display: flex; gap: 5px; }
        .tab-btn { background: none; border: none; padding: 10px 18px; font-size: 15px; cursor: pointer; border-bottom: 3px solid transparent; color: #7f8c8d; font-weight: bold; }
        .tab-btn.active { border-bottom-color: #34495e; color: #2c3e50; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .tree details { border: 1px solid #ddd; border-radius: 6px; margin-bottom: 8px; background: #fbfbfb; }
        .tree summary { cursor: pointer; padding: 10px 14px; font-weight: bold; background: #ecf0f1; border-radius: 6px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
        .tree details > .node-body { padding: 8px 14px; }
        .tree .node-meta { font-weight: normal; font-size: 13px; color: #7f8c8d; }
        .tree .node-info { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .tree .node-actions { display: inline-flex; align-items: center; gap: 5px; margin-left: auto; white-space: nowrap; font-weight: normal; }
        .assign { font-size: 13px; color: #34495e; margin-top: 6px; }
        .comments { margin: 8px 0; padding: 8px 10px; background: #f4f6f7; border-left: 3px solid #3498db; }
        .comments .comment-note { font-size: 12px; color: #7f8c8d; margin-bottom: 4px; }
        .comments .comment { font-size: 13px; margin-bottom: 6px; }
        .muted { color: #95a5a6; }
        .name-cell { white-space: nowrap; min-width: 200px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ title }}</h1>
        <div style="margin-top:8px; font-size:13px; color:#bdc3c7;">Активная БД: <strong style="color:#ecf0f1;">{{ current_db }}</strong> &nbsp;|&nbsp; <a href="{{ url_for('database_index') }}" style="color:#ecf0f1;">управление БД</a></div>
    </div>
    <div class="nav">
        <a href="{{ url_for('index') }}">Главная</a>
        <div class="dropdown">
            <span class="dropbtn">Справочники ▾</span>
            <div class="dropdown-content">
                <a href="{{ url_for('priorities_list') }}">Приоритеты</a>
                <a href="{{ url_for('stakeholder_types_list') }}">Типы стейкхолдеров</a>
                <a href="{{ url_for('requirement_types_list') }}">Типы требований</a>
                <a href="{{ url_for('position_types_list') }}">Типы должностей</a>
                <a href="{{ url_for('employee_statuses_list') }}">Статусы сотрудников</a>
                <a href="{{ url_for('stage_types_list') }}">Типы этапов</a>
                <a href="{{ url_for('stage_statuses_list') }}">Статусы этапов</a>
                <a href="{{ url_for('task_statuses_list') }}">Статусы задач</a>
                <a href="{{ url_for('task_types_list') }}">Типы задач</a>
            </div>
        </div>
        <a href="{{ url_for('stakeholders_list') }}">Стейкхолдеры</a>
        <a href="{{ url_for('employees_list') }}">Сотрудники</a>
        <a href="{{ url_for('projects_list') }}">Проекты</a>
        <a href="{{ url_for('events_list') }}">События</a>
        <a href="{{ url_for('database_index') }}">База данных</a>
        <div class="dropdown">
            <span class="dropbtn">Отчёты ▾</span>
            <div class="dropdown-content">
                <a href="{{ url_for('report_projects') }}">Проекты: сводка и прогресс</a>
                <a href="{{ url_for('report_stakeholders') }}">Стейкхолдеры: типы</a>
                <a href="{{ url_for('report_employees') }}">Сотрудники: загрузка и состав</a>
                <a href="{{ url_for('report_requirements') }}">Требования: анализ</a>
                <a href="{{ url_for('report_stages') }}">Этапы: статусы</a>
                <a href="{{ url_for('report_tasks') }}">Задачи: статусы и просрочка</a>
                <a href="{{ url_for('report_subtasks') }}">Подзадачи: статусы</a>
                <a href="{{ url_for('report_assignments') }}">Назначения: загрузка</a>
                <a href="{{ url_for('report_events') }}">События: динамика</a>
            </div>
        </div>
    </div>
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash flash-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {{ content|safe }}
    </div>
</body>
</html>
'''


def _render_tables(tables):
    out = ''
    for t in tables:
        headers_html = ''.join(f'<th>{html.escape(str(h))}</th>' for h in t['headers'])
        rows_html = ''.join(
            '<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>'
            for row in t['rows']
        )
        out += f'''
        <div class="card">
            <h2>{t['title']}</h2>
            <table><thead><tr>{headers_html}</tr></thead><tbody>{rows_html}</tbody></table>
        </div>'''
    return out

def _report_page(title, cards, tables):
    card_html = ''.join([
        f'<div class="stat-card"><h3>{html.escape(str(label))}</h3>'
        f'<div class="value" style="color:{color}">{html.escape(str(value))}</div></div>'
        for label, value, color in cards
    ])
    content = f'''
    <div class="stats">{card_html}</div>
    {_render_tables(tables)}
    '''
    return render_template_string(BASE_TEMPLATE, title=title, content=content)

def _detail_page(title, info, tables=None, actions=None):
    info_html = ''.join([
        f'<p style="margin:6px 0;"><strong>{html.escape(str(k))}:</strong> {v}</p>'
        for k, v in info
    ])
    tables_html = _render_tables(tables or [])
    actions_html = f'<div style="margin-top:14px;">{actions}</div>' if actions else ''
    content = f'''
    <div class="card">
        <h2>{html.escape(title)}</h2>
        {info_html}
        {actions_html}
        <p style="margin-top:14px;"><a href="#" onclick="window.history.back(); return false;" class="btn btn-primary">Назад</a></p>
    </div>
    {tables_html}
    '''
    return render_template_string(BASE_TEMPLATE, title=title, content=content)


