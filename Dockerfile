# 使用與你本機一致的 Python 3.11 輕量版映像檔
FROM python:3.11-slim

# 避免 Python 產生 .pyc 檔，並讓 print/log 即時輸出到 Docker 紀錄
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安裝 OpenCV、TensorFlow 與編譯套件所需的 Linux 系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 設定容器內的工作目錄
WORKDIR /app

# 先複製最外層的 requirements.txt 並安裝（利用 Docker 快取機制，未來改程式不用重裝套件）
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 將整個 progresspal 專案資料夾複製進 /app/progresspal
COPY ./progresspal /app/progresspal

# 切換工作目錄到包含 manage.py 的資料夾
WORKDIR /app/progresspal

# 建立獨立保存實驗資料庫的掛載資料夾
RUN mkdir -p /app/db_data

# 收集所有 CSS / JS 靜態檔案（供 WhiteNoise 在正式環境提供服務）
RUN python manage.py collectstatic --noinput