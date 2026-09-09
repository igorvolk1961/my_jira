"""
Учебный проектный офис (УПО) - приложение для управления проектами, 
задачами и персоналом.
Для ролевых игр на курсах системных аналитиков
"""

from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify, session, send_file
import sqlite3
from datetime import datetime, date
from io import BytesIO
import html
import json
import os
import shutil

app = Flask(__name__)
app.secret_key = 'upo_secret_key_2026'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, 'data')
DEFAULT_DB_NAME = os.environ.get('UPO_DATABASE', 'upo_database.db')
os.makedirs(DATABASE_DIR, exist_ok=True)

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
        
        -- Задачи
        CREATE TABLE IF NOT EXISTS task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_id INTEGER REFERENCES requirement(id) ON DELETE SET NULL,
            description TEXT NOT NULL,
            stage_id INTEGER REFERENCES project_stage(id),
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
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_one_executor_per_subtask ON task_assignment(task_id) WHERE task_kind='subtask' AND is_deleted=0")
    except sqlite3.IntegrityError:
        pass
    
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

# ==================== ГЛАВНАЯ СТРАНИЦА ====================

@app.route('/')
def index():
    db = get_db()
    
    stats = {
        'projects': db.execute("SELECT COUNT(*) FROM project WHERE is_deleted=0").fetchone()[0],
        'tasks': db.execute("SELECT COUNT(*) FROM task WHERE is_deleted=0").fetchone()[0],
        'employees': db.execute("SELECT COUNT(*) FROM employee WHERE is_deleted=0").fetchone()[0],
        'events': db.execute("SELECT COUNT(*) FROM event WHERE is_deleted=0").fetchone()[0],
        'active_tasks': db.execute("""
            SELECT COUNT(*) FROM task t
            JOIN task_status ts ON t.status_id = ts.id
            WHERE t.is_deleted=0 AND ts.name IN ('Новая', 'В работе')
        """).fetchone()[0],
        'overdue_tasks': db.execute("""
            SELECT COUNT(*) FROM task
            WHERE is_deleted=0 AND deadline < date('now') AND status_id NOT IN (
                SELECT id FROM task_status WHERE name IN ('Выполнена', 'Отменена')
            )
        """).fetchone()[0]
    }
    
    content = f'''
    <div class="stats">
        <div class="stat-card">
            <h3>Всего проектов</h3>
            <div class="value">{stats['projects']}</div>
        </div>
        <div class="stat-card">
            <h3>Активных задач</h3>
            <div class="value">{stats['active_tasks']}</div>
        </div>
        <div class="stat-card">
            <h3>Просроченных задач</h3>
            <div class="value" style="color: {'#e74c3c' if stats['overdue_tasks'] > 0 else '#27ae60'}">{stats['overdue_tasks']}</div>
        </div>
        <div class="stat-card">
            <h3>Сотрудников</h3>
            <div class="value">{stats['employees']}</div>
        </div>
        <div class="stat-card">
            <h3>Событий</h3>
            <div class="value">{stats['events']}</div>
        </div>
    </div>
    
    <div class="card">
        <h2>Добро пожаловать в Учебный проектный офис!</h2>
        <p style="margin-top: 10px;">Используйте меню выше для управления проектами, задачами и персоналом.</p>
    </div>
    '''
    
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Главная', content=content)

# ==================== ПРИОРИТЕТЫ ====================

