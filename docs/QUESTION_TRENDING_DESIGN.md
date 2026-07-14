# 语义热点问句任务设计

## 目标

从历史对话中抽取用户提问，将其向量化并做语义聚类，计算“问的人多且彼此不相似”的热点簇，在前端 mini 区域展示 Top10 热点问题，帮助学生发现常见疑问和代表性问题。

## 数据流概览

1. **增量抽取问句**
   - 来源表：`turns`（轮次，字段 `prompt`, `created_at`）与 `sessions`（会话，字段 `user_id`）。
   - 通过 `Session.id = Turn.session_id_fk` 关联，抽取 `(user_id, prompt, turn_created_at)`。
   - 只处理 `Turn.created_at > last_max_created_at` 的新数据，`last_max_created_at` 存在独立状态表或 Redis key 中。

2. **句向量计算（双后端）**
   - 统一接口：`embed_texts(list[str]) -> list[list[float]]`。
   - 后端选择通过环境变量控制：
     - `EMBEDDING_BACKEND=local`：使用本地 `sentence-transformers` 模型（在 Docker 镜像中安装）。
     - `EMBEDDING_BACKEND=silicon`：调用 SiliconFlow 的 embedding API（从 `.env` 读取密钥和模型名）。
   - 支持批量 embedding、超时和错误重试。

3. **新表 `question_embeddings`**

字段设计：

- `id`：自增主键。
- `user_id`：提问用户 ID（学号）。
- `prompt`：原始提问文本。
- `prompt_hash`：对 `(user_id, prompt)` 做哈希（如 `sha256`），唯一约束，用于逻辑去重。
- `embedding`：句向量（JSON 或 BLOB，存 float 数组）。
- `turn_created_at`：对应 `Turn.created_at`，原始问句时间。
- `created_at` / `updated_at`：记录写入/更新时间（复用 `TimestampMixin`）。

写入策略：

- 后台任务按批获取新问句，逐条：
  - 计算 `prompt_hash` 并检查是否已存在记录：
    - 已存在：跳过或按需更新 embedding；
    - 不存在：调用 embedding 服务生成向量，插入新行。
- 每成功处理一条即插入，保证任务中途失败不会丢失已处理结果。

4. **聚类与热度计算（内存中完成）**

- 选择最近 N 条记录（按 `turn_created_at` 或 `created_at` 倒序，如 N=10_000）。
- 将 embedding 正则化到单位向量，用余弦相似度做聚类：
  - 维护若干“簇中心”（可使用簇内向量均值）。
  - 遍历每条 embedding，与所有簇中心计算相似度：
    - 若所有相似度均 `< SIM_THRESHOLD`（从 env 读取，如 0.8），则新建簇；
    - 否则归入相似度最高的簇。
- 热度分数：
  - 基础：簇内样本数量 `count`（问的人越多越热）。
  - 可选时间衰减：按 `turn_created_at` 计算距离当前的小时数 `h`，使用 `exp(-lambda * h)` 加权最近问题。
  - 最终分数示例：`score = count * avg_time_decay`。

5. **写入 Redis Top10 结果**

- 聚类结束后，将所有簇按 `score` 降序排序，取前 `QUESTION_TRENDING_TOP_K`（默认 10）。
- 对每个簇选一个代表性 prompt（例如：
  - 簇中最新一条；或
  - 最短的一条提问作为标题）。
- 写入 Redis：
  - key 示例：`question_trending_top`。
  - 值为 JSON 数组：
    ```json
    [
      {
        "prompt": "...",
        "score": 12.3,
        "count": 10,
        "examples": ["p1", "p2", ...]
      },
      ...
    ]
    ```
  - 可设置 TTL（例如 3 小时），但后台任务每 2 小时刷新一次，TTL 主要用于降级时兜底。

6. **定时任务与运行方式**

- 新增一个后台任务函数，例如 `services.question_trending_task.run_periodic()`：
  - 步骤：
    1. 读取 `last_max_created_at`；
    2. 增量扫描 `turns + sessions`，生成新问句；
    3. 写入/更新 `question_embeddings`；
    4. 选取最近 N 条做聚类和打分；
    5. 写入 Redis Top 结果；
    6. 更新 `last_max_created_at`。
- 集成方式：
  - 方案 A：复用现有 `services.runtime_service.start_periodic_sync` 机制，在其中增加一个每 2 小时触发的问题聚类任务。
  - 方案 B：新增一个独立 worker 容器，在 `docker-compose.yml` 中用 `while true; sleep 7200` 的方式每 2 小时执行一次脚本（推荐生产环境使用）。

7. **API 与前端展示**

- 新增路由：`GET /api/trending/questions`：
  - 从 Redis 读取 `question_trending_top`；
  - 若无数据返回 `{ status: "success", trending: [] }`。
- 前端 `mini-trending-placeholder` 调用该接口：
  - 若结果为空，显示“暂无热点问句”；
  - 否则渲染 Top10 问句列表（可展示 `prompt`、`count` 等信息）。

## 配置项（.env）

- `EMBEDDING_BACKEND`：`local` 或 `silicon`。
- `EMBEDDING_LOCAL_MODEL`：本地 sentence-transformers 模型名（如 `sentence-transformers/all-MiniLM-L6-v2`）。
- `SILICON_EMBEDDING_MODEL`：SiliconFlow embedding 模型名称。
- `QUESTION_EMBEDDING_LOOKBACK_DAYS`：聚类时回溯的天数（如 7）。
- `QUESTION_EMBEDDING_MAX_SAMPLES`：参与聚类的最大样本数（如 10000）。
- `SIM_THRESHOLD`：同簇最小余弦相似度阈值（如 0.8）。
- `QUESTION_TRENDING_TOP_K`：前端展示的簇数量（默认 10）。

## 安全与性能注意事项

- 避免全表扫描：使用 `created_at` 增量拉取，结合唯一 `prompt_hash` 保证幂等。
- 控制调用外部 embedding API 的 QPS，并做好异常重试和超时处理。
- 聚类仅在内存中对近一段时间的样本执行，避免加载全部历史数据。
- Redis 只存最终结果，不做相似度计算，保证缓存简单可靠。
