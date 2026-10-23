FROM python:3.12-slim

# 非 root 執行：入門先修正 /data 擁有權（既有 volume 可能為 root），再以 gosu 降權
RUN useradd --create-home --uid 1000 appuser \
 && apt-get update \
 && apt-get install -y --no-install-recommends gosu \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 官方 python image 內建 pip 的 vendored CA bundle 較舊（eMudhra/emSign 事件），
# 先升級 pip 再安裝相依，確保自 PyPI 下載時的 HTTPS 驗證使用修補後的信任庫
RUN pip install --no-cache-dir --upgrade pip==26.2.2

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser app/ ./app/
COPY --chmod=755 entrypoint.sh /entrypoint.sh

RUN mkdir -p /data

ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
