# ExpertLLM-V3

> 多模型学术AI对话平台 — 支持 Gemini、GPT-4、SiliconFlow，实时公屏讨论，语义热点发现

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ 功能特性

- 🤖 **多模型对话**: 同时支持 Google Gemini、OpenAI GPT-4、SiliconFlow，可任意切换
- 💬 **实时公屏**: 基于 Socket.IO + Redis Pub/Sub 的专业内实时消息
- 🔥 **语义热点**: 自动聚类相似问题，发现专业内热议话题
- 📊 **Prometheus 监控**: 内置 `/metrics` 端点，支持 Grafana 仪表板
- 🐳 **Docker 部署**: 一键 `docker-compose up` 启动全部服务
- 🔐 **用户系统**: 注册/登录/密码修改，专业分组

## 🚀 快速启动

### 前置要求

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- 或本地安装 Python 3.11+、MySQL 8.0+、Redis 7+

### 1. 克隆仓库

```bash
git clone https://github.com/setsu2420/ExpertLLM-V3.git
cd ExpertLLM-V3
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API 密钥
```

必填的 API 密钥：
- `GEMINI_API_KEY` — [Google AI Studio](https://aistudio.google.com/apikey)
- `OPENAI_API_KEY` — [OpenAI Platform](https://platform.openai.com/api-keys)
- `SILICON_KEY` — [SiliconFlow](https://siliconflow.cn)

### 3. 启动服务

```bash
# Docker 方式（推荐）
make up
# 或
docker-compose up -d

# 本地开发方式
make dev
# 或
python app.py
```

访问 http://localhost:8885

### 常用命令

| 命令 | 说明 |
|------|------|
| `make up` | 启动所有 Docker 服务 |
| `make down` | 停止所有服务 |
| `make logs` | 查看日志 |
| `make build` | 重新构建镜像 |
| `make health` | 健康检查 |
| `make clean` | 清理临时文件 |

## 🏗️ 架构

```
┌─────────────────────────────────────────────┐
│                  Nginx / CDN                 │
└─────────────────┬───────────────────────────┘
                  │ :8885
┌─────────────────▼───────────────────────────┐
│              Flask + Socket.IO               │
│  ┌──────────┬──────────┬──────────────────┐ │
│  │  Auth    │  Chat    │  Public Chat     │ │
│  │  Routes  │  Routes  │  (Redis PubSub)  │ │
│  └──────────┴──────────┴──────────────────┘ │
│  ┌──────────────────────────────────────┐   │
│  │         LLM Service                  │   │
│  │  Gemini │ GPT-4 │ SiliconFlow        │   │
│  └──────────────────────────────────────┘   │
└──────┬──────────────────────┬───────────────┘
       │                      │
┌──────▼──────┐    ┌─────────▼──────────┐
│   MySQL 8   │    │     Redis 7        │
│  (持久化)    │    │  (缓存/PubSub)     │
└─────────────┘    └────────────────────┘
```

## 📁 项目结构

```
ExpertLLM/
├── app.py                  # 应用入口
├── config.py               # 配置管理
├── db_service.py           # 数据库服务层
├── docker-compose.yml      # Docker 编排
├── Dockerfile              # 容器构建
├── Makefile                # 便捷命令
├── .env.example            # 环境变量模板
├── models/                 # SQLAlchemy 模型
│   ├── users.py
│   ├── database.py
│   └── admin.py
├── routes/                 # Flask 路由
│   ├── auth_routes.py      # 认证
│   ├── llm_chat_routes.py  # LLM 聊天
│   ├── public_routes.py    # 公屏
│   ├── history_routes.py   # 历史记录
│   ├── trending_routes.py  # 热点榜单
│   ├── user_routes.py      # 用户中心
│   └── admin_routes.py     # 管理后台
├── services/               # 业务逻辑
│   ├── chat_service.py     # 聊天管理
│   ├── llm_service.py      # LLM 调用
│   ├── user_service.py     # 用户管理
│   ├── runtime_service.py  # 后台任务
│   ├── trending_service.py # 热点计算
│   └── metrics.py          # Prometheus 指标
├── utils/                  # 工具模块
├── static/                 # 静态资源
├── templates/              # Jinja2 模板
└── docs/                   # 详细文档
```

## 📊 监控

Prometheus 指标端点: `http://localhost:8885/metrics`

内置指标：
- 请求计数与延迟
- LLM 调用计数与延迟
- 数据库查询计数
- Socket.IO 连接数
- 公屏消息数

Grafana 仪表板配置: `docs/grafana-dashboard.json`

## 📚 文档

- [功能概览](docs/FEATURES_OVERVIEW.md)
- [Docker 部署指南](docs/DEPLOYMENT_DOCKER.md)
- [开发路线图](docs/DEVELOPMENT_PLAN.md)
- [热点问句设计](docs/QUESTION_TRENDING_DESIGN.md)

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)
