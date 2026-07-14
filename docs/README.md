# ExpertLLM-V3 文档索引

## 文档列表

| 文档 | 说明 |
|------|------|
| [FEATURES_OVERVIEW.md](./FEATURES_OVERVIEW.md) | 项目功能与架构概览 |
| [DEPLOYMENT_DOCKER.md](./DEPLOYMENT_DOCKER.md) | Docker 容器化部署指南 |
| [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) | 后续开发计划与路线图 |
| [QUESTION_TRENDING_DESIGN.md](./QUESTION_TRENDING_DESIGN.md) | 语义热点问句功能设计 |
| [script_js_code_blocks.md](./script_js_code_blocks.md) | 前端 script.js 代码块映射参考 |
| [grafana-dashboard.json](./grafana-dashboard.json) | Grafana 监控仪表板 JSON 配置 |

## 技术参考

### LaTeX 公式渲染示例

项目支持 LaTeX 数学公式渲染，以下为参考示例：

- 行内公式：`$\frac{dy}{dx}$` → $\frac{dy}{dx}$
- 积分：`$\int_0^1 x^2 \, dx = \frac{1}{3}$` → $\int_0^1 x^2 \, dx = \frac{1}{3}$
- 指数函数：`$e^x = \sum_{n=0}^{\infty} \frac{x^n}{n!}$` → $e^x = \sum_{n=0}^{\infty} \frac{x^n}{n!}$
- 正态分布：`$X \sim \mathcal{N}(\mu, \sigma^2)$` → $X \sim \mathcal{N}(\mu, \sigma^2)$

## 快速启动

```bash
# 1. 配置环境变量
cp .env.example .env  # 编辑 .env 填入 API Key

# 2. 启动所有服务
docker compose up -d --build

# 3. 查看日志
docker compose logs -f app

# 4. 停止服务
docker compose down
```

访问地址：`http://localhost:8885`

## 项目结构

```
ExpertLLM/
├── app.py                 # Flask 应用入口
├── config.py              # 配置管理
├── db_service.py          # 数据库服务层
├── models/                # SQLAlchemy 数据模型
├── routes/                # HTTP 路由
├── services/              # 业务逻辑服务
├── static/                # 前端静态资源
├── templates/             # Jinja2 模板
├── utils/                 # 工具模块
├── docker-compose.yml     # Docker Compose 编排
├── Dockerfile             # Docker 镜像构建
├── requirements.txt       # Python 依赖
└── docs/                  # 项目文档
```
