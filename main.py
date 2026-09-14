"""Учебный проектный офис (УПО) — точка входа.

Ядро (app, БД, шаблон, хелперы) — в app_core.py; маршруты — в модулях routes_*.
"""

from app_core import *  # noqa: F401,F403
from app_core import _covered_for_employee  # noqa: F401  (используется тестами)
import os  # noqa: F401

# Регистрация маршрутов: импорт модулей вешает их на общий app
import routes_main  # noqa: F401
import routes_reference  # noqa: F401
import routes_stakeholders  # noqa: F401
import routes_projects  # noqa: F401
import routes_requirements  # noqa: F401
import routes_employees  # noqa: F401
import routes_stages  # noqa: F401
import routes_tasks  # noqa: F401
import routes_assignments  # noqa: F401
import routes_events  # noqa: F401
import routes_reports  # noqa: F401
import routes_details  # noqa: F401
import routes_interviews  # noqa: F401
import routes_comments  # noqa: F401
import routes_database  # noqa: F401
import routes_auth  # noqa: F401
import routes_chat  # noqa: F401
import routes_audit  # noqa: F401
import routes_settings  # noqa: F401
import routes_personal  # noqa: F401


#==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

# Инициализация БД при импорте (важно для gunicorn/WSGI, где main.py не выполняется как __main__)
init_db()

if __name__ == '__main__':
    print("=" * 60)
    print(f"Учебный проектный офис (УПО) запущен! Активная БД: {DEFAULT_DB_NAME}")
    print("=" * 60)
    app.run(debug=os.environ.get('UPO_DEBUG', '') == '1',
            host=os.environ.get('HOST', '0.0.0.0'),
            port=int(os.environ.get('PORT', '5000')))
