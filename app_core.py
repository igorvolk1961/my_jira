"""
Учебный проектный офис (УПО) - приложение для управления проектами, 
задачами и персоналом.
Для ролевых игр на курсах системных аналитиков
"""

from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify, session, send_file, g
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime, date
from io import BytesIO
from functools import wraps
from urllib.parse import urlsplit
import html
import json
import os
import re
import secrets
import shutil

app = Flask(__name__)
_secret = os.environ.get('UPO_SECRET_KEY')
if not _secret:
    _secret = secrets.token_hex(32)
    print('ВНИМАНИЕ: UPO_SECRET_KEY не задан — используется случайный ключ сессии '
          '(сессии не сохраняются между перезапусками). Для продакшена задайте UPO_SECRET_KEY.')
app.secret_key = _secret

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


def list_projects(db):
    return db.execute("SELECT id, name FROM project WHERE is_deleted=0 ORDER BY id").fetchall()


def current_project_row(db=None):
    """Текущий проект из сессии; при отсутствии/невалидности — первый активный."""
    own = db is None
    db = db or get_db()
    try:
        pid = session.get('project_id')
        row = None
        if pid:
            row = db.execute("SELECT * FROM project WHERE id=? AND is_deleted=0", (pid,)).fetchone()
        if not row:
            row = db.execute("SELECT * FROM project WHERE is_deleted=0 ORDER BY id LIMIT 1").fetchone()
            session['project_id'] = row['id'] if row else None
        return row
    finally:
        if own:
            db.close()


def current_project_id(db=None):
    row = current_project_row(db)
    return row['id'] if row else None


