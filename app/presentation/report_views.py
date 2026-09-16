"""HTML-представление отчётов (карточки и таблицы)."""

import html
from typing import Any

from fastapi import Request

Row = dict[str, Any]
Cards = list[tuple[str, Any, str]]
Table = dict[str, Any]
Tables = list[Table]


def _url(request: Request, name: str, fallback: str, **params: Any) -> str:
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return fallback


def _esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def projects(request: Request, data: Row) -> tuple[Cards, Tables]:
    total = int(data["total"])
    cards: Cards = [
        ("Всего проектов", total, "#2c3e50"),
        ("Общая стоимость", f"{data['cost']:,.0f}", "#2c3e50"),
        ("Проектов с бюджетом", data["budget"], "#2c3e50"),
        ("Средний приоритет", f"{data['avg_priority']:.2f}" if total else 0, "#2c3e50"),
    ]
    rows1 = [[_esc(p["name"]), p["weight"], p["cnt"], f"{p['cost']:,.0f}"] for p in data["by_priority"]]
    rows2: list[list[Any]] = []
    for p in data["progress"]:
        task_pct = round(p["tasks_done"] / p["tasks"] * 100) if p["tasks"] else 0
        stage_pct = round(p["stages_done"] / p["stages"] * 100) if p["stages"] else 0
        link = _url(request, "project_detail", f"/projects/{p['id']}", id=p["id"])
        rows2.append(
            [
                f'<a href="{link}">{_esc(p["name"])}</a>',
                f"{p['stages_done']}/{p['stages']}",
                f"{p['tasks_done']}/{p['tasks']}",
                f"{task_pct}%",
                f"{stage_pct}%",
            ]
        )
    tables: Tables = [
        {
            "title": "Проекты по приоритетам",
            "headers": ["Приоритет", "Вес", "Кол-во", "Стоимость"],
            "rows": rows1,
        },
        {
            "title": "Прогресс проектов",
            "headers": [
                "Проект",
                "Этапы (завершено/всего)",
                "Задачи (выполнено/всего)",
                "Прогресс по задачам",
                "Прогресс по этапам",
            ],
            "rows": rows2,
        },
    ]
    return cards, tables


def stakeholders(request: Request, data: Row) -> tuple[Cards, Tables]:
    types = data["types"]
    cards: Cards = [
        ("Всего стейкхолдеров", data["total"], "#2c3e50"),
        ("Типов", len(types), "#2c3e50"),
        ("Ключевые игроки", data["key"], "#e74c3c"),
    ]
    rows = [[_esc(t["name"]), t["inf"], t["ints"], t["cnt"], t["quadrant"]] for t in types]
    tables: Tables = [
        {
            "title": "Матрица власти и интереса (по типам)",
            "headers": ["Тип", "Влияние", "Интерес", "Кол-во", "Квадрант"],
            "rows": rows,
        }
    ]
    return cards, tables


def employees(request: Request, data: Row) -> tuple[Cards, Tables]:
    cards: Cards = [
        ("Всего сотрудников", data["total"], "#2c3e50"),
        ("Доступно", data["available"], "#27ae60"),
        ("Заняты в задачах", data["assigned"], "#2c3e50"),
        ("Перегружены (>100%)", data["overloaded"], "#e74c3c"),
    ]
    rows: list[list[Any]] = []
    for item in data["load"]:
        link = _url(request, "employee_detail", f"/employees/{item['id']}", id=item["id"])
        rows.append(
            [
                f'<a href="{link}">{_esc(item["last_name"])} {_esc(item["first_name"])}</a>',
                _esc(item["pos"]),
                _esc(item["st"]),
                item["acnt"],
                f"{round(item['load'] * 100)}%",
            ]
        )
    rows2 = [[_esc(p["name"]), p["cnt"], p["avail"]] for p in data["by_position"]]
    tables: Tables = [
        {
            "title": "Загрузка сотрудников",
            "headers": ["Фамилия", "Имя", "Должность", "Статус", "Назначений", "Загрузка %"],
            "rows": rows,
        },
        {
            "title": "Состав по должностям",
            "headers": ["Должность", "Сотрудников", "Доступно"],
            "rows": rows2,
        },
    ]
    return cards, tables


