.PHONY: help up down build logs test lint clean shell db-shell redis-shell

# 默认目标
help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ========== Docker 命令 ==========

up: ## 启动所有服务 (docker-compose up -d)
	docker-compose up -d

down: ## 停止所有服务
	docker-compose down

build: ## 重新构建镜像
	docker-compose build --no-cache

restart: down up ## 重启所有服务

logs: ## 查看所有服务日志
	docker-compose logs -f --tail=100

logs-app: ## 查看应用日志
	docker-compose logs -f app

logs-worker: ## 查看Worker日志
	docker-compose logs -f question-worker

# ========== 开发命令 ==========

dev: ## 本地开发模式启动 (需要本地MySQL+Redis)
	python app.py

shell: ## 进入应用容器Shell
	docker-compose exec app /bin/bash

db-shell: ## 进入MySQL容器
	docker-compose exec mysql mysql -u$${MYSQL_USER:-expertllm_user} -p$${MYSQL_PASSWORD:-UserPassword456!} $${MYSQL_DATABASE:-expertllm-db}

redis-shell: ## 进入Redis CLI
	docker-compose exec redis redis-cli

# ========== 代码质量 ==========

lint: ## 代码风格检查
	python -m py_compile $$(find . -name '*.py' -not -path './.venv/*' -not -path './env/*')

clean: ## 清理临时文件
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type f -name '.DS_Store' -delete 2>/dev/null || true
	find . -type f -name '*.log' -delete 2>/dev/null || true

# ========== 环境设置 ==========

env: ## 从模板创建 .env 文件
	@if [ -f .env ]; then \
		echo "⚠️  .env 已存在，跳过创建"; \
	else \
		cp .env.example .env && echo "✅ .env 已从 .env.example 创建，请编辑填入实际密钥"; \
	fi

install: ## 安装Python依赖
	pip install -r requirements.txt

# ========== 状态检查 ==========

status: ## 查看服务状态
	docker-compose ps

health: ## 检查应用健康状态
	@curl -s http://localhost:8885/health 2>/dev/null || echo "⚠️  应用未运行或 /health 端点不可用"
