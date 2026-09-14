# 11. Модель данных (ER)

Текстовое описание. Реализация в DDL — `init_db()` в `main.py`.

## 11.1 Справочники (словари)
`priority`(id, name, weight 1–5)
`stakeholder_type`(id, name, influence_priority 1–5, interest_priority 1–5)
`requirement_type`(id, name)
`position_type`(id, name)
`employee_status`(id, name, is_available)
`project_stage_type`(id, name, sort_order)
`project_stage_status`(id, name, color)
`task_status`(id, name, color)
`task_type`(id, name)

## 11.2 Основные сущности
- **stakeholder**(id, last_name, first_name, middle_name, type_id→stakeholder_type, position, priority 1–5, employee_id→employee NULL)
- **project**(id, name, main_stakeholder_id→stakeholder, cost, mvp_deadline, deadline, priority_id→priority, description)
- **requirement**(id, project_id→project, stakeholder_id→stakeholder, requirement_type_id→requirement_type, description, priority_id→priority, acceptance_criteria)
- **project_stage**(id, project_id→project, stage_type_id→project_stage_type, status_id→project_stage_status, planned_end)
- **employee**(id, last_name, first_name, middle_name, position_type_id→position_type, status_id→employee_status, subordinates_total, subordinates_available, is_stackholder)
- **task**(id, requirement_id→requirement, description, stage_id→project_stage, task_type_id→task_type, priority_id→priority, deadline, status_id→task_status)
- **subtask**(id, parent_task_id→task, parent_subtask_id→subtask, description, stage_id→project_stage, priority_id→priority, deadline, status_id→task_status)
- **task_assignment**(id, task_id, task_kind IN('task','subtask'), employee_id→employee, share 0–1)
- **interview**(id, stakeholder_id→stakeholder, scheduled_at)
- **interview_qa**(id, interview_id→interview, question, answer)
- **interview_audio**(id, interview_id→interview, filename, original_name, mime, duration_ms) — записи интервью (диктофон/загрузка)
- **transcript_segment**(id, interview_id→interview, audio_id→interview_audio, start_ms, end_ms, speaker, text) — посегментные таймкоды + метка спикера
- **comment**(id, entity_type IN('task','subtask'), entity_id, author, text, created_at)
- **event**(id, occurred_at, description, decision)

## 11.3 Связи «многие-к-одному»
- project_stakeholder(project_id, stakeholder_id) — между проектом и стейкхолдером
- project_employee(project_id, employee_id) — между проектом и исполнителями

## 11.4 Ключевые ограничения
- `task_type.name` — UNIQUE.
- `project_stakeholder` / `project_employee` — UNIQUE(project_id, related_id).
- `task_assignment` — частичный уникальный индекс: не более одного активного назначения подзадачи (`WHERE task_kind='subtask' AND is_deleted=0`).
- Задача: обязательны `requirement_id`, `task_type_id`, `stage_id` (проверяется в коде).
- Суммарная загрузка сотрудника ≤ 100% (проверяется в коде).
- Каскадное удаление: этап → задачи → подзадачи; задача → подзадачи; подзадача → вложенные подзадачи (мягкое удаление `is_deleted`).
- `subtask.parent_task_id` — корневая задача; `parent_subtask_id` — непосредственный родитель (вложенность).

## 11.5 Схема взаимосвязей (упрощённо)
```
priority ◄── project
stakeholder_type ◄── stakeholder ◄── project (main)
requirement ◄── project, stakeholder, requirement_type, priority
project_stage ◄── project, stage_type, stage_status
employee ◄── position_type, employee_status
project_stakeholder (project ↔ stakeholder)
project_employee (project ↔ employee)
task ◄── requirement, stage, task_type, priority, task_status
subtask ◄── task, subtask(parent), stage, priority, task_status
task_assignment (task/subtask ↔ employee)
interview ◄── stakeholder ; interview_qa ◄── interview
comment (→ task/subtask)
event
```

## 11.6 ER-диаграмма (Mermaid)

