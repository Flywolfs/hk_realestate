# ============================================================
# 第一阶段：构建前端
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

# 复制前端依赖文件并安装
COPY 28hse_system/frontend/package.json 28hse_system/frontend/package-lock.json* ./
RUN npm install

# 复制前端源码并构建
COPY 28hse_system/frontend/ ./
RUN npm run build


# ============================================================
# 第二阶段：生产镜像
# ============================================================
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ---- 目录结构 ----
# /app/                          (工作目录，对应 centanet_system/crawler/)
#   estate_info_20260221_convert.json
#   average_rent_sale_ratio.json
#   monthly_price_trend_20260306.json
#   estate_info_20260221.json
#   crawler/
#     transaction_record_20260306_trans/
#       buy/   (5313 个交易文件)
#       rent/  (2879 个交易文件)
# /app/28hse_system/
#   housing_types.json
#   backend/
#     app.py
#     auth.py
#     requirements.txt
#     utils/
#       data_loader.py
#   frontend/
#     dist/    (前端构建产物)

# 创建应用目录
RUN mkdir -p /app/28hse_system/backend/utils \
             /app/28hse_system/frontend/dist \
             /app/crawler/transaction_record_20260306_trans/buy \
             /app/crawler/transaction_record_20260306_trans/rent

# ---- 复制数据文件（工作目录层） ----
COPY centanet_system/crawler/estate_info_20260221_convert.json /app/
COPY centanet_system/crawler/average_rent_sale_ratio.json      /app/
COPY centanet_system/crawler/monthly_price_trend_20260306.json /app/
COPY centanet_system/crawler/estate_info_20260221.json         /app/

# ---- 复制交易记录 ----
COPY centanet_system/crawler/transaction_record_20260306_trans/buy/  /app/crawler/transaction_record_20260306_trans/buy/
COPY centanet_system/crawler/transaction_record_20260306_trans/rent/ /app/crawler/transaction_record_20260306_trans/rent/

# ---- 复制 28hse_system 数据文件 ----
COPY 28hse_system/housing_types.json /app/28hse_system/

# ---- 复制后端代码 ----
COPY 28hse_system/backend/requirements.txt /app/28hse_system/backend/
RUN pip install --no-cache-dir -r /app/28hse_system/backend/requirements.txt

COPY 28hse_system/backend/app.py   /app/28hse_system/backend/
COPY 28hse_system/backend/auth.py  /app/28hse_system/backend/
COPY 28hse_system/backend/utils/   /app/28hse_system/backend/utils/

# ---- 复制前端构建产物 ----
COPY --from=frontend-builder /build/frontend/dist/ /app/28hse_system/frontend/dist/

# 工作目录设为数据根目录（对应 centanet_system/crawler/）
WORKDIR /app

# 对外暴露端口
EXPOSE 5000

# 启动命令：在 /app 下运行后端
CMD ["python", "28hse_system/backend/app.py"]
