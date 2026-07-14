# ExpertLLM-V3 容器化部署指南（Docker/Compose）

本指南用通俗语言解释 Docker/Compose 的基本概念，并给出本项目的开发/生产两种部署方式。照做即可跑起来，理解逐步加深。

## 一、为什么用 Docker/Compose
- 一致性：把运行环境（Python、系统库）封装进镜像，开发/测试/生产一致。
- 多服务编排：本项目依赖 MySQL 与 Redis，Compose 可一键启动/停止三者（app+mysql+redis）。
- 配置集中：通过 `.env` 管理变量，容器内直接读取，避免“在我机器上能跑”的问题。
- 易回滚与迁移：镜像版本化，到处运行。

## 二、关键概念（够用就好）
- 镜像 Image：像“程序安装包”。由 `Dockerfile` 构建。
- 容器 Container：镜像运行起来的实例，类似“进程”。
- Compose：一次性编排多个容器（网络、依赖、启动顺序）。文件名通常 `docker-compose.yml`。
- 卷 Volume：给容器持久化数据用（这里用于 MySQL 数据）。

## 三、两种运行模式
- 开发（简单直跑）：`python app.py`，Socket.IO 使用 threading，最省事。
- 生产（推荐）：用 `gunicorn -k eventlet` 提升 WebSocket 并发与稳定性。需要在 `requirements.txt` 加上 `eventlet` 与 `gunicorn`。

## 四、必要的环境变量（容器内取值）
请在项目根目录 `.env` 中设置（你已存在大部分）：
- 数据库（指向 Compose 内部服务名）：
  - `SQLALCHEMY_DATABASE_URI=mysql+pymysql://root:123456@mysql:3306/expertllm-db?charset=utf8mb4`
- Redis（指向服务名）：
  - `REDIS_HOST=redis`
- 安全与其他：`SECRET_KEY`、`GEMINI_API_KEY`、`OPENAI_API_KEY`、`SILICON_KEY` 等。
- Redis 缓存可调参数：`REDIS_PUBLIC_TTL_SECONDS`、`REDIS_PUBLIC_LIST_MAX`、前缀 `REDIS_PUBLIC_*_PREFIX`

## 五、示例 Dockerfile（开发版）
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8886
CMD ["python", "app.py"]
```

## 六、示例 docker-compose.yml（开发为主，可直接用）
```yaml
version: "3.9"
services:
  app:
    build: .
    container_name: expertllm-app
    env_file: .env
    ports:
      - "8886:8886"
    depends_on:
      - redis
      - mysql
    command: python app.py
  redis:
    image: redis:7-alpine
    container_name: expertllm-redis
    ports:
      - "6379:6379"
  mysql:
    image: mysql:8
    container_name: expertllm-mysql
    environment:
      MYSQL_ROOT_PASSWORD: 123456
      MYSQL_DATABASE: expertllm-db
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"
volumes:
  mysql_data:
```

生产建议：把 `app` 的 `command` 替换为（并在 requirements.txt 添加 `gunicorn`、`eventlet`）：
```yaml
command: gunicorn -k eventlet -w 1 -b 0.0.0.0:8886 app:app
```

## 七、一步步操作（Windows / Linux 通用）
1) 安装 Docker（Windows 用 Docker Desktop，Linux 按发行版文档）
2) 在项目根目录放置 `Dockerfile` 与 `docker-compose.yml`，确认 `.env` 已配置（见上）
3) 构建并启动：
```bash
# 首次/更新后构建
docker compose build
# 前台启动观察日志（或用 -d 后台）
docker compose up
```
4) 访问后端：默认 http://localhost:8886/

## 八、验证与排错
- 容器状态：
```bash
docker compose ps
docker compose logs app
```
- 数据库连通性：确保 `SQLALCHEMY_DATABASE_URI` 指向 `mysql` 服务名。
- Redis：`REDIS_HOST=redis`，若 Redis 不可用，后端将回源 DB，但实时推送会降级。
- 端口冲突：如本机已有 3306/6379，占用会导致启动失败，可映射到其他宿主端口。

## 九、关于 Socket.IO 与稳定性
- 开发模式 `threading` 已可用；
- 生产模式建议 `eventlet`/`gevent`，我们在代码中已实现 Redis Pub/Sub 转发与指数退避重连；
- 如启用 `gunicorn -k eventlet`，请确保 `requirements.txt` 加入：
```text
eventlet
gunicorn
```

## 十、常见问答
- Q: 一定需要容器吗？
  - A: 不是必须，但容器在多服务场景更稳更易维护。
- Q: 可以只跑 Redis 而数据库用外部托管吗？
  - A: 可以，把 `SQLALCHEMY_DATABASE_URI` 指向外部 MySQL 即可。

若你需要，我可以把上述 Dockerfile 与 Compose 直接写入仓库，并按你的 `.env` 做一次性适配。