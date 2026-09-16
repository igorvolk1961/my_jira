"""Репозиторий сотрудников и синхронизаций (должность <-> роль, стейкхолдер)."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_active(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            text(
                """
                SELECT e.*, pt.name AS position_name, es.name AS status_name, es.is_available,
                       u.id AS user_id, u.role AS user_role, u.is_analyst AS user_analyst
                FROM employee e
                JOIN position_type pt ON e.position_type_id = pt.id
                JOIN employee_status es ON e.status_id = es.id
                LEFT JOIN app_user u ON u.employee_id = e.id AND u.is_deleted = 0
                WHERE e.is_deleted = 0
                ORDER BY e.last_name
                """
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get(db: Session, employee_id: int) -> dict[str, Any] | None:
    row = (
        db.execute(text("SELECT * FROM employee WHERE id=:id AND is_deleted=0"), {"id": employee_id}).mappings().first()
    )
    return dict(row) if row else None


def get_detail(db: Session, employee_id: int) -> dict[str, Any] | None:
    row = (
        db.execute(
            text(
                """
                SELECT e.*, pt.name AS position_name, es.name AS status_name, es.is_available,
                       u.role AS user_role, u.is_analyst AS user_analyst, u.login AS user_login
                FROM employee e
                JOIN position_type pt ON e.position_type_id = pt.id
                JOIN employee_status es ON e.status_id = es.id
                LEFT JOIN app_user u ON u.employee_id = e.id AND u.is_deleted = 0
                WHERE e.id=:id AND e.is_deleted=0
                """
            ),
            {"id": employee_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_positions(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT * FROM position_type WHERE is_deleted=0 ORDER BY name")).mappings().all()
    return [dict(row) for row in rows]


def list_statuses(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(text("SELECT * FROM employee_status WHERE is_deleted=0 ORDER BY name")).mappings().all()
    return [dict(row) for row in rows]


def create(db: Session, values: dict[str, Any]) -> int:
    result = db.execute(
        text(
            """
            INSERT INTO employee (last_name, first_name, middle_name, position_type_id, status_id,
                                  subordinates_total, subordinates_available, is_stackholder)
            VALUES (:last_name, :first_name, :middle_name, :position_type_id, :status_id,
                    :subordinates_total, :subordinates_available, :is_stackholder)
            RETURNING id
            """
        ),
        values,
    )
    return int(result.scalar_one())


def update(db: Session, employee_id: int, values: dict[str, Any]) -> None:
    db.execute(
        text(
            """
            UPDATE employee SET last_name=:last_name, first_name=:first_name, middle_name=:middle_name,
                   position_type_id=:position_type_id, status_id=:status_id,
                   subordinates_total=:subordinates_total, subordinates_available=:subordinates_available,
                   is_stackholder=:is_stackholder, updated_at=CURRENT_TIMESTAMP
            WHERE id=:id
            """
        ),
        {**values, "id": employee_id},
    )


def soft_delete_employee(db: Session, employee_id: int) -> None:
    db.execute(
        text("UPDATE employee SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"id": employee_id},
    )


def deactivate_users_for_employee(db: Session, employee_id: int) -> int:
    count = db.execute(
        text("SELECT COUNT(*) FROM app_user WHERE employee_id=:id AND is_deleted=0"),
        {"id": employee_id},
    ).scalar_one()
    db.execute(
        text("UPDATE app_user SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE employee_id=:id AND is_deleted=0"),
        {"id": employee_id},
    )
    return int(count)


def get_active_user_for_employee(db: Session, employee_id: int) -> dict[str, Any] | None:
    row = (
        db.execute(
            text("SELECT id FROM app_user WHERE employee_id=:id AND is_deleted=0"),
            {"id": employee_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def set_user_role(db: Session, user_id: int, role: str, is_analyst: int) -> None:
    db.execute(
        text("UPDATE app_user SET role=:role, is_analyst=:is_analyst, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
        {"role": role, "is_analyst": is_analyst, "id": user_id},
    )


def add_project_employee(db: Session, project_id: int, employee_id: int) -> None:
    db.execute(
        text("INSERT INTO project_employee (project_id, employee_id) VALUES (:pid, :eid)"),
        {"pid": project_id, "eid": employee_id},
    )


def position_name(db: Session, position_type_id: int | None) -> str | None:
    if not position_type_id:
        return None
    row = db.execute(text("SELECT name FROM position_type WHERE id=:id"), {"id": position_type_id}).first()
    return str(row[0]) if row else None


def position_is_analyst(db: Session, position_type_id: int | None) -> bool:
    if not position_type_id:
        return False
    row = db.execute(text("SELECT is_analyst FROM position_type WHERE id=:id"), {"id": position_type_id}).first()
    return bool(row and row[0])


def analyst_position_id(db: Session) -> int | None:
    row = db.execute(
        text("SELECT id FROM position_type WHERE is_analyst=1 AND is_deleted=0 ORDER BY id LIMIT 1")
    ).first()
    return int(row[0]) if row else None


def default_position_id(db: Session) -> int:
    row = db.execute(
        text("SELECT id FROM position_type WHERE lower(name)=lower('Пользователь') AND is_deleted=0")
    ).first()
    if row:
        return int(row[0])
    result = db.execute(text("INSERT INTO position_type (name) VALUES ('Пользователь') RETURNING id"))
    return int(result.scalar_one())


def set_position(db: Session, employee_id: int, position_type_id: int) -> None:
    db.execute(
        text("UPDATE employee SET position_type_id=:pid, updated_at=CURRENT_TIMESTAMP WHERE id=:id AND is_deleted=0"),
        {"pid": position_type_id, "id": employee_id},
    )


def sync_analyst_role_from_position(db: Session, employee_id: int) -> None:
    """Должность сотрудника -> флаг роли is_analyst у связанной учётной записи."""
    row = db.execute(
        text("SELECT position_type_id FROM employee WHERE id=:id AND is_deleted=0"),
        {"id": employee_id},
    ).first()
    if not row:
        return
    want = 1 if position_is_analyst(db, row[0]) else 0
    db.execute(
        text(
            "UPDATE app_user SET is_analyst=:want, updated_at=CURRENT_TIMESTAMP WHERE employee_id=:id AND is_deleted=0"
        ),
        {"want": want, "id": employee_id},
    )


def sync_position_from_analyst_role(db: Session, employee_id: int, want: bool) -> None:
    """Флаг роли is_analyst -> должность сотрудника (только при реальном переходе)."""
    row = db.execute(
        text("SELECT position_type_id FROM employee WHERE id=:id AND is_deleted=0"),
        {"id": employee_id},
    ).first()
    if not row:
        return
    current = row[0]
    if want:
        if not position_is_analyst(db, current):
            pos_id = analyst_position_id(db)
            if pos_id:
                set_position(db, employee_id, pos_id)
    elif position_is_analyst(db, current):
        set_position(db, employee_id, default_position_id(db))


def developer_type_id(db: Session) -> int:
    row = db.execute(
        text("SELECT id FROM stakeholder_type WHERE lower(name)=lower('Разработчик') AND is_deleted=0")
    ).first()
    if row:
        return int(row[0])
    result = db.execute(
        text(
            "INSERT INTO stakeholder_type (name, influence_priority, interest_priority)"
            " VALUES ('Разработчик', 3, 3) RETURNING id"
        )
    )
    return int(result.scalar_one())


def reset_employee_stackholder_if_unlinked(db: Session, employee_id: int | None) -> None:
    if not employee_id:
        return
    count = db.execute(
        text("SELECT COUNT(*) FROM stakeholder WHERE employee_id=:id AND is_deleted=0"),
        {"id": employee_id},
    ).scalar_one()
    if count == 0:
        db.execute(
            text("UPDATE employee SET is_stackholder=0 WHERE id=:id AND is_deleted=0"),
            {"id": employee_id},
        )


def set_employee_stackholder(db: Session, employee_id: int) -> None:
    db.execute(
        text("UPDATE employee SET is_stackholder=1 WHERE id=:id AND is_deleted=0"),
        {"id": employee_id},
    )


def sync_stakeholder_for_employee(db: Session, employee_id: int, active: bool) -> None:
    """Синхронизирует связанного стейкхолдера-«разработчика» с флагом is_stackholder."""
    emp = get(db, employee_id)
    if not emp:
        return
    linked = (
        db.execute(
            text("SELECT id FROM stakeholder WHERE employee_id=:id AND is_deleted=0"),
            {"id": employee_id},
        )
        .scalars()
        .all()
    )
    if active:
        position = position_name(db, emp["position_type_id"])
        type_id = developer_type_id(db)
        if linked:
            for existing in linked:
                db.execute(
                    text(
                        """
                        UPDATE stakeholder SET last_name=:ln, first_name=:fn, middle_name=:mn,
                               position=:pos, type_id=:tid, updated_at=CURRENT_TIMESTAMP
                        WHERE id=:id
                        """
                    ),
                    {
                        "ln": emp["last_name"],
                        "fn": emp["first_name"],
                        "mn": emp["middle_name"],
                        "pos": position,
                        "tid": type_id,
                        "id": int(existing),
                    },
                )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO stakeholder (last_name, first_name, middle_name, type_id, position,
                                             priority, employee_id)
                    VALUES (:ln, :fn, :mn, :tid, :pos, 3, :eid)
                    """
                ),
                {
                    "ln": emp["last_name"],
                    "fn": emp["first_name"],
                    "mn": emp["middle_name"],
                    "tid": type_id,
                    "pos": position,
                    "eid": employee_id,
                },
            )
    else:
        for existing in linked:
            db.execute(
                text("UPDATE stakeholder SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
                {"id": int(existing)},
            )


def _subtask_parent_map(db: Session) -> dict[int, tuple[int, int | None]]:
    rows = (
        db.execute(text("SELECT id, parent_task_id, parent_subtask_id FROM subtask WHERE is_deleted=0"))
        .mappings()
        .all()
    )
    return {int(r["id"]): (int(r["parent_task_id"]), r["parent_subtask_id"]) for r in rows}


def covered_for_employees(db: Session, employee_ids: set[int]) -> dict[int, set[tuple[str, int]]]:
    """Позиции (kind, id), покрытые подзадачами, для набора сотрудников (батчем)."""
    ids = sorted(employee_ids)
    result: dict[int, set[tuple[str, int]]] = {emp: set() for emp in ids}
    if not ids:
        return result
    placeholders = ",".join(f":e{i}" for i in range(len(ids)))
    params = {f"e{i}": value for i, value in enumerate(ids)}
    pairs = (
        db.execute(
            text(
                "SELECT employee_id, task_id FROM task_assignment"
                f" WHERE task_kind='subtask' AND is_deleted=0 AND employee_id IN ({placeholders})"
            ),
            params,
        )
        .mappings()
        .all()
    )
    parents = _subtask_parent_map(db)
    for pair in pairs:
        employee_id = int(pair["employee_id"])
        info = parents.get(int(pair["task_id"]))
        if not info:
            continue
        task_id, parent_subtask = info
        result[employee_id].add(("task", task_id))
        while parent_subtask:
            result[employee_id].add(("subtask", int(parent_subtask)))
            info = parents.get(int(parent_subtask))
            parent_subtask = info[1] if info else None
    return result


def covered_for_employee(db: Session, employee_id: int) -> set[tuple[str, int]]:
    """Позиции (kind, id), где сотрудник занят в подзадаче (покрывает предка)."""
    return covered_for_employees(db, {employee_id}).get(employee_id, set())


def effective_loads(db: Session, employee_ids: set[int]) -> dict[int, float]:
    """Эффективная загрузка набора сотрудников одним набором запросов."""
    ids = sorted(employee_ids)
    loads: dict[int, float] = {emp: 0.0 for emp in ids}
    if not ids:
        return loads
    covered = covered_for_employees(db, set(ids))
    placeholders = ",".join(f":e{i}" for i in range(len(ids)))
    params = {f"e{i}": value for i, value in enumerate(ids)}
    rows = (
        db.execute(
            text(
                "SELECT employee_id, task_id, task_kind, share FROM task_assignment"
                f" WHERE is_deleted=0 AND employee_id IN ({placeholders})"
            ),
            params,
        )
        .mappings()
        .all()
    )
    for row in rows:
        employee_id = int(row["employee_id"])
        if (str(row["task_kind"]), int(row["task_id"])) in covered.get(employee_id, set()):
            continue
        loads[employee_id] += float(row["share"])
    return loads


def effective_load(db: Session, employee_id: int) -> float:
    return effective_loads(db, {employee_id}).get(employee_id, 0.0)


def assigned_tasks(db: Session, employee_id: int) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            text(
                """
                SELECT ta.share, t.id, t.description, t.deadline, pr.name AS prio, ts.name AS st,
                       ts.color AS color, p.name AS pname, pst.name AS stype
                FROM task_assignment ta
                JOIN task t ON ta.task_id = t.id
                JOIN priority pr ON t.priority_id = pr.id
                JOIN task_status ts ON t.status_id = ts.id
                LEFT JOIN project_stage ps ON t.stage_id = ps.id
                LEFT JOIN project_stage_type pst ON ps.stage_type_id = pst.id
                LEFT JOIN project p ON p.id = COALESCE(ps.project_id,
                    (SELECT project_id FROM requirement WHERE id = t.requirement_id))
                WHERE ta.employee_id=:id AND ta.task_kind='task' AND ta.is_deleted=0 AND t.is_deleted=0
                ORDER BY t.id DESC
                """
            ),
            {"id": employee_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def assigned_subtasks(db: Session, employee_id: int) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            text(
                """
                SELECT ta.share, s.id, s.description, s.deadline, pr.name AS prio, ts.name AS st,
                       ts.color AS color, t.description AS parent
                FROM task_assignment ta
                JOIN subtask s ON ta.task_id = s.id
                JOIN task t ON s.parent_task_id = t.id
                JOIN priority pr ON s.priority_id = pr.id
                JOIN task_status ts ON s.status_id = ts.id
                WHERE ta.employee_id=:id AND ta.task_kind='subtask' AND ta.is_deleted=0 AND s.is_deleted=0
                ORDER BY s.id DESC
                """
            ),
            {"id": employee_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