@app.route('/priorities')
def priorities_list():
    db = get_db()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0 ORDER BY weight").fetchall()
    
    rows = ''.join([f'''
        <tr>
            <td>{p['id']}</td>
            <td>{p['name']}</td>
            <td>{p['weight']}</td>
            <td>
                <a href="{url_for('priority_edit', id=p['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('priority_delete', id=p['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for p in priorities])
    
    content = f'''
    <div class="card">
        <h2>Приоритеты</h2>
        <a href="{url_for('priority_create')}" class="btn btn-success">+ Добавить приоритет</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Название</th><th>Вес</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Приоритеты', content=content)

@app.route('/priorities/create', methods=['GET', 'POST'])
def priority_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO priority (name, weight) VALUES (?, ?)",
                  (request.form['name'], int(request.form['weight'])))
        db.commit()
        db.close()
        flash('Приоритет создан', 'success')
        return redirect(url_for('priorities_list'))
    
    content = f'''
    <div class="card">
        <h2>Новый приоритет</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Вес (1-5)</label>
                <input type="number" name="weight" min="1" max="5" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('priorities_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый приоритет', content=content)

@app.route('/priorities/edit/<int:id>', methods=['GET', 'POST'])
def priority_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE priority SET name=?, weight=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], int(request.form['weight']), id))
        db.commit()
        db.close()
        flash('Приоритет обновлён', 'success')
        return redirect(url_for('priorities_list'))
    
    priority = db.execute("SELECT * FROM priority WHERE id=?", (id,)).fetchone()
    if not priority:
        db.close()
        flash('Приоритет не найден', 'error')
        return redirect(url_for('priorities_list'))
    db.close()
    
    content = f'''
    <div class="card">
        <h2>Редактировать приоритет</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{priority['name']}" required>
            </div>
            <div class="form-group">
                <label>Вес (1-5)</label>
                <input type="number" name="weight" value="{priority['weight']}" min="1" max="5" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('priorities_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать приоритет', content=content)

@app.route('/priorities/delete/<int:id>')
def priority_delete(id):
    db = get_db()
    db.execute("UPDATE priority SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Приоритет удалён', 'success')
    return redirect(url_for('priorities_list'))

# ==================== ТИПЫ СТЕЙКХОЛДЕРОВ ====================

@app.route('/stakeholder_types')
def stakeholder_types_list():
    db = get_db()
    types = db.execute("SELECT * FROM stakeholder_type WHERE is_deleted=0 ORDER BY id").fetchall()
    
    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>{t['influence_priority']}</td>
            <td>{t['interest_priority']}</td>
            <td>
                <a href="{url_for('stakeholder_type_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('stakeholder_type_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in types])
    
    content = f'''
    <div class="card">
        <h2>Типы стейкхолдеров</h2>
        <a href="{url_for('stakeholder_type_create')}" class="btn btn-success">+ Добавить тип</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Название</th><th>Влияние</th><th>Заинтересованность</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Типы стейкхолдеров', content=content)

@app.route('/stakeholder_types/create', methods=['GET', 'POST'])
def stakeholder_type_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO stakeholder_type (name, influence_priority, interest_priority) VALUES (?, ?, ?)",
                  (request.form['name'], int(request.form['influence_priority']), int(request.form['interest_priority'])))
        db.commit()
        db.close()
        flash('Тип стейкхолдера создан', 'success')
        return redirect(url_for('stakeholder_types_list'))
    
    content = f'''
    <div class="card">
        <h2>Новый тип стейкхолдера</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Приоритет влияния (1-5)</label>
                <input type="number" name="influence_priority" min="1" max="5" required>
            </div>
            <div class="form-group">
                <label>Приоритет заинтересованности (1-5)</label>
                <input type="number" name="interest_priority" min="1" max="5" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('stakeholder_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый тип стейкхолдера', content=content)

@app.route('/stakeholder_types/edit/<int:id>', methods=['GET', 'POST'])
def stakeholder_type_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE stakeholder_type SET name=?, influence_priority=?, interest_priority=?, 
                     updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (request.form['name'], int(request.form['influence_priority']),
                   int(request.form['interest_priority']), id))
        db.commit()
        db.close()
        flash('Тип стейкхолдера обновлён', 'success')
        return redirect(url_for('stakeholder_types_list'))
    
    stype = db.execute("SELECT * FROM stakeholder_type WHERE id=?", (id,)).fetchone()
    if not stype:
        db.close()
        flash('Тип стейкхолдера не найден', 'error')
        return redirect(url_for('stakeholder_types_list'))
    db.close()
    
    content = f'''
    <div class="card">
        <h2>Редактировать тип стейкхолдера</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{stype['name']}" required>
            </div>
            <div class="form-group">
                <label>Приоритет влияния (1-5)</label>
                <input type="number" name="influence_priority" value="{stype['influence_priority']}" min="1" max="5" required>
            </div>
            <div class="form-group">
                <label>Приоритет заинтересованности (1-5)</label>
                <input type="number" name="interest_priority" value="{stype['interest_priority']}" min="1" max="5" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('stakeholder_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать тип стейкхолдера', content=content)

@app.route('/stakeholder_types/delete/<int:id>')
def stakeholder_type_delete(id):
    db = get_db()
    db.execute("UPDATE stakeholder_type SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Тип стейкхолдера удалён', 'success')
    return redirect(url_for('stakeholder_types_list'))

# ==================== СТЕЙКХОЛДЕРЫ ====================

@app.route('/stakeholders')
def stakeholders_list():
    db = get_db()
    stakeholders = db.execute("""
        SELECT s.*, st.name as type_name 
        FROM stakeholder s
        JOIN stakeholder_type st ON s.type_id = st.id
        WHERE s.is_deleted=0
        ORDER BY s.last_name
    """).fetchall()
    
    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td class="name-cell">{s['last_name']} {s['first_name']} {s['middle_name'] or ''}</td>
            <td>{s['type_name']}</td>
            <td>{s['position'] or '-'}</td>
            <td>{s['priority']}</td>
            <td>
                <a href="{url_for('stakeholder_detail', id=s['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('stakeholder_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('stakeholder_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in stakeholders])
    
    content = f'''
    <div class="card">
        <h2>Стейкхолдеры</h2>
        <a href="{url_for('stakeholder_create')}" class="btn btn-success">+ Добавить стейкхолдера</a>
        <table>
            <thead>
                <tr><th>ID</th><th>ФИО</th><th>Тип</th><th>Должность</th><th>Приоритет</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Стейкхолдеры', content=content)

@app.route('/stakeholders/create', methods=['GET', 'POST'])
def stakeholder_create():
    db = get_db()
    if request.method == 'POST':
        type_id = int(request.form['type_id'])
        dev_id = _developer_type_id(db)
        emp_id = (request.form.get('employee_id') or None) if type_id == dev_id else None
        cur = db.execute("""INSERT INTO stakeholder (last_name, first_name, middle_name, type_id, position, priority, employee_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (request.form['last_name'], request.form['first_name'],
                   request.form.get('middle_name'), type_id,
                   request.form.get('position'), int(request.form['priority']), emp_id))
        new_id = cur.lastrowid
        pid = request.form.get('project_id')
        if pid:
            db.execute("INSERT INTO project_stakeholder (project_id, stakeholder_id) VALUES (?, ?)", (int(pid), new_id))
        if emp_id:
            db.execute("UPDATE employee SET is_stackholder=1 WHERE id=? AND is_deleted=0", (int(emp_id),))
        db.commit()
        db.close()
        flash('Стейкхолдер создан', 'success')
        if pid:
            return redirect(url_for('project_detail', id=int(pid), tab='stk'))
        return redirect(url_for('stakeholders_list'))
    
    types = db.execute("SELECT * FROM stakeholder_type WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0 ORDER BY weight").fetchall()
    dev_id = _developer_type_id(db)
    linked_emp = {r[0] for r in db.execute("SELECT DISTINCT employee_id FROM stakeholder WHERE employee_id IS NOT NULL AND is_deleted=0")}
    employees = [e for e in db.execute("SELECT * FROM employee WHERE is_deleted=0 ORDER BY last_name") if e['id'] not in linked_emp]
    db.close()
    
    options = ''.join([f'<option value="{t["id"]}">{t["name"]}</option>' for t in types])
    priority_options = ''.join([
        f'<option value="{p["weight"]}" {"selected" if p["weight"] == 3 else ""}>{p["name"]}</option>'
        for p in priorities
    ])
    type_prio = ','.join(f'{t["id"]}:{int(t["influence_priority"])}' for t in types)
    employee_options = ''.join(f'<option value="{e["id"]}">{e["last_name"]} {e["first_name"]} {e["middle_name"] or ""}</option>' for e in employees)
    pre_project = request.args.get('project_id')
    cancel_url = url_for('project_detail', id=int(pre_project), tab='stk') if pre_project else url_for('stakeholders_list')
    
    content = f'''
    <div class="card">
        <h2>Новый стейкхолдер</h2>
        <form method="POST">
            <input type="hidden" name="project_id" value="{pre_project or ''}">
            <div class="form-group">
                <label>Фамилия</label>
                <input type="text" name="last_name" required>
            </div>
            <div class="form-group">
                <label>Имя</label>
                <input type="text" name="first_name" required>
            </div>
            <div class="form-group">
                <label>Отчество</label>
                <input type="text" name="middle_name">
            </div>
            <div class="form-group">
                <label>Тип стейкхолдера</label>
                <select name="type_id" required onchange="setPrio(this.value); toggleEmp()">{options}</select>
            </div>
            <div class="form-group" id="employee_select" style="display:none;">
                <label>Сотрудник</label>
                <select name="employee_id"><option value="">— не выбран —</option>{employee_options}</select>
            </div>
            <div class="form-group">
                <label>Должность</label>
                <input type="text" name="position">
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority" required>{priority_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    <script>
    var prioByType = {{ {type_prio} }};
    var devType = {dev_id};
    function setPrio(tid) {{
        var p = prioByType[tid];
        if (p) {{ document.querySelector('select[name=priority]').value = p; }}
    }}
    function toggleEmp() {{
        var v = document.querySelector('select[name=type_id]').value;
        document.getElementById('employee_select').style.display = (v == devType) ? 'block' : 'none';
    }}
    toggleEmp();
    </script>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый стейкхолдер', content=content)

@app.route('/stakeholders/edit/<int:id>', methods=['GET', 'POST'])
def stakeholder_edit(id):
    db = get_db()
    if request.method == 'POST':
        type_id = int(request.form['type_id'])
        dev_id = _developer_type_id(db)
        emp_id = (request.form.get('employee_id') or None) if type_id == dev_id else None
        old = db.execute("SELECT employee_id FROM stakeholder WHERE id=?", (id,)).fetchone()
        db.execute("""UPDATE stakeholder SET last_name=?, first_name=?, middle_name=?, type_id=?,
                     position=?, priority=?, employee_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (request.form['last_name'], request.form['first_name'],
                   request.form.get('middle_name'), type_id,
                   request.form.get('position'), int(request.form['priority']), emp_id, id))
        if emp_id:
            db.execute("UPDATE employee SET is_stackholder=1 WHERE id=? AND is_deleted=0", (int(emp_id),))
        old_eid = old[0] if old else None
        if old_eid and str(old_eid) != (emp_id or ''):
            _reset_employee_stackholder_if_unlinked(db, old_eid)
        db.commit()
        db.close()
        flash('Стейкхолдер обновлён', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stk'))
        return redirect(url_for('stakeholders_list'))
    
    stakeholder = db.execute("SELECT * FROM stakeholder WHERE id=?", (id,)).fetchone()
    if not stakeholder:
        db.close()
        flash('Стейкхолдер не найден', 'error')
        return redirect(url_for('stakeholders_list'))
    types = db.execute("SELECT * FROM stakeholder_type WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0 ORDER BY weight").fetchall()
    dev_id = _developer_type_id(db)
    linked_emp = {r[0] for r in db.execute("SELECT DISTINCT employee_id FROM stakeholder WHERE employee_id IS NOT NULL AND is_deleted=0")}
    employees = [e for e in db.execute("SELECT * FROM employee WHERE is_deleted=0 ORDER BY last_name") if e['id'] not in linked_emp]
    if stakeholder['employee_id'] and all(e['id'] != stakeholder['employee_id'] for e in employees):
        cur_e = db.execute("SELECT * FROM employee WHERE id=? AND is_deleted=0", (stakeholder['employee_id'],)).fetchone()
        if cur_e:
            employees.append(cur_e)
    db.close()
    
    options = ''.join([f'<option value="{t["id"]}" {"selected" if t["id"]==stakeholder["type_id"] else ""}>{t["name"]}</option>' for t in types])
    priority_options = ''.join([
        f'<option value="{p["weight"]}" {"selected" if p["weight"]==stakeholder["priority"] else ""}>{p["name"]}</option>'
        for p in priorities
    ])
    type_prio = ','.join(f'{t["id"]}:{int(t["influence_priority"])}' for t in types)
    employee_options = ''.join(
        f'<option value="{e["id"]}" {"selected" if e["id"] == stakeholder["employee_id"] else ""}>{e["last_name"]} {e["first_name"]} {e["middle_name"] or ""}</option>'
        for e in employees)
    origin = request.args.get('origin')
    cancel_url = url_for('project_detail', id=int(origin), tab='stk') if origin else url_for('stakeholders_list')
    
    content = f'''
    <div class="card">
        <h2>Редактировать стейкхолдера</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Фамилия</label>
                <input type="text" name="last_name" value="{stakeholder['last_name']}" required>
            </div>
            <div class="form-group">
                <label>Имя</label>
                <input type="text" name="first_name" value="{stakeholder['first_name']}" required>
            </div>
            <div class="form-group">
                <label>Отчество</label>
                <input type="text" name="middle_name" value="{stakeholder['middle_name'] or ''}">
            </div>
            <div class="form-group">
                <label>Тип стейкхолдера</label>
                <select name="type_id" required onchange="setPrio(this.value); toggleEmp()">{options}</select>
            </div>
            <div class="form-group" id="employee_select" style="display:{'block' if stakeholder['type_id'] == dev_id else 'none'};">
                <label>Сотрудник</label>
                <select name="employee_id"><option value="">— не выбран —</option>{employee_options}</select>
            </div>
            <div class="form-group">
                <label>Должность</label>
                <input type="text" name="position" value="{stakeholder['position'] or ''}">
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority" required>{priority_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    <script>
    var prioByType = {{ {type_prio} }};
    var devType = {dev_id};
    function setPrio(tid) {{
        var p = prioByType[tid];
        if (p) {{ document.querySelector('select[name=priority]').value = p; }}
    }}
    function toggleEmp() {{
        var v = document.querySelector('select[name=type_id]').value;
        document.getElementById('employee_select').style.display = (v == devType) ? 'block' : 'none';
    }}
    toggleEmp();
    </script>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать стейкхолдера', content=content)

@app.route('/stakeholders/delete/<int:id>')
def stakeholder_delete(id):
    db = get_db()
    st = db.execute("SELECT employee_id FROM stakeholder WHERE id=? AND is_deleted=0", (id,)).fetchone()
    db.execute("UPDATE stakeholder SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    if st and st['employee_id']:
        _reset_employee_stackholder_if_unlinked(db, st['employee_id'])
    db.commit()
    db.close()
    flash('Стейкхолдер удалён', 'success')
    return redirect(url_for('stakeholders_list'))

#==================== ТИПЫ ТРЕБОВАНИЙ ====================

@app.route('/requirement_types')
def requirement_types_list():
    db = get_db()
    types = db.execute("SELECT * FROM requirement_type WHERE is_deleted=0 ORDER BY id").fetchall()
    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>
                <a href="{url_for('requirement_type_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('requirement_type_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in types])

    content = f'''
    <div class="card">
        <h2>Типы требований</h2>
        <a href="{url_for('requirement_type_create')}" class="btn btn-success">+ Добавить тип</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Типы требований', content=content)

@app.route('/requirement_types/create', methods=['GET', 'POST'])
def requirement_type_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO requirement_type (name) VALUES (?)", (request.form['name'],))
        db.commit()
        db.close()
        flash('Тип требования создан', 'success')
        return redirect(url_for('requirement_types_list'))

    content = f'''
    <div class="card">
        <h2>Новый тип требования</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('requirement_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый тип требования', content=content)

@app.route('/requirement_types/edit/<int:id>', methods=['GET', 'POST'])
def requirement_type_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE requirement_type SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], id))
        db.commit()
        db.close()
        flash('Тип требования обновлён', 'success')
        return redirect(url_for('requirement_types_list'))

    rtype = db.execute("SELECT * FROM requirement_type WHERE id=?", (id,)).fetchone()
    if not rtype:
        db.close()
        flash('Тип требования не найден', 'error')
        return redirect(url_for('requirement_types_list'))
    db.close()
    content = f'''
    <div class="card">
        <h2>Редактировать тип требования</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{rtype['name']}" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('requirement_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать тип требования', content=content)

@app.route('/requirement_types/delete/<int:id>')
def requirement_type_delete(id):
    db = get_db()
    db.execute("UPDATE requirement_type SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Тип требования удалён', 'success')
    return redirect(url_for('requirement_types_list'))
#==================== ПРОЕКТЫ ====================
@app.route('/projects')
def projects_list():
    db = get_db()
    projects = db.execute("""
        SELECT p.*, s.last_name, s.first_name, pr.name as priority_name, pr.weight
        FROM project p
        LEFT JOIN stakeholder s ON p.main_stakeholder_id = s.id
        JOIN priority pr ON p.priority_id = pr.id
        WHERE p.is_deleted=0
        ORDER BY p.id DESC
    """).fetchall()


    rows = ''.join([f'''
        <tr>
            <td>{p['id']}</td>
            <td><a href="{url_for('project_detail', id=p['id'])}">{p['name']}</a></td>
            <td>{f'<a href="{url_for("stakeholder_detail", id=p["main_stakeholder_id"])}">{p["last_name"]} {p["first_name"]}</a>' if p['main_stakeholder_id'] else '-'}</td>
            <td>{p['cost'] or '-'}</td>
            <td>{p['mvp_deadline'] or '-'}</td>
            <td>{p['deadline'] or '-'}</td>
            <td><span class="badge" style="background: {['#95a5a6','#3498db','#f39c12','#e67e22','#e74c3c'][p['weight']-1]}">{p['priority_name']}</span></td>
            <td>
                <a href="{url_for('project_detail', id=p['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('project_edit', id=p['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('project_delete', id=p['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for p in projects])

    content = f'''
    <div class="card">
        <h2>Проекты</h2>
        <a href="{url_for('project_create')}" class="btn btn-success">+ Добавить проект</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Название</th><th>Главный стейкхолдер</th><th>Стоимость</th><th>MVP срок</th><th>Проект срок</th><th>Приоритет</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Проекты', content=content)

@app.route('/projects/create', methods=['GET', 'POST'])
def project_create():
    db = get_db()
    if request.method == 'POST':
        db.execute("""INSERT INTO project (name, description, main_stakeholder_id, cost, mvp_deadline, deadline, priority_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (request.form['name'], request.form.get('description'),
                   request.form.get('main_stakeholder_id') or None,
                   request.form.get('cost') or None,
                   request.form.get('mvp_deadline') or None,
                   request.form.get('deadline') or None,
                   int(request.form['priority_id'])))
        db.commit()
        db.close()
        flash('Проект создан', 'success')
        return redirect(url_for('projects_list'))

    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    db.close()

    stakeholder_options = '<option value="">Не выбран</option>' + ''.join([f'<option value="{s["id"]}">{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    priority_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in priorities])

    content = f'''
    <div class="card">
        <h2>Новый проект</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description"></textarea>
            </div>
            <div class="form-group">
                <label>Главный стейкхолдер</label>
                <select name="main_stakeholder_id">{stakeholder_options}</select>
            </div>
            <div class="form-group">
                <label>Стоимость</label>
                <input type="number" name="cost" step="0.01">
            </div>
            <div class="form-group">
                <label>Срок MVP</label>
                <input type="date" name="mvp_deadline">
            </div>
            <div class="form-group">
                <label>Срок проекта</label>
                <input type="date" name="deadline">
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('projects_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый проект', content=content)

@app.route('/projects/edit/<int:id>', methods=['GET', 'POST'])
def project_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE project SET name=?, description=?, main_stakeholder_id=?, cost=?,
                     mvp_deadline=?, deadline=?, priority_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (request.form['name'], request.form.get('description'),
                   request.form.get('main_stakeholder_id') or None,
                   request.form.get('cost') or None,
                   request.form.get('mvp_deadline') or None,
                   request.form.get('deadline') or None,
                   int(request.form['priority_id']), id))
        db.commit()
        db.close()
        flash('Проект обновлён', 'success')
        return redirect(url_for('projects_list'))

    project = db.execute("SELECT * FROM project WHERE id=?", (id,)).fetchone()
    if not project:
        db.close()
        flash('Проект не найден', 'error')
        return redirect(url_for('projects_list'))
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    db.close()

    stakeholder_options = '<option value="">Не выбран</option>' + ''.join([f'<option value="{s["id"]}" {"selected" if s["id"]==project["main_stakeholder_id"] else ""}>{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    priority_options = ''.join([f'<option value="{p["id"]}" {"selected" if p["id"]==project["priority_id"] else ""}>{p["name"]}</option>' for p in priorities])

    content = f'''
    <div class="card">
        <h2>Редактировать проект</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{project['name']}" required>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description">{project['description'] or ''}</textarea>
            </div>
            <div class="form-group">
                <label>Главный стейкхолдер</label>
                <select name="main_stakeholder_id">{stakeholder_options}</select>
            </div>
            <div class="form-group">
                <label>Стоимость</label>
                <input type="number" name="cost" value="{project['cost'] or ''}" step="0.01">
            </div>
            <div class="form-group">
                <label>Срок MVP</label>
                <input type="date" name="mvp_deadline" value="{project['mvp_deadline'] or ''}">
            </div>
            <div class="form-group">
                <label>Срок проекта</label>
                <input type="date" name="deadline" value="{project['deadline'] or ''}">
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('projects_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать проект', content=content)

@app.route('/projects/delete/<int:id>')
def project_delete(id):
    db = get_db()
    db.execute("UPDATE project SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Проект удалён', 'success')
    return redirect(url_for('projects_list'))

@app.route('/projects/<int:id>')
def project_detail(id):
    db = get_db()
    project = db.execute("""
        SELECT p.*, s.last_name, s.first_name, pr.name as priority_name, pr.weight
        FROM project p
        LEFT JOIN stakeholder s ON p.main_stakeholder_id = s.id
        JOIN priority pr ON p.priority_id = pr.id
        WHERE p.id=? AND p.is_deleted=0
    """, (id,)).fetchone()
    if not project:
        db.close()
        flash('Проект не найден', 'error')
        return redirect(url_for('projects_list'))

    requirements = db.execute("""
        SELECT r.*, s.last_name, s.first_name, rt.name as type_name, pr.name as priority_name
        FROM requirement r
        LEFT JOIN stakeholder s ON r.stakeholder_id = s.id
        JOIN requirement_type rt ON r.requirement_type_id = rt.id
        JOIN priority pr ON r.priority_id = pr.id
        WHERE r.project_id=? AND r.is_deleted=0
        ORDER BY r.id DESC
    """, (id,)).fetchall()

    stages = db.execute("""
        SELECT ps.*, pst.name as type_name, pss.name as status_name, pss.color
        FROM project_stage ps
        JOIN project_stage_type pst ON ps.stage_type_id = pst.id
        JOIN project_stage_status pss ON ps.status_id = pss.id
        WHERE ps.project_id=? AND ps.is_deleted=0
        ORDER BY pst.sort_order
    """, (id,)).fetchall()

    tasks = db.execute("""
        SELECT t.*, ps.id as stage_id, pr.name as priority_name,
               ts.name as status_name, ts.color as status_color
        FROM task t
        JOIN priority pr ON t.priority_id = pr.id
        JOIN task_status ts ON t.status_id = ts.id
        LEFT JOIN project_stage ps ON t.stage_id = ps.id
        LEFT JOIN requirement r ON t.requirement_id = r.id
        WHERE t.is_deleted=0 AND (ps.project_id=? OR r.project_id=?)
        ORDER BY t.id
    """, (id, id)).fetchall()

    task_ids = [t['id'] for t in tasks]
    subtasks = []
    if task_ids:
        ph = ','.join('?' * len(task_ids))
        subtasks = db.execute(f"""
            SELECT st.*, pr.name as priority_name, ts.name as status_name, ts.color as status_color
            FROM subtask st
            JOIN priority pr ON st.priority_id = pr.id
            JOIN task_status ts ON st.status_id = ts.id
            WHERE st.is_deleted=0 AND st.parent_task_id IN ({ph})
            ORDER BY st.id
        """, tuple(task_ids)).fetchall()
    sub_children = {}
    top_by_task = {}
    for st in subtasks:
        sub_children.setdefault(st['parent_subtask_id'], []).append(st)
        if st['parent_subtask_id'] is None:
            top_by_task.setdefault(st['parent_task_id'], []).append(st)

    assignments = {}
    def collect_assignments(kind, ids):
        if not ids:
            return
        ph = ','.join('?' * len(ids))
        rows = db.execute(f"""
            SELECT ta.*, e.last_name, e.first_name
            FROM task_assignment ta JOIN employee e ON ta.employee_id = e.id
            WHERE ta.is_deleted=0 AND ta.task_kind=? AND ta.task_id IN ({ph})
        """, tuple([kind] + list(ids))).fetchall()
        for a in rows:
            assignments.setdefault((kind, a['task_id']), []).append(a)
    collect_assignments('task', task_ids)
    collect_assignments('subtask', [s['id'] for s in subtasks])

    def render_assignees(lines):
        if not lines:
            return '<span class="muted">исполнители не назначены</span>'
        items = [f'{a["last_name"]} {a["first_name"]} ({int(a["share"] * 100)}%)' for a in lines]
        return 'Исполнители: ' + ', '.join(items)

    def render_assignments_block(kind, tid):
        return f'<div class="assign">{render_assignees(assignments.get((kind, tid), []))}</div>'

    def render_subtask(st):
        children = sub_children.get(st['id'], [])
        asg = url_for('task_assignment_create', task_id=st['id'], task_kind='subtask', origin=id)
        edit_link = url_for('subtask_edit', id=st['id'], origin=id)
        child_link = url_for('subtask_create', parent_subtask_id=st['id'], origin=id)
        del_link = url_for('subtask_delete', id=st['id'])
        comments_html = _comments_html(db, 'subtask', st['id'], id)
        return f'''
            <details class="subtask" open>
                <summary>
                    <span class="node-info">
                        Подзадача #{st['id']}: {st['description'][:60]}
                        <span class="badge" style="background: {st['status_color'] or '#95a5a6'}">{st['status_name']}</span>
                        <span class="node-meta">Приоритет: {st['priority_name']}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-warning" href="{asg}">Назначить</a>
                        <a class="btn btn-primary" href="{edit_link}">Изменить</a>
                        <a class="btn btn-success" href="{child_link}">+ Подзадача</a>
                        <a class="btn btn-danger" href="{del_link}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">
                    {comments_html}
                    {st['description']}
                    {render_assignments_block('subtask', st['id'])}
                    {''.join([render_subtask(c) for c in children])}
                </div>
            </details>'''

    def render_task(t):
        task_subtasks = top_by_task.get(t['id'], [])
        subtask_html = ''.join([render_subtask(s) for s in task_subtasks])
        asg = url_for('task_assignment_create', task_id=t['id'], task_kind='task', origin=id)
        subtask_link = url_for('subtask_create', parent_task_id=t['id'], origin=id)
        edit_link = url_for('task_edit', id=t['id'], origin=id)
        del_link = url_for('task_delete', id=t['id'])
        comments_html = _comments_html(db, 'task', t['id'], id)
        return f'''
            <details class="task" open>
                <summary>
                    <span class="node-info">
                        Задача #{t['id']}: {t['description'][:60]}
                        <span class="badge" style="background: {t['status_color'] or '#95a5a6'}">{t['status_name']}</span>
                        <span class="node-meta">Приоритет: {t['priority_name']}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-warning" href="{asg}">Назначить</a>
                        <a class="btn btn-primary" href="{edit_link}">Изменить</a>
                        <a class="btn btn-success" href="{subtask_link}">+ Подзадача</a>
                        <a class="btn btn-danger" href="{del_link}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">
                    {comments_html}
                    {t['description']}
                    {render_assignments_block('task', t['id'])}
                    {subtask_html}
                </div>
            </details>'''

    tasks_by_stage = {}
    no_stage = []
    for t in tasks:
        if t['stage_id'] is None:
            no_stage.append(t)
        else:
            tasks_by_stage.setdefault(t['stage_id'], []).append(t)

    stage_html = ''
    for s in stages:
        stage_tasks = tasks_by_stage.get(s['id'], [])
        inner = ''.join([render_task(t) for t in stage_tasks])
        if not stage_tasks:
            inner = '<div class="node-body muted">Задач по этапу нет</div>'
        stage_html += f'''
            <details class="stage" open>
                <summary>
                    <span class="node-info">
                        {s['type_name']}
                        <span class="badge" style="background: {s['color'] or '#95a5a6'}">{s['status_name']}</span>
                        <span class="node-meta">План. окончание: {s['planned_end'] or '-'}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-success" href="{url_for('task_create', stage_id=s['id'], origin=id)}">+ Задача</a>
                        <a class="btn btn-danger" href="{url_for('project_stage_delete', id=s['id'])}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">{inner}</div>
            </details>'''
    req_rows = ''.join([f'''
        <tr>
            <td>{r['id']}</td>
            <td>{r['type_name']}</td>
            <td>{r['last_name'] or '-'} {r['first_name'] or ''}</td>
            <td>{r['description'][:80]}</td>
            <td>{r['priority_name']}</td>
            <td>
                <a href="{url_for('requirement_detail', id=r['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('requirement_edit', id=r['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('requirement_delete', id=r['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>''' for r in requirements])

    main_id = project['main_stakeholder_id']
    assoc_rows = db.execute("SELECT stakeholder_id FROM project_stakeholder WHERE project_id=? AND is_deleted=0", (id,)).fetchall()
    assoc_ids = {a['stakeholder_id'] for a in assoc_rows}
    req_st_ids = {row[0] for row in db.execute("SELECT DISTINCT stakeholder_id FROM requirement WHERE project_id=? AND stakeholder_id IS NOT NULL AND is_deleted=0", (id,))}
    stk_ids = set(assoc_ids)
    if main_id:
        stk_ids.add(main_id)
    stk_ids |= req_st_ids
    project_stakeholders = []
    if stk_ids:
        ph = ','.join('?' * len(stk_ids))
        project_stakeholders = db.execute(f"""
            SELECT s.*, st.name type_name, st.influence_priority inf, st.interest_priority ints,
                   (SELECT COUNT(*) FROM requirement r WHERE r.stakeholder_id=s.id AND r.project_id=? AND r.is_deleted=0) req_count
            FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id
            WHERE s.is_deleted=0 AND s.id IN ({ph})
            ORDER BY s.last_name
        """, tuple([id] + list(stk_ids))).fetchall()
    def stk_quadrant(inf, ints):
        if inf >= 4 and ints >= 4:
            return 'Ключевые игроки'
        if inf >= 4:
            return 'Удовлетворять'
        if ints >= 4:
            return 'Держать в курсе'
        return 'Наблюдать'
    def remove_btn(sid):
        if sid in assoc_ids and sid != main_id:
            return f' <a href="{url_for("project_remove_stakeholder", id=id, stakeholder_id=sid)}" class="btn btn-danger" onclick="return confirm(\'Убрать?\')">Убрать</a>'
        return ''
    stk_rows = ''.join([f'''
        <tr>
            <td class="name-cell"><a href="{url_for('stakeholder_detail', id=s['id'])}">{s['last_name']} {s['first_name']}</a> {f'<span class="badge" style="background:#e74c3c">главный</span>' if s['id'] == main_id else ''}{f' <span class="badge" style="background:#3498db">добавлен</span>' if s['id'] in assoc_ids and s['id'] != main_id else ''}</td>
            <td>{s['type_name']}</td>
            <td>{s['inf']}/5, {s['ints']}/5</td>
            <td>{stk_quadrant(s['inf'], s['ints'])}</td>
            <td>{s['position'] or '-'}</td>
            <td>{s['req_count']}</td>
            <td><a href="{url_for('stakeholder_detail', id=s['id'])}" class="btn btn-success">Открыть</a> <a href="{url_for('stakeholder_edit', id=s['id'], origin=id)}" class="btn btn-primary">Изменить</a>{remove_btn(s['id'])}</td>
        </tr>''' for s in project_stakeholders])
    candidate_rows = []
    if stk_ids:
        cph = ','.join('?' * len(stk_ids))
        candidate_rows = db.execute(f"""
            SELECT s.*, st.name type_name FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id
            WHERE s.is_deleted=0 AND s.id NOT IN ({cph})
            ORDER BY s.last_name
        """, tuple(list(stk_ids))).fetchall()
    else:
        candidate_rows = db.execute("SELECT s.*, st.name type_name FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id WHERE s.is_deleted=0 ORDER BY s.last_name").fetchall()
    candidate_options = ''.join(f'<option value="{s["id"]}">{s["last_name"]} {s["first_name"]} — {s["type_name"]}</option>' for s in candidate_rows)

    emp_rows = db.execute("""
        SELECT e.*, pe.project_id, pt.name position_name, es.name status_name, es.is_available
        FROM project_employee pe
        JOIN employee e ON pe.employee_id=e.id
        JOIN position_type pt ON e.position_type_id=pt.id
        JOIN employee_status es ON e.status_id=es.id
        WHERE pe.project_id=? AND pe.is_deleted=0 AND e.is_deleted=0
        ORDER BY e.last_name
    """, (id,)).fetchall()
    emp_ids = {e['id'] for e in emp_rows}
    def emp_remove_btn(eid):
        return f' <a href="{url_for("project_remove_employee", id=id, employee_id=eid)}" class="btn btn-danger" onclick="return confirm(\'Убрать?\')">Убрать</a>'
    emp_rows_html = ''.join([f'''
        <tr>
            <td class="name-cell"><a href="{url_for('employee_detail', id=e['id'])}">{e['last_name']} {e['first_name']} {e['middle_name'] or ''}</a></td>
            <td>{e['position_name']}</td>
            <td><span class="badge" style="background: {'#27ae60' if e['is_available'] else '#e74c3c'}">{e['status_name']}</span></td>
            <td>{e['subordinates_total']}</td>
            <td>
                <a href="{url_for('employee_detail', id=e['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('employee_edit', id=e['id'], origin=id)}" class="btn btn-primary">Изменить</a>{emp_remove_btn(e['id'])}
            </td>
        </tr>''' for e in emp_rows])
    emp_candidates = []
    if emp_ids:
        eph = ','.join('?' * len(emp_ids))
        emp_candidates = db.execute(f"""
            SELECT e.*, pt.name position_name FROM employee e JOIN position_type pt ON e.position_type_id=pt.id
            WHERE e.is_deleted=0 AND e.id NOT IN ({eph}) ORDER BY e.last_name
        """, tuple(list(emp_ids))).fetchall()
    else:
        emp_candidates = db.execute("SELECT e.*, pt.name position_name FROM employee e JOIN position_type pt ON e.position_type_id=pt.id WHERE e.is_deleted=0 ORDER BY e.last_name").fetchall()
    emp_candidate_options = ''.join(f'<option value="{e["id"]}">{e["last_name"]} {e["first_name"]} — {e["position_name"]}</option>' for e in emp_candidates)

    active_tab = request.args.get('tab') or 'req'
    if active_tab not in ('req', 'stages', 'stk', 'emp'):
        active_tab = 'req'
    btn_d = {k: ('tab-btn active' if active_tab == k else 'tab-btn') for k in ('req', 'stages', 'stk', 'emp')}
    panel_d = {k: ('tab-content active' if active_tab == k else 'tab-content') for k in ('req', 'stages', 'stk', 'emp')}

    content = f'''
    <div class="card">
        <h2>{project['name']}
            <span class="node-meta">
                | Приоритет: {project['priority_name']}
                | Стейкхолдер: {f'<a href="{url_for("stakeholder_detail", id=project["main_stakeholder_id"])}">{project["last_name"]} {project["first_name"]}</a>' if project['main_stakeholder_id'] else '-'}
                | Стоимость: {project['cost'] or '-'}
                | Срок: {project['deadline'] or '-'}
            </span>
        </h2>
        <div class="tabs">
            <button class="{btn_d['req']}" id="btn-req" onclick="showTab('req')">Требования ({len(requirements)})</button>
            <button class="{btn_d['stages']}" id="btn-stages" onclick="showTab('stages')">Этапы ({len(stages)})</button>
            <button class="{btn_d['stk']}" id="btn-stk" onclick="showTab('stk')">Стейкхолдеры ({len(project_stakeholders)})</button>
            <button class="{btn_d['emp']}" id="btn-emp" onclick="showTab('emp')">Исполнители ({len(emp_rows)})</button>
        </div>
        <div class="{panel_d['req']}" id="tab-req">
            <a href="{url_for('requirement_create', project_id=id)}" class="btn btn-success">+ Добавить требование</a>
            <table>
                <thead>
                    <tr><th>ID</th><th>Тип</th><th>Стейкхолдер</th><th>Описание</th><th>Приоритет</th><th>Действия</th></tr>
                </thead>
                <tbody>{req_rows}</tbody>
            </table>
        </div>
        <div class="{panel_d['stages']}" id="tab-stages">
            <a href="{url_for('project_stage_create')}" class="btn btn-success">+ Добавить этап</a>
            <div class="tree">{stage_html}</div>
        </div>
        <div class="{panel_d['stk']}" id="tab-stk">
            <a href="{url_for('stakeholder_create', project_id=id)}" class="btn btn-success">+ Добавить стейкхолдера</a>
            <form method="POST" action="{url_for('project_add_stakeholder', id=id)}" style="display:inline-flex; gap:6px; margin-left:8px; vertical-align:middle;">
                <select name="stakeholder_id" required>
                    <option value="">— выберите из имеющихся —</option>
                    {candidate_options}
                </select>
                <button type="submit" class="btn btn-primary">Добавить</button>
            </form>
            <table>
                <thead>
                    <tr><th>Стейкхолдер</th><th>Тип</th><th>Влияние/Интерес</th><th>Квадрант</th><th>Должность</th><th>Требований</th><th>Действия</th></tr>
                </thead>
                <tbody>{stk_rows}</tbody>
            </table>
        </div>
        <div class="{panel_d['emp']}" id="tab-emp">
            <a href="{url_for('employee_create', project_id=id)}" class="btn btn-success">+ Добавить исполнителя</a>
            <form method="POST" action="{url_for('project_add_employee', id=id)}" style="display:inline-flex; gap:6px; margin-left:8px; vertical-align:middle;">
                <select name="employee_id" required>
                    <option value="">— выберите из имеющихся —</option>
                    {emp_candidate_options}
                </select>
                <button type="submit" class="btn btn-primary">Добавить</button>
            </form>
            <table>
                <thead>
                    <tr><th>Исполнитель</th><th>Должность</th><th>Статус</th><th>Подчинённые</th><th>Действия</th></tr>
                </thead>
                <tbody>{emp_rows_html}</tbody>
            </table>
        </div>
    </div>
    <script>
    function showTab(name) {{
        document.querySelectorAll('.tab-btn').forEach(function(el) {{ el.classList.remove('active'); }});
        document.querySelectorAll('.tab-content').forEach(function(el) {{ el.classList.remove('active'); }});
        document.getElementById('btn-' + name).classList.add('active');
        document.getElementById('tab-' + name).classList.add('active');
    }}
    </script>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title=project['name'], content=content)

@app.route('/projects/<int:id>/add_stakeholder', methods=['POST'])
def project_add_stakeholder(id):
    db = get_db()
    sid = int(request.form['stakeholder_id'])
    try:
        db.execute("INSERT INTO project_stakeholder (project_id, stakeholder_id) VALUES (?, ?)", (id, sid))
        db.commit()
        flash('Стейкхолдер добавлен к проекту', 'success')
    except sqlite3.IntegrityError:
        flash('Стейкхолдер уже в проекте', 'warning')
    db.close()
    return redirect(url_for('project_detail', id=id, tab='stk'))

@app.route('/projects/<int:id>/remove_stakeholder/<int:stakeholder_id>')
def project_remove_stakeholder(id, stakeholder_id):
    db = get_db()
    db.execute("UPDATE project_stakeholder SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE project_id=? AND stakeholder_id=?", (id, stakeholder_id))
    db.commit()
    db.close()
    flash('Стейкхолдер убран из проекта', 'success')
    return redirect(url_for('project_detail', id=id, tab='stk'))

@app.route('/projects/<int:id>/add_employee', methods=['POST'])
def project_add_employee(id):
    db = get_db()
    eid = int(request.form['employee_id'])
    try:
        db.execute("INSERT INTO project_employee (project_id, employee_id) VALUES (?, ?)", (id, eid))
        db.commit()
        flash('Исполнитель добавлен к проекту', 'success')
    except sqlite3.IntegrityError:
        flash('Исполнитель уже в проекте', 'warning')
    db.close()
    return redirect(url_for('project_detail', id=id, tab='emp'))

@app.route('/projects/<int:id>/remove_employee/<int:employee_id>')
def project_remove_employee(id, employee_id):
    db = get_db()
    db.execute("UPDATE project_employee SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE project_id=? AND employee_id=?", (id, employee_id))
    db.commit()
    db.close()
    flash('Исполнитель убран из проекта', 'success')
    return redirect(url_for('project_detail', id=id, tab='emp'))

#==================== ТРЕБОВАНИЯ ====================

@app.route('/requirements')
def requirements_list():
    db = get_db()
    requirements = db.execute("""
        SELECT r.*, p.name as project_name, s.last_name, s.first_name,
               rt.name as type_name, pr.name as priority_name
        FROM requirement r
        JOIN project p ON r.project_id = p.id
        LEFT JOIN stakeholder s ON r.stakeholder_id = s.id
        JOIN requirement_type rt ON r.requirement_type_id = rt.id
        JOIN priority pr ON r.priority_id = pr.id
        WHERE r.is_deleted=0
        ORDER BY r.id DESC
    """).fetchall()


    rows = ''.join([f'''
           <tr>
                <td>{r['id']}</td>
                <td><a href="{url_for('project_detail', id=r['project_id'])}">{r['project_name']}</a></td>
                <td>{f'<a href="{url_for("stakeholder_detail", id=r["stakeholder_id"])}">{r["last_name"]} {r["first_name"]}</a>' if r['stakeholder_id'] else '-'}</td>
                <td>{r['type_name']}</td>
                <td>{r['description'][:50]}...</td>
                <td>{r['priority_name']}</td>
                <td>
                    <a href="{url_for('requirement_detail', id=r['id'])}" class="btn btn-success">Открыть</a>
                    <a href="{url_for('requirement_edit', id=r['id'])}" class="btn btn-primary">Изменить</a>
                    <a href="{url_for('requirement_delete', id=r['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
                </td>
            </tr>
        ''' for r in requirements])

    content = f'''
       <div class="card">
           <h2>Требования</h2>
           <a href="{url_for('requirement_create')}" class="btn btn-success">+ Добавить требование</a>
           <table>
               <thead>
                   <tr><th>ID</th><th>Проект</th><th>Стейкхолдер</th><th>Тип</th><th>Описание</th><th>Приоритет</th><th>Действия</th></tr>
               </thead>
               <tbody>{rows}</tbody>
           </table>
       </div>
       '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Требования', content=content)

@app.route('/requirements/create', methods=['GET', 'POST'])
def requirement_create():
    db = get_db()
    if request.method == 'POST':
        db.execute("""INSERT INTO requirement (project_id, stakeholder_id, requirement_type_id, description, priority_id, acceptance_criteria)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (int(request.form['project_id']),
                   request.form.get('stakeholder_id') or None,
                   int(request.form['requirement_type_id']),
                   request.form['description'],
                   int(request.form['priority_id']),
                   request.form.get('acceptance_criteria')))
        db.commit()
        db.close()
        flash('Требование создано', 'success')
        return redirect(url_for('project_detail', id=int(request.form['project_id'])))

    pre_project = request.args.get('project_id')
    projects = db.execute("SELECT * FROM project WHERE is_deleted=0").fetchall()
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    req_types = db.execute("SELECT * FROM requirement_type WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    db.close()

    project_options = ''.join([f'<option value="{p["id"]}" {"selected" if str(p["id"]) == pre_project else ""}>{p["name"]}</option>' for p in projects])
    stakeholder_options = '<option value="">Не выбран</option>' + ''.join([f'<option value="{s["id"]}">{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    type_options = ''.join([f'<option value="{t["id"]}">{t["name"]}</option>' for t in req_types])
    priority_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in priorities])
    cancel_url = url_for('project_detail', id=int(pre_project)) if pre_project else url_for('requirements_list')

    content = f'''
    <div class="card">
        <h2>Новое требование</h2>
        <form method="POST">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id" required>{project_options}</select>
            </div>
            <div class="form-group">
                <label>Стейкхолдер</label>
                <select name="stakeholder_id">{stakeholder_options}</select>
            </div>
            <div class="form-group">
                <label>Тип требования</label>
                <select name="requirement_type_id" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required></textarea>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Критерий проверки</label>
                <textarea name="acceptance_criteria"></textarea>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новое требование', content=content)

@app.route('/requirements/edit/<int:id>', methods=['GET', 'POST'])
def requirement_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE requirement SET project_id=?, stakeholder_id=?, requirement_type_id=?,
                     description=?, priority_id=?, acceptance_criteria=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (int(request.form['project_id']),
                   request.form.get('stakeholder_id') or None,
                   int(request.form['requirement_type_id']),
                   request.form['description'],
                   int(request.form['priority_id']),
                   request.form.get('acceptance_criteria'), id))
        db.commit()
        db.close()
        flash('Требование обновлено', 'success')
        return redirect(url_for('requirements_list'))

    req = db.execute("SELECT * FROM requirement WHERE id=?", (id,)).fetchone()
    if not req:
        db.close()
        flash('Требование не найдено', 'error')
        return redirect(url_for('requirements_list'))
    projects = db.execute("SELECT * FROM project WHERE is_deleted=0").fetchall()
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    req_types = db.execute("SELECT * FROM requirement_type WHERE is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    db.close()

    project_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == req["project_id"] else ""}>{p["name"]}</option>' for p in
         projects])
    stakeholder_options = '<option value="">Не выбран</option>' + ''.join([
                                                                              f'<option value="{s["id"]}" {"selected" if s["id"] == req["stakeholder_id"] else ""}>{s["last_name"]} {s["first_name"]}</option>'
                                                                              for s in stakeholders])
    type_options = ''.join(
        [f'<option value="{t["id"]}" {"selected" if t["id"] == req["requirement_type_id"] else ""}>{t["name"]}</option>'
         for t in req_types])
    priority_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == req["priority_id"] else ""}>{p["name"]}</option>' for p
         in priorities])

    content = f'''
    <div class="card">
        <h2>Редактировать требование</h2>
        <form method="POST">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id" required>{project_options}</select>
            </div>
            <div class="form-group">
                <label>Стейкхолдер</label>
                <select name="stakeholder_id">{stakeholder_options}</select>
            </div>
            <div class="form-group">
                <label>Тип требования</label>
                <select name="requirement_type_id" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required>{req['description']}</textarea>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Критерий проверки</label>
                <textarea name="acceptance_criteria">{req['acceptance_criteria'] or ''}</textarea>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('requirements_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать требование', content=content)

@app.route('/requirements/delete/<int:id>')
def requirement_delete(id):
    db = get_db()
    db.execute("UPDATE requirement SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Требование удалено', 'success')
    return redirect(url_for('requirements_list'))

#==================== ТИПЫ ДОЛЖНОСТЕЙ ====================
@app.route('/position_types')
def position_types_list():
    db = get_db()
    types = db.execute("SELECT * FROM position_type WHERE is_deleted=0 ORDER BY id").fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>
                <a href="{url_for('position_type_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('position_type_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in types])

    content = f'''
    <div class="card">
        <h2>Типы должностей</h2>
        <a href="{url_for('position_type_create')}" class="btn btn-success">+ Добавить тип</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Типы должностей', content=content)

@app.route('/position_types/create', methods=['GET', 'POST'])
def position_type_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO position_type (name) VALUES (?)", (request.form['name'],))
        db.commit()
        db.close()
        flash('Тип должности создан', 'success')
        return redirect(url_for('position_types_list'))
    content = f'''
    <div class="card">
        <h2>Новый тип должности</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('position_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый тип должности', content=content)

@app.route('/position_types/edit/<int:id>', methods=['GET', 'POST'])
def position_type_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE position_type SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], id))
        db.commit()
        db.close()
        flash('Тип должности обновлён', 'success')
        return redirect(url_for('position_types_list'))

    ptype = db.execute("SELECT * FROM position_type WHERE id=?", (id,)).fetchone()
    if not ptype:
        db.close()
        flash('Тип должности не найден', 'error')
        return redirect(url_for('position_types_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать тип должности</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{ptype['name']}" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('position_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать тип должности', content=content)

@app.route('/position_types/delete/<int:id>')
def position_type_delete(id):
    db = get_db()
    db.execute("UPDATE position_type SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Тип должности удалён', 'success')
    return redirect(url_for('position_types_list'))

#==================== СТАТУСЫ СОТРУДНИКОВ ====================
@app.route('/employee_statuses')
def employee_statuses_list():
    db = get_db()
    statuses = db.execute("SELECT * FROM employee_status WHERE is_deleted=0 ORDER BY id").fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td>{s['name']}</td>
            <td>{'Да' if s['is_available'] else 'Нет'}</td>
            <td>
                <a href="{url_for('employee_status_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('employee_status_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in statuses])

    content = f'''
    <div class="card">
        <h2>Статусы сотрудников</h2>
        <a href="{url_for('employee_status_create')}" class="btn btn-success">+ Добавить статус</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Доступен</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Статусы сотрудников', content=content)

@app.route('/employee_statuses/create', methods=['GET', 'POST'])
def employee_status_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO employee_status (name, is_available) VALUES (?, ?)",
                  (request.form['name'], int(request.form.get('is_available', 0))))
        db.commit()
        db.close()
        flash('Статус сотрудника создан', 'success')
        return redirect(url_for('employee_statuses_list'))

    content = f'''
    <div class="card">
        <h2>Новый статус сотрудника</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Доступен для работы</label>
                <select name="is_available">
                    <option value="1">Да</option>
                    <option value="0">Нет</option>
                </select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('employee_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый статус сотрудника', content=content)

@app.route('/employee_statuses/edit/<int:id>', methods=['GET', 'POST'])
def employee_status_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE employee_status SET name=?, is_available=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], int(request.form.get('is_available', 0)), id))
        db.commit()
        db.close()
        flash('Статус сотрудника обновлён', 'success')
        return redirect(url_for('employee_statuses_list'))

    status = db.execute("SELECT * FROM employee_status WHERE id=?", (id,)).fetchone()
    if not status:
        db.close()
        flash('Статус сотрудника не найден', 'error')
        return redirect(url_for('employee_statuses_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать статус сотрудника</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{status['name']}" required>
            </div>
            <div class="form-group">
                <label>Доступен для работы</label>
                <select name="is_available">
                    <option value="1" {"selected" if status['is_available'] else ""}>Да</option>
                    <option value="0" {"selected" if not status['is_available'] else ""}>Нет</option>
                </select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('employee_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать статус сотрудника', content=content)

@app.route('/employee_statuses/delete/<int:id>')
def employee_status_delete(id):
    db = get_db()
    db.execute("UPDATE employee_status SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Статус сотрудника удалён', 'success')
    return redirect(url_for('employee_statuses_list'))
#==================== СОТРУДНИКИ ====================
@app.route('/employees')
def employees_list():
    db = get_db()
    employees = db.execute("""
        SELECT e.*, pt.name as position_name, es.name as status_name, es.is_available
        FROM employee e
        JOIN position_type pt ON e.position_type_id = pt.id
        JOIN employee_status es ON e.status_id = es.id
        WHERE e.is_deleted=0
        ORDER BY e.last_name
    """).fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{e['id']}</td>
            <td class="name-cell">{e['last_name']} {e['first_name']} {e['middle_name'] or ''}</td>
            <td>{e['position_name']}</td>
            <td><span class="badge" style="background: {'#27ae60' if e['is_available'] else '#e74c3c'}">{e['status_name']}</span></td>
            <td>{e['subordinates_total']}</td>
            <td>{e['subordinates_available']}</td>
            <td>
                <a href="{url_for('employee_detail', id=e['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('employee_edit', id=e['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('employee_delete', id=e['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for e in employees])

    content = f'''
    <div class="card">
        <h2>Сотрудники</h2>
        <a href="{url_for('employee_create')}" class="btn btn-success">+ Добавить сотрудника</a>
        <table>
            <thead>
                <tr><th>ID</th><th>ФИО</th><th>Должность</th><th>Статус</th><th>Всего подчинённых</th><th>Доступно подчинённых</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Сотрудники', content=content)

@app.route('/employees/create', methods=['GET', 'POST'])
def employee_create():
    db = get_db()
    if request.method == 'POST':
        is_sh = 1 if request.form.get('is_stackholder') else 0
        cur = db.execute("""INSERT INTO employee (last_name, first_name, middle_name, position_type_id, status_id, subordinates_total, subordinates_available, is_stackholder)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (request.form['last_name'], request.form['first_name'],
                   request.form.get('middle_name'),
                   int(request.form['position_type_id']),
                   int(request.form['status_id']),
                   int(request.form.get('subordinates_total', 0)),
                   int(request.form.get('subordinates_available', 0)),
                   is_sh))
        new_id = cur.lastrowid
        pid = request.form.get('project_id')
        if pid:
            db.execute("INSERT INTO project_employee (project_id, employee_id) VALUES (?, ?)", (int(pid), new_id))
        sync_stakeholder_for_employee(db, new_id, bool(is_sh))
        db.commit()
        db.close()
        flash('Сотрудник создан', 'success')
        if pid:
            return redirect(url_for('project_detail', id=int(pid), tab='emp'))
        return redirect(url_for('employees_list'))

    positions = db.execute("SELECT * FROM position_type WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM employee_status WHERE is_deleted=0").fetchall()
    db.close()

    position_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in positions])
    status_options = ''.join([f'<option value="{s["id"]}">{s["name"]}</option>' for s in statuses])
    pre_project = request.args.get('project_id')
    cancel_url = url_for('project_detail', id=int(pre_project), tab='emp') if pre_project else url_for('employees_list')

    content = f'''
    <div class="card">
        <h2>Новый сотрудник</h2>
        <form method="POST">
            <input type="hidden" name="project_id" value="{pre_project or ''}">
            <div class="form-group">
                <label>Фамилия</label>
                <input type="text" name="last_name" required>
            </div>
            <div class="form-group">
                <label>Имя</label>
                <input type="text" name="first_name" required>
            </div>
            <div class="form-group">
                <label>Отчество</label>
                <input type="text" name="middle_name">
            </div>
            <div class="form-group">
                <label>Тип должности</label>
                <select name="position_type_id" required>{position_options}</select>
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <div class="form-group">
                <label>Всего подчинённых</label>
                <input type="number" name="subordinates_total" value="0" min="0">
            </div>
            <div class="form-group">
                <label>Доступно подчинённых</label>
                <input type="number" name="subordinates_available" value="0" min="0">
            </div>
            <div class="form-group">
                <label><input type="checkbox" name="is_stackholder" value="1" style="width:auto; display:inline; margin-right:6px;"> Является стейкхолдером (разработчик)</label>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый сотрудник', content=content)

@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
def employee_edit(id):
    db = get_db()
    if request.method == 'POST':
        is_sh = 1 if request.form.get('is_stackholder') else 0
        db.execute("""UPDATE employee SET last_name=?, first_name=?, middle_name=?, position_type_id=?,
                     status_id=?, subordinates_total=?, subordinates_available=?, is_stackholder=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (request.form['last_name'], request.form['first_name'],
                   request.form.get('middle_name'),
                   int(request.form['position_type_id']),
                   int(request.form['status_id']),
                   int(request.form.get('subordinates_total', 0)),
                   int(request.form.get('subordinates_available', 0)), is_sh, id))
        sync_stakeholder_for_employee(db, id, bool(is_sh))
        db.commit()
        db.close()
        flash('Сотрудник обновлён', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='emp'))
        return redirect(url_for('employees_list'))

    employee = db.execute("SELECT * FROM employee WHERE id=?", (id,)).fetchone()
    if not employee:
        db.close()
        flash('Сотрудник не найден', 'error')
        return redirect(url_for('employees_list'))
    positions = db.execute("SELECT * FROM position_type WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM employee_status WHERE is_deleted=0").fetchall()
    db.close()

    position_options = ''.join([
                                   f'<option value="{p["id"]}" {"selected" if p["id"] == employee["position_type_id"] else ""}>{p["name"]}</option>'
                                   for p in positions])
    status_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if s["id"] == employee["status_id"] else ""}>{s["name"]}</option>' for
         s in statuses])
    origin = request.args.get('origin')
    cancel_url = url_for('project_detail', id=int(origin), tab='emp') if origin else url_for('employees_list')

    content = f'''
    <div class="card">
        <h2>Редактировать сотрудника</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Фамилия</label>
                <input type="text" name="last_name" value="{employee['last_name']}" required>
            </div>
            <div class="form-group">
                <label>Имя</label>
                <input type="text" name="first_name" value="{employee['first_name']}" required>
            </div>
            <div class="form-group">
                <label>Отчество</label>
                <input type="text" name="middle_name" value="{employee['middle_name'] or ''}">
            </div>
            <div class="form-group">
                <label>Тип должности</label>
                <select name="position_type_id" required>{position_options}</select>
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <div class="form-group">
                <label>Всего подчинённых</label>
                <input type="number" name="subordinates_total" value="{employee['subordinates_total']}" min="0">
            </div>
            <div class="form-group">
                <label>Доступно подчинённых</label>
                <input type="number" name="subordinates_available" value="{employee['subordinates_available']}" min="0">
            </div>
            <div class="form-group">
                <label><input type="checkbox" name="is_stackholder" value="1" style="width:auto; display:inline; margin-right:6px;" {'checked' if employee['is_stackholder'] else ''}> Является стейкхолдером (разработчик)</label>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать сотрудника', content=content)

@app.route('/employees/delete/<int:id>')
def employee_delete(id):
    db = get_db()
    db.execute("UPDATE employee SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Сотрудник удалён', 'success')
    return redirect(url_for('employees_list'))

#==================== ТИПЫ ЭТАПОВ ПРОЕКТА ====================
@app.route('/stage_types')
def stage_types_list():
    db = get_db()
    types = db.execute("SELECT * FROM project_stage_type WHERE is_deleted=0 ORDER BY sort_order").fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>{t['sort_order']}</td>
            <td>
                <a href="{url_for('stage_type_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('stage_type_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in types])

    content = f'''
    <div class="card">
        <h2>Типы этапов проекта</h2>
        <a href="{url_for('stage_type_create')}" class="btn btn-success">+ Добавить тип</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Порядок</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Типы этапов', content=content)

@app.route('/stage_types/create', methods=['GET', 'POST'])
def stage_type_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO project_stage_type (name, sort_order) VALUES (?, ?)",
                  (request.form['name'], int(request.form.get('sort_order', 0))))
        db.commit()
        db.close()
        flash('Тип этапа создан', 'success')
        return redirect(url_for('stage_types_list'))

    content = f'''
    <div class="card">
        <h2>Новый тип этапа</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Порядок</label>
                <input type="number" name="sort_order" value="0">
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('stage_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый тип этапа', content=content)

@app.route('/stage_types/edit/<int:id>', methods=['GET', 'POST'])
def stage_type_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE project_stage_type SET name=?, sort_order=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], int(request.form.get('sort_order', 0)), id))
        db.commit()
        db.close()
        flash('Тип этапа обновлён', 'success')
        return redirect(url_for('stage_types_list'))
    stype = db.execute("SELECT * FROM project_stage_type WHERE id=?", (id,)).fetchone()
    if not stype:
        db.close()
        flash('Тип этапа не найден', 'error')
        return redirect(url_for('stage_types_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать тип этапа</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{stype['name']}" required>
            </div>
            <div class="form-group">
                <label>Порядок</label>
                <input type="number" name="sort_order" value="{stype['sort_order']}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('stage_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать тип этапа', content=content)

@app.route('/stage_types/delete/<int:id>')
def stage_type_delete(id):
    db = get_db()
    db.execute("UPDATE project_stage_type SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Тип этапа удалён', 'success')
    return redirect(url_for('stage_types_list'))
#==================== СТАТУСЫ ЭТАПОВ ПРОЕКТА ====================
@app.route('/stage_statuses')
def stage_statuses_list():
    db = get_db()
    statuses = db.execute("SELECT * FROM project_stage_status WHERE is_deleted=0 ORDER BY id").fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td>{s['name']}</td>
            <td><span class="badge" style="background: {s['color'] or '#95a5a6'}">{s['color'] or '-'}</span></td>
            <td>
                <a href="{url_for('stage_status_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('stage_status_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in statuses])

    content = f'''
    <div class="card">
        <h2>Статусы этапов проекта</h2>
        <a href="{url_for('stage_status_create')}" class="btn btn-success">+ Добавить статус</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Цвет</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Статусы этапов', content=content)

@app.route('/stage_statuses/create', methods=['GET', 'POST'])
def stage_status_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO project_stage_status (name, color) VALUES (?, ?)",
                  (request.form['name'], request.form.get('color')))
        db.commit()
        db.close()
        flash('Статус этапа создан', 'success')
        return redirect(url_for('stage_statuses_list'))

    content = f'''
    <div class="card">
        <h2>Новый статус этапа</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Цвет (например: blue, green, red)</label>
                <input type="text" name="color">
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('stage_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый статус этапа', content=content)

@app.route('/stage_statuses/edit/<int:id>', methods=['GET', 'POST'])
def stage_status_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE project_stage_status SET name=?, color=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], request.form.get('color'), id))
        db.commit()
        db.close()
        flash('Статус этапа обновлён', 'success')
        return redirect(url_for('stage_statuses_list'))

    status = db.execute("SELECT * FROM project_stage_status WHERE id=?", (id,)).fetchone()
    if not status:
        db.close()
        flash('Статус этапа не найден', 'error')
        return redirect(url_for('stage_statuses_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать статус этапа</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{status['name']}" required>
            </div>
            <div class="form-group">
                <label>Цвет</label>
                <input type="text" name="color" value="{status['color'] or ''}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('stage_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать статус этапа', content=content)

@app.route('/stage_statuses/delete/<int:id>')
def stage_status_delete(id):
    db = get_db()
    db.execute("UPDATE project_stage_status SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Статус этапа удалён', 'success')
    return redirect(url_for('stage_statuses_list'))
#==================== ЭТАПЫ ПРОЕКТА ====================
@app.route('/project_stages')
def project_stages_list():
    db = get_db()
    stages = db.execute("""
        SELECT ps.*, p.name as project_name, pst.name as type_name, pss.name as status_name, pss.color
        FROM project_stage ps
        JOIN project p ON ps.project_id = p.id
        JOIN project_stage_type pst ON ps.stage_type_id = pst.id
        JOIN project_stage_status pss ON ps.status_id = pss.id
        WHERE ps.is_deleted=0
        ORDER BY p.name, pst.sort_order
    """).fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td>{s['project_name']}</td>
            <td>{s['type_name']}</td>
            <td><span class="badge" style="background: {s['color'] or '#95a5a6'}">{s['status_name']}</span></td>
            <td>{s['planned_end'] or '-'}</td>
            <td>
                <a href="{url_for('project_stage_detail', id=s['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('project_stage_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('project_stage_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in stages])

    content = f'''
    <div class="card">
        <h2>Этапы проектов</h2>
        <a href="{url_for('project_stage_create')}" class="btn btn-success">+ Добавить этап</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Проект</th><th>Тип этапа</th><th>Статус</th><th>Плановая дата завершения</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Этапы проектов', content=content)

@app.route('/project_stages/create', methods=['GET', 'POST'])
def project_stage_create():
    db = get_db()
    if request.method == 'POST':
        db.execute("""INSERT INTO project_stage (project_id, stage_type_id, status_id, planned_end)
                     VALUES (?, ?, ?, ?)""",
                  (int(request.form['project_id']),
                   int(request.form['stage_type_id']),
                   int(request.form['status_id']),
                   request.form.get('planned_end') or None))
        db.commit()
        db.close()
        flash('Этап проекта создан', 'success')
        return redirect(url_for('project_stages_list'))

    projects = db.execute("SELECT * FROM project WHERE is_deleted=0").fetchall()
    stage_types = db.execute("SELECT * FROM project_stage_type WHERE is_deleted=0 ORDER BY sort_order").fetchall()
    stage_statuses = db.execute("SELECT * FROM project_stage_status WHERE is_deleted=0").fetchall()
    db.close()

    project_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in projects])
    type_options = ''.join([f'<option value="{t["id"]}">{t["name"]}</option>' for t in stage_types])
    status_options = ''.join([f'<option value="{s["id"]}">{s["name"]}</option>' for s in stage_statuses])

    content = f'''
    <div class="card">
        <h2>Новый этап проекта</h2>
        <form method="POST">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id" required>{project_options}</select>
            </div>
            <div class="form-group">
                <label>Тип этапа</label>
                <select name="stage_type_id" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <div class="form-group">
                <label>Плановая дата завершения</label>
                <input type="date" name="planned_end">
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('project_stages_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый этап проекта', content=content)

@app.route('/project_stages/edit/<int:id>', methods=['GET', 'POST'])
def project_stage_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE project_stage SET project_id=?, stage_type_id=?, status_id=?,
                     planned_end=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (int(request.form['project_id']),
                   int(request.form['stage_type_id']),
                   int(request.form['status_id']),
                   request.form.get('planned_end') or None, id))
        db.commit()
        db.close()
        flash('Этап проекта обновлён', 'success')
        return redirect(url_for('project_stages_list'))
    stage = db.execute("SELECT * FROM project_stage WHERE id=?", (id,)).fetchone()
    if not stage:
        db.close()
        flash('Этап не найден', 'error')
        return redirect(url_for('project_stages_list'))
    projects = db.execute("SELECT * FROM project WHERE is_deleted=0").fetchall()
    stage_types = db.execute("SELECT * FROM project_stage_type WHERE is_deleted=0 ORDER BY sort_order").fetchall()
    stage_statuses = db.execute("SELECT * FROM project_stage_status WHERE is_deleted=0").fetchall()
    db.close()

    project_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == stage["project_id"] else ""}>{p["name"]}</option>' for p
         in projects])
    type_options = ''.join(
        [f'<option value="{t["id"]}" {"selected" if t["id"] == stage["stage_type_id"] else ""}>{t["name"]}</option>' for
         t in stage_types])
    status_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if s["id"] == stage["status_id"] else ""}>{s["name"]}</option>' for s
         in stage_statuses])

    content = f'''
    <div class="card">
        <h2>Редактировать этап проекта</h2>
        <form method="POST">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id" required>{project_options}</select>
            </div>
            <div class="form-group">
                <label>Тип этапа</label>
                <select name="stage_type_id" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <div class="form-group">
                <label>Плановая дата завершения</label>
                <input type="date" name="planned_end" value="{stage['planned_end'] or ''}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('project_stages_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать этап проекта', content=content)

@app.route('/project_stages/delete/<int:id>')
def project_stage_delete(id):
    db = get_db()
    rows = db.execute("SELECT id FROM task WHERE stage_id=? AND is_deleted=0", (id,)).fetchall()
    task_ids = [r[0] for r in rows]
    if task_ids:
        ph = ','.join('?' * len(task_ids))
        db.execute(f"UPDATE subtask SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE parent_task_id IN ({ph}) AND is_deleted=0", tuple(task_ids))
        db.execute(f"UPDATE task SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id IN ({ph})", tuple(task_ids))
    db.execute("UPDATE project_stage SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Этап проекта удалён', 'success')
    return redirect(url_for('project_stages_list'))
#==================== СТАТУСЫ ЗАДАЧ ====================
@app.route('/task_statuses')
def task_statuses_list():
    db = get_db()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0 ORDER BY id").fetchall()
    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td>{s['name']}</td>
            <td><span class="badge" style="background: {s['color'] or '#95a5a6'}">{s['color'] or '-'}</span></td>
            <td>
                <a href="{url_for('task_status_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('task_status_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in statuses])

    content = f'''
    <div class="card">
        <h2>Статусы задач</h2>
        <a href="{url_for('task_status_create')}" class="btn btn-success">+ Добавить статус</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Цвет</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Статусы задач', content=content)

@app.route('/task_statuses/create', methods=['GET', 'POST'])
def task_status_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO task_status (name, color) VALUES (?, ?)",
                  (request.form['name'], request.form.get('color')))
        db.commit()
        db.close()
        flash('Статус задачи создан', 'success')
        return redirect(url_for('task_statuses_list'))

    content = f'''
    <div class="card">
        <h2>Новый статус задачи</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Цвет</label>
                <input type="text" name="color">
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('task_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый статус задачи', content=content)


@app.route('/task_statuses/edit/<int:id>', methods=['GET', 'POST'])
def task_status_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE task_status SET name=?, color=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], request.form.get('color'), id))
        db.commit()
        db.close()
        flash('Статус задачи обновлён', 'success')
        return redirect(url_for('task_statuses_list'))
    status = db.execute("SELECT * FROM task_status WHERE id=?", (id,)).fetchone()
    if not status:
        db.close()
        flash('Статус задачи не найден', 'error')
        return redirect(url_for('task_statuses_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать статус задачи</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{status['name']}" required>
            </div>
            <div class="form-group">
                <label>Цвет</label>
                <input type="text" name="color" value="{status['color'] or ''}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('task_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать статус задачи', content=content)

@app.route('/task_statuses/delete/<int:id>')
def task_status_delete(id):
    db = get_db()
    db.execute("UPDATE task_status SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Статус задачи удалён', 'success')
    return redirect(url_for('task_statuses_list'))

#==================== ЗАДАЧИ ====================
@app.route('/tasks')
def tasks_list():
    db = get_db()
    tasks = db.execute("""
        SELECT t.*, r.description as req_desc, p.name as project_name, p.id as project_id,
               ps.id as stage_id, pst.name as stage_name,
               pr.name as priority_name, ts.name as status_name, ts.color as status_color
        FROM task t
        LEFT JOIN requirement r ON t.requirement_id = r.id
        LEFT JOIN project_stage ps ON t.stage_id = ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id = pst.id
        LEFT JOIN project p ON p.id = COALESCE(ps.project_id, r.project_id)
        JOIN priority pr ON t.priority_id = pr.id
        JOIN task_status ts ON t.status_id = ts.id
        WHERE t.is_deleted=0
        ORDER BY t.id DESC
    """).fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{f'<a href="{url_for("project_detail", id=t["project_id"])}">{t["project_name"]}</a>' if t['project_id'] else '-'}</td>
            <td>{t['description'][:40]}...</td>
            <td>{f'<a href="{url_for("project_stage_detail", id=t["stage_id"])}">{t["stage_name"]}</a>' if t['stage_id'] else '-'}</td>
            <td>{t['priority_name']}</td>
            <td>{t['deadline'] or '-'}</td>
            <td><span class="badge" style="background: {t['status_color'] or '#95a5a6'}">{t['status_name']}</span></td>
            <td>
                <a href="{url_for('task_detail', id=t['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('task_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('task_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in tasks])

    content = f'''
    <div class="card">
        <h2>Задачи</h2>
        <a href="{url_for('task_create')}" class="btn btn-success">+ Добавить задачу</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Проект</th><th>Описание</th><th>Этап</th><th>Приоритет</th><th>Срок</th><th>Статус</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Задачи', content=content)

@app.route('/tasks/create', methods=['GET', 'POST'])
def task_create():
    db = get_db()
    if request.method == 'POST':
        stage_id = request.form.get('stage_id')
        if not stage_id:
            db.close()
            flash('Задача должна быть создана под этапом — выберите этап', 'error')
            origin = request.form.get('origin')
            return redirect(url_for('project_detail', id=int(origin), tab='stages')) if origin else redirect(url_for('tasks_list'))
        db.execute("""INSERT INTO task (requirement_id, description, stage_id, priority_id, deadline, status_id)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (request.form.get('requirement_id') or None,
                   request.form['description'],
                   int(stage_id),
                   int(request.form['priority_id']),
                   request.form.get('deadline') or None,
                   int(request.form['status_id'])))
        db.commit()
        db.close()
        flash('Задача создана', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        return redirect(url_for('tasks_list'))

    requirements = db.execute(
        "SELECT r.id, r.description, p.name as project_name FROM requirement r JOIN project p ON r.project_id=p.id WHERE r.is_deleted=0").fetchall()
    stages = db.execute(
        "SELECT ps.id, ps.project_id, p.name as project_name, pst.name as type_name FROM project_stage ps JOIN project p ON ps.project_id=p.id JOIN project_stage_type pst ON ps.stage_type_id=pst.id WHERE ps.is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0").fetchall()
    db.close()

    pre_stage = request.args.get('stage_id')
    origin = request.args.get('origin')
    if not pre_stage and stages:
        chosen = stages[0]
        if origin:
            for s in stages:
                if str(s['project_id']) == str(origin):
                    chosen = s
                    break
        pre_stage = str(chosen['id'])
    req_options = '<option value="">Не выбрано</option>' + ''.join(
        [f'<option value="{r["id"]}">[{r["project_name"]}] {r["description"][:50]}</option>' for r in requirements])
    stage_options = '<option value="">— выберите этап —</option>' + ''.join(
        [f'<option value="{s["id"]}" {"selected" if str(s["id"]) == pre_stage else ""}>[{s["project_name"]}] {s["type_name"]}</option>' for s in stages])
    priority_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in priorities])
    status_options = ''.join([f'<option value="{s["id"]}">{s["name"]}</option>' for s in statuses])
    cancel_url = url_for('project_detail', id=int(origin), tab='stages') if origin else url_for('tasks_list')

    content = f'''
    <div class="card">
        <h2>Новая задача</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Требование</label>
                <select name="requirement_id">{req_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required></textarea>
            </div>
            <div class="form-group">
                <label>Этап проекта</label>
                <select name="stage_id" required>{stage_options}</select>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Срок исполнения</label>
                <input type="date" name="deadline">
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новая задача', content=content)

@app.route('/tasks/edit/<int:id>', methods=['GET', 'POST'])
def task_edit(id):
    db = get_db()
    if request.method == 'POST':
        stage_id = request.form.get('stage_id')
        if not stage_id:
            db.close()
            flash('Задача должна быть под этапом — выберите этап', 'error')
            return redirect(url_for('tasks_list'))
        db.execute("""UPDATE task SET requirement_id=?, description=?, stage_id=?,
                     priority_id=?, deadline=?, status_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (request.form.get('requirement_id') or None,
                   request.form['description'],
                   int(stage_id),
                   int(request.form['priority_id']),
                   request.form.get('deadline') or None,
                   int(request.form['status_id']), id))
        db.commit()
        db.close()
        flash('Задача обновлена', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        return redirect(url_for('tasks_list'))

    task = db.execute("SELECT * FROM task WHERE id=?", (id,)).fetchone()
    if not task:
        db.close()
        flash('Задача не найдена', 'error')
        return redirect(url_for('tasks_list'))
    requirements = db.execute(
        "SELECT r.id, r.description, p.name as project_name FROM requirement r JOIN project p ON r.project_id=p.id WHERE r.is_deleted=0").fetchall()
    stages = db.execute(
        "SELECT ps.id, p.name as project_name, pst.name as type_name FROM project_stage ps JOIN project p ON ps.project_id=p.id JOIN project_stage_type pst ON ps.stage_type_id=pst.id WHERE ps.is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0").fetchall()
    db.close()

    origin = request.args.get('origin')
    cancel_url = url_for('project_detail', id=int(origin), tab='stages') if origin else url_for('tasks_list')
    req_options = '<option value="">Не выбрано</option>' + ''.join([
                                                                       f'<option value="{r["id"]}" {"selected" if r["id"] == task["requirement_id"] else ""}>[{r["project_name"]}] {r["description"][:50]}</option>'
                                                                       for r in requirements])
    stage_options = '<option value="">— выберите этап —</option>' + ''.join([
                                                                        f'<option value="{s["id"]}" {"selected" if s["id"] == task["stage_id"] else ""}>[{s["project_name"]}] {s["type_name"]}</option>'
                                                                        for s in stages])
    priority_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == task["priority_id"] else ""}>{p["name"]}</option>' for p
         in priorities])
    status_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if s["id"] == task["status_id"] else ""}>{s["name"]}</option>' for s in
         statuses])

    content = f'''
    <div class="card">
        <h2>Редактировать задачу</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Требование</label>
                <select name="requirement_id">{req_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required>{task['description']}</textarea>
            </div>
            <div class="form-group">
                <label>Этап проекта</label>
                <select name="stage_id" required>{stage_options}</select>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Срок исполнения</label>
                <input type="date" name="deadline" value="{task['deadline'] or ''}">
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать задачу', content=content)

@app.route('/tasks/delete/<int:id>')
def task_delete(id):
    db = get_db()
    db.execute("UPDATE task SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.execute("UPDATE subtask SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE parent_task_id=? AND is_deleted=0", (id,))
    db.commit()
    db.close()
    flash('Задача удалена', 'success')
    return redirect(url_for('tasks_list'))

#==================== ПОДЗАДАЧИ ====================
@app.route('/subtasks')
def subtasks_list():
    db = get_db()
    subtasks = db.execute("""
        SELECT st.*, t.description as parent_desc, pr.name as priority_name,
               ts.name as status_name, ts.color as status_color
        FROM subtask st
        JOIN task t ON st.parent_task_id = t.id
        JOIN priority pr ON st.priority_id = pr.id
        JOIN task_status ts ON st.status_id = ts.id
        WHERE st.is_deleted=0
        ORDER BY st.id DESC
    """).fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td><a href="{url_for('task_detail', id=s['parent_task_id'])}">{s['parent_desc'][:40]}...</a></td>
            <td>{s['description'][:40]}...</td>
            <td>{s['priority_name']}</td>
            <td>{s['deadline'] or '-'}</td>
            <td><span class="badge" style="background: {s['status_color'] or '#95a5a6'}">{s['status_name']}</span></td>
            <td>
                <a href="{url_for('subtask_detail', id=s['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('subtask_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('subtask_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in subtasks])

    content = f'''
    <div class="card">
        <h2>Подзадачи</h2>
        <a href="{url_for('subtask_create')}" class="btn btn-success">+ Добавить подзадачу</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Родительская задача</th><th>Описание</th><th>Приоритет</th><th>Срок</th><th>Статус</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Подзадачи', content=content)

@app.route('/subtasks/create', methods=['GET', 'POST'])
def subtask_create():
    db = get_db()
    if request.method == 'POST':
        psid = request.form.get('parent_subtask_id') or None
        ptid = request.form.get('parent_task_id')
        if psid:
            root = db.execute("SELECT parent_task_id FROM subtask WHERE id=? AND is_deleted=0", (int(psid),)).fetchone()
            if root:
                parent_task_id = root[0]
            else:
                psid = None
                parent_task_id = int(ptid) if ptid else None
        else:
            parent_task_id = int(ptid) if ptid else None
        if not parent_task_id:
            db.close()
            flash('Подзадача должна относиться к задаче', 'error')
            return redirect(url_for('subtasks_list'))
        db.execute("""INSERT INTO subtask (parent_task_id, parent_subtask_id, description, stage_id, priority_id, deadline, status_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (parent_task_id, psid,
                   request.form['description'],
                   request.form.get('stage_id') or None,
                   int(request.form['priority_id']),
                   request.form.get('deadline') or None,
                   int(request.form['status_id'])))
        db.commit()
        db.close()
        flash('Подзадача создана', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        return redirect(url_for('subtasks_list'))

    tasks = db.execute("SELECT * FROM task WHERE is_deleted=0").fetchall()
    subtasks = db.execute("SELECT * FROM subtask WHERE is_deleted=0").fetchall()
    stages = db.execute(
        "SELECT ps.id, p.name as project_name, pst.name as type_name FROM project_stage ps JOIN project p ON ps.project_id=p.id JOIN project_stage_type pst ON ps.stage_type_id=pst.id WHERE ps.is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0").fetchall()
    db.close()

    pre_task = request.args.get('parent_task_id')
    pre_psub = request.args.get('parent_subtask_id')
    origin = request.args.get('origin')
    root_task = pre_task
    if pre_psub:
        r = db.execute("SELECT parent_task_id FROM subtask WHERE id=? AND is_deleted=0", (int(pre_psub),)).fetchone()
        root_task = str(r[0]) if r else pre_task
    task_options = ''.join([f'<option value="{t["id"]}" {"selected" if str(t["id"]) == root_task else ""}>{t["id"]}. {t["description"][:50]}</option>' for t in tasks])
    subtask_options = '<option value="">— нет, подзадача напрямую от задачи —</option>' + ''.join(
        [f'<option value="{s["id"]}" {"selected" if str(s["id"]) == pre_psub else ""}>{s["id"]}. {s["description"][:50]}</option>' for s in subtasks])
    stage_options = '<option value="">Не выбран</option>' + ''.join(
        [f'<option value="{s["id"]}">[{s["project_name"]}] {s["type_name"]}</option>' for s in stages])
    priority_options = ''.join([f'<option value="{p["id"]}">{p["name"]}</option>' for p in priorities])
    status_options = ''.join([f'<option value="{s["id"]}">{s["name"]}</option>' for s in statuses])
    cancel_url = url_for('project_detail', id=int(origin), tab='stages') if origin else url_for('subtasks_list')

    content = f'''
    <div class="card">
        <h2>Новая подзадача</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Родительская подзадача</label>
                <select name="parent_subtask_id">{subtask_options}</select>
            </div>
            <div class="form-group">
                <label>Родительская задача</label>
                <select name="parent_task_id" required>{task_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required></textarea>
            </div>
            <div class="form-group">
                <label>Этап проекта</label>
                <select name="stage_id">{stage_options}</select>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Срок исполнения</label>
                <input type="date" name="deadline">
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{cancel_url}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новая подзадача', content=content)

@app.route('/subtasks/edit/<int:id>', methods=['GET', 'POST'])
def subtask_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE subtask SET parent_task_id=?, description=?, stage_id=?,
                     priority_id=?, deadline=?, status_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (int(request.form['parent_task_id']),
                   request.form['description'],
                   request.form.get('stage_id') or None,
                   int(request.form['priority_id']),
                   request.form.get('deadline') or None,
                   int(request.form['status_id']), id))
        db.commit()
        db.close()
        flash('Подзадача обновлена', 'success')
        return redirect(url_for('subtasks_list'))

    subtask = db.execute("SELECT * FROM subtask WHERE id=?", (id,)).fetchone()
    if not subtask:
        db.close()
        flash('Подзадача не найдена', 'error')
        return redirect(url_for('subtasks_list'))
    tasks = db.execute("SELECT * FROM task WHERE is_deleted=0").fetchall()
    stages = db.execute(
        "SELECT ps.id, p.name as project_name, pst.name as type_name FROM project_stage ps JOIN project p ON ps.project_id=p.id JOIN project_stage_type pst ON ps.stage_type_id=pst.id WHERE ps.is_deleted=0").fetchall()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0").fetchall()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0").fetchall()
    db.close()

    task_options = ''.join([
                               f'<option value="{t["id"]}" {"selected" if t["id"] == subtask["parent_task_id"] else ""}>{t["id"]}. {t["description"][:50]}</option>'
                               for t in tasks])
    stage_options = '<option value="">Не выбран</option>' + ''.join([
                                                                        f'<option value="{s["id"]}" {"selected" if s["id"] == subtask["stage_id"] else ""}>[{s["project_name"]}] {s["type_name"]}</option>'
                                                                        for s in stages])
    priority_options = ''.join(
        [f'<option value="{p["id"]}" {"selected" if p["id"] == subtask["priority_id"] else ""}>{p["name"]}</option>' for
         p in priorities])
    status_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if s["id"] == subtask["status_id"] else ""}>{s["name"]}</option>' for s
         in statuses])

    content = f'''
    <div class="card">
        <h2>Редактировать подзадачу</h2>
        <form method="POST">
            <div class="form-group">
                <label>Родительская задача</label>
                <select name="parent_task_id" required>{task_options}</select>
            </div>
            <div class="form-group">
                <label>Описание</label>
                <textarea name="description" required>{subtask['description']}</textarea>
            </div>
            <div class="form-group">
                <label>Этап проекта</label>
                <select name="stage_id">{stage_options}</select>
            </div>
            <div class="form-group">
                <label>Приоритет</label>
                <select name="priority_id" required>{priority_options}</select>
            </div>
            <div class="form-group">
                <label>Срок исполнения</label>
                <input type="date" name="deadline" value="{subtask['deadline'] or ''}">
            </div>
            <div class="form-group">
                <label>Статус</label>
                <select name="status_id" required>{status_options}</select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('subtasks_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать подзадачу', content=content)

@app.route('/subtasks/delete/<int:id>')
def subtask_delete(id):
    db = get_db()
    _soft_delete_subtask_tree(db, id)
    db.commit()
    db.close()
    flash('Подзадача удалена', 'success')
    return redirect(url_for('subtasks_list'))
#==================== НАЗНАЧЕНИЯ ЗАДАЧ ====================
@app.route('/task_assignments')
def task_assignments_list():
    db = get_db()
    assignments = db.execute("""
        SELECT ta.*, e.last_name, e.first_name,
               CASE WHEN ta.task_kind='task' THEN (SELECT description FROM task WHERE id=ta.task_id)
                    ELSE (SELECT description FROM subtask WHERE id=ta.task_id) END as task_desc
        FROM task_assignment ta
        JOIN employee e ON ta.employee_id = e.id
        WHERE ta.is_deleted=0
        ORDER BY ta.id DESC
    """).fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{a['id']}</td>
            <td>{a['task_kind']}</td>
            <td>{f'<a href="{url_for("task_detail", id=a["task_id"])}">{a["task_desc"][:40]}...</a>' if a['task_kind'] == 'task' else f'<a href="{url_for("subtask_detail", id=a["task_id"])}">{a["task_desc"][:40]}...</a>'}</td>
            <td>{f'<a href="{url_for("employee_detail", id=a["employee_id"])}">{a["last_name"]} {a["first_name"]}</a>'}</td>
            <td>{int(a['share'] * 100)}%</td>
            <td>
                <a href="{url_for('task_assignment_detail', id=a['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('task_assignment_edit', id=a['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('task_assignment_delete', id=a['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for a in assignments])

    content = f'''
    <div class="card">
        <h2>Назначения задач</h2>
        <a href="{url_for('task_assignment_create')}" class="btn btn-success">+ Добавить назначение</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Тип</th><th>Задача</th><th>Сотрудник</th><th>Доля</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Назначения задач', content=content)

@app.route('/task_assignments/create', methods=['GET', 'POST'])
def task_assignment_create():
    db = get_db()
    if request.method == 'POST':
        task_id = int(request.form['task_id'])
        kind = request.form['task_kind']
        emp_id = int(request.form['employee_id'])
        origin = request.form.get('origin')
        if kind == 'task':
            pid = db.execute("SELECT COALESCE(ps.project_id, r.project_id) FROM task t LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE t.id=? AND t.is_deleted=0", (task_id,)).fetchone()
        else:
            pid = db.execute("SELECT COALESCE(ps.project_id, r.project_id) FROM subtask s JOIN task t ON s.parent_task_id=t.id LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE s.id=? AND s.is_deleted=0", (task_id,)).fetchone()
        if pid and pid[0] is not None:
            ok = db.execute("SELECT COUNT(*) FROM project_employee WHERE project_id=? AND employee_id=? AND is_deleted=0", (pid[0], emp_id)).fetchone()[0]
            if not ok:
                db.close()
                flash('Исполнитель не назначен на проект задачи', 'error')
                return redirect(url_for('project_detail', id=int(origin), tab='stages')) if origin else redirect(url_for('task_assignments_list'))
        if kind == 'subtask':
            existing = db.execute("SELECT id FROM task_assignment WHERE task_id=? AND task_kind='subtask' AND is_deleted=0", (task_id,)).fetchone()
            if existing:
                db.execute("UPDATE task_assignment SET employee_id=?, share=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (emp_id, float(request.form['share']), existing['id']))
                db.commit()
                db.close()
                flash('Исполнитель подзадачи заменён (у подзадачи один исполнитель)', 'success')
                return redirect(url_for('project_detail', id=int(origin), tab='stages')) if origin else redirect(url_for('task_assignments_list'))
        db.execute("""INSERT INTO task_assignment (task_id, task_kind, employee_id, share)
                     VALUES (?, ?, ?, ?)""",
                  (task_id,
                   kind,
                   emp_id,
                   float(request.form['share'])))
        db.commit()
        db.close()
        flash('Назначение создано', 'success')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        return redirect(url_for('task_assignments_list'))
    tasks = db.execute("SELECT id, description FROM task WHERE is_deleted=0").fetchall()
    subtasks = db.execute("SELECT id, description FROM subtask WHERE is_deleted=0").fetchall()
    employees = db.execute("SELECT id, last_name, first_name FROM employee WHERE is_deleted=0").fetchall()
    task_proj = {}
    for t in db.execute("""
        SELECT t.id, COALESCE(ps.project_id, r.project_id) pid FROM task t
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        WHERE t.is_deleted=0
    """):
        task_proj['task:' + str(t['id'])] = t['pid']
    for s in db.execute("""
        SELECT s.id, COALESCE(ps.project_id, r.project_id) pid FROM subtask s
        JOIN task t ON s.parent_task_id=t.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        WHERE s.is_deleted=0
    """):
        task_proj['subtask:' + str(s['id'])] = s['pid']
    proj_emp = _project_employee_options(db)
    db.close()
    task_proj_json = json.dumps({k: (str(v) if v else '') for k, v in task_proj.items()})
    proj_emp_json = json.dumps({str(k): ''.join(v) for k, v in proj_emp.items()})

    pre_task = request.args.get('task_id')
    pre_kind = request.args.get('task_kind', 'task')
    origin = request.args.get('origin')

    task_options = ''.join([f'<option value="{t["id"]}" {"selected" if str(t["id"]) == pre_task and pre_kind == "task" else ""}>Задача: {t["description"][:50]}</option>' for t in tasks])
    subtask_options = ''.join(
        [f'<option value="{s["id"]}" {"selected" if str(s["id"]) == pre_task and pre_kind == "subtask" else ""}>Подзадача: {s["description"][:50]}</option>' for s in subtasks])
    employee_options = ''.join(
        [f'<option value="{e["id"]}">{e["last_name"]} {e["first_name"]}</option>' for e in employees])

    content = f'''
    <div class="card">
        <h2>Новое назначение</h2>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            <div class="form-group">
                <label>Тип задачи</label>
                <select name="task_kind" required onchange="toggleTaskSelect(this.value); setEmployees()">
                    <option value="task" {"selected" if pre_kind == "task" else ""}>Задача</option>
                    <option value="subtask" {"selected" if pre_kind == "subtask" else ""}>Подзадача</option>
                </select>
            </div>
            <div class="form-group" id="task_select" style="display:{'block' if pre_kind == 'task' else 'none'}">
                <label>Задача</label>
                <select name="task_id" onchange="setEmployees()">{task_options}</select>
            </div>
            <div class="form-group" id="subtask_select" style="display:{'block' if pre_kind == 'subtask' else 'none'}">
                <label>Подзадача</label>
                <select name="task_id" onchange="setEmployees()">{subtask_options}</select>
            </div>
            <div class="form-group">
                <label>Сотрудник</label>
                <select name="employee_id" required>{employee_options}</select>
            </div>
            <div class="form-group">
                <label>Доля (0.0 - 1.0)</label>
                <input type="number" name="share" step="0.1" min="0" max="1" value="1.0" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('task_assignments_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    <script>
    var taskProject = {task_proj_json};
    var projEmployees = {proj_emp_json};
    function toggleTaskSelect(kind) {{
        document.getElementById('task_select').style.display = kind==='task' ? 'block' : 'none';
        document.getElementById('subtask_select').style.display = kind==='subtask' ? 'block' : 'none';
    }}
    function setEmployees() {{
        var empSel = document.querySelector('select[name=employee_id]');
        var cur = empSel.value;
        var kind = document.querySelector('select[name=task_kind]').value;
        var box = document.querySelector(kind==='task' ? '#task_select select' : '#subtask_select select');
        var taskId = box ? box.value : '';
        var pid = taskProject[kind + ':' + taskId];
        var opts = (pid && projEmployees[pid]) ? projEmployees[pid] : '<option value="">нет исполнителей, назначенных на проект</option>';
        empSel.innerHTML = opts;
        var has = Array.prototype.some.call(empSel.options, function(o) {{ return o.value === cur; }});
        if (cur) {{ empSel.value = has ? cur : ''; }}
    }}
    setEmployees();
    </script>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новое назначение', content=content)

@app.route('/task_assignments/edit/<int:id>', methods=['GET', 'POST'])
def task_assignment_edit(id):
    db = get_db()
    if request.method == 'POST':
        task_id = int(request.form['task_id'])
        kind = request.form['task_kind']
        emp_id = int(request.form['employee_id'])
        if kind == 'task':
            pid = db.execute("SELECT COALESCE(ps.project_id, r.project_id) FROM task t LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE t.id=? AND t.is_deleted=0", (task_id,)).fetchone()
        else:
            pid = db.execute("SELECT COALESCE(ps.project_id, r.project_id) FROM subtask s JOIN task t ON s.parent_task_id=t.id LEFT JOIN project_stage ps ON t.stage_id=ps.id LEFT JOIN requirement r ON t.requirement_id=r.id WHERE s.id=? AND s.is_deleted=0", (task_id,)).fetchone()
        if pid and pid[0] is not None:
            ok = db.execute("SELECT COUNT(*) FROM project_employee WHERE project_id=? AND employee_id=? AND is_deleted=0", (pid[0], emp_id)).fetchone()[0]
            if not ok:
                db.close()
                flash('Исполнитель не назначен на проект задачи', 'error')
                return redirect(url_for('task_assignments_list'))
        if kind == 'subtask':
            conflict = db.execute("SELECT id FROM task_assignment WHERE task_id=? AND task_kind='subtask' AND is_deleted=0 AND id<>?", (task_id, id)).fetchone()
            if conflict:
                db.close()
                flash('У подзадачи уже есть исполнитель (только один)', 'error')
                return redirect(url_for('task_assignments_list'))
        db.execute("""UPDATE task_assignment SET task_id=?, task_kind=?, employee_id=?,
                     share=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (task_id,
                   kind,
                   emp_id,
                   float(request.form['share']), id))
        db.commit()
        db.close()
        flash('Назначение обновлено', 'success')
        return redirect(url_for('task_assignments_list'))

    assignment = db.execute("SELECT * FROM task_assignment WHERE id=?", (id,)).fetchone()
    if not assignment:
        db.close()
        flash('Назначение не найдено', 'error')
        return redirect(url_for('task_assignments_list'))
    tasks = db.execute("SELECT id, description FROM task WHERE is_deleted=0").fetchall()
    subtasks = db.execute("SELECT id, description FROM subtask WHERE is_deleted=0").fetchall()
    employees = db.execute("SELECT id, last_name, first_name FROM employee WHERE is_deleted=0").fetchall()
    task_proj = {}
    for t in db.execute("""
        SELECT t.id, COALESCE(ps.project_id, r.project_id) pid FROM task t
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        WHERE t.is_deleted=0
    """):
        task_proj['task:' + str(t['id'])] = t['pid']
    for s in db.execute("""
        SELECT s.id, COALESCE(ps.project_id, r.project_id) pid FROM subtask s
        JOIN task t ON s.parent_task_id=t.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        WHERE s.is_deleted=0
    """):
        task_proj['subtask:' + str(s['id'])] = s['pid']
    proj_emp = _project_employee_options(db)
    db.close()

    task_options = ''.join([
                               f'<option value="{t["id"]}" {"selected" if t["id"] == assignment["task_id"] and assignment["task_kind"] == "task" else ""}>Задача: {t["description"][:50]}</option>'
                               for t in tasks])
    subtask_options = ''.join([
                                  f'<option value="{s["id"]}" {"selected" if s["id"] == assignment["task_id"] and assignment["task_kind"] == "subtask" else ""}>Подзадача: {s["description"][:50]}</option>'
                                  for s in subtasks])
    employee_options = ''.join([
                                   f'<option value="{e["id"]}" {"selected" if e["id"] == assignment["employee_id"] else ""}>{e["last_name"]} {e["first_name"]}</option>'
                                   for e in employees])
    task_proj_json = json.dumps({k: (str(v) if v else '') for k, v in task_proj.items()})
    proj_emp_json = json.dumps({str(k): ''.join(v) for k, v in proj_emp.items()})

    content = f'''
    <div class="card">
        <h2>Редактировать назначение</h2>
        <form method="POST">
            <div class="form-group">
                <label>Тип задачи</label>
                <select name="task_kind" required onchange="toggleTaskSelect(this.value); setEmployees()">
                    <option value="task" {"selected" if assignment["task_kind"] == "task" else ""}>Задача</option>
                    <option value="subtask" {"selected" if assignment["task_kind"] == "subtask" else ""}>Подзадача</option>
                </select>
            </div>
            <div class="form-group" id="task_select" style="display:{'block' if assignment['task_kind'] == 'task' else 'none'}">
                <label>Задача</label>
                <select name="task_id" onchange="setEmployees()">{task_options}</select>
            </div>
            <div class="form-group" id="subtask_select" style="display:{'block' if assignment['task_kind'] == 'subtask' else 'none'}">
                <label>Подзадача</label>
                <select name="task_id" onchange="setEmployees()">{subtask_options}</select>
            </div>
            <div class="form-group">
                <label>Сотрудник</label>
                <select name="employee_id" required>{employee_options}</select>
            </div>
            <div class="form-group">
                <label>Доля (0.0 - 1.0)</label>
                <input type="number" name="share" step="0.1" min="0" max="1" value="{assignment['share']}" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('task_assignments_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    <script>
    var taskProject = {task_proj_json};
    var projEmployees = {proj_emp_json};
    function toggleTaskSelect(kind) {{
        document.getElementById('task_select').style.display = kind==='task' ? 'block' : 'none';
        document.getElementById('subtask_select').style.display = kind==='subtask' ? 'block' : 'none';
    }}
    function setEmployees() {{
        var empSel = document.querySelector('select[name=employee_id]');
        var cur = empSel.value;
        var kind = document.querySelector('select[name=task_kind]').value;
        var box = document.querySelector(kind==='task' ? '#task_select select' : '#subtask_select select');
        var taskId = box ? box.value : '';
        var pid = taskProject[kind + ':' + taskId];
        var opts = (pid && projEmployees[pid]) ? projEmployees[pid] : '<option value="">нет исполнителей, назначенных на проект</option>';
        empSel.innerHTML = opts;
        var has = Array.prototype.some.call(empSel.options, function(o) {{ return o.value === cur; }});
        if (cur) {{ empSel.value = has ? cur : ''; }}
    }}
    setEmployees();
    </script>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать назначение', content=content)

@app.route('/task_assignments/delete/<int:id>')
def task_assignment_delete(id):
    db = get_db()
    db.execute("UPDATE task_assignment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Назначение удалено', 'success')
    return redirect(url_for('task_assignments_list'))
#==================== СОБЫТИЯ ====================
@app.route('/events')
def events_list():
    db = get_db()
    events = db.execute("""
        SELECT * FROM event WHERE is_deleted=0 ORDER BY occurred_at DESC
    """).fetchall()
    rows = ''.join([f'''
        <tr>
            <td>{e['id']}</td>
            <td>{e['occurred_at']}</td>
            <td>{e['description'][:60]}...</td>
            <td>{(e['decision'] or '-')[:60]}</td>
            <td>
                <a href="{url_for('event_detail', id=e['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('event_edit', id=e['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('event_delete', id=e['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for e in events])

    content = f'''
    <div class="card">
        <h2>События (вводные преподавателя)</h2>
        <a href="{url_for('event_create')}" class="btn btn-success">+ Добавить событие</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Дата/время</th><th>Описание</th><th>Решение</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='События', content=content)

@app.route('/events/create', methods=['GET', 'POST'])
def event_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO event (occurred_at, description, decision) VALUES (?, ?, ?)",
                  (request.form.get('occurred_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   request.form['description'],
                   request.form.get('decision')))
        db.commit()
        db.close()
        flash('Событие создано', 'success')
        return redirect(url_for('events_list'))

    content = f'''
    <div class="card">
        <h2>Новое событие</h2>
        <form method="POST">
            <div class="form-group">
                <label>Дата/время события</label>
                <input type="datetime-local" name="occurred_at" value="{datetime.now().strftime('%Y-%m-%dT%H:%M')}">
            </div>
            <div class="form-group">
                <label>Описание события</label>
                <textarea name="description" required placeholder="Например: форс-мажор, изменение конъюнктуры, болезнь сотрудника..."></textarea>
            </div>
            <div class="form-group">
                <label>Принятое решение</label>
                <textarea name="decision" placeholder="Как отреагировал СА"></textarea>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('events_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новое событие', content=content)

@app.route('/events/edit/<int:id>', methods=['GET', 'POST'])
def event_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE event SET occurred_at=?, description=?, decision=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form.get('occurred_at'), request.form['description'],
                   request.form.get('decision'), id))
        db.commit()
        db.close()
        flash('Событие обновлено', 'success')
        return redirect(url_for('events_list'))

    event = db.execute("SELECT * FROM event WHERE id=?", (id,)).fetchone()
    if not event:
        db.close()
        flash('Событие не найдено', 'error')
        return redirect(url_for('events_list'))
    db.close()

    occurred = event['occurred_at'].replace(' ', 'T') if event['occurred_at'] else ''

    content = f'''
    <div class="card">
        <h2>Редактировать событие</h2>
        <form method="POST">
            <div class="form-group">
                <label>Дата/время события</label>
                <input type="datetime-local" name="occurred_at" value="{occurred}">
            </div>
            <div class="form-group">
                <label>Описание события</label>
                <textarea name="description" required>{event['description']}</textarea>
            </div>
            <div class="form-group">
                <label>Принятое решение</label>
                <textarea name="decision">{event['decision'] or ''}</textarea>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('events_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать событие', content=content)

@app.route('/events/delete/<int:id>')
def event_delete(id):
    db = get_db()
    db.execute("UPDATE event SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Событие удалено', 'success')
    return redirect(url_for('events_list'))
#==================== ОТЧЁТЫ ====================

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

@app.route('/reports/projects')
def report_projects():
    db = get_db()
    proj_total = db.execute("SELECT COUNT(*) FROM project WHERE is_deleted=0").fetchone()[0]
    cost_total = db.execute("SELECT COALESCE(SUM(cost), 0) FROM project WHERE is_deleted=0").fetchone()[0]
    proj_budget = db.execute("SELECT COUNT(*) FROM project WHERE is_deleted=0 AND cost IS NOT NULL").fetchone()[0]
    prj_by_prio = db.execute("""
        SELECT pr.name, pr.weight, COUNT(p.id) cnt, COALESCE(SUM(p.cost), 0) cost
        FROM priority pr
        LEFT JOIN project p ON p.priority_id=pr.id AND p.is_deleted=0
        WHERE pr.is_deleted=0
        GROUP BY pr.id ORDER BY pr.weight
    """).fetchall()
    progress = db.execute("""
        SELECT p.name,
            (SELECT COUNT(*) FROM project_stage ps WHERE ps.project_id=p.id AND ps.is_deleted=0) stages,
            (SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
                WHERE ps.project_id=p.id AND ps.is_deleted=0 AND pss.name='Завершён') stages_done,
            (SELECT COUNT(*) FROM task t
                LEFT JOIN project_stage ps ON t.stage_id=ps.id
                LEFT JOIN requirement r ON t.requirement_id=r.id
                WHERE t.is_deleted=0 AND COALESCE(ps.project_id, r.project_id)=p.id) tasks,
            (SELECT COUNT(*) FROM task t
                LEFT JOIN project_stage ps ON t.stage_id=ps.id
                LEFT JOIN requirement r ON t.requirement_id=r.id
                JOIN task_status ts ON t.status_id=ts.id
                WHERE t.is_deleted=0 AND COALESCE(ps.project_id, r.project_id)=p.id
                  AND ts.name='Выполнена') tasks_done
        FROM project p WHERE p.is_deleted=0 ORDER BY p.name
    """).fetchall()
    db.close()
    avg_prio = (sum(p['weight'] * p['cnt'] for p in prj_by_prio) / proj_total) if proj_total else 0
    cards = [
        ('Всего проектов', proj_total, '#2c3e50'),
        ('Общая стоимость', f'{cost_total:,.0f}', '#2c3e50'),
        ('Проектов с бюджетом', proj_budget, '#2c3e50'),
        ('Средний приоритет', f'{avg_prio:.2f}' if proj_total else 0, '#2c3e50'),
    ]
    rows1 = [[p['name'], p['weight'], p['cnt'], f"{p['cost']:,.0f}"] for p in prj_by_prio]
    rows2 = []
    for p in progress:
        t_pct = round(p['tasks_done'] / p['tasks'] * 100) if p['tasks'] else 0
        s_pct = round(p['stages_done'] / p['stages'] * 100) if p['stages'] else 0
        rows2.append([p['name'], f"{p['stages_done']}/{p['stages']}",
                      f"{p['tasks_done']}/{p['tasks']}", f"{t_pct}%", f"{s_pct}%"])
    return _report_page('Отчёт: Проекты', cards, [
        {'title': 'Проекты по приоритетам', 'headers': ['Приоритет', 'Вес', 'Кол-во', 'Стоимость'], 'rows': rows1},
        {'title': 'Прогресс проектов', 'headers': ['Проект', 'Этапы (завершено/всего)', 'Задачи (выполнено/всего)', 'Прогресс по задачам', 'Прогресс по этапам'], 'rows': rows2},
    ])

@app.route('/reports/stakeholders')
def report_stakeholders():
    db = get_db()
    st_total = db.execute("SELECT COUNT(*) FROM stakeholder WHERE is_deleted=0").fetchone()[0]
    types = db.execute("""
        SELECT st.name, st.influence_priority inf, st.interest_priority ints, COUNT(s.id) cnt
        FROM stakeholder_type st
        LEFT JOIN stakeholder s ON s.type_id=st.id AND s.is_deleted=0
        WHERE st.is_deleted=0
        GROUP BY st.id ORDER BY st.influence_priority DESC, st.interest_priority DESC
    """).fetchall()
    db.close()
    def quadrant(inf, ints):
        if inf >= 4 and ints >= 4:
            return 'Ключевые игроки'
        if inf >= 4:
            return 'Удовлетворять'
        if ints >= 4:
            return 'Держать в курсе'
        return 'Наблюдать'
    key = sum(1 for t in types if quadrant(t['inf'], t['ints']) == 'Ключевые игроки')
    cards = [('Всего стейкхолдеров', st_total, '#2c3e50'),
             ('Типов', len(types), '#2c3e50'),
             ('Ключевые игроки', key, '#e74c3c')]
    rows = [[t['name'], t['inf'], t['ints'], t['cnt'], quadrant(t['inf'], t['ints'])] for t in types]
    return _report_page('Отчёт: Стейкхолдеры', cards, [
        {'title': 'Матрица власти и интереса (по типам)', 'headers': ['Тип', 'Влияние', 'Интерес', 'Кол-во', 'Квадрант'], 'rows': rows},
    ])

@app.route('/reports/employees')
def report_employees():
    db = get_db()
    emp_total = db.execute("SELECT COUNT(*) FROM employee WHERE is_deleted=0").fetchone()[0]
    emp_avail = db.execute("""
        SELECT COUNT(*) FROM employee e JOIN employee_status es ON e.status_id=es.id
        WHERE e.is_deleted=0 AND es.is_available=1
    """).fetchone()[0]
    emp_assigned = db.execute("SELECT COUNT(DISTINCT employee_id) FROM task_assignment WHERE is_deleted=0").fetchone()[0]
    load = db.execute("""
        SELECT e.last_name, e.first_name, pt.name pos, es.name st, es.is_available av,
               (SELECT COUNT(*) FROM task_assignment ta WHERE ta.employee_id=e.id AND ta.is_deleted=0) acnt,
               COALESCE((SELECT SUM(ta.share) FROM task_assignment ta WHERE ta.employee_id=e.id AND ta.is_deleted=0), 0) lshare
        FROM employee e
        JOIN position_type pt ON e.position_type_id=pt.id
        JOIN employee_status es ON e.status_id=es.id
        WHERE e.is_deleted=0
        ORDER BY lshare DESC
    """).fetchall()
    by_pos = db.execute("""
        SELECT pt.name, COUNT(e.id) cnt,
               COALESCE(SUM(CASE WHEN es.is_available=1 THEN 1 ELSE 0 END), 0) avail
        FROM position_type pt
        LEFT JOIN employee e ON e.position_type_id=pt.id AND e.is_deleted=0
        LEFT JOIN employee_status es ON e.status_id=es.id
        WHERE pt.is_deleted=0
        GROUP BY pt.id ORDER BY pt.name
    """).fetchall()
    db.close()
    overloaded = sum(1 for l in load if l['lshare'] > 1.0)
    cards = [('Всего сотрудников', emp_total, '#2c3e50'),
             ('Доступно', emp_avail, '#27ae60'),
             ('Заняты в задачах', emp_assigned, '#2c3e50'),
             ('Перегружены (>100%)', overloaded, '#e74c3c')]
    rows = [[l['last_name'], l['first_name'], l['pos'], l['st'], l['acnt'], f"{round(l['lshare'] * 100)}%"] for l in load]
    rows2 = [[p['name'], p['cnt'], p['avail']] for p in by_pos]
    return _report_page('Отчёт: Сотрудники', cards, [
        {'title': 'Загрузка сотрудников', 'headers': ['Фамилия', 'Имя', 'Должность', 'Статус', 'Назначений', 'Загрузка %'], 'rows': rows},
        {'title': 'Состав по должностям', 'headers': ['Должность', 'Сотрудников', 'Доступно'], 'rows': rows2},
    ])

@app.route('/reports/requirements')
def report_requirements():
    db = get_db()
    req_total = db.execute("SELECT COUNT(*) FROM requirement WHERE is_deleted=0").fetchone()[0]
    req_criteria = db.execute("""
        SELECT COUNT(*) FROM requirement
        WHERE is_deleted=0 AND acceptance_criteria IS NOT NULL AND acceptance_criteria <> ''
    """).fetchone()[0]
    req_impl = db.execute("""
        SELECT COUNT(DISTINCT r.id) FROM requirement r
        WHERE r.is_deleted=0 AND EXISTS (SELECT 1 FROM task t WHERE t.requirement_id=r.id AND t.is_deleted=0)
    """).fetchone()[0]
    by_proj = db.execute("""
        SELECT p.name, COUNT(r.id) total,
               COALESCE(SUM(CASE WHEN r.acceptance_criteria IS NOT NULL AND r.acceptance_criteria <> '' THEN 1 ELSE 0 END), 0) crit,
               COALESCE(SUM(CASE WHEN EXISTS (SELECT 1 FROM task t WHERE t.requirement_id=r.id AND t.is_deleted=0) THEN 1 ELSE 0 END), 0) impl
        FROM project p LEFT JOIN requirement r ON r.project_id=p.id AND r.is_deleted=0
        WHERE p.is_deleted=0 GROUP BY p.id ORDER BY p.name
    """).fetchall()
    by_type = db.execute("""
        SELECT rt.name, COUNT(r.id) cnt FROM requirement_type rt
        LEFT JOIN requirement r ON r.requirement_type_id=rt.id AND r.is_deleted=0
        WHERE rt.is_deleted=0 GROUP BY rt.id ORDER BY rt.name
    """).fetchall()
    by_prio = db.execute("""
        SELECT pr.name, COUNT(r.id) cnt FROM priority pr
        LEFT JOIN requirement r ON r.priority_id=pr.id AND r.is_deleted=0
        WHERE pr.is_deleted=0 GROUP BY pr.id ORDER BY pr.weight
    """).fetchall()
    db.close()
    cards = [('Всего требований', req_total, '#2c3e50'),
             ('С критерием проверки', req_criteria, '#2c3e50'),
             ('Реализовано (есть задачи)', req_impl, '#27ae60'),
             ('Без задач', req_total - req_impl, '#e74c3c')]
    rows = [[p['name'], p['total'], p['crit'], p['impl'], p['total'] - p['impl']] for p in by_proj]
    rows2 = [[t['name'], t['cnt']] for t in by_type]
    rows3 = [[t['name'], t['cnt']] for t in by_prio]
    return _report_page('Отчёт: Требования', cards, [
        {'title': 'По проектам', 'headers': ['Проект', 'Требований', 'С критерием', 'Реализовано', 'Без задач'], 'rows': rows},
        {'title': 'По типам', 'headers': ['Тип требования', 'Кол-во'], 'rows': rows2},
        {'title': 'По приоритетам', 'headers': ['Приоритет', 'Кол-во'], 'rows': rows3},
    ])

@app.route('/reports/stages')
def report_stages():
    db = get_db()
    st_total = db.execute("SELECT COUNT(*) FROM project_stage WHERE is_deleted=0").fetchone()[0]
    st_done = db.execute("""
        SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE ps.is_deleted=0 AND pss.name='Завершён'
    """).fetchone()[0]
    st_work = db.execute("""
        SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE ps.is_deleted=0 AND pss.name='В работе'
    """).fetchone()[0]
    st_over = db.execute("""
        SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE ps.is_deleted=0 AND ps.planned_end < date('now') AND pss.name NOT IN ('Завершён', 'Отменён')
    """).fetchone()[0]
    by_proj = db.execute("""
        SELECT p.name, COUNT(ps.id) total,
               SUM(CASE WHEN pss.name='Завершён' THEN 1 ELSE 0 END) done,
               SUM(CASE WHEN pss.name='В работе' THEN 1 ELSE 0 END) work,
               SUM(CASE WHEN ps.planned_end < date('now') AND pss.name NOT IN ('Завершён', 'Отменён') THEN 1 ELSE 0 END) over
        FROM project p
        LEFT JOIN project_stage ps ON ps.project_id=p.id AND ps.is_deleted=0
        LEFT JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE p.is_deleted=0 GROUP BY p.id ORDER BY p.name
    """).fetchall()
    db.close()
    cards = [('Всего этапов', st_total, '#2c3e50'),
             ('В работе', st_work, '#3498db'),
             ('Завершено', st_done, '#27ae60'),
             ('Просрочено', st_over, '#e74c3c')]
    rows = [[p['name'], p['total'], p['done'], p['work'], p['over']] for p in by_proj]
    return _report_page('Отчёт: Этапы', cards, [
        {'title': 'Этапы по проектам', 'headers': ['Проект', 'Всего', 'Завершено', 'В работе', 'Просрочено'], 'rows': rows},
    ])

@app.route('/reports/tasks')
def report_tasks():
    db = get_db()
    t_total = db.execute("SELECT COUNT(*) FROM task WHERE is_deleted=0").fetchone()[0]
    t_done = db.execute("""
        SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id=ts.id
        WHERE t.is_deleted=0 AND ts.name='Выполнена'
    """).fetchone()[0]
    t_work = db.execute("""
        SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id=ts.id
        WHERE t.is_deleted=0 AND ts.name IN ('Новая', 'В работе')
    """).fetchone()[0]
    t_over = db.execute("""
        SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id=ts.id
        WHERE t.is_deleted=0 AND t.deadline < date('now') AND ts.name NOT IN ('Выполнена', 'Отменена')
    """).fetchone()[0]
    t_noexec = db.execute("""
        SELECT COUNT(*) FROM task t WHERE t.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta WHERE ta.task_id=t.id AND ta.task_kind='task' AND ta.is_deleted=0)
    """).fetchone()[0]
    by_status = db.execute("""
        SELECT ts.name, ts.color, COUNT(t.id) cnt FROM task_status ts
        LEFT JOIN task t ON t.status_id=ts.id AND t.is_deleted=0
        WHERE ts.is_deleted=0 GROUP BY ts.id ORDER BY ts.id
    """).fetchall()
    by_prio = db.execute("""
        SELECT pr.name, COUNT(t.id) cnt FROM priority pr
        LEFT JOIN task t ON t.priority_id=pr.id AND t.is_deleted=0
        WHERE pr.is_deleted=0 GROUP BY pr.id ORDER BY pr.weight
    """).fetchall()
    noexec_list = db.execute("""
        SELECT t.id, p.name pname, pst.name stype, t.description, pr.name prio, ts.name st
        FROM task t
        JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        LEFT JOIN project p ON p.id = COALESCE(ps.project_id, (SELECT project_id FROM requirement WHERE id=t.requirement_id))
        WHERE t.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta WHERE ta.task_id=t.id AND ta.task_kind='task' AND ta.is_deleted=0)
    """).fetchall()
    db.close()
    cards = [('Всего задач', t_total, '#2c3e50'),
             ('В работе', t_work, '#3498db'),
             ('Выполнено', t_done, '#27ae60'),
             ('Просрочено', t_over, '#e74c3c'),
             ('Без исполнителя', t_noexec, '#f39c12')]
    rows = [[f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["name"]}</span>', s['cnt']] for s in by_status]
    rows2 = [[t['name'], t['cnt']] for t in by_prio]
    rows3 = [[t['id'], t['pname'] or '-', t['stype'] or '-', t['description'][:60], t['prio'], t['st']] for t in noexec_list]
    return _report_page('Отчёт: Задачи', cards, [
        {'title': 'По статусам', 'headers': ['Статус', 'Кол-во'], 'rows': rows},
        {'title': 'По приоритетам', 'headers': ['Приоритет', 'Кол-во'], 'rows': rows2},
        {'title': 'Задачи без исполнителя', 'headers': ['ID', 'Проект', 'Этап', 'Описание', 'Приоритет', 'Статус'], 'rows': rows3},
    ])

@app.route('/reports/subtasks')
def report_subtasks():
    db = get_db()
    s_total = db.execute("SELECT COUNT(*) FROM subtask WHERE is_deleted=0").fetchone()[0]
    s_done = db.execute("""
        SELECT COUNT(*) FROM subtask s JOIN task_status ts ON s.status_id=ts.id
        WHERE s.is_deleted=0 AND ts.name='Выполнена'
    """).fetchone()[0]
    s_work = db.execute("""
        SELECT COUNT(*) FROM subtask s JOIN task_status ts ON s.status_id=ts.id
        WHERE s.is_deleted=0 AND ts.name IN ('Новая', 'В работе')
    """).fetchone()[0]
    s_over = db.execute("""
        SELECT COUNT(*) FROM subtask s JOIN task_status ts ON s.status_id=ts.id
        WHERE s.is_deleted=0 AND s.deadline < date('now') AND ts.name NOT IN ('Выполнена', 'Отменена')
    """).fetchone()[0]
    s_noexec = db.execute("""
        SELECT COUNT(*) FROM subtask s WHERE s.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta WHERE ta.task_id=s.id AND ta.task_kind='subtask' AND ta.is_deleted=0)
    """).fetchone()[0]
    by_status = db.execute("""
        SELECT ts.name, ts.color, COUNT(s.id) cnt FROM task_status ts
        LEFT JOIN subtask s ON s.status_id=ts.id AND s.is_deleted=0
        WHERE ts.is_deleted=0 GROUP BY ts.id ORDER BY ts.id
    """).fetchall()
    noexec_list = db.execute("""
        SELECT s.id, t.description parent, s.description, pr.name prio, ts.name st
        FROM subtask s
        JOIN task t ON s.parent_task_id=t.id
        JOIN priority pr ON s.priority_id=pr.id
        JOIN task_status ts ON s.status_id=ts.id
        WHERE s.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta WHERE ta.task_id=s.id AND ta.task_kind='subtask' AND ta.is_deleted=0)
    """).fetchall()
    db.close()
    cards = [('Всего подзадач', s_total, '#2c3e50'),
             ('В работе', s_work, '#3498db'),
             ('Выполнено', s_done, '#27ae60'),
             ('Просрочено', s_over, '#e74c3c'),
             ('Без исполнителя', s_noexec, '#f39c12')]
    rows = [[f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["name"]}</span>', s['cnt']] for s in by_status]
    rows2 = [[s['id'], s['parent'][:50], s['description'][:50], s['prio'], s['st']] for s in noexec_list]
    return _report_page('Отчёт: Подзадачи', cards, [
        {'title': 'По статусам', 'headers': ['Статус', 'Кол-во'], 'rows': rows},
        {'title': 'Подзадачи без исполнителя', 'headers': ['ID', 'Родительская задача', 'Описание', 'Приоритет', 'Статус'], 'rows': rows2},
    ])

@app.route('/reports/assignments')
def report_assignments():
    db = get_db()
    a_total = db.execute("SELECT COUNT(*) FROM task_assignment WHERE is_deleted=0").fetchone()[0]
    a_task = db.execute("SELECT COUNT(*) FROM task_assignment WHERE is_deleted=0 AND task_kind='task'").fetchone()[0]
    a_sub = db.execute("SELECT COUNT(*) FROM task_assignment WHERE is_deleted=0 AND task_kind='subtask'").fetchone()[0]
    by_emp = db.execute("""
        SELECT e.last_name, e.first_name, pt.name pos,
               COALESCE(SUM(CASE WHEN ta.task_kind='task' THEN ta.share ELSE 0 END), 0) task_share,
               COALESCE(SUM(CASE WHEN ta.task_kind='subtask' THEN ta.share ELSE 0 END), 0) sub_share,
               COUNT(ta.id) acnt
        FROM employee e
        LEFT JOIN task_assignment ta ON ta.employee_id=e.id AND ta.is_deleted=0
        JOIN position_type pt ON e.position_type_id=pt.id
        WHERE e.is_deleted=0
        GROUP BY e.id ORDER BY (task_share + sub_share) DESC
    """).fetchall()
    db.close()
    max_load = max((a['task_share'] + a['sub_share'] for a in by_emp), default=0)
    cards = [('Назначений всего', a_total, '#2c3e50'),
             ('По задачам', a_task, '#3498db'),
             ('По подзадачам', a_sub, '#27ae60'),
             ('Максимальная загрузка', f'{round(max_load * 100)}%', '#e74c3c')]
    rows = [[a['last_name'], a['first_name'], a['pos'], f"{round(a['task_share'] * 100)}%",
             f"{round(a['sub_share'] * 100)}%", f"{round((a['task_share'] + a['sub_share']) * 100)}%", a['acnt']] for a in by_emp]
    return _report_page('Отчёт: Назначения', cards, [
        {'title': 'Загрузка по сотрудникам', 'headers': ['Сотрудник', 'Должность', 'Задачи (доля)', 'Подзадачи (доля)', 'Итого %', 'Назначений'], 'rows': rows},
    ])

@app.route('/reports/events')
def report_events():
    db = get_db()
    e_total = db.execute("SELECT COUNT(*) FROM event WHERE is_deleted=0").fetchone()[0]
    e_last30 = db.execute("""
        SELECT COUNT(*) FROM event WHERE is_deleted=0 AND occurred_at >= date('now', '-30 days')
    """).fetchone()[0]
    months = db.execute("""
        SELECT strftime('%Y-%m', occurred_at) m, COUNT(*) cnt
        FROM event WHERE is_deleted=0 GROUP BY m ORDER BY m DESC
    """).fetchall()
    recent = db.execute("SELECT * FROM event WHERE is_deleted=0 ORDER BY occurred_at DESC LIMIT 10").fetchall()
    db.close()
    cards = [('Всего событий', e_total, '#2c3e50'),
             ('За 30 дней', e_last30, '#3498db'),
             ('Последнее событие', recent[0]['occurred_at'] if recent else '-', '#2c3e50')]
    rows = [[m['m'], m['cnt']] for m in months]
    rows2 = [[e['occurred_at'], e['description'], e['decision'] or '-'] for e in recent]
    return _report_page('Отчёт: События', cards, [
        {'title': 'Динамика по месяцам', 'headers': ['Месяц', 'Кол-во'], 'rows': rows},
        {'title': 'Последние события', 'headers': ['Дата', 'Описание', 'Решение'], 'rows': rows2},
    ])

#==================== ДЕТАЛЬНЫЕ СТРАНИЦЫ ====================

@app.route('/employees/<int:id>')
def employee_detail(id):
    db = get_db()
    emp = db.execute("""
        SELECT e.*, pt.name position_name, es.name status_name, es.is_available
        FROM employee e
        JOIN position_type pt ON e.position_type_id=pt.id
        JOIN employee_status es ON e.status_id=es.id
        WHERE e.id=? AND e.is_deleted=0
    """, (id,)).fetchone()
    if not emp:
        db.close()
        flash('Сотрудник не найден', 'error')
        return redirect(url_for('employees_list'))
    load = db.execute("SELECT COALESCE(SUM(share), 0) FROM task_assignment WHERE employee_id=? AND is_deleted=0", (id,)).fetchone()[0]
    tasks = db.execute("""
        SELECT ta.share, t.id, t.description, t.deadline, pr.name prio, ts.name st, ts.color color,
               p.name pname, pst.name stype
        FROM task_assignment ta
        JOIN task t ON ta.task_id=t.id
        JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        LEFT JOIN project p ON p.id=COALESCE(ps.project_id, (SELECT project_id FROM requirement WHERE id=t.requirement_id))
        WHERE ta.employee_id=? AND ta.task_kind='task' AND ta.is_deleted=0 AND t.is_deleted=0
        ORDER BY t.id DESC
    """, (id,)).fetchall()
    subtasks = db.execute("""
        SELECT ta.share, s.id, s.description, s.deadline, pr.name prio, ts.name st, ts.color color, t.description parent
        FROM task_assignment ta
        JOIN subtask s ON ta.task_id=s.id
        JOIN task t ON s.parent_task_id=t.id
        JOIN priority pr ON s.priority_id=pr.id
        JOIN task_status ts ON s.status_id=ts.id
        WHERE ta.employee_id=? AND ta.task_kind='subtask' AND ta.is_deleted=0 AND s.is_deleted=0
        ORDER BY s.id DESC
    """, (id,)).fetchall()
    db.close()
    info = [
        ('Сотрудник', f"{emp['last_name']} {emp['first_name']} {emp['middle_name'] or ''}"),
        ('Должность', html.escape(emp['position_name'])),
        ('Статус', f'<span class="badge" style="background: {"#27ae60" if emp["is_available"] else "#e74c3c"}">{html.escape(emp["status_name"])}</span>'),
        ('Подчинённые', f"{emp['subordinates_total']} (доступно: {emp['subordinates_available']})"),
        ('Загрузка', f'{round(load * 100)}%'),
    ]
    rows_t = [[
        f'<a href="{url_for("task_detail", id=t["id"])}">#{t["id"]}</a>',
        t['pname'] or '-', t['stype'] or '-', t['description'][:50], t['prio'],
        t['deadline'] or '-',
        f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{t["st"]}</span>',
        f'{round(t["share"] * 100)}%',
    ] for t in tasks]
    rows_s = [[
        f'<a href="{url_for("subtask_detail", id=s["id"])}">#{s["id"]}</a>',
        s['parent'][:50], s['description'][:50], s['prio'], s['deadline'] or '-',
        f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["st"]}</span>',
        f'{round(s["share"] * 100)}%',
    ] for s in subtasks]
    return _detail_page('Сотрудник: ' + emp['last_name'] + ' ' + emp['first_name'], info, [
        {'title': 'Задачи, где сотрудник назначен', 'headers': ['ID', 'Проект', 'Этап', 'Задача', 'Приоритет', 'Срок', 'Статус', 'Доля'], 'rows': rows_t},
        {'title': 'Подзадачи, где сотрудник назначен', 'headers': ['ID', 'Родительская задача', 'Описание', 'Приоритет', 'Срок', 'Статус', 'Доля'], 'rows': rows_s},
    ])

@app.route('/tasks/<int:id>')
def task_detail(id):
    db = get_db()
    t = db.execute("""
        SELECT t.*, pr.name prio, ts.name st, ts.color color, p.name pname, pst.name stype,
               r.description req_desc
        FROM task t
        JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        LEFT JOIN project p ON p.id=COALESCE(ps.project_id, (SELECT project_id FROM requirement WHERE id=t.requirement_id))
        WHERE t.id=? AND t.is_deleted=0
    """, (id,)).fetchone()
    if not t:
        db.close()
        flash('Задача не найдена', 'error')
        return redirect(url_for('tasks_list'))
    executors = db.execute("""
        SELECT e.id eid, e.last_name, e.first_name, pt.name pos, ta.share
        FROM task_assignment ta JOIN employee e ON ta.employee_id=e.id
        LEFT JOIN position_type pt ON e.position_type_id=pt.id
        WHERE ta.task_id=? AND ta.task_kind='task' AND ta.is_deleted=0
    """, (id,)).fetchall()
    subtasks = db.execute("""
        SELECT s.id, s.description, s.deadline, pr.name prio, ts.name st, ts.color color
        FROM subtask s JOIN priority pr ON s.priority_id=pr.id
        JOIN task_status ts ON s.status_id=ts.id
        WHERE s.parent_task_id=? AND s.is_deleted=0 ORDER BY s.id
    """, (id,)).fetchall()
    comments = db.execute("SELECT * FROM comment WHERE entity_type='task' AND entity_id=? AND is_deleted=0 ORDER BY created_at DESC, id DESC", (id,)).fetchall()
    db.close()
    info = [
        ('Задача', f'#{id}'),
        ('Проект', t['pname'] or '-'),
        ('Этап', t['stype'] or '-'),
        ('Описание', t['description']),
        ('Приоритет', t['prio']),
        ('Срок', t['deadline'] or '-'),
        ('Статус', f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{t["st"]}</span>'),
        ('Требование', t['req_desc'] or '-'),
    ]
    rows_exec = [[f'<a href="{url_for("employee_detail", id=e["eid"])}">{e["last_name"]} {e["first_name"]}</a>',
                  e['pos'] or '-', f'{round(e["share"] * 100)}%'] for e in executors]
    rows_sub = [[f'<a href="{url_for("subtask_detail", id=s["id"])}">#{s["id"]}</a>', s['description'][:60], s['prio'],
                 s['deadline'] or '-', f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["st"]}</span>'] for s in subtasks]
    add_comment = f'<a href="{url_for("comment_create", entity_type="task", entity_id=id)}" class="btn btn-success">+ Комментарий</a>'
    rows_c = [[c['created_at'], c['author'] or '-', c['text'],
               f'<a href="{url_for("comment_delete", id=c["id"])}" class="btn btn-danger" onclick="return confirm(\'Удалить?\')">Удалить</a>'] for c in comments]
    return _detail_page(f'Задача #{id}', info, [
        {'title': 'Кто выполняет', 'headers': ['Сотрудник', 'Должность', 'Доля'], 'rows': rows_exec},
        {'title': 'Подзадачи', 'headers': ['ID', 'Описание', 'Приоритет', 'Срок', 'Статус'], 'rows': rows_sub},
        {'title': 'Комментарии ' + add_comment, 'headers': ['Дата', 'Автор', 'Текст', 'Действия'], 'rows': rows_c},
    ])

@app.route('/subtasks/<int:id>')
def subtask_detail(id):
    db = get_db()
    s = db.execute("""
        SELECT s.*, t.description parent_desc, t.id parent_id, pr.name prio, ts.name st, ts.color color
        FROM subtask s JOIN task t ON s.parent_task_id=t.id
        JOIN priority pr ON s.priority_id=pr.id
        JOIN task_status ts ON s.status_id=ts.id
        WHERE s.id=? AND s.is_deleted=0
    """, (id,)).fetchone()
    if not s:
        db.close()
        flash('Подзадача не найдена', 'error')
        return redirect(url_for('subtasks_list'))
    executors = db.execute("""
        SELECT e.id eid, e.last_name, e.first_name, pt.name pos, ta.share
        FROM task_assignment ta JOIN employee e ON ta.employee_id=e.id
        LEFT JOIN position_type pt ON e.position_type_id=pt.id
        WHERE ta.task_id=? AND ta.task_kind='subtask' AND ta.is_deleted=0
    """, (id,)).fetchall()
    comments = db.execute("SELECT * FROM comment WHERE entity_type='subtask' AND entity_id=? AND is_deleted=0 ORDER BY created_at DESC, id DESC", (id,)).fetchall()
    db.close()
    info = [
        ('Подзадача', f'#{id}'),
        ('Родительская задача', f'<a href="{url_for("task_detail", id=s["parent_id"])}">#{s["parent_id"]} {s["parent_desc"][:40]}</a>'),
        ('Описание', s['description']),
        ('Приоритет', s['prio']),
        ('Срок', s['deadline'] or '-'),
        ('Статус', f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["st"]}</span>'),
    ]
    rows_exec = [[f'<a href="{url_for("employee_detail", id=e["eid"])}">{e["last_name"]} {e["first_name"]}</a>',
                  e['pos'] or '-', f'{round(e["share"] * 100)}%'] for e in executors]
    add_comment = f'<a href="{url_for("comment_create", entity_type="subtask", entity_id=id)}" class="btn btn-success">+ Комментарий</a>'
    rows_c = [[c['created_at'], c['author'] or '-', c['text'],
               f'<a href="{url_for("comment_delete", id=c["id"])}" class="btn btn-danger" onclick="return confirm(\'Удалить?\')">Удалить</a>'] for c in comments]
    return _detail_page(f'Подзадача #{id}', info, [
        {'title': 'Кто выполняет', 'headers': ['Сотрудник', 'Должность', 'Доля'], 'rows': rows_exec},
        {'title': 'Комментарии ' + add_comment, 'headers': ['Дата', 'Автор', 'Текст', 'Действия'], 'rows': rows_c},
    ])

@app.route('/stakeholders/<int:id>')
def stakeholder_detail(id):
    db = get_db()
    sh = db.execute("""
        SELECT s.*, st.name type_name, st.influence_priority inf, st.interest_priority ints
        FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id
        WHERE s.id=? AND s.is_deleted=0
    """, (id,)).fetchone()
    if not sh:
        db.close()
        flash('Стейкхолдер не найден', 'error')
        return redirect(url_for('stakeholders_list'))
    projects = db.execute("""
        SELECT p.id, p.name, pr.name prio, p.deadline
        FROM project p JOIN priority pr ON p.priority_id=pr.id
        WHERE p.main_stakeholder_id=? AND p.is_deleted=0
    """, (id,)).fetchall()
    reqs = db.execute("""
        SELECT r.id, r.description, p.name pname, rt.name type_name, pr.name prio
        FROM requirement r JOIN project p ON r.project_id=p.id
        JOIN requirement_type rt ON r.requirement_type_id=rt.id
        JOIN priority pr ON r.priority_id=pr.id
        WHERE r.stakeholder_id=? AND r.is_deleted=0
    """, (id,)).fetchall()
    interviews = db.execute("""
        SELECT INTERV.* FROM interview INTERV
        WHERE INTERV.stakeholder_id=? AND INTERV.is_deleted=0
        ORDER BY INTERV.scheduled_at DESC
    """, (id,)).fetchall()
    db.close()
    info = [
        ('Стейкхолдер', f"{sh['last_name']} {sh['first_name']}"),
        ('Тип', sh['type_name']),
        ('Влияние / Интерес', f"{sh['inf']}/5, {sh['ints']}/5"),
        ('Должность', sh['position'] or '-'),
        ('Приоритет', sh['priority']),
    ]
    rows_proj = [[f'<a href="{url_for("project_detail", id=p["id"])}">{p["name"]}</a>', p['prio'], p['deadline'] or '-'] for p in projects]
    rows_req = [[f'<a href="{url_for("requirement_detail", id=r["id"])}">#{r["id"]}</a>', r['description'][:60], r['pname'], r['type_name'], r['prio']] for r in reqs]
    rows_int = [[f'<a href="{url_for("interview_detail", id=i["id"])}">#{i["id"]}</a>', i['scheduled_at'] or '-'] for i in interviews]
    add_interview = f'<a href="{url_for("interview_create", stakeholder_id=id)}" class="btn btn-success">+ Назначить интервью</a>'
    return _detail_page('Стейкхолдер: ' + sh['last_name'] + ' ' + sh['first_name'], info, [
        {'title': 'Проекты (главный стейкхолдер)', 'headers': ['Проект', 'Приоритет', 'Срок'], 'rows': rows_proj},
        {'title': 'Требования стейкхолдера', 'headers': ['ID', 'Описание', 'Проект', 'Тип', 'Приоритет'], 'rows': rows_req},
        {'title': 'Интервью стейкхолдера ' + add_interview, 'headers': ['ID', 'Дата-время'], 'rows': rows_int},
    ])

@app.route('/requirements/<int:id>')
def requirement_detail(id):
    db = get_db()
    r = db.execute("""
        SELECT r.*, p.name pname, rt.name type_name, pr.name prio, s.last_name, s.first_name
        FROM requirement r JOIN project p ON r.project_id=p.id
        JOIN requirement_type rt ON r.requirement_type_id=rt.id
        JOIN priority pr ON r.priority_id=pr.id
        LEFT JOIN stakeholder s ON r.stakeholder_id=s.id
        WHERE r.id=? AND r.is_deleted=0
    """, (id,)).fetchone()
    if not r:
        db.close()
        flash('Требование не найдено', 'error')
        return redirect(url_for('requirements_list'))
    tasks = db.execute("""
        SELECT t.id, t.description, t.deadline, pr.name prio, ts.name st, ts.color color, pst.name stype
        FROM task t JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        WHERE t.requirement_id=? AND t.is_deleted=0
    """, (id,)).fetchall()
    db.close()
    info = [
        ('Требование', f'#{id}'),
        ('Проект', r['pname']),
        ('Тип', r['type_name']),
        ('Приоритет', r['prio']),
        ('Стейкхолдер', f"{r['last_name'] or '-'} {r['first_name'] or ''}"),
        ('Описание', r['description']),
        ('Критерий проверки', r['acceptance_criteria'] or '-'),
    ]
    rows = [[f'<a href="{url_for("task_detail", id=t["id"])}">#{t["id"]}</a>', t['description'][:60], t['stype'] or '-',
             t['prio'], t['deadline'] or '-', f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{t["st"]}</span>'] for t in tasks]
    return _detail_page(f'Требование #{id}', info, [
        {'title': 'Задачи, реализующие требование', 'headers': ['ID', 'Описание', 'Этап', 'Приоритет', 'Срок', 'Статус'], 'rows': rows},
    ])

@app.route('/project_stages/<int:id>')
def project_stage_detail(id):
    db = get_db()
    st = db.execute("""
        SELECT ps.*, p.name pname, pst.name type_name, pss.name status_name, pss.color
        FROM project_stage ps
        JOIN project p ON ps.project_id=p.id
        JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE ps.id=? AND ps.is_deleted=0
    """, (id,)).fetchone()
    if not st:
        db.close()
        flash('Этап не найден', 'error')
        return redirect(url_for('project_stages_list'))
    tasks = db.execute("""
        SELECT t.id, t.description, t.deadline, pr.name prio, ts.name st, ts.color color,
               (SELECT GROUP_CONCAT(e.last_name || ' ' || e.first_name, ', ')
                FROM task_assignment ta JOIN employee e ON ta.employee_id=e.id
                WHERE ta.task_id=t.id AND ta.task_kind='task' AND ta.is_deleted=0) executors
        FROM task t JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        WHERE t.stage_id=? AND t.is_deleted=0
        ORDER BY t.id
    """, (id,)).fetchall()
    db.close()
    info = [
        ('Этап', st['type_name']),
        ('Проект', f'<a href="{url_for("project_detail", id=st["project_id"])}">{st["pname"]}</a>'),
        ('Статус', f'<span class="badge" style="background: {st["color"] or "#95a5a6"}">{st["status_name"]}</span>'),
        ('Плановая дата', st['planned_end'] or '-'),
    ]
    rows = [[f'<a href="{url_for("task_detail", id=t["id"])}">#{t["id"]}</a>', t['description'][:60], t['prio'],
             t['deadline'] or '-', f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{t["st"]}</span>',
             t['executors'] or 'не назначено'] for t in tasks]
    return _detail_page('Этап: ' + st['type_name'], info, [
        {'title': 'Задачи этапа', 'headers': ['ID', 'Описание', 'Приоритет', 'Срок', 'Статус', 'Исполнители'], 'rows': rows},
    ])

@app.route('/task_assignments/<int:id>')
def task_assignment_detail(id):
    db = get_db()
    a = db.execute("""
        SELECT ta.*, e.last_name, e.first_name, pt.name pos,
               CASE WHEN ta.task_kind='task' THEN (SELECT description FROM task WHERE id=ta.task_id)
                    ELSE (SELECT description FROM subtask WHERE id=ta.task_id) END task_desc
        FROM task_assignment ta JOIN employee e ON ta.employee_id=e.id
        LEFT JOIN position_type pt ON e.position_type_id=pt.id
        WHERE ta.id=? AND ta.is_deleted=0
    """, (id,)).fetchone()
    if not a:
        db.close()
        flash('Назначение не найдено', 'error')
        return redirect(url_for('task_assignments_list'))
    db.close()
    info = [
        ('Назначение', f'#{id}'),
        ('Тип', a['task_kind']),
        ('Задача', a['task_desc'] or '-'),
        ('Сотрудник', a['last_name'] + ' ' + a['first_name']),
        ('Должность', a['pos'] or '-'),
        ('Доля', f'{round(a["share"] * 100)}%'),
    ]
    return _detail_page(f'Назначение #{id}', info)

@app.route('/events/<int:id>')
def event_detail(id):
    db = get_db()
    e = db.execute("SELECT * FROM event WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not e:
        db.close()
        flash('Событие не найдено', 'error')
        return redirect(url_for('events_list'))
    db.close()
    info = [
        ('Событие', f'#{id}'),
        ('Дата', e['occurred_at']),
        ('Описание', e['description']),
        ('Решение', e['decision'] or '-'),
    ]
    return _detail_page(f'Событие #{id}', info)

#==================== ИНТЕРВЬЮ СТЕЙКХОЛДЕРОВ ====================

@app.route('/interviews')
def interviews_list():
    db = get_db()
    items = db.execute("""
        SELECT i.*, s.last_name, s.first_name
        FROM interview i JOIN stakeholder s ON i.stakeholder_id=s.id
        WHERE i.is_deleted=0 ORDER BY i.scheduled_at DESC
    """).fetchall()
    rows = ''.join([f'''
        <tr>
            <td>{i['id']}</td>
            <td><a href="{url_for('stakeholder_detail', id=i['stakeholder_id'])}">{i['last_name']} {i['first_name']}</a></td>
            <td>{i['scheduled_at'] or '-'}</td>
            <td>
                <a href="{url_for('interview_detail', id=i['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('interview_edit', id=i['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('interview_delete', id=i['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for i in items])
    content = f'''
    <div class="card">
        <h2>Интервью стейкхолдеров</h2>
        <a href="{url_for('interview_create')}" class="btn btn-success">+ Назначить интервью</a>
        <table>
            <thead><tr><th>ID</th><th>Стейкхолдер</th><th>Дата-время</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Интервью', content=content)

@app.route('/interviews/create', methods=['GET', 'POST'])
def interview_create():
    db = get_db()
    if request.method == 'POST':
        cur = db.execute("INSERT INTO interview (stakeholder_id, scheduled_at) VALUES (?, ?)",
                         (int(request.form['stakeholder_id']), request.form.get('scheduled_at') or None))
        db.commit()
        new_id = cur.lastrowid
        db.close()
        flash('Интервью назначено', 'success')
        return redirect(url_for('interview_detail', id=new_id))
    pre_sh = request.args.get('stakeholder_id')
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    db.close()
    options = ''.join([f'<option value="{s["id"]}" {"selected" if str(s["id"]) == pre_sh else ""}>{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    content = f'''
    <div class="card">
        <h2>Новое интервью</h2>
        <form method="POST">
            <div class="form-group">
                <label>Стейкхолдер</label>
                <select name="stakeholder_id" required>{options}</select>
            </div>
            <div class="form-group">
                <label>Дата-время</label>
                <input type="datetime-local" name="scheduled_at">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('interviews_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новое интервью', content=content)

@app.route('/interviews/edit/<int:id>', methods=['GET', 'POST'])
def interview_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE interview SET stakeholder_id=?, scheduled_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (int(request.form['stakeholder_id']), request.form.get('scheduled_at') or None, id))
        db.commit()
        db.close()
        flash('Интервью обновлено', 'success')
        return redirect(url_for('interview_detail', id=id))
    iv = db.execute("SELECT * FROM interview WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not iv:
        db.close()
        flash('Интервью не найдено', 'error')
        return redirect(url_for('interviews_list'))
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    db.close()
    options = ''.join([f'<option value="{s["id"]}" {"selected" if s["id"] == iv["stakeholder_id"] else ""}>{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    content = f'''
    <div class="card">
        <h2>Редактировать интервью</h2>
        <form method="POST">
            <div class="form-group">
                <label>Стейкхолдер</label>
                <select name="stakeholder_id" required>{options}</select>
            </div>
            <div class="form-group">
                <label>Дата-время</label>
                <input type="datetime-local" name="scheduled_at" value="{iv['scheduled_at'] or ''}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('interview_detail', id=id)}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать интервью', content=content)

@app.route('/interviews/delete/<int:id>')
def interview_delete(id):
    db = get_db()
    db.execute("UPDATE interview SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Интервью удалено', 'success')
    return redirect(url_for('interviews_list'))

@app.route('/interviews/<int:id>')
def interview_detail(id):
    db = get_db()
    iv = db.execute("""
        SELECT i.*, s.last_name, s.first_name
        FROM interview i JOIN stakeholder s ON i.stakeholder_id=s.id
        WHERE i.id=? AND i.is_deleted=0
    """, (id,)).fetchone()
    if not iv:
        db.close()
        flash('Интервью не найдено', 'error')
        return redirect(url_for('interviews_list'))
    qas = db.execute("SELECT * FROM interview_qa WHERE interview_id=? AND is_deleted=0 ORDER BY id", (id,)).fetchall()
    db.close()
    info = [
        ('Интервью', f'#{id}'),
        ('Стейкхолдер', f'<a href="{url_for("stakeholder_detail", id=iv["stakeholder_id"])}">{iv["last_name"]} {iv["first_name"]}</a>'),
        ('Дата-время', iv['scheduled_at'] or '-'),
    ]
    add_qa = f'<a href="{url_for("interview_qa_create", interview_id=id)}" class="btn btn-success">+ Добавить вопрос</a>'
    export_btn = f'<a href="{url_for("interview_export", id=id)}" class="btn btn-success">Экспорт (Markdown)</a>'
    rows_q = [[f'<a href="{url_for("interview_qa_edit", id=q["id"])}">#{q["id"]}</a>', q['question'], q['answer'] or '-',
               '<div style="white-space:nowrap">'
               f'<a href="{url_for("interview_qa_edit", id=q["id"])}" class="btn btn-primary">Изменить</a> '
               f'<a href="{url_for("interview_qa_delete", id=q["id"])}" class="btn btn-danger" onclick="return confirm(\'Удалить?\')">Удалить</a>'
               '</div>'] for q in qas]
    return _detail_page('Интервью #' + str(id), info, [
        {'title': 'Вопросы и ответы ' + add_qa, 'headers': ['ID', 'Вопрос', 'Ответ', 'Действия'], 'rows': rows_q},
    ], actions=export_btn)

@app.route('/interviews/<int:id>/export')
def interview_export(id):
    db = get_db()
    iv = db.execute("""
        SELECT i.*, s.last_name, s.first_name, s.position
        FROM interview i JOIN stakeholder s ON i.stakeholder_id=s.id
        WHERE i.id=? AND i.is_deleted=0
    """, (id,)).fetchone()
    if not iv:
        db.close()
        flash('Интервью не найдено', 'error')
        return redirect(url_for('interviews_list'))
    qas = db.execute("SELECT * FROM interview_qa WHERE interview_id=? AND is_deleted=0 ORDER BY id", (id,)).fetchall()
    db.close()
    lines = [f'# Интервью #{id}', '']
    lines.append(f'- **Стейкхолдер:** {iv["last_name"]} {iv["first_name"]}')
    if iv['position']:
        lines.append(f'- **Должность:** {iv["position"]}')
    lines.append(f'- **Дата и время:** {iv["scheduled_at"] or "—"}')
    if qas:
        lines += ['', '## Вопросы и ответы', '']
        for i, q in enumerate(qas, 1):
            lines += [f'### Вопрос {i}', '', f'**Вопрос:** {q["question"]}',
                      '', f'**Ответ:** {q["answer"] or "_(нет ответа)_"}', '']
    md = '\n'.join(lines)
    return send_file(BytesIO(md.encode('utf-8')), mimetype='text/markdown',
                     as_attachment=True, download_name=f'interview_{id}.md')

@app.route('/interview_qa/create', methods=['GET', 'POST'])
def interview_qa_create():
    db = get_db()
    if request.method == 'POST':
        db.execute("INSERT INTO interview_qa (interview_id, question, answer) VALUES (?, ?, ?)",
                   (int(request.form['interview_id']), request.form['question'], request.form.get('answer')))
        db.commit()
        db.close()
        flash('Вопрос добавлен', 'success')
        return redirect(url_for('interview_detail', id=int(request.form['interview_id'])))
    pre_iv = request.args.get('interview_id')
    interviews = db.execute("SELECT * FROM interview WHERE is_deleted=0").fetchall()
    db.close()
    options = ''.join([f'<option value="{i["id"]}" {"selected" if str(i["id"]) == pre_iv else ""}>#{i["id"]}</option>' for i in interviews])
    cancel = url_for('interview_detail', id=int(pre_iv)) if pre_iv else url_for('interviews_list')
    content = f'''
    <div class="card">
        <h2>Новый вопрос-ответ</h2>
        <form method="POST">
            <div class="form-group">
                <label>Интервью</label>
                <select name="interview_id" required>{options}</select>
            </div>
            <div class="form-group">
                <label>Вопрос</label>
                <textarea name="question" required></textarea>
            </div>
            <div class="form-group">
                <label>Ответ</label>
                <textarea name="answer"></textarea>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{cancel}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый вопрос-ответ', content=content)

@app.route('/interview_qa/edit/<int:id>', methods=['GET', 'POST'])
def interview_qa_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE interview_qa SET interview_id=?, question=?, answer=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (int(request.form['interview_id']), request.form['question'], request.form.get('answer'), id))
        db.commit()
        db.close()
        flash('Вопрос-ответ обновлён', 'success')
        return redirect(url_for('interview_detail', id=int(request.form['interview_id'])))
    qa = db.execute("SELECT * FROM interview_qa WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not qa:
        db.close()
        flash('Вопрос-ответ не найден', 'error')
        return redirect(url_for('interviews_list'))
    interviews = db.execute("SELECT * FROM interview WHERE is_deleted=0").fetchall()
    db.close()
    options = ''.join([f'<option value="{i["id"]}" {"selected" if i["id"] == qa["interview_id"] else ""}>#{i["id"]}</option>' for i in interviews])
    content = f'''
    <div class="card">
        <h2>Редактировать вопрос-ответ</h2>
        <form method="POST">
            <div class="form-group">
                <label>Интервью</label>
                <select name="interview_id" required>{options}</select>
            </div>
            <div class="form-group">
                <label>Вопрос</label>
                <textarea name="question" required>{qa['question']}</textarea>
            </div>
            <div class="form-group">
                <label>Ответ</label>
                <textarea name="answer">{qa['answer'] or ''}</textarea>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('interview_detail', id=qa['interview_id'])}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать вопрос-ответ', content=content)

@app.route('/interview_qa/delete/<int:id>')
def interview_qa_delete(id):
    db = get_db()
    qa = db.execute("SELECT interview_id FROM interview_qa WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if qa:
        db.execute("UPDATE interview_qa SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
        db.commit()
        db.close()
        flash('Вопрос-ответ удалён', 'success')
        return redirect(url_for('interview_detail', id=qa['interview_id']))
    db.close()
    flash('Вопрос-ответ не найден', 'error')
    return redirect(url_for('interviews_list'))

#==================== УПРАВЛЕНИЕ БАЗОЙ ДАННЫХ ====================

@app.context_processor
def _inject_current_db():
    return {'current_db': current_db_name()}

def _sanitize_db_name(name):
    name = (name or '').strip()
    if not name or '/' in name or '\\' in name:
        return None
    if not name.endswith('.db'):
        name += '.db'
    if name.startswith('.') or '..' in name:
        return None
    if not all(ch.isalnum() or ch in '_.-' for ch in name):
        return None
    return name

def _list_databases():
    return sorted(f for f in os.listdir(DATABASE_DIR) if f.endswith('.db'))

@app.route('/database')
def database_index():
    current = current_db_name()
    files = _list_databases()
    rows = ''.join([f'''
        <tr>
            <td>{f}
                {f'<span class="badge" style="background:#27ae60">активная</span>' if f == current else ''}
            </td>
            <td>{os.path.getsize(db_path_for(f)):,} байт</td>
            <td>
                {'' if f == current else f'<a href="{url_for("database_use", name=f)}" class="btn btn-primary">Использовать</a> '}
                <a href="{url_for("database_delete", name=f)}" class="btn btn-danger" onclick="return confirm(\'Удалить БД?\')">Удалить</a>
            </td>
        </tr>''' for f in files])
    content = f'''
    <div class="card">
        <h2>Управление базой данных</h2>
        <p style="margin-top:10px;">Текущая активная БД: <strong>{current}</strong></p>
    </div>
    <div class="card">
        <h2>Создать новую БД</h2>
        <form method="POST" action="{url_for('database_create')}">
            <div class="form-group">
                <label>Имя новой БД</label>
                <input type="text" name="name" placeholder="например, projekt_alpha" required>
            </div>
            <button type="submit" class="btn btn-success">Создать и переключиться</button>
        </form>
    </div>
    <div class="card">
        <h2>Имеющиеся БД</h2>
        <table>
            <thead><tr><th>Имя</th><th>Размер</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='База данных', content=content)

@app.route('/database/create', methods=['POST'])
def database_create():
    name = _sanitize_db_name(request.form.get('name'))
    if not name:
        flash('Некорректное имя БД', 'error')
        return redirect(url_for('database_index'))
    path = db_path_for(name)
    if os.path.exists(path):
        flash(f'БД «{name}» уже существует — переключились на неё', 'warning')
    else:
        init_db(path)
        flash(f'Создана БД «{name}»', 'success')
    session['db_name'] = name
    return redirect(url_for('database_index'))

@app.route('/database/use/<name>')
def database_use(name):
    name = _sanitize_db_name(name)
    if not name or not os.path.exists(db_path_for(name)):
        flash('БД не найдена', 'error')
        return redirect(url_for('database_index'))
    session['db_name'] = name
    flash(f'Активная БД: {name}', 'success')
    return redirect(url_for('database_index'))

@app.route('/database/delete/<name>')
def database_delete(name):
    name = _sanitize_db_name(name)
    if not name or not os.path.exists(db_path_for(name)):
        flash('БД не найдена', 'error')
        return redirect(url_for('database_index'))
    if name == DEFAULT_DB_NAME:
        flash('Нельзя удалить основную БД', 'error')
        return redirect(url_for('database_index'))
    try:
        for suffix in ('', '-wal', '-shm'):
            p = db_path_for(name) + suffix
            if os.path.exists(p):
                os.remove(p)
        if session.get('db_name') == name:
            session['db_name'] = DEFAULT_DB_NAME
        flash(f'БД «{name}» удалена', 'success')
    except OSError as e:
        flash(f'Ошибка удаления: {e}', 'error')
    return redirect(url_for('database_index'))

#==================== КОММЕНТАРИИ ====================

@app.route('/comments/create', methods=['GET', 'POST'])
def comment_create():
    db = get_db()
    if request.method == 'POST':
        db.execute("INSERT INTO comment (entity_type, entity_id, author, text) VALUES (?, ?, ?, ?)",
                   (request.form['entity_type'], int(request.form['entity_id']),
                    request.form.get('author') or None, request.form['text']))
        db.commit()
        db.close()
        flash('Комментарий добавлен', 'success')
        origin = request.form.get('origin')
        if origin:
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        if request.form['entity_type'] == 'task':
            return redirect(url_for('task_detail', id=int(request.form['entity_id'])))
        return redirect(url_for('subtask_detail', id=int(request.form['entity_id'])))
    etype = request.args.get('entity_type', 'task')
    eid = request.args.get('entity_id')
    origin = request.args.get('origin')
    label = '—'
    if etype == 'task' and eid:
        row = db.execute("SELECT description FROM task WHERE id=? AND is_deleted=0", (int(eid),)).fetchone()
        label = row[0] if row else '—'
    elif etype == 'subtask' and eid:
        row = db.execute("SELECT description FROM subtask WHERE id=? AND is_deleted=0", (int(eid),)).fetchone()
        label = row[0] if row else '—'
    pid = _entity_project_id(db, etype, eid) if eid else None
    executors = []
    if pid:
        executors = db.execute("SELECT e.id, e.last_name, e.first_name FROM project_employee pe JOIN employee e ON pe.employee_id=e.id WHERE pe.project_id=? AND pe.is_deleted=0 AND e.is_deleted=0 ORDER BY e.last_name", (pid,)).fetchall()
    author_options = '<option value="">— не указан —</option>' + ''.join(
        [f'<option value="{e["last_name"]} {e["first_name"]}">{e["last_name"]} {e["first_name"]}</option>' for e in executors])
    author_field = f'<select name="author">{author_options}</select>' if executors else '<input type="text" name="author">'
    type_options = ''.join([f'<option value="{v}" {"selected" if v==etype else ""}">{t}</option>' for v,t in (('task','Задача'),('subtask','Подзадача'))])
    if etype and eid:
        schema_fields = (f'<input type="hidden" name="entity_type" value="{etype}">'
                         f'<input type="hidden" name="entity_id" value="{eid}">')
    else:
        schema_fields = f'''
            <div class="form-group">
                <label>Тип</label>
                <select name="entity_type" required>{type_options}</select>
            </div>
            <div class="form-group">
                <label>ID задачи/подзадачи</label>
                <input type="number" name="entity_id" required>
            </div>'''
    db.close()
    cancel = url_for('project_detail', id=int(origin), tab='stages') if origin else url_for('tasks_list')
    entity_title = ('Задача #' + eid if etype == 'task' and eid else ('Подзадача #' + eid if etype == 'subtask' and eid else '—'))
    content = f'''
    <div class="card">
        <h2>Новый комментарий</h2>
        <div class="comment" style="margin-bottom:12px;">
            <strong>{entity_title}</strong><br>{html.escape(label)}
        </div>
        <form method="POST">
            <input type="hidden" name="origin" value="{origin or ''}">
            {schema_fields}
            <div class="form-group">
                <label>Автор (исполнитель проекта)</label>
                {author_field}
            </div>
            <div class="form-group">
                <label>Комментарий</label>
                <textarea name="text" required></textarea>
            </div>
            <button type="submit" class="btn btn-success">Добавить</button>
            <a href="{cancel}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый комментарий', content=content)

@app.route('/comments/delete/<int:id>')
def comment_delete(id):
    db = get_db()
    c = db.execute("SELECT * FROM comment WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if c:
        db.execute("UPDATE comment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
        db.commit()
        origin = request.args.get('origin')
        if origin:
            db.close()
            return redirect(url_for('project_detail', id=int(origin), tab='stages'))
        eid, etype = c['entity_id'], c['entity_type']
        db.close()
        return redirect(url_for('task_detail', id=eid) if etype == 'task' else url_for('subtask_detail', id=eid))
    db.close()
    flash('Комментарий не найден', 'error')
    return redirect(url_for('tasks_list'))

#==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("Учебный проектный офис (УПО) запущен!")
    print("Откройте в браузере: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, host='127.0.0.1', port=5000)
