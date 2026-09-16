"""Идемпотентное начальное заполнение БД (справочники, admin, шаблон интервью)."""

from sqlalchemy import Connection, text

from app.db.models.reference import NonfunctionalRequirementType  # noqa: F401  (регистрация моделей)
from app.security import hash_password

NONFUNCTIONAL_REQUIREMENT_TYPES = [
    "Производительность",
    "Масштабируемость",
    "Доступность",
    "Надёжность",
    "Безопасность",
    "Удобство использования",
    "Совместимость",
    "Сопровождаемость",
    "Ограничения и соответствие",
]

DEFAULT_INTERVIEW_TEMPLATE_NAME = "Вопросы Заказчику"

DEFAULT_INTERVIEW_QUESTIONS = [
    'Не будете ли Вы возражать, если я буду делать аудиозапись встречи? Это поможет мне ничего не упустить и сосредоточиться на диалоге, а не на конспектировании. (Если "да" – уточнить, можно ли поделиться расшифровкой).',
    "Кто еще, по Вашему мнению, должен участвовать в обсуждении требований? (Например, ключевые пользователи, ИТ-архитектор, юрист, специалист по безопасности).",
    "Кто является конечным лицом, принимающим решение (ЛПР) по приемке требований и результата проекта?",
    "Расскажите, пожалуйста, в чем ключевая идея и главная бизнес-предпосылка проекта? (Что случилось: новый закон, давление конкурентов, внутренние издержки, новая возможность на рынке?)",
    "По каким конкретным, измеримым критериям (KPI/метрикам) Вы будете оценивать, что проект успешен? (Например: снижение времени обработки заявки на 30%, рост конверсии на 15%).",
    "Как Вы планируете монетизировать проект или какую экономическую выгоду он должен принести компании?",
    "Есть ли жесткие дедлайны или привязка к внешним событиям (выставка, изменение законодательства, конец финансового года)?",
    "Кто целевая аудитория проекта? Можно ли выделить ключевые роли/персоны пользователей?",
    "Какие цели преследуют эти пользователи и какие задачи они пытаются решить с помощью нашего будущего продукта?",
    'Как пользователи решают эти задачи сейчас? (Опишите текущий процесс "As-Is").',
    'С какими основными проблемами, "узкими местами" или "болями" они сталкиваются в текущем процессе?',
    "Сколько времени у пользователей уходит на выполнение этих задач сейчас? Какой выигрыш по времени или усилиям Вы сочтете приемлемым в новой системе?",
    "Что должно быть реализовано в рамках MVP (минимально жизнеспособного продукта), чтобы запустить проект?",
    "Критически важный вопрос: Что мы точно НЕ будем делать в рамках этого проекта? (Что находится за рамками / out of scope).",
    "Планируете ли Вы масштабирование (расширение) функционала или географии проекта в будущем? Если да, то в каком горизонте?",
    "На каких устройствах и платформах должен работать проект? (Web, iOS, Android, десктоп, киоски самообслуживания).",
    "Какова ожидаемая нагрузка? Сколько пользователей будет работать с системой одновременно (пиковая и средняя нагрузка)?",
    "Какие требования предъявляются к доступности системы? (Например, 99.9% uptime, работа 24/7 или только в рабочие часы).",
    "Какие у Вас есть требования, касающиеся информационной безопасности, обработки персональных данных (152-ФЗ, GDPR) или отраслевые стандарты (например, PCI DSS для платежей)?",
    "Должна ли новая система обмениваться данными с существующими системами компании? (Например, 1С, CRM, ERP, сайт). Если да, то знаете ли Вы, есть ли у этих систем готовые API?",
    "Есть ли необходимость миграции исторических данных из старых систем? В каком виде они сейчас хранятся?",
    "Кто будет владельцем данных в новой системе и кто отвечает за их актуальность?",
    "Есть ли определенные рамки по бюджету или стоимости владения (TCO), которые нам нужно учитывать при выборе архитектурных или технологических решений?",
    'Есть ли предпочтения по технологическому стеку? (Например, "только открытое ПО", "только решения от отечественных вендоров", "уже куплены лицензии на Microsoft").',
    "Мне нужно обдумать полученную информацию, структурировать ее и, возможно, подготовить уточняющие вопросы. Как нам лучше выстроить дальнейшую коммуникацию? (Формат следующих встреч, каналы связи, сроки предоставления протокола встречи).",
]