def requirements(request: Request, data: Row) -> tuple[Cards, Tables]:
    total = int(data["total"])
    implemented = int(data["implemented"])
    cards: Cards = [
        ("Всего требований", total, "#2c3e50"),
        ("С критерием проверки", data["criteria"], "#2c3e50"),
        ("Реализовано (есть задачи)", implemented, "#27ae60"),
        ("Без задач", total - implemented, "#e74c3c"),
    ]
    rows: list[list[Any]] = []
    for p in data["by_project"]:
        link = _url(request, "project_detail", f"/projects/{p['id']}", id=p["id"])
        rows.append(
            [
                f'<a href="{link}">{_esc(p["name"])}</a>',
                p["total"],
                p["crit"],
                p["impl"],
                p["total"] - p["impl"],
            ]
        )
    rows2 = [[_esc(t["name"]), t["cnt"]] for t in data["by_type"]]
    rows3 = [[_esc(t["name"]), t["cnt"]] for t in data["by_priority"]]
    tables: Tables = [
        {
            "title": "По проектам",
            "headers": ["Проект", "Требований", "С критерием", "Реализовано", "Без задач"],
            "rows": rows,
        },
        {"title": "По типам", "headers": ["Тип требования", "Кол-во"], "rows": rows2},
        {"title": "По приоритетам", "headers": ["Приоритет", "Кол-во"], "rows": rows3},
    ]
    return cards, tables


def stages(request: Request, data: Row) -> tuple[Cards, Tables]:
    cards: Cards = [
        ("Всего этапов", data["total"], "#2c3e50"),
        ("В работе", data["work"], "#3498db"),
        ("Завершено", data["done"], "#27ae60"),
        ("Просрочено", data["overdue"], "#e74c3c"),
    ]
    rows: list[list[Any]] = []
    for p in data["by_project"]:
        link = _url(request, "project_detail", f"/projects/{p['id']}", id=p["id"])
        rows.append(
            [
                f'<a href="{link}">{_esc(p["name"])}</a>',
                p["total"],
                p["done"],
                p["work"],
                p["over"],
            ]
        )
    tables: Tables = [
        {
            "title": "Этапы по проектам",
            "headers": ["Проект", "Всего", "Завершено", "В работе", "Просрочено"],
            "rows": rows,
        }
    ]
    return cards, tables


def tasks(request: Request, data: Row) -> tuple[Cards, Tables]:
    cards: Cards = [
        ("Всего задач", data["total"], "#2c3e50"),
        ("В работе", data["work"], "#3498db"),
        ("Выполнено", data["done"], "#27ae60"),
        ("Просрочено", data["overdue"], "#e74c3c"),
        ("Без исполнителя", data["noexec"], "#f39c12"),
    ]
    rows = [
        [
            f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{_esc(s["name"])}</span>',
            s["cnt"],
        ]
        for s in data["by_status"]
    ]
    rows2 = [[_esc(t["name"]), t["cnt"]] for t in data["by_priority"]]
    rows3: list[list[Any]] = []
    for t in data["without_executor"]:
        task_link = _url(request, "task_detail", f"/tasks/{t['id']}", id=t["id"])
        if t["pid"]:
            project_url = _url(request, "project_detail", f"/projects/{t['pid']}", id=t["pid"])
            project_cell = f'<a href="{project_url}">{_esc(t["pname"])}</a>'
        else:
            project_cell = "-"
        if t["stage_id"]:
            stage_url = _url(request, "project_stage_detail", f"/project_stages/{t['stage_id']}", id=t["stage_id"])
            stage_cell = f'<a href="{stage_url}">{_esc(t["stype"])}</a>'
        else:
            stage_cell = "-"
        rows3.append(
            [
                f'<a href="{task_link}">#{t["id"]}</a>',
                project_cell,
                stage_cell,
                _esc(t["description"][:60]),
                _esc(t["prio"]),
                _esc(t["st"]),
            ]
        )
    tables: Tables = [
        {"title": "По статусам", "headers": ["Статус", "Кол-во"], "rows": rows},
        {"title": "По приоритетам", "headers": ["Приоритет", "Кол-во"], "rows": rows2},
        {
            "title": "Задачи без исполнителя",
            "headers": ["ID", "Проект", "Этап", "Описание", "Приоритет", "Статус"],
            "rows": rows3,
        },
    ]
    return cards, tables


