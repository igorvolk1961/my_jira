#!/usr/bin/env bash
# Запуск/остановка УПО в фоне (не зависит от SSH-сессии).
# Использование: ./upo.sh {start|stop|restart|status|logs}
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/data/upo.pid"
LOG_FILE="$SCRIPT_DIR/data/upo.log"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    RUN=("$SCRIPT_DIR/.venv/bin/python" main.py)
elif command -v uv >/dev/null 2>&1; then
    RUN=(uv run main.py)
else
    echo "Не найден $SCRIPT_DIR/.venv/bin/python и не установлен uv." >&2
    echo "Установите зависимости: uv sync" >&2
    exit 1
fi

is_running() {
    [ -f "$PID_FILE" ] || return 1
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null
}

start() {
    if is_running; then
        echo "УПО уже запущен (PID $(cat "$PID_FILE"))."
        return 0
    fi
    mkdir -p "$SCRIPT_DIR/data"
    echo "Запуск УПО на $HOST:$PORT ..."
    HOST="$HOST" PORT="$PORT" nohup "${RUN[@]}" >>"$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" >"$PID_FILE"
    sleep 1
    if is_running; then
        echo "УПО запущен (PID $pid). Лог: $LOG_FILE"
    else
        echo "Не удалось запустить. Смотрите лог: $LOG_FILE" >&2
        rm -f "$PID_FILE"
        return 1
    fi
}

stop() {
    if ! is_running; then
        echo "УПО не запущен."
        rm -f "$PID_FILE"
        return 0
    fi
    local pid
    pid="$(cat "$PID_FILE")"
    echo "Остановка УПО (PID $pid) ..."
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "Процесс не завершился за 10 с, посылаю SIGKILL ..."
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "УПО остановлен."
}

status() {
    if is_running; then
        echo "УПО запущен (PID $(cat "$PID_FILE"))."
    else
        echo "УПО не запущен."
        return 1
    fi
}

case "${1:-}" in
    start) start ;;
    stop) stop ;;
    restart)
        stop
        start
        ;;
    status) status ;;
    logs) tail -f "$LOG_FILE" ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs}"
        exit 2
        ;;
esac
