# 生产镜像：Python 3.11-slim + FastAPI (QuoteSys Quote-Service)
FROM python:3.11-slim

# 避免生成 __pycache__，减小镜像体积并实时输出标准日志
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先安装依赖，利用 Docker 镜像层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝应用后端代码
COPY . .

# 确保运行时数据卷目录存在
RUN mkdir -p /app/data /app/uploads

# 后端监听 8000 端口
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