def subtasks(request: Request, data: Row) -> tuple[Cards, Tables]:
    cards: Cards = [
        ("Всего подзадач", data["total"], "#2c3e50"),
        ("В работе", data["work"], "#3498db"),
        ("Выполнено", data["done"], "#27ae60"),
        ("Просрочено", data["overdue"], "#e74c3c"),
        ("Без исполнителя", data["noexec"], "#f39c12"),
    ]
    rows = [
        [
            f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{_esc(s["name"])}</span>',
            s["cnt"],
        ]
        for s in data["by_status"]
    ]
    rows2: list[list[Any]] = []
    for s in data["without_executor"]:
        sub_link = _url(request, "subtask_detail", f"/subtasks/{s['id']}", id=s["id"])
        task_link = _url(request, "task_detail", f"/tasks/{s['parent_id']}", id=s["parent_id"])
        rows2.append(
            [
                f'<a href="{sub_link}">#{s["id"]}</a>',
                f'<a href="{task_link}">{_esc(s["parent"][:50])}</a>',
                _esc(s["description"][:50]),
                _esc(s["prio"]),
                _esc(s["st"]),
            ]
        )
    tables: Tables = [
        {"title": "По статусам", "headers": ["Статус", "Кол-во"], "rows": rows},
        {
            "title": "Подзадачи без исполнителя",
            "headers": ["ID", "Родительская задача", "Описание", "Приоритет", "Статус"],
            "rows": rows2,
        },
    ]
    return cards, tables


def assignments(request: Request, data: Row) -> tuple[Cards, Tables]:
    cards: Cards = [
        ("Назначений всего", data["total"], "#2c3e50"),
        ("По задачам", data["task"], "#3498db"),
        ("По подзадачам", data["subtask"], "#27ae60"),
        ("Максимальная загрузка", f"{round(data['max_load'] * 100)}%", "#e74c3c"),
    ]
    rows: list[list[Any]] = []
    for a in data["by_employee"]:
        link = _url(request, "employee_detail", f"/employees/{a['id']}", id=a["id"])
        load_pct = f"{round(a['load'] * 100)}%"
        rows.append(
            [
                f'<a href="{link}">{_esc(a["last_name"])} {_esc(a["first_name"])}</a>',
                _esc(a["pos"]),
                load_pct,
                "—",
                load_pct,
                a["acnt"],
            ]
        )
    tables: Tables = [
        {
            "title": "Загрузка по сотрудникам",
            "headers": ["Сотрудник", "Должность", "Задачи (доля)", "Подзадачи (доля)", "Итого %", "Назначений"],
            "rows": rows,
        }
    ]
    return cards, tables


def events(request: Request, data: Row) -> tuple[Cards, Tables]:
    cards: Cards = [
        ("Всего событий", data["total"], "#2c3e50"),
        ("За 30 дней", data["last30"], "#3498db"),
        ("Последнее событие", data["last_event"] if data["last_event"] else "-", "#2c3e50"),
    ]
    rows = [[_esc(m["m"]), m["cnt"]] for m in data["months"]]
    rows2: list[list[Any]] = []
    for e in data["recent"]:
        link = _url(request, "event_detail", f"/events/{e['id']}", id=e["id"])
        rows2.append(
            [
                f'<a href="{link}">{_esc(e["occurred_at"])}</a>',
                _esc(e["description"]),
                _esc(e["decision"]) if e["decision"] else "-",
            ]
        )
    tables: Tables = [
        {"title": "Динамика по месяцам", "headers": ["Месяц", "Кол-во"], "rows": rows},
        {"title": "Последние события", "headers": ["Дата", "Описание", "Решение"], "rows": rows2},
    ]
    return cards, tables
