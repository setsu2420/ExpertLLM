FROM python:3.11-slim
# FROM registry.cn-hangzhou.aliyuncs.com/google_containers/python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
# RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

EXPOSE 7100

# 开发模式：直接运行 Flask + Socket.IO (threading)
CMD ["python", "app.py"]
