#!/bin/sh
# 容器啟動流程：建立／更新資料表 → 全新資料庫時初始化章節與題庫 → 啟動網站
set -e
cd /app/progresspal

echo "[entrypoint] migrate"
python manage.py migrate --noinput

echo "[entrypoint] init_experiment"
python manage.py init_experiment

# 設定了 ANALYSIS_SHEET_ID 時，每 10 分鐘（SHEETS_SYNC_INTERVAL 秒）自動同步分析資料到 Google 試算表（SPEC R7.3）
if [ -n "$ANALYSIS_SHEET_ID" ]; then
    echo "[entrypoint] Google 試算表自動同步：每 ${SHEETS_SYNC_INTERVAL:-600} 秒"
    (
        while true; do
            sleep "${SHEETS_SYNC_INTERVAL:-600}"
            python manage.py export_analysis --sheets || echo "[sheets-sync] 同步失敗，下次再試"
        done
    ) &
fi

echo "[entrypoint] gunicorn"
exec gunicorn progresspal.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-8}" \
    --timeout "${GUNICORN_TIMEOUT:-180}" \
    --access-logfile - \
    --error-logfile -
