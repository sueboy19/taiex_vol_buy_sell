# TAIEX 大盤 K線圖系統

台股大盤指數 K線圖，含成交量、融資融券，盤中即時更新，支援畫線工具。

## 展示
![alt text](runtime_pic/1782184263980.jpg)

![alt text](runtime_pic/2026-06-23_112631.png)

## 功能

- **K線圖**（日線 / 分鐘線）— KLineChart
- **成交量**副圖
- **融資 / 融券**副圖（每日，證交所資料）
- **盤中即時**更新（開盤 09:00-13:30，WebSocket 推播分鐘K）
- **畫線工具**：線段、射線、水平線、畫筆（自由手繪）、箭頭
  - 畫線儲存於瀏覽器 localStorage

## 技術架構

| 層 | 技術 |
|----|------|
| 後端 | Python + FastAPI |
| 資料庫 | DuckDB（列式，適合時序聚合） |
| 前端 | React + TypeScript + Vite |
| 圖表 | KLineChart v9（含畫線工具） |
| 即時推送 | WebSocket |
| 容器 | Docker Compose（開發/正式分離） |

## 資料來源

| 資料 | 來源 | 頻率 |
|------|------|------|
| 日線 OHLC | TWSE OpenAPI `/indicesReport/MI_5MINS_HIST` | 收盤後 |
| 日成交量 | TWSE OpenAPI `/exchangeReport/FMTQIK` | 收盤後 |
| 融資融券 | TWSE OpenAPI `/exchangeReport/MI_MARGN`（全市場合計） | 收盤後 |
| 盤中分鐘K指數 | Yahoo Finance v8 `^TWII` | 盤中每 30s |
| 盤中分鐘量 | TWSE OpenAPI `/exchangeReport/MI_5MINS`（5秒累計差值） | 盤中每 10s |

## 快速開始

### 開發模式

```bash
docker compose -f docker-compose.dev.yml up --build
```

- 後端：http://localhost:8000 （API 文件：http://localhost:8000/docs）
- 前端：http://localhost:5173

### 正式部署（Coolify）

1. 將此 repo 連接到 Coolify
2. Build Pack 選 **Docker Compose**
3. Docker Compose Location 指定 `docker-compose.prod.yml`
4. 在 Coolify UI 為 `frontend` service 指派網域
5. 部署

#### Coolify 環境變數

在 Coolify 專案的 **Environment variables** 頁面設定（並勾選可用於 build/deploy）：

| 變數 | 必填 | 說明 |
|------|------|------|
| `SERVICE_URL_FRONTEND` | 自動 | Coolify 依 frontend 指派的網域**自動產生**（如 `https://taiex.mkinweb.com`），compose 檔用它帶入 `CORS_ORIGINS`，不需手動設 |
| `FINMIND_TOKEN` | 否 | FinMind API token，提升資料回填額度 |
| `WS_MAX_CONNECTIONS` | 否 | WebSocket 連線數上限，預設 200 |

注意：CORS 是否正確收緊，取決於 **frontend service 有在 Coolify 指派網域**（產生 `SERVICE_URL_FRONTEND`）。
若想明確固定，也可直接在 Coolify 加一組 `CORS_ORIGINS=https://taiex.mkinweb.com` 覆蓋。

#### 資安設計

- API 為公開唯讀（GET only）；`CORS_ORIGINS=*` 時自動停用 credentials
- WebSocket 允許同源連線（本站前端）；跨站需符合 Origin 白名單，並限制連線數（防跨站 WS 劫持與資源耗盡）
- nginx 限流以 `X-Forwarded-For` 為鍵（站點位於 Cloudflare/Traefik 之後，`$remote_addr` 為代理 IP）：API 20 r/s、WS 10 條連線 / 客戶端；並提供安全標頭（CSP / nosniff / frame-ancestors）
- 後端容器以非 root（appuser）執行；frontend 僅保留 nginx 最小權限（cap_drop ALL + 最小 cap_add）
- Python 相依套件已鎖定版本（`backend/requirements.txt`）
- CA 事件（如 2026-10 eMudhra/emSign 中繼 CA 私鑰外洩）：更新 `requirements.txt` 中的
  `certifi` 版本號即可觸發 Docker layer 重建（一般 Redeploy 即可，不必清 cache）；
  build 時並先升級 pip 以修補其內建信任庫

## 專案結構

```
├── docker-compose.dev.yml     # 開發
├── docker-compose.prod.yml    # 正式（Coolify）
├── backend/                   # FastAPI + DuckDB
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── twse_client.py
│   │   ├── yahoo_client.py
│   │   ├── scheduler.py
│   │   ├── aggregator.py
│   │   ├── routes/
│   │   └── ws/
│   ├── Dockerfile             # 正式
│   └── Dockerfile.dev         # 開發
└── frontend/                  # React + KLineChart
    ├── src/
    │   ├── components/
    │   ├── hooks/
    │   ├── store/
    │   └── api/
    ├── nginx.conf             # 正式反向代理
    ├── Dockerfile             # 正式
    └── Dockerfile.dev         # 開發
```