def project_selector_html(db, current_id, next_url=None):
    """Выпадающий список выбора текущего проекта (сохраняется в сессии)."""
    projects = list_projects(db)
    if not projects:
        return '<span class="muted">Проектов пока нет</span>'
    nxt = next_url or request.path
    options = ''.join(
        f'<option value="{p["id"]}" {"selected" if p["id"] == current_id else ""}>{html.escape(p["name"])}</option>'
        for p in projects)
    base = url_for('current_project_set', id=0)
    onchange = ("location.href='" + base + "'.replace(/0$/, this.value)+'?next='+"
                "encodeURIComponent('" + html.escape(nxt, quote=True) + "');")
    return f'''<label style="margin-right:6px;">Текущий проект:</label>
        <select name="project_id" onchange="{onchange}">{options}</select>'''

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

        -- Пользователи системы (аутентификация/авторизация)
        CREATE TABLE IF NOT EXISTS app_user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin','user')),
            employee_id INTEGER REFERENCES employee(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );

        -- Настройки приложения (ключ-значение)
        CREATE TABLE IF NOT EXISTS setting (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Журнал аудита (неизменяемый)
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_login TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            project_id INTEGER,
            position_id INTEGER,
            details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_log(project_id);
        CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);

        -- Общий чат
        CREATE TABLE IF NOT EXISTS chat_message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES app_user(id),
            author TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Шаблоны интервью
        CREATE TABLE IF NOT EXISTS interview_template (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS interview_template_question (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER REFERENCES interview_template(id),
            question TEXT NOT NULL,
            answer TEXT,
            position INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        );

        -- Артефакты системного аналитика по проекту (документные, Markdown)
        CREATE TABLE IF NOT EXISTS project_artifact (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
            artifact_key TEXT NOT NULL,
            content TEXT,
            updated_by_user_id INTEGER REFERENCES app_user(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0,
            UNIQUE(project_id, artifact_key)
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
    tcols = [r[1] for r in db.execute("PRAGMA table_info(task)").fetchall()]
    if 'task_type_id' not in tcols:
        db.execute("ALTER TABLE task ADD COLUMN task_type_id INTEGER REFERENCES task_type(id)")
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_one_executor_per_subtask ON task_assignment(task_id) WHERE task_kind='subtask' AND is_deleted=0")
    except sqlite3.IntegrityError:
        pass
    ccols = [r[1] for r in db.execute("PRAGMA table_info(comment)").fetchall()]
    if 'user_id' not in ccols:
        db.execute("ALTER TABLE comment ADD COLUMN user_id INTEGER REFERENCES app_user(id)")
    acols = [r[1] for r in db.execute("PRAGMA table_info(task_assignment)").fetchall()]
    if 'assigned_by_user_id' not in acols:
        db.execute("ALTER TABLE task_assignment ADD COLUMN assigned_by_user_id INTEGER REFERENCES app_user(id)")
    if 'assigned_at' not in acols:
        db.execute("ALTER TABLE task_assignment ADD COLUMN assigned_at DATETIME")
    ucols = [r[1] for r in db.execute("PRAGMA table_info(app_user)").fetchall()]
    if 'is_analyst' not in ucols:
        db.execute("ALTER TABLE app_user ADD COLUMN is_analyst INTEGER NOT NULL DEFAULT 0")
    pcols = [r[1] for r in db.execute("PRAGMA table_info(position_type)").fetchall()]
    if 'is_analyst' not in pcols:
        db.execute("ALTER TABLE position_type ADD COLUMN is_analyst INTEGER NOT NULL DEFAULT 0")
        db.execute("UPDATE position_type SET is_analyst=1 WHERE lower(name)=lower('Системный аналитик')")

    # Типы задач: отдельное наполнение (для существующих БД, где основные справочники уже есть)
    for ttype in ('Новый функционал', 'Исправление ошибки', 'Улучшение',
                  'Документирование', 'Тестирование', 'Код-ревью'):
        db.execute("INSERT OR IGNORE INTO task_type (name) VALUES (?)", (ttype,))

    # Должность по умолчанию для зарегистрированных пользователей
    db.execute("INSERT OR IGNORE INTO position_type (name) VALUES (?)", ('Пользователь',))

    # Статус «Принята к исполнению» (для существующих и новых БД)
    db.execute("INSERT OR IGNORE INTO task_status (name, color) VALUES (?, ?)", ('Принята к исполнению', '#8e44ad'))

    # Настройка по умолчанию
    db.execute("INSERT OR IGNORE INTO setting (key, value) VALUES (?, ?)",
               ('allow_users_assign_subtask_executors', '1'))
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
        db.execute("UPDATE position_type SET is_analyst=1 WHERE lower(name)=lower('Системный аналитик')")
        
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
    
    # Пользователь по умолчанию (администратор)
    _seed_default_admin(db)
    _seed_interview_templates(db)
    db.close()

DEFAULT_INTERVIEW_TEMPLATE_NAME = 'Вопросы Заказчику'

# Предзаполненный шаблон (источник: «Вопросы Заказчику.txt»).
_DEFAULT_INTERVIEW_QUESTIONS = [
    'Не будете ли Вы возражать, если я буду делать аудиозапись встречи? Это поможет мне ничего не упустить и сосредоточиться на диалоге, а не на конспектировании. (Если "да" – уточнить, можно ли поделиться расшифровкой).',
    'Кто еще, по Вашему мнению, должен участвовать в обсуждении требований? (Например, ключевые пользователи, ИТ-архитектор, юрист, специалист по безопасности).',
    'Кто является конечным лицом, принимающим решение (ЛПР) по приемке требований и результата проекта?',
    'Расскажите, пожалуйста, в чем ключевая идея и главная бизнес-предпосылка проекта? (Что случилось: новый закон, давление конкурентов, внутренние издержки, новая возможность на рынке?)',
    'По каким конкретным, измеримым критериям (KPI/метрикам) Вы будете оценивать, что проект успешен? (Например: снижение времени обработки заявки на 30%, рост конверсии на 15%).',
    'Как Вы планируете монетизировать проект или какую экономическую выгоду он должен принести компании?',
    'Есть ли жесткие дедлайны или привязка к внешним событиям (выставка, изменение законодательства, конец финансового года)?',
    'Кто целевая аудитория проекта? Можно ли выделить ключевые роли/персоны пользователей?',
    'Какие цели преследуют эти пользователи и какие задачи они пытаются решить с помощью нашего будущего продукта?',
    'Как пользователи решают эти задачи сейчас? (Опишите текущий процесс "As-Is").',
    'С какими основными проблемами, "узкими местами" или "болями" они сталкиваются в текущем процессе?',
    'Сколько времени у пользователей уходит на выполнение этих задач сейчас? Какой выигрыш по времени или усилиям Вы сочтете приемлемым в новой системе?',
    'Что должно быть реализовано в рамках MVP (минимально жизнеспособного продукта), чтобы запустить проект?',
    'Критически важный вопрос: Что мы точно НЕ будем делать в рамках этого проекта? (Что находится за рамками / out of scope).',
    'Планируете ли Вы масштабирование (расширение) функционала или географии проекта в будущем? Если да, то в каком горизонте?',
    'На каких устройствах и платформах должен работать проект? (Web, iOS, Android, десктоп, киоски самообслуживания).',
    'Какова ожидаемая нагрузка? Сколько пользователей будет работать с системой одновременно (пиковая и средняя нагрузка)?',
    'Какие требования предъявляются к доступности системы? (Например, 99.9% uptime, работа 24/7 или только в рабочие часы).',
    'Какие у Вас есть требования, касающиеся информационной безопасности, обработки персональных данных (152-ФЗ, GDPR) или отраслевые стандарты (например, PCI DSS для платежей)?',
    'Должна ли новая система обмениваться данными с существующими системами компании? (Например, 1С, CRM, ERP, сайт). Если да, то знаете ли Вы, есть ли у этих систем готовые API?',
    'Есть ли необходимость миграции исторических данных из старых систем? В каком виде они сейчас хранятся?',
    'Кто будет владельцем данных в новой системе и кто отвечает за их актуальность?',
    'Есть ли определенные рамки по бюджету или стоимости владения (TCO), которые нам нужно учитывать при выборе архитектурных или технологических решений?',
    'Есть ли предпочтения по технологическому стеку? (Например, "только открытое ПО", "только решения от отечественных вендоров", "уже куплены лицензии на Microsoft").',
    'Мне нужно обдумать полученную информацию, структурировать ее и, возможно, подготовить уточняющие вопросы. Как нам лучше выстроить дальнейшую коммуникацию? (Формат следующих встреч, каналы связи, сроки предоставления протокола встречи).',
]


def _seed_interview_templates(db):
    """Идемпотентно создаёт предзаполненный шаблон интервью (если его нет, включая удалённый)."""
    try:
        exists = db.execute("SELECT 1 FROM interview_template WHERE name=?", (DEFAULT_INTERVIEW_TEMPLATE_NAME,)).fetchone()
        if exists:
            return
        cur = db.execute("INSERT INTO interview_template (name, description) VALUES (?, ?)",
                         (DEFAULT_INTERVIEW_TEMPLATE_NAME, 'Базовый набор вопросов для интервью с заказчиком'))
        tid = cur.lastrowid
        for i, q in enumerate(_DEFAULT_INTERVIEW_QUESTIONS):
            db.execute("INSERT INTO interview_template_question (template_id, question, position) VALUES (?, ?, ?)",
                       (tid, q, i))
        db.commit()
    except sqlite3.Error:
        pass

def _seed_default_admin(db):
    """Идемпотентно создаёт пользователя admin/12345 (роль admin) со связанным сотрудником."""
    try:
        if db.execute("SELECT 1 FROM app_user WHERE lower(login)='admin'").fetchone():
            return
        db.execute("INSERT OR IGNORE INTO position_type (name) VALUES ('Пользователь')")
        pos = db.execute("SELECT id FROM position_type WHERE lower(name)=lower('Пользователь') ORDER BY id LIMIT 1").fetchone()
        pos_id = pos[0]
        db.execute("INSERT OR IGNORE INTO employee_status (name, is_available) VALUES ('Работает', 1)")
        st = db.execute("SELECT id FROM employee_status WHERE lower(name)=lower('Работает') ORDER BY id LIMIT 1").fetchone()
        status_id = st[0]
        emp = db.execute("SELECT id FROM employee WHERE last_name='admin' AND first_name='admin' ORDER BY id LIMIT 1").fetchone()
        if emp:
            emp_id = emp[0]
        else:
            cur = db.execute("""INSERT INTO employee (last_name, first_name, middle_name, position_type_id, status_id,
                                subordinates_total, subordinates_available, is_stackholder)
                                VALUES ('admin', 'admin', 'admin', ?, ?, 0, 0, 0)""", (pos_id, status_id))
            emp_id = cur.lastrowid
        db.execute("INSERT OR IGNORE INTO app_user (login, password, role, employee_id) VALUES ('admin', '12345', 'admin', ?)", (emp_id,))
        db.commit()
    except sqlite3.IntegrityError:
        # повторный/конкурентный запуск — запись уже создана другим процессом
        pass

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

# ==================== АУТЕНТИФИКАЦИЯ, АВТОРИЗАЦИЯ, АУДИТ ====================

# Защищённые маршруты: admin-изменения
ADMIN_WRITE_ENDPOINTS = {
    'priority_create', 'priority_edit', 'priority_delete',
    'stakeholder_type_create', 'stakeholder_type_edit', 'stakeholder_type_delete',
    'requirement_type_create', 'requirement_type_edit', 'requirement_type_delete',
    'position_type_create', 'position_type_edit', 'position_type_delete',
    'employee_status_create', 'employee_status_edit', 'employee_status_delete',
    'stage_type_create', 'stage_type_edit', 'stage_type_delete',
    'stage_status_create', 'stage_status_edit', 'stage_status_delete',
    'task_status_create', 'task_status_edit', 'task_status_delete',
    'task_type_create', 'task_type_edit', 'task_type_delete',
    'stakeholder_create', 'stakeholder_edit', 'stakeholder_delete',
    'employee_create', 'employee_edit', 'employee_delete', 'employee_role_change',
    'project_create', 'project_edit', 'project_delete',
    'project_add_stakeholder', 'project_remove_stakeholder',
    'project_add_employee', 'project_remove_employee',
    'project_stage_create', 'project_stage_edit', 'project_stage_delete',
    'task_create', 'task_edit', 'task_delete',
    'task_assignment_edit', 'task_assignment_delete',
    'event_create', 'event_edit', 'event_delete',
    'interview_create', 'interview_edit', 'interview_delete',
    'interview_qa_create', 'interview_qa_edit', 'interview_qa_delete',
    'interview_template_create', 'interview_template_delete',
    'interview_template_question_create', 'interview_template_question_edit',
    'interview_template_question_delete', 'interview_save_as_template',
    'interview_audio_upload', 'interview_audio_delete',
    'interview_transcribe', 'transcript_edit', 'transcript_segments_save',
    'transcript_clear', 'transcript_segment_delete',
    'database_create', 'database_delete', 'database_use', 'database_copy',
    # admin-only страницы (GET защищается тем же механизмом)
    'audit_index', 'settings_index', 'admin_tasks',
}

# Маршруты, доступные вошедшему пользователю (admin тоже проходит)
USER_WRITE_ENDPOINTS = {
    'subtask_create', 'subtask_edit', 'subtask_delete',
    'task_status_change', 'subtask_status_change',
    'comment_create', 'comment_delete',
    'task_assignment_create', 'chat_post',
    'my_tasks',
}

# Маршруты, доступные системному аналитику (и администратору)
ANALYST_WRITE_ENDPOINTS = {
    'requirement_create', 'requirement_edit', 'requirement_delete',
    'artifact_edit', 'artifact_clear',
}

WRITE_ENDPOINTS = ADMIN_WRITE_ENDPOINTS | USER_WRITE_ENDPOINTS | ANALYST_WRITE_ENDPOINTS
PUBLIC_ENDPOINTS = {'login', 'register', 'logout'}

# GET-ссылки, изменяющие состояние (нужны для аудита, т.к. это не POST)
GET_MUTATION_ENDPOINTS = {
    'database_use', 'database_delete', 'logout',
    'project_remove_stakeholder', 'project_remove_employee',
    'interview_audio_upload', 'interview_audio_delete', 'interview_transcribe',
    'interview_template_delete', 'interview_template_question_delete',
    'transcript_edit', 'transcript_segments_save', 'transcript_clear', 'transcript_segment_delete',
    'comment_delete', 'subtask_delete', 'task_assignment_delete', 'task_delete',
    'employee_delete', 'stakeholder_delete', 'project_delete', 'requirement_delete',
    'artifact_clear',
    'project_stage_delete', 'event_delete', 'interview_delete', 'interview_qa_delete',
    'employee_status_delete', 'position_type_delete', 'priority_delete',
    'stakeholder_type_delete', 'requirement_type_delete', 'stage_type_delete',
    'stage_status_delete', 'task_status_delete', 'task_type_delete',
}


def get_setting(db, key, default=None):
    try:
        row = db.execute("SELECT value FROM setting WHERE key=?", (key,)).fetchone()
        return row[0] if row else default
    except sqlite3.OperationalError:
        return default


def set_setting(db, key, value):
    db.execute("""INSERT INTO setting (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
                  ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
               (key, value))


def current_user():
    """Текущий пользователь (dict) или None. Кэшируется в g на время запроса."""
    if not getattr(g, 'current_user_loaded', False):
        g.current_user_loaded = True
        g.current_user = None
        uid = session.get('user_id')
        if uid:
            try:
                db = get_db()
                row = db.execute("""
                    SELECT u.*, e.last_name, e.first_name, e.middle_name, e.position_type_id,
                           pt.name AS position_name
                    FROM app_user u LEFT JOIN employee e ON u.employee_id=e.id
                    LEFT JOIN position_type pt ON e.position_type_id=pt.id
                    WHERE u.id=? AND u.is_deleted=0
                """, (uid,)).fetchone()
                db.close()
                if row:
                    name = ' '.join(x for x in (row['last_name'], row['first_name'], row['middle_name']) if x) or row['login']
                    g.current_user = {
                        'id': row['id'],
                        'login': row['login'],
                        'role': row['role'],
                        'is_analyst': row['is_analyst'],
                        'employee_id': row['employee_id'],
                        'position_id': row['position_type_id'],
                        'position_name': row['position_name'],
                        'full_name': name,
                    }
            except sqlite3.Error:
                g.current_user = None
    return g.current_user


def is_admin():
    u = current_user()
    return bool(u and u['role'] == 'admin')


def is_analyst():
    u = current_user()
    return bool(u and u.get('is_analyst'))


def can_edit_artifacts():
    """Документные артефакты и требования правят администратор и системный аналитик."""
    return is_admin() or is_analyst()


def role_label(role, is_analyst_flag=False):
    labels = {'admin': 'администратор', 'user': 'пользователь'}
    parts = [labels.get(role, role or '—')]
    if is_analyst_flag:
        parts.append('системный аналитик')
    return ', '.join(parts)


# ---------- Синхронизация должности и роли «Системный аналитик» ----------

def _position_is_analyst(db, position_id):
    if not position_id:
        return False
    row = db.execute("SELECT is_analyst FROM position_type WHERE id=?", (position_id,)).fetchone()
    return bool(row and row['is_analyst'])


def _analyst_position_id(db):
    row = db.execute("SELECT id FROM position_type WHERE is_analyst=1 AND is_deleted=0 ORDER BY id LIMIT 1").fetchone()
    return row['id'] if row else None


def _default_position_id(db):
    """Должность «Пользователь» (создаётся при отсутствии)."""
    row = db.execute("SELECT id FROM position_type WHERE lower(name)=lower('Пользователь') AND is_deleted=0").fetchone()
    if row:
        return row['id']
    return db.execute("INSERT INTO position_type (name) VALUES ('Пользователь')").lastrowid


def sync_analyst_role_from_position(db, employee_id):
    """Должность сотрудника → флаг роли is_analyst у связанной учётной записи."""
    row = db.execute("SELECT position_type_id FROM employee WHERE id=? AND is_deleted=0", (employee_id,)).fetchone()
    if not row:
        return
    want = 1 if _position_is_analyst(db, row['position_type_id']) else 0
    db.execute("UPDATE app_user SET is_analyst=?, updated_at=CURRENT_TIMESTAMP WHERE employee_id=? AND is_deleted=0",
               (want, employee_id))


def sync_position_from_analyst_role(db, employee_id, want):
    """Флаг роли is_analyst → должность сотрудника."""
    if want:
        pos_id = _analyst_position_id(db)
        if pos_id:
            db.execute("UPDATE employee SET position_type_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND is_deleted=0",
                       (pos_id, employee_id))
    else:
        pos_id = _default_position_id(db)
        db.execute("UPDATE employee SET position_type_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND is_deleted=0",
                   (pos_id, employee_id))


def _login_redirect():
    nxt = request.path
    if request.query_string:
        nxt += '?' + request.query_string.decode('utf-8', 'ignore')
    session['next'] = nxt
    return redirect(url_for('login'))


def safe_next(value, fallback):
    """Возвращает value, только если это локальный путь (защита от open redirect)."""
    if value and isinstance(value, str) and '\\' not in value:
        parts = urlsplit(value)
        if not parts.scheme and not parts.netloc and value.startswith('/') and not value.startswith('//'):
            return value
    return fallback


def assigner_sql(emp_alias, user_alias, extra_fallback=None):
    """SQL-выражение «ФИО того, кто назначил» с единым набором fallback-ов."""
    parts = [f"TRIM({emp_alias}.last_name || ' ' || {emp_alias}.first_name)"]
    if extra_fallback:
        parts.append(extra_fallback)
    parts.append(f"{user_alias}.login")
    parts.append("'—'")
    return 'COALESCE(' + ', '.join(parts) + ')'


def status_form(endpoint, entity_id, statuses, selected_id, back=None, label='Сменить статус'):
    """Единая мини-форма смены статуса для карточек и списков."""
    opts = ''.join(
        f'<option value="{s["id"]}" {"selected" if s["id"] == selected_id else ""}>{html.escape(s["name"])}</option>'
        for s in statuses)
    next_field = f'<input type="hidden" name="next" value="{html.escape(back)}">' if back else ''
    return (f'<form method="POST" action="{url_for(endpoint, id=entity_id)}" '
            f'style="display:inline-flex; gap:6px; align-items:center; margin:5px;">'
            f'<select name="status_id">{opts}</select>{next_field}'
            f'<button type="submit" class="btn btn-success" style="margin:0;">{label}</button></form>')


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            return _login_redirect()
        return view(*args, **kwargs)
    return wrapper


# ---------- Доступ пользователя к подзадачам («исполнитель приоритетен») ----------

def _active_task_assignee(db, task_id, emp_id):
    return db.execute("""SELECT 1 FROM task_assignment
                         WHERE task_id=? AND task_kind='task' AND employee_id=? AND is_deleted=0 LIMIT 1""",
                      (task_id, emp_id)).fetchone() is not None


def _subtask_assignee(db, subtask_id):
    r = db.execute("""SELECT employee_id FROM task_assignment
                      WHERE task_id=? AND task_kind='subtask' AND is_deleted=0 LIMIT 1""", (subtask_id,)).fetchone()
    return r['employee_id'] if r else None


def _user_can_manage_subtask(db, emp_id, subtask_id):
    if not emp_id:
        return False
    target = _subtask_assignee(db, subtask_id)
    if target is not None:
        return target == emp_id
    cur = db.execute("SELECT parent_task_id, parent_subtask_id FROM subtask WHERE id=? AND is_deleted=0",
                     (subtask_id,)).fetchone()
    if not cur:
        return False
    pid, psub = cur['parent_task_id'], cur['parent_subtask_id']
    while True:
        if psub:
            a = _subtask_assignee(db, psub)
            if a is not None:
                return a == emp_id
            r = db.execute("SELECT parent_task_id, parent_subtask_id FROM subtask WHERE id=? AND is_deleted=0",
                           (psub,)).fetchone()
            if not r:
                return False
            pid, psub = r['parent_task_id'], r['parent_subtask_id']
        else:
            return _active_task_assignee(db, pid, emp_id) if pid else False


def _managed_subtask_ids(db, emp_id):
    """Множество подзадач, которыми emp_id управляет, без N+1: одна загрузка карт связей."""
    if not emp_id:
        return set()
    task_asg = {r['task_id']: r['employee_id'] for r in db.execute(
        "SELECT task_id, employee_id FROM task_assignment WHERE task_kind='task' AND is_deleted=0")}
    sub_asg = {r['task_id']: r['employee_id'] for r in db.execute(
        "SELECT task_id, employee_id FROM task_assignment WHERE task_kind='subtask' AND is_deleted=0")}
    parents = {r['id']: (r['parent_task_id'], r['parent_subtask_id']) for r in db.execute(
        "SELECT id, parent_task_id, parent_subtask_id FROM subtask WHERE is_deleted=0")}

    def can(sid):
        target = sub_asg.get(sid)
        if target is not None:
            return target == emp_id
        cur = parents.get(sid)
        if not cur:
            return False
        pid, psub = cur
        while True:
            if psub is not None:
                a = sub_asg.get(psub)
                if a is not None:
                    return a == emp_id
                nxt = parents.get(psub)
                if not nxt:
                    return False
                pid, psub = nxt
            else:
                return task_asg.get(pid) == emp_id if pid else False

    return {sid for sid in parents if can(sid)}


# ---------- Аудит ----------

def _audit_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _endpoint_entity_type(endpoint):
    e = endpoint or ''
    if e in ('task_status_change', 'subtask_status_change'):
        return 'task' if e == 'task_status_change' else 'subtask'
    if e == 'task_assignment_create':
        kind = request.form.get('task_kind')
        return kind if kind in ('task', 'subtask') else 'assignment'
    if e.startswith('task_assignment'):
        return 'assignment'
    if e.startswith('task_status') or e.startswith('task_type'):
        return 'reference'
    if e.startswith('task_'):
        return 'task'
    if e.startswith('subtask_'):
        return 'subtask'
    if e.startswith('project_stage'):
        return 'stage'
    if e.startswith('project_'):
        return 'project'
    if e.startswith('requirement'):
        return 'requirement'
    if e.startswith('stakeholder_type'):
        return 'reference'
    if e.startswith('stakeholder'):
        return 'stakeholder'
    if e.startswith('employee_status'):
        return 'reference'
    if e.startswith('employee'):
        return 'employee'
    if e.startswith('comment'):
        return 'comment'
    if e.startswith('chat'):
        return 'chat'
    if e.startswith('interview') or e.startswith('transcript'):
        return 'interview'
    if e.startswith('event'):
        return 'event'
    if e.startswith('database'):
        return 'database'
    if e.startswith('priority'):
        return 'reference'
    if e.startswith('position_type'):
        return 'reference'
    if e.startswith('stage_'):
        return 'reference'
    if e.startswith('setting'):
        return 'setting'
    if e.startswith('my_tasks'):
        return 'user'
    return None


def _audit_entity_id():
    for v in (request.view_args or {}).values():
        iv = _audit_int(v)
        if iv is not None:
            return iv
    for key in ('entity_id', 'task_id', 'parent_task_id', 'parent_subtask_id', 'id', 'project_id', 'employee_id'):
        iv = _audit_int(request.form.get(key))
        if iv is not None:
            return iv
    return None


def _audit_project_id(db, etype, eid):
    try:
        if etype == 'project' and eid:
            return eid
        if etype == 'task' and eid:
            return _entity_project_id(db, 'task', eid)
        if etype == 'subtask' and eid:
            return _entity_project_id(db, 'subtask', eid)
        if etype == 'comment':
            ce = request.form.get('entity_type')
            ci = _audit_int(request.form.get('entity_id'))
            if ce and ci:
                return _entity_project_id(db, ce, ci)
        if etype == 'assignment' and eid:
            r = db.execute("SELECT task_kind, task_id FROM task_assignment WHERE id=?", (eid,)).fetchone()
            if r:
                return _entity_project_id(db, r['task_kind'], r['task_id'])
        if etype == 'requirement' and eid:
            r = db.execute("SELECT project_id FROM requirement WHERE id=?", (eid,)).fetchone()
            return r[0] if r else None
        if etype == 'stage' and eid:
            r = db.execute("SELECT project_id FROM project_stage WHERE id=?", (eid,)).fetchone()
            return r[0] if r else None
    except sqlite3.Error:
        return None
    return None


def _audit_details():
    if request.method != 'POST':
        return None
    parts = []
    for k, v in request.form.items():
        s = '***' if k == 'password' else str(v)
        if len(s) > 60:
            s = s[:60] + '…'
        parts.append(f'{k}={s}')
    out = '; '.join(parts)
    return out[:300] if out else None


def log_action(action, user=None, entity_type=None, entity_id=None, project_id=None, details=None):
    try:
        db = get_db()
        if entity_type is None:
            entity_type = _endpoint_entity_type(action)
        if entity_id is None:
            entity_id = _audit_entity_id()
        if project_id is None:
            project_id = _audit_project_id(db, entity_type, entity_id)
        if details is None:
            details = _audit_details()
        user_login = user['login'] if user else (request.form.get('login') if request.method == 'POST' else None)
        db.execute("""INSERT INTO audit_log (user_id, user_login, action, entity_type, entity_id,
                                             project_id, position_id, details)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (user['id'] if user else None, user_login, action, entity_type,
                    entity_id, project_id, user['position_id'] if user else None, details))
        db.commit()
        db.close()
    except sqlite3.Error:
        pass


def _audit_request(user):
    endpoint = request.endpoint
    if endpoint not in WRITE_ENDPOINTS and endpoint not in PUBLIC_ENDPOINTS:
        return
    if request.method != 'POST' and endpoint not in GET_MUTATION_ENDPOINTS:
        return
    log_action(endpoint, user=user)


@app.before_request
def _auth_guard():
    # Сбрасываем кэш пользователя, чтобы он вычислялся заново для каждого запроса
    # (иначе при переиспользовании app-контекста может «протечь» пользователь предыдущего запроса).
    g.current_user_loaded = False
    endpoint = request.endpoint
    if not endpoint or endpoint == 'static':
        return None
    user = current_user()
    if endpoint in PUBLIC_ENDPOINTS:
        _audit_request(user)
        return None
    if endpoint not in WRITE_ENDPOINTS:
        return None
    if endpoint in USER_WRITE_ENDPOINTS:
        if not user:
            return _login_redirect()
        _audit_request(user)
        return None
    if endpoint in ANALYST_WRITE_ENDPOINTS:
        if not user:
            return _login_redirect()
        _audit_request(user)
        if not (is_admin() or is_analyst()):
            flash('Недостаточно прав: требуется роль системного аналитика', 'error')
            return redirect(url_for('index'))
        return None
    if not user:
        return _login_redirect()
    _audit_request(user)
    if not is_admin():
        flash('Недостаточно прав: требуется роль администратора', 'error')
        return redirect(url_for('index'))
    return None


# ---------- Скрытие контролов изменения для не-админов ----------

_ANCHOR_RE = re.compile(r'<a\b[^>]*?href="([^"]*)"[^>]*>.*?</a>', re.S | re.I)
_FORM_RE = re.compile(r'<form\b[^>]*?action="([^"]*)"[^>]*>.*?</form>', re.S | re.I)


def _url_path(url):
    if not url or not url.startswith('/'):
        return ''
    return url.split('?', 1)[0].split('#', 1)[0]


_url_adapter = None


def _get_url_adapter():
    global _url_adapter
    if _url_adapter is None:
        try:
            _url_adapter = app.url_map.bind('localhost')
        except Exception:
            return None
    return _url_adapter


def _endpoint_for_path(path):
    if not path:
        return None
    adapter = _get_url_adapter()
    if adapter is None:
        return None
    for method in ('GET', 'POST'):
        try:
            return adapter.match(path, method=method)[0]
        except Exception:
            continue
    return None


def _control_hidden(endpoint, user):
    if not endpoint:
        return False
    if endpoint in ADMIN_WRITE_ENDPOINTS:
        return True
    if endpoint in ANALYST_WRITE_ENDPOINTS:
        return not (user and (user['role'] == 'admin' or user.get('is_analyst')))
    if not user and endpoint in USER_WRITE_ENDPOINTS:
        return True
    return False


def _strip_write_controls(text, user):
    cache = {}

    def hidden_for(url):
        path = _url_path(url)
        if path not in cache:
            cache[path] = _control_hidden(_endpoint_for_path(path), user)
        return cache[path]

    text = _ANCHOR_RE.sub(lambda m: '' if hidden_for(m.group(1)) else m.group(0), text)
    text = _FORM_RE.sub(lambda m: '' if hidden_for(m.group(1)) else m.group(0), text)
    return text


_WRITE_URL_TOKENS = ('/create', '/edit/', '/delete/', '/remove_', '/add_', '/status', '/use/', '/upload',
                     '/save', '/clear', '/transcribe', '/chat/post')


@app.after_request
def _filter_write_controls(response):
    try:
        if response.mimetype != 'text/html':
            return response
        user = current_user()
        if user and user['role'] == 'admin':
            return response
        data = response.get_data(as_text=True)
        if not any(tok in data for tok in _WRITE_URL_TOKENS):
            return response
        new = _strip_write_controls(data, user)
        if new != data:
            response.set_data(new)
    except Exception:
        pass
    return response


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
        .nav { background: #34495e; padding: 10px; margin-bottom: 20px; display: flex; flex-wrap: wrap; align-items: center; }
        .nav a { color: white; text-decoration: none; padding: 8px 15px; margin-right: 10px; display: inline-block; }
        .nav-right { margin-left: auto; display: flex; align-items: center; gap: 6px; color: #bdc3c7; font-size: 13px; }
        .nav-right a { margin-right: 0; }
        .nav-right a.login-btn { background: #27ae60; border-radius: 4px; }
        .nav-right a.logout-btn { background: #e74c3c; border-radius: 4px; }
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
        <div style="margin-top:8px; font-size:13px; color:#bdc3c7;">Активная БД: <strong style="color:#ecf0f1;">{{ current_db }}</strong> &nbsp;|&nbsp; <a href="{{ url_for('database_index') }}" style="color:#ecf0f1;">управление БД</a>{% if current_project %} &nbsp;|&nbsp; Текущий проект: <a href="{{ url_for('project_detail', id=current_project.id) }}" style="color:#ecf0f1;">{{ current_project.name }}</a>{% endif %}</div>
    </div>
    <div class="nav">
        <a href="{{ url_for('index') }}">Главная</a>
        <div class="dropdown">
            <span class="dropbtn">Артефакты СА ▾</span>
            <div class="dropdown-content">
                <a href="{{ url_for('artifact_view', key='vision') }}">Видение (Vision)</a>
                <a href="{{ url_for('artifact_view', key='glossary') }}">Глоссарий</a>
                <a href="{{ url_for('artifact_view', key='stakeholders') }}">Заинтересованные лица</a>
                <a href="{{ url_for('artifact_view', key='personas') }}">Персоны</a>
                <a href="{{ url_for('artifact_view', key='user_stories') }}">Пользовательские истории</a>
                <a href="{{ url_for('artifact_view', key='use_cases') }}">Варианты использования</a>
                <a href="{{ url_for('artifact_view', key='functional_requirements') }}">Функциональные требования</a>
                <a href="{{ url_for('artifact_view', key='nonfunctional_requirements') }}">Нефункциональные требования</a>
                <a href="{{ url_for('artifact_view', key='bpmn') }}">Модель бизнес-процессов (BPMN)</a>
                <a href="{{ url_for('artifact_view', key='state_machines') }}">Диаграммы состояний</a>
                <a href="{{ url_for('artifact_view', key='data_model') }}">Модель данных (ER)</a>
                <a href="{{ url_for('artifact_view', key='prototype') }}">Прототип и навигация</a>
                <a href="{{ url_for('artifact_view', key='backlog') }}">Бэклог и критерии приёмки</a>
                <a href="{{ url_for('artifact_view', key='risks') }}">Риски и допущения</a>
            </div>
        </div>
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
        {% if is_admin %}
        <a href="{{ url_for('admin_tasks') }}">Задачи</a>
        <a href="{{ url_for('audit_index') }}">Аудит</a>
        <a href="{{ url_for('settings_index') }}">Настройки</a>
        {% elif current_user %}
        <a href="{{ url_for('my_tasks') }}">Мои задачи</a>
        {% endif %}
        <a href="{{ url_for('chat_index') }}">Чат</a>
        <div class="nav-right">
            {% if current_user %}
                <span>{% if current_user.position_name %}{{ current_user.position_name }} {% endif %}{{ current_user.full_name }} ({{ 'администратор' if is_admin else 'пользователь' }}{% if is_analyst %}, системный аналитик{% endif %})</span>
                <a class="logout-btn" href="{{ url_for('logout') }}">Выход</a>
            {% else %}
                <a class="login-btn" href="{{ url_for('login') }}">Вход</a>
            {% endif %}
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

_markdown_renderer = None


def _render_markdown(text):
    """Markdown → HTML (markdown-it-py, gfm-like, без сырого HTML). Фолбэк — экранированный текст."""
    global _markdown_renderer
    if _markdown_renderer is None:
        try:
            from markdown_it import MarkdownIt
            _markdown_renderer = MarkdownIt('gfm-like', {'html': False, 'linkify': False})
        except Exception:
            _markdown_renderer = False
    if _markdown_renderer:
        return _markdown_renderer.render(text or '')
    return f'<div style="white-space: pre-wrap;">{html.escape(text or "")}</div>'


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


# ==================== ОБЩИЕ БЛОКИ КАРТОЧКИ ПРОЕКТА / АРТЕФАКТОВ ====================

def _project_requirements_html(db, project_id, type_name=None, next_url=None, preset_type_id=None):
    """Таблица требований проекта (общая для вкладки проекта и артефактов №7/№8)."""
    params = [project_id]
    type_filter = ''
    if type_name:
        type_filter = ' AND rt.name=?'
        params.append(type_name)
    requirements = db.execute(f"""
        SELECT r.*, s.last_name, s.first_name, rt.name as type_name, pr.name as priority_name
        FROM requirement r
        LEFT JOIN stakeholder s ON r.stakeholder_id = s.id
        JOIN requirement_type rt ON r.requirement_type_id = rt.id
        JOIN priority pr ON r.priority_id = pr.id
        WHERE r.project_id=? AND r.is_deleted=0{type_filter}
        ORDER BY r.id DESC
    """, tuple(params)).fetchall()

    def with_next(endpoint, **kw):
        if next_url:
            kw['next'] = next_url
        return url_for(endpoint, **kw)

    rows = ''.join([f'''
        <tr>
            <td>{r['id']}</td>
            <td>{r['type_name']}</td>
            <td>{f'<a href="{url_for("stakeholder_detail", id=r["stakeholder_id"])}">{r["last_name"] or ""} {r["first_name"] or ""}</a>' if r['stakeholder_id'] else '-'}</td>
            <td>{r['description'][:80]}</td>
            <td>{r['priority_name']}</td>
            <td>
                <a href="{with_next('requirement_detail', id=r['id'])}" class="btn btn-success">Открыть</a>
                <a href="{with_next('requirement_edit', id=r['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{with_next('requirement_delete', id=r['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>''' for r in requirements])

    create_kwargs = {'project_id': project_id}
    if preset_type_id:
        create_kwargs['requirement_type_id'] = preset_type_id
    if next_url:
        create_kwargs['next'] = next_url
    add_link = url_for('requirement_create', **create_kwargs)

    html_out = f'''
        <a href="{add_link}" class="btn btn-success">+ Добавить требование</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Тип</th><th>Стейкхолдер</th><th>Описание</th><th>Приоритет</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>'''
    return html_out, len(requirements)


def _project_stakeholders_html(db, project_id):
    """Вкладка «Стейкхолдеры» проекта (общая для карточки проекта и артефакта)."""
    project = db.execute("SELECT id, main_stakeholder_id FROM project WHERE id=?", (project_id,)).fetchone()
    main_id = project['main_stakeholder_id'] if project else None
    assoc_rows = db.execute("SELECT stakeholder_id FROM project_stakeholder WHERE project_id=? AND is_deleted=0", (project_id,)).fetchall()
    assoc_ids = {a['stakeholder_id'] for a in assoc_rows}
    req_st_ids = {row[0] for row in db.execute("SELECT DISTINCT stakeholder_id FROM requirement WHERE project_id=? AND stakeholder_id IS NOT NULL AND is_deleted=0", (project_id,))}
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
        """, tuple([project_id] + list(stk_ids))).fetchall()

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
            return f' <a href="{url_for("project_remove_stakeholder", id=project_id, stakeholder_id=sid)}" class="btn btn-danger" onclick="return confirm(\'Убрать?\')">Убрать</a>'
        return ''

    stk_rows = ''.join([f'''
        <tr>
            <td class="name-cell"><a href="{url_for('stakeholder_detail', id=s['id'])}">{s['last_name']} {s['first_name']}</a> {f'<span class="badge" style="background:#e74c3c">главный</span>' if s['id'] == main_id else ''}{f' <span class="badge" style="background:#3498db">добавлен</span>' if s['id'] in assoc_ids and s['id'] != main_id else ''}</td>
            <td>{s['type_name']}</td>
            <td>{s['inf']}/5, {s['ints']}/5</td>
            <td>{stk_quadrant(s['inf'], s['ints'])}</td>
            <td>{s['position'] or '-'}</td>
            <td>{s['req_count']}</td>
            <td><a href="{url_for('stakeholder_detail', id=s['id'])}" class="btn btn-success">Открыть</a> <a href="{url_for('stakeholder_edit', id=s['id'], origin=project_id)}" class="btn btn-primary">Изменить</a>{remove_btn(s['id'])}</td>
        </tr>''' for s in project_stakeholders])

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

    html_out = f'''
            <a href="{url_for('stakeholder_create', project_id=project_id)}" class="btn btn-success">+ Добавить стейкхолдера</a>
            <form method="POST" action="{url_for('project_add_stakeholder', id=project_id)}" style="display:inline-flex; gap:6px; margin-left:8px; vertical-align:middle;">
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
            </table>'''
    return html_out, len(project_stakeholders)


def _project_stage_tree_html(db, project_id):
    """Дерево этапы → задачи → подзадачи проекта (общая для вкладки проекта и артефакта)."""
    stages = db.execute("""
        SELECT ps.*, pst.name as type_name, pss.name as status_name, pss.color
        FROM project_stage ps
        JOIN project_stage_type pst ON ps.stage_type_id = pst.id
        JOIN project_stage_status pss ON ps.status_id = pss.id
        WHERE ps.project_id=? AND ps.is_deleted=0
        ORDER BY pst.sort_order
    """, (project_id,)).fetchall()

    tasks = db.execute("""
        SELECT t.*, ps.id as stage_id, pr.name as priority_name,
               ts.name as status_name, ts.color as status_color, tt.name as type_name
        FROM task t
        JOIN priority pr ON t.priority_id = pr.id
        JOIN task_status ts ON t.status_id = ts.id
        LEFT JOIN project_stage ps ON t.stage_id = ps.id
        LEFT JOIN requirement r ON t.requirement_id = r.id
        LEFT JOIN task_type tt ON t.task_type_id = tt.id
        WHERE t.is_deleted=0 AND (ps.project_id=? OR r.project_id=?)
        ORDER BY t.id
    """, (project_id, project_id)).fetchall()

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
            SELECT ta.*, e.id as eid, e.last_name, e.first_name,
                   COALESCE(TRIM(au.last_name || ' ' || au.first_name), ap.login, '—') as assigner
            FROM task_assignment ta JOIN employee e ON ta.employee_id = e.id
            LEFT JOIN app_user ap ON ta.assigned_by_user_id = ap.id
            LEFT JOIN employee au ON ap.employee_id = au.id
            WHERE ta.is_deleted=0 AND ta.task_kind=? AND ta.task_id IN ({ph})
        """, tuple([kind] + list(ids))).fetchall()
        for a in rows:
            assignments.setdefault((kind, a['task_id']), []).append(a)
    collect_assignments('task', task_ids)
    collect_assignments('subtask', [s['id'] for s in subtasks])

    covered_by_emp = {}
    for (k, eidkey), rows in assignments.items():
        for a in rows:
            emp = a['employee_id']
            if emp not in covered_by_emp:
                covered_by_emp[emp] = _covered_for_employee(db, emp)
    def _not_covered(k, tid, emp):
        return (k, tid) not in covered_by_emp.get(emp, set())
    assignments = {(k, tid): [a for a in rows if _not_covered(k, tid, a['employee_id'])]
                   for (k, tid), rows in assignments.items()}

    def render_assignees(lines):
        if not lines:
            return '<span class="muted">исполнители не назначены</span>'
        items = [f'<a href="{url_for("employee_detail", id=a["eid"])}">{html.escape(a["last_name"])} {html.escape(a["first_name"])}</a> ({int(a["share"] * 100)}%, назначил: {html.escape(a["assigner"] or "—")})' for a in lines]
        return 'Исполнители: ' + ', '.join(items)

    def render_assignments_block(kind, tid):
        return f'<div class="assign">{render_assignees(assignments.get((kind, tid), []))}</div>'

    def render_subtask(st):
        children = sub_children.get(st['id'], [])
        asg = url_for('task_assignment_create', task_id=st['id'], task_kind='subtask', origin=project_id)
        edit_link = url_for('subtask_edit', id=st['id'], origin=project_id)
        card_link = url_for('subtask_detail', id=st['id'])
        child_link = url_for('subtask_create', parent_subtask_id=st['id'], origin=project_id)
        del_link = url_for('subtask_delete', id=st['id'])
        overdue = bool(st['deadline']) and str(st['deadline']) < date.today().isoformat() and st['status_name'] not in ('Выполнена', 'Отменена')
        deadline_style = ' color:#e74c3c; font-weight:bold;' if overdue else ''
        return f'''
            <details class="subtask" open>
                <summary>
                    <span class="node-info">
                        <a href="{card_link}">Подзадача #{st['id']}</a>
                        <span class="badge" style="background: {st['status_color'] or '#95a5a6'}">{st['status_name']}</span>
                        <span class="node-meta">Приоритет: {st['priority_name']}</span>
                        <span class="node-meta" style="{deadline_style}">Срок: {st['deadline'] or '-'}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-warning" href="{asg}">Назначить</a>
                        <a class="btn btn-primary" href="{edit_link}">Изменить</a>
                        <a class="btn btn-success" href="{child_link}">+ Подзадача</a>
                        <a class="btn btn-danger" href="{del_link}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">
                    {render_assignments_block('subtask', st['id'])}
                    {''.join([render_subtask(c) for c in children])}
                </div>
            </details>'''

    def render_task(t):
        task_subtasks = top_by_task.get(t['id'], [])
        subtask_html = ''.join([render_subtask(s) for s in task_subtasks])
        asg = url_for('task_assignment_create', task_id=t['id'], task_kind='task', origin=project_id)
        subtask_link = url_for('subtask_create', parent_task_id=t['id'], origin=project_id)
        edit_link = url_for('task_edit', id=t['id'], origin=project_id)
        card_link = url_for('task_detail', id=t['id'])
        del_link = url_for('task_delete', id=t['id'])
        overdue = bool(t['deadline']) and str(t['deadline']) < date.today().isoformat() and t['status_name'] not in ('Выполнена', 'Отменена')
        deadline_style = ' color:#e74c3c; font-weight:bold;' if overdue else ''
        return f'''
            <details class="task" open>
                <summary>
                    <span class="node-info">
                        <a href="{card_link}">Задача #{t['id']}</a>
                        <span class="badge" style="background: {t['status_color'] or '#95a5a6'}">{t['status_name']}</span>
                        <span class="node-meta">Тип: {t['type_name'] or '-'}</span>
                        <span class="node-meta">Приоритет: {t['priority_name']}</span>
                        <span class="node-meta" style="{deadline_style}">Срок: {t['deadline'] or '-'}</span>
                    </span>
                    <span class="node-actions">
                        <a class="btn btn-warning" href="{asg}">Назначить</a>
                        <a class="btn btn-primary" href="{edit_link}">Изменить</a>
                        <a class="btn btn-success" href="{subtask_link}">+ Подзадача</a>
                        <a class="btn btn-danger" href="{del_link}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">
                    {render_assignments_block('task', t['id'])}
                    {subtask_html}
                </div>
            </details>'''

    tasks_by_stage = {}
    for t in tasks:
        if t['stage_id'] is None:
            tasks_by_stage.setdefault(None, []).append(t)
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
                        <a class="btn btn-success" href="{url_for('task_create', stage_id=s['id'], origin=project_id)}">+ Задача</a>
                        <a class="btn btn-danger" href="{url_for('project_stage_delete', id=s['id'])}" onclick="return confirm('Удалить?')">Удалить</a>
                    </span>
                </summary>
                <div class="node-body">{inner}</div>
            </details>'''

    html_out = f'''
            <a href="{url_for('project_stage_create')}" class="btn btn-success">+ Добавить этап</a>
            <div class="tree">{stage_html}</div>'''
    return html_out, len(stages)