```mermaid
erDiagram
    STAKEHOLDER ||--o{ STAKEHOLDER_TYPE : "имеет тип"
    STAKEHOLDER ||--o{ PROJECT : "главный стейкхолдер"
    STAKEHOLDER ||--o{ REQUIREMENT : "автор"
    STAKEHOLDER ||--o{ INTERVIEW : "проходит"
    STAKEHOLDER ||--o{ PROJECT_STAKEHOLDER : ""
    PROJECT ||--o{ PROJECT_STAKEHOLDER : ""
    PROJECT ||--o{ PROJECT_EMPLOYEE : ""
    EMPLOYEE ||--o{ PROJECT_EMPLOYEE : ""
    PROJECT ||--o{ REQUIREMENT : "содержит"
    PROJECT ||--o{ PROJECT_STAGE : "состоит из"
    PROJECT ||--|| PRIORITY : "имеет приоритет"
    PROJECT_STAGE ||--|| PROJECT_STAGE_TYPE : "тип"
    PROJECT_STAGE ||--|| PROJECT_STAGE_STATUS : "статус"
    REQUIREMENT ||--|| REQUIREMENT_TYPE : "тип"
    REQUIREMENT ||--|| PRIORITY : "приоритет"
    REQUIREMENT ||--o{ TASK : "реализуется"
    TASK ||--|| PROJECT_STAGE : "этап"
    TASK ||--|| TASK_TYPE : "тип задачи"
    TASK ||--|| TASK_STATUS : "статус"
    TASK ||--|| PRIORITY : "приоритет"
    TASK ||--o{ SUBTASK : "декомпозиция"
    SUBTASK ||--o{ SUBTASK : "вложенные"
    TASK ||--o{ TASK_ASSIGNMENT : "назначения"
    SUBTASK ||--o{ TASK_ASSIGNMENT : "назначения"
    EMPLOYEE ||--o{ TASK_ASSIGNMENT : "исполнитель"
    EMPLOYEE ||--|| POSITION_TYPE : "должность"
    EMPLOYEE ||--|| EMPLOYEE_STATUS : "статус"
    TASK ||--o{ COMMENT : "комментарии"
    SUBTASK ||--o{ COMMENT : "комментарии"
    INTERVIEW ||--o{ INTERVIEW_QA : "вопросы"

    STAKEHOLDER {
        int id PK
        string last_name
        string first_name
        string middle_name
        int type_id FK
        string position
        int priority "1-5"
        int employee_id FK "NULL"
    }
    STAKEHOLDER_TYPE {
        int id PK
        string name
        int influence_priority "1-5"
        int interest_priority "1-5"
    }
    PROJECT {
        int id PK
        string name
        int main_stakeholder_id FK
        double cost
        date mvp_deadline
        date deadline
        int priority_id FK
        string description
    }
    PRIORITY { int id PK string name int weight "1-5" }
    REQUIREMENT {
        int id PK
        int project_id FK
        int stakeholder_id FK
        int requirement_type_id FK
        string description
        int priority_id FK
        string acceptance_criteria
    }
    REQUIREMENT_TYPE { int id PK string name }
    PROJECT_STAGE {
        int id PK
        int project_id FK
        int stage_type_id FK
        int status_id FK
        date planned_end
    }
    PROJECT_STAGE_TYPE { int id PK string name int sort_order }
    PROJECT_STAGE_STATUS { int id PK string name string color }
    EMPLOYEE {
        int id PK
        string last_name
        string first_name
        string middle_name
        int position_type_id FK
        int status_id FK
        int subordinates_total
        int subordinates_available
        int is_stackholder "0/1"
    }
    POSITION_TYPE { int id PK string name }
    EMPLOYEE_STATUS { int id PK string name int is_available }
    TASK {
        int id PK
        int requirement_id FK
        string description
        int stage_id FK
        int task_type_id FK
        int priority_id FK
        date deadline
        int status_id FK
    }
    TASK_TYPE { int id PK string name }
    TASK_STATUS { int id PK string name string color }
    SUBTASK {
        int id PK
        int parent_task_id FK
        int parent_subtask_id FK "NULL"
        string description
        int stage_id FK
        int priority_id FK
        date deadline
        int status_id FK
    }
    TASK_ASSIGNMENT {
        int id PK
        int task_id "task или subtask"
        string task_kind "task|subtask"
        int employee_id FK
        double share "0-1"
    }
    PROJECT_STAKEHOLDER { int id PK int project_id FK int stakeholder_id FK }
    PROJECT_EMPLOYEE { int id PK int project_id FK int employee_id FK }
    INTERVIEW { int id PK int stakeholder_id FK date scheduled_at }
    INTERVIEW_QA { int id PK int interview_id FK string question string answer }
    COMMENT { int id PK string entity_type "task|subtask" int entity_id string author string text }
    EVENT { int id PK date occurred_at string description string decision }
```

## 11.x Аутентификация, аудит и чат (дополнение)

```mermaid
erDiagram
    APP_USER {
        int id PK
        string login "уникальный"
        string password "открытый текст (учебный проект)"
        string role "admin|user"
        int employee_id FK
    }
    SETTING { string key PK string value }
    AUDIT_LOG {
        int id PK
        int user_id FK
        string user_login
        string action
        string entity_type
        int entity_id
        int project_id FK
        int position_id FK
        string details
        datetime created_at
    }
    CHAT_MESSAGE { int id PK int user_id FK string author string text datetime created_at }
    APP_USER ||--o| EMPLOYEE : "связан с сотрудником"
    AUDIT_LOG }o--o| APP_USER : "автор действия"
    AUDIT_LOG }o--o| PROJECT : "проект действия"
    CHAT_MESSAGE }o--o| APP_USER : "автор сообщения"
```

- `task_assignment` дополнена полями `assigned_by_user_id` (FK → `app_user`) и `assigned_at` — кто и когда назначил исполнителя.
- `comment` дополнена `user_id` (FK → `app_user`); `author` заполняется ФИО текущего пользователя.
- `task_status` содержит статус «Принята к исполнению».
- `AUDIT_LOG` неизменяем: маршрутов редактирования/удаления нет.
