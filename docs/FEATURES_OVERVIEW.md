# 项目功能与内容概览

## 1. 架构概述
- 入口：`app.py`（Flask + Socket.IO），启动时进行 DB→Redis 初始同步，开启 Redis Pub/Sub 转发和 2h 定时同步任务。（docker compose up -d --build）
- 数据访问：集中在 `db_service.py`（会话、历史、公屏、投票），路由/服务不直接操作 `db.session`。
- 路由：`routes/`（auth、chat、history、public、trending、admin）。
- 服务：`services/`（chat、llm、sensitive_filter、trending、user、admin），封装业务逻辑。
- 模型：`models/` 定义 SQLAlchemy 表和 `TimestampMixin`。
- 工具：`utils/redis_client.py`、`utils/decorators.py`（登录校验）、JSON 帮助方法。

## 2. 核心功能
- 认证与用户
  - 登录/注册/登出；注册时校验学生证图片大小 ≤1.5MB；当前用户信息接口。
  - 会话认证依赖 Flask session；可开启 `SECURE_SOCKETS` 禁止通过 Socket.IO auth 传 user_id。
- 聊天
  - `POST /api/session/new` 创建会话；`/api/chat` 与 `/api/chat/stream` 支持非流式与流式。
  - 每轮：session 锁 → upsert turn → 追加 user message 到线程 → 取历史 → LLM 调用（Gemini/GPT/SiliconFlow，支持 streaming）→ 保存 assistant → 记录历史（record_turn）。
  - 上下文线程按模型分开存储，支持模型顺序 `model_order`。
- 公屏（公共消息）
  - 按专业隔离；Redis 缓存优先，DB 回源；消息写入 Redis list/hash 并广播 Pub/Sub。
  - 投票支持 like/dislike，防重复与专业校验；缓存只更新 hash 避免列表重复。
  - 启动和定期 DB→Redis 同步确保一致性；Pub/Sub 转发到 Socket.IO 房间。
- 历史记录
  - 通过 `db_service` 读取摘要与详情；`model_order` 用于展示排序；提供 project/session/turn 层级。
- 热点榜（trending）
  - 统计“昨日”公屏消息（按专业/学校），按 like_count 排序。
- 敏感词
  - `static/sensitive-word/*.txt` 载入；聊天流式接口阻断敏感提示；`/api/check-sensitive` 实时检测。
- 管理端
  - `routes/admin_routes.py` + `services/admin_service.py`（未详述 UI，但有 admin.html/admin.js）。

## 3. 数据与缓存
- 数据库：MySQL，DSN 从 `SQLALCHEMY_DATABASE_URI`；表包含 Session/Turn/Message/Thread/PublicMessage/PublicVote/Project/Users。
- Redis：可禁用 (`REDIS_ENABLED`)，默认 host/port 从 env；在 compose 中为 `redis:3306`（未对外暴露）。
- 公屏缓存：key 前缀 `REDIS_PUBLIC_*`，列表最大 300，TTL 默认 7 天；读：LRANGE + HGET；写：HSET → LREM → RPUSH → LTRIM → PUBLISH。

## 4. 运行与部署
- 本地开发：`python app.py`，host/port/DEBUG 从 env，禁用 Flask reloader 以兼容后台线程。
- 容器（当前 compose）：
  - app：`gunicorn -k eventlet -w 1 -b 0.0.0.0:7100 app:app` 暴露宿主 8885。
  - mysql：容器 3306 → 宿主 7102；redis：容器 1000（未映射宿主）。
  - `.env` 提供 DB/Redis/LLM/SECRET_KEY 及缓存参数。
- 典型命令：`docker compose build`、`docker compose up -d`、`docker compose logs -f app`、`docker compose down`。

## 5. 配置要点
- 必需：`SECRET_KEY`、LLM keys（GEMINI/OPENAI/SILICON）、`SQLALCHEMY_DATABASE_URI`。
- Redis：`REDIS_HOST`、`REDIS_PORT`、`REDIS_ENABLED`；公屏相关 `REDIS_PUBLIC_*`。
- Socket 安全：`SECURE_SOCKETS` 控制是否允许通过 Socket.IO auth 携带 user_id。
- 其他：`MAX_THREAD_MESSAGES`、`TRENDING_BOARD_SIZE`、`SYSTEM_PROMPT` 可通过 env 覆盖。

## 6. 背景任务
- Pub/Sub 转发：订阅 `public:major:*`，转发到对应房间；含指数退避重连。
- DB→Redis 同步：启动时一次 + 每 2h 定时；清理受管前缀后回填缓存。

## 7. 约定与扩展
- 所有 DB 读写通过 `db_service`；路由只是编排，服务层封装业务。
- 添加新模型：在 `services/llm_service.py` 实现 `call_llm`/`call_llm_stream`，沿用 `model_key`，无需改表。
- 公屏扩展：在 `db_service` 增加写入逻辑，缓存/广播留在 `routes/public_routes.py` helper。

## 8. 已知默认端口
- 应用：容器 7100 → 宿主 8885（compose）。
- MySQL：容器 3306 → 宿主 7102。
- Redis：容器 3306（无宿主映射）。

## 9. 参考文件
- 入口与同步逻辑：`app.py`
- 数据访问：`db_service.py`
- 路由：`routes/*.py`
- 服务：`services/*.py`
- 配置：`config.py`
- 部署：`docs/DEPLOYMENT_DOCKER.md`