def seed_database(engine) -> None:
    with engine.begin() as conn:
        _seed_reference(conn)
        _seed_default_admin(conn)
        _seed_interview_templates(conn)


def _seed_reference(conn: Connection) -> None:
    for nfr in NONFUNCTIONAL_REQUIREMENT_TYPES:
        conn.execute(text("INSERT OR IGNORE INTO nonfunctional_requirement_type (name) VALUES (:n)"), {"n": nfr})

    for ttype in (
        "Новый функционал",
        "Исправление ошибки",
        "Улучшение",
        "Документирование",
        "Тестирование",
        "Код-ревью",
    ):
        conn.execute(text("INSERT OR IGNORE INTO task_type (name) VALUES (:n)"), {"n": ttype})

    conn.execute(text("INSERT OR IGNORE INTO position_type (name) VALUES ('Пользователь')"))
    conn.execute(
        text("INSERT OR IGNORE INTO task_status (name, color) VALUES (:n, :c)"),
        {"n": "Принята к исполнению", "c": "#8e44ad"},
    )
    conn.execute(
        text("INSERT OR IGNORE INTO setting (key, value) VALUES (:k, :v)"),
        {"k": "allow_users_assign_subtask_executors", "v": "1"},
    )

    if conn.execute(text("SELECT COUNT(*) FROM priority")).scalar_one() == 0:
        conn.execute(
            text("INSERT INTO priority (name, weight) VALUES (:n, :w)"),
            [
                {"n": "Низкий", "w": 1},
                {"n": "Ниже среднего", "w": 2},
                {"n": "Средний", "w": 3},
                {"n": "Выше среднего", "w": 4},
                {"n": "Высокий", "w": 5},
            ],
        )
        conn.execute(
            text("INSERT INTO stakeholder_type (name, influence_priority, interest_priority) VALUES (:n, :i, :t)"),
            [
                {"n": "Инвестор", "i": 5, "t": 3},
                {"n": "Бизнес-заказчик", "i": 5, "t": 5},
                {"n": "Конечный пользователь", "i": 2, "t": 5},
                {"n": "Разработчик", "i": 3, "t": 4},
                {"n": "Ответственный за безопасность", "i": 4, "t": 3},
                {"n": "Юрист / комплаенс", "i": 4, "t": 2},
                {"n": "Эксплуатация / поддержка", "i": 3, "t": 4},
            ],
        )
        conn.execute(
            text("INSERT INTO requirement_type (name) VALUES (:n)"),
            [
                {"n": "Бизнес-требование"},
                {"n": "Пользовательское требование"},
                {"n": "Функциональное требование"},
                {"n": "Нефункциональное требование"},
            ],
        )
        conn.execute(
            text("INSERT INTO project_stage_type (name, sort_order) VALUES (:n, :s)"),
            [
                {"n": "Инициация", "s": 1},
                {"n": "Анализ", "s": 2},
                {"n": "Проектирование", "s": 3},
                {"n": "Разработка", "s": 4},
                {"n": "Тестирование", "s": 5},
                {"n": "Внедрение", "s": 6},
                {"n": "Закрытие", "s": 7},
            ],
        )
        conn.execute(
            text("INSERT INTO project_stage_status (name, color) VALUES (:n, :c)"),
            [
                {"n": "Не начат", "c": "gray"},
                {"n": "В работе", "c": "blue"},
                {"n": "На паузе", "c": "yellow"},
                {"n": "Завершён", "c": "green"},
                {"n": "Отменён", "c": "red"},
            ],
        )
        conn.execute(
            text("INSERT INTO position_type (name) VALUES (:n)"),
            [
                {"n": "Системный аналитик"},
                {"n": "Архитектор"},
                {"n": "Начальник тех. отдела"},
                {"n": "Юрист"},
                {"n": "Ведущий бэкендер"},
                {"n": "Ведущий фронтендер"},
                {"n": "QA-инженер"},
                {"n": "DevOps"},
                {"n": "Аналитик данных"},
                {"n": "Менеджер проекта"},
                {"n": "Дизайнер"},
                {"n": "Специалист по информационной безопасности"},
            ],
        )
        conn.execute(text("UPDATE position_type SET is_analyst=1 WHERE lower(name)=lower('Системный аналитик')"))
        conn.execute(
            text("INSERT INTO employee_status (name, is_available) VALUES (:n, :a)"),
            [
                {"n": "Работает", "a": 1},
                {"n": "В командировке", "a": 0},
                {"n": "Болеет", "a": 0},
                {"n": "В отпуске", "a": 0},
                {"n": "Уволен", "a": 0},
            ],
        )
        conn.execute(
            text("INSERT INTO task_status (name, color) VALUES (:n, :c)"),
            [
                {"n": "Новая", "c": "gray"},
                {"n": "В работе", "c": "blue"},
                {"n": "На проверке", "c": "yellow"},
                {"n": "Выполнена", "c": "green"},
                {"n": "Отменена", "c": "red"},
                {"n": "Заблокирована", "c": "orange"},
            ],
        )


