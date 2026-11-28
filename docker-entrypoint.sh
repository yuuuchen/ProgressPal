#!/bin/sh
# 容器啟動流程：建立／更新資料表 → 全新資料庫時初始化章節與題庫 → 啟動網站
set -e
cd /app/progresspal

echo "[entrypoint] migrate"
python manage.py migrate --noinput

echo "[entrypoint] init_experiment"
python manage.py init_experiment

echo "[entrypoint] gunicorn"
exec gunicorn progresspal.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-8}" \
    --timeout "${GUNICORN_TIMEOUT:-180}" \
    --access-logfile - \
    --error-logfile -