def _seed_default_admin(conn: Connection) -> None:
    if conn.execute(text("SELECT 1 FROM app_user WHERE lower(login)='admin'")).first():
        return
    conn.execute(text("INSERT OR IGNORE INTO position_type (name) VALUES ('Пользователь')"))
    pos_id = conn.execute(
        text("SELECT id FROM position_type WHERE lower(name)=lower('Пользователь') ORDER BY id LIMIT 1")
    ).scalar_one()
    conn.execute(text("INSERT OR IGNORE INTO employee_status (name, is_available) VALUES ('Работает', 1)"))
    status_id = conn.execute(
        text("SELECT id FROM employee_status WHERE lower(name)=lower('Работает') ORDER BY id LIMIT 1")
    ).scalar_one()
    emp_id = conn.execute(
        text("SELECT id FROM employee WHERE last_name='admin' AND first_name='admin' ORDER BY id LIMIT 1")
    ).scalar()
    if emp_id is None:
        emp_id = conn.execute(
            text(
                "INSERT INTO employee (last_name, first_name, middle_name, position_type_id, status_id,"
                " subordinates_total, subordinates_available, is_stackholder)"
                " VALUES ('admin', 'admin', 'admin', :pos, :status, 0, 0, 0)"
            ),
            {"pos": pos_id, "status": status_id},
        ).lastrowid
    conn.execute(
        text(
            "INSERT OR IGNORE INTO app_user (login, password, role, employee_id) VALUES ('admin', :pw, 'admin', :emp)"
        ),
        {"pw": hash_password("12345"), "emp": emp_id},
    )


def _seed_interview_templates(conn: Connection) -> None:
    exists = conn.execute(
        text("SELECT 1 FROM interview_template WHERE name=:name"), {"name": DEFAULT_INTERVIEW_TEMPLATE_NAME}
    ).first()
    if exists:
        return
    template_id = conn.execute(
        text("INSERT INTO interview_template (name, description) VALUES (:name, :descr)"),
        {"name": DEFAULT_INTERVIEW_TEMPLATE_NAME, "descr": "Базовый набор вопросов для интервью с заказчиком"},
    ).lastrowid
    conn.execute(
        text("INSERT INTO interview_template_question (template_id, question, position) VALUES (:tid, :q, :pos)"),
        [
            {"tid": template_id, "q": question, "pos": index}
            for index, question in enumerate(DEFAULT_INTERVIEW_QUESTIONS)
        ],
    )
