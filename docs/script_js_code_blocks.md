# script.js 代码块映射

说明：列出 `static/script.js` 中执行具体任务的主要代码块，包含起止行号、功能简介、以及主要调用关系（调用方 / 被调用方）。行号基于当前仓库文件，范围是闭区间。

注意：此文件为静态映射，帮助快速定位实现与调用关系。

-- 概览 --
- 文件： [static/script.js](static/script.js)
- 总行数：2365

## 代码块清单

1. `attachSendHandlers()` — 行 8-139
   - 功能：注册主输入区的发送按钮与回车键处理器；按下发送时决定执行 `handleSend`、`handleSend2` 或在流式期间调用 `stopAllStreams`。
   - 调用关系：由 DOMContentLoaded 作用域在初始化时直接调用（见文件顶部）；内部回调触发 `handleSend` / `handleSend2` / `stopAllStreams`。

2. `setSendEnabled(enabled)` — 行 140-154
   - 功能：统一控制发送按钮与主输入框的可用性（根据登录、历史视图、流式状态等）。
   - 调用关系：被 `applyLoginLock()`、`exitStreamingMode()`、其他初始化流程调用以更新 UI 状态。

3. `enterStreamingMode()` — 行 155-163
   - 功能：进入流式状态（更新 `isStreaming`、按钮样式与提示），允许停止操作。
   - 调用关系：由 `handleSend()`、`handleSend2()` 等在开始请求前调用。

4. `exitStreamingMode()` — 行 164-176
   - 功能：退出流式状态，恢复按钮显示并调用 `setSendEnabled(true)`。
   - 调用关系：在所有模型流结束或被停止时调用（`fetchModelResponse` 和 `fetchModelDeepResponse` 在 pending 结束后会触发）；也由 `stopAllStreams()` 间接导致。

5. `scrollToBottomIfAllowed(force = false)` — 行 177-203
   - 功能：根据当前滚动锁（`suppressAutoScroll`）与距离底部阈值决定是否自动滚动到底部；`force=true` 时强制滚动。
   - 调用关系：广泛用于消息追加与流式渲染（如 `appendUserMessage`、`renderStreamingFrame`、`createModelRowUI` 的返回后、`fetchModelResponse` 渲染等）。

6. `showModal(title, textOrHtml, type = 'alert', defaultValue = '')` — 行 204-239
   - 功能：通用模态对话框/输入/确认封装，返回 Promise 以便调用者等待用户交互结果。
   - 调用关系：被大量控制流使用，如未登录提示、删除确认、重命名输入、单端登录提示（`forceLogout`）等。

7. `forceLogout(reason = '')` — 行 240-253
   - 功能：在检测到单端登录/未授权时强制登出并跳转到登录页面。
   - 调用关系：当覆盖的 `window.fetch` 拦截到 HTTP 401 或后端返回 Unauthorized 标记时会触发调用。

8. `window.fetch = async (...args) => { ... }`（fetch 覆盖）— 行 254-494
   - 功能：全局包装原生 `fetch`，拦截 401 与后端 JSON 中的 Unauthorized 字段以调用 `forceLogout`，保持原有返回值行为。
   - 调用关系：替代浏览器全局 `fetch`，因此项目中所有使用 `fetch` 的代码（例如 `/api/...` 调用）都会被此逻辑拦截并可能触发 `forceLogout`。

9. `ensurePublicSocket()` — 行 495-553
   - 功能：为公屏（按专业）初始化并管理一次性的 Socket.IO 连接，订阅 `public:new_message` 与 `public:vote` 事件，将更新写入 `publicMessagesCache` 并调用 `renderMiniPublicMessages`。
   - 调用关系：在 `init()` 中按登录状态调用；Socket 事件内部会调用 `upsertPublicMessage()` 与 `renderMiniPublicMessages()`。

10. `renderMiniPublicMessages(msgs)` — 行 554-619
    - 功能：渲染左侧 mini 公屏消息列表，包括点赞/点踩按钮、悬停暂停行为与滚动保持逻辑。
    - 调用关系：由 `ensurePublicSocket` 的事件回调、`loadMiniPublicMessages()`、以及消息更新后的本地操作调用。

11. `loadMiniPublicMessages()` — 行 620-660
    - 功能：从 `/api/public/messages` 拉取当前专业的公屏消息，填充 `publicMessagesCache` 并调用 `renderMiniPublicMessages` 与 `startMiniPublicAutoScroll`。
    - 调用关系：在 `init()` 中调用，也可在需要时重新加载。

12. `sendMiniPublicMessage()` — 行 661-688
    - 功能：发送 mini 公屏消息（POST `/api/public/messages`），由按钮或 Enter 触发，成功后清空输入；真正的更新由 Socket 事件驱动同步。
    - 调用关系：由 `miniPublicSendBtn.onclick` 与 `miniPublicInput` 的回车事件触发。

13. `handleMiniPublicVote(messageId, vote)` — 行 689-711
    - 功能：对公屏消息投票（POST `/api/public/vote`），后端成功后由 Socket 推送更新缓存。
    - 调用关系：由 `renderMiniPublicMessages` 内的点赞/点踩按钮调用。

14. `startMiniPublicAutoScroll()` — 行 712-741
    - 功能：为 mini 公屏开启一个定时器，实现平滑自动滚动（结合 `PUBLIC_SCROLL_STEP` 与 `PUBLIC_SCROLL_INTERVAL`）。
    - 调用关系：在 `loadMiniPublicMessages()` 成功后启动；触发时会修改 `miniPublicMessagesEl.scrollTop`。

15. `createNewSessionAndReset()` — 行 742-769
    - 功能：调用 `/api/session/new` 创建新 session，写入 `localStorage` 并调用 `resetUIForNewChat()` 重置界面到新工程状态。
    - 调用关系：由 `newChatBtn.onclick`（新建工程按钮）调用。

16. `appendUserMessage(text)` — 行 770-795
    - 功能：将用户输入以消息块形式追加到 `chatContainer`，并绑定点击以切换对应模型回答的折叠；随后调用 `scrollToBottomIfAllowed()`。
    - 调用关系：在 `handleSend()`、`handleSend2()`、`renderHistoryDetail()` 等处用于渲染用户提问。

17. `createModelRowUI(models, turnId)` — 行 796-1018
    - 功能：构建一轮对话的模型列 UI（`models-block`），包括 `models-console`（深度模式）及每个模型的列、拖拽排序、展开/收起、并返回 `uiMap` 以供后续填充。
    - 调用关系：由 `handleSend()`、`handleSend2()`、`renderHistoryDetail()` 创建界面并随后由 `fetchModelResponse` / `fetchModelDeepResponse` 填充内容。

18. `initSessionIfNeeded()` — 行 1019-1031
    - 功能：若全局 `sessionId` 为空则调用 `/api/session/new` 预创建 session 并写入 `localStorage`。
    - 调用关系：在发送、保存顺序（`saveTurnOrder`）等需要 session 的地方被调用。

19. `handleSend()` — 行 1032-1103
    - 功能：并行地对所选模型发起流式推理（`/api/chat/stream`），创建 UI（`createModelRowUI`）、调用 `fetchModelResponse` 并维护 `pendingModelResponses`、`activeStreams` 等流控状态。
    - 调用关系：由 `attachSendHandlers()` 或发送按钮触发；内部调用 `initSessionIfNeeded()`、`appendUserMessage()`、`createModelRowUI()`、并为每个模型调用 `fetchModelResponse()`。

20. `fetchModelResponse({...})` — 行 1104-1296
    - 功能：执行对 `/api/chat/stream` 的 streaming 请求，逐行解析 NDJSON（event: meta/delta/error/done），实时渲染到 `analysisEl`（思考）和 `opinionEl`（结论），并在结束时做最终 Markdown 渲染。
    - 调用关系：被 `handleSend()`（并行）调用；完成后会更新 `pendingModelResponses` 并在全部结束时触发 `exitStreamingMode()`。

21. `handleSend2()` — 行 1297-1416
    - 功能：串行地对所选模型发起深度推理（`/api/chat/deep`），支持模型间的串行依赖（`summeryList` / `lastAnalysis`），并在 `models-console` 中显示进度与 summary 列表。
    - 调用关系：由 `attachSendHandlers()`（深度思考选中时）触发；内部顺序调用 `fetchModelDeepResponse()`。

22. `fetchModelDeepResponse({...})` — 行 1417-1581
    - 功能：向 `/api/chat/deep` 发起请求（支持流式 NDJSON 或一次性 JSON），解析结构化 `result`（包含 `summary`、`analysis`、`opinion` 等），将结果渲染到 `models-console`、`analysisEl`、`opinionEl` 并返回 `resultObj` 以便串行依赖使用。
    - 调用关系：由 `handleSend2()` 串行调用；返回的 `summary` 会被累积到 `summeryList` 传递给后续模型。

23. `stopAllStreams()` — 行 1582-1704
    - 功能：中止所有正在进行的流（遍历 `activeStreams` 调用 `AbortController.abort()`），清空 `activeStreams`，重置 `pendingModelResponses` 并调用 `exitStreamingMode()`。
    - 调用关系：可由发送按钮在流式期间触发（`attachSendHandlers()`），也在其他异常或终止情形下使用。

24. `saveBtn` 点击处理器（提交入库） — 行 1705-1747
    - 功能：读取 `expertTextarea`、用户名与工程名，并 POST 到 `/api/save`；成功后刷新历史并提示完成。
    - 调用关系：由页面上的 `saveBtn` 点击触发；调用后会调用 `loadHistory()`。

25. `loadHistory()` — 行 1748-1789
    - 功能：从 `/api/history` 获取历史项目列表，创建/复用搜索框并调用 `filterAndRenderHistory()` 渲染列表。
    - 调用关系：在 `init()`、保存成功后、重命名/删除后被调用以刷新历史列表。

26. `filterAndRenderHistory(list, keyword)` — 行 1790-1923
    - 功能：对历史项目进行过滤、排序并渲染每个条目（包含打开详情、重命名、删除的事件绑定）。
    - 调用关系：由 `loadHistory()` 调用；其中的事件回调会触发 `openHistoryDetail`、`handleRename`、`handleDelete`。

27. `loadMiniTrendingQuestions()` — 行 1924-1981
    - 功能：从 `/api/trending/questions` 拉取语义热点问句并渲染为可点击的快捷填充项。
    - 调用关系：在 `init()` 时调用，渲染的条目会将提示填入主输入框。

28. `handleRename(id, newName)` — 行 1982-2000
    - 功能：POST `/api/history/rename` 重命名工程，成功后刷新历史。
    - 调用关系：由历史列表的“重命名”按钮调用。

29. `handleDelete(id)` — 行 2001-2022
    - 功能：POST `/api/history/delete` 删除工程，成功后刷新历史；若删除当前查看记录则调用 `resetUIForNewChat()`。
    - 调用关系：由历史列表的“删除”按钮调用。

30. `openHistoryDetail(recordId)` — 行 2023-2037
    - 功能：GET `/api/history/detail?id=...` 并将返回的 `record` 传给 `renderHistoryDetail()` 进行渲染。
    - 调用关系：由历史项点击触发。

31. `renderHistoryDetail(record)` — 行 2038-2165
    - 功能：渲染历史工程详情：禁用自动滚动、显示已摘选数据集、按轮次重建 `models` 行并把历史回答渲染到对应模型列（使用 `createModelRowUI` + `renderMarkdownTo`）。
    - 调用关系：由 `openHistoryDetail()` 调用；将使用 `createModelRowUI()` 并直接填充内容而非走流式请求。

32. `init()` — 行 2166-2263
    - 功能：页面启动时的主初始化流程：尝试创建 session、加载历史、检查管理员权限、加载语义热点、初始化公屏 Socket、加载 mini 公屏 消息、加载弹幕数据、绑定弹幕按钮与输入锁定等。
    - 调用关系：在文件底部自动调用 `init()`，是全局启动顺序的入口。

33. `loadBarrageData()` — 行 2264-2280
    - 功能：从 `/api/trending/school` 拉取热点数据并填充 `trendingCache` 以供弹幕使用。
    - 调用关系：被 `init()` 调用，结果影响 `startBarrage()` 的行为。

34. `toggleBarrage()` — 行 2281-2299
    - 功能：切换弹幕开启状态，依据 `barrageDataLoaded` 与 `trendingCache` 做提示，调用 `startBarrage()` / `stopBarrage()`。
    - 调用关系：绑定到 `barrageToggleBtn` 的点击事件。

35. `startBarrage()` — 行 2300-2318
    - 功能：开启定时器按 `BARRAGE_CONFIG.interval` 周期随机生成弹幕，通过 `addBarrageItem()` 插入 DOM。
    - 调用关系：由 `toggleBarrage()` 启动；依赖 `trendingCache` 数据。

36. `stopBarrage()` — 行 2319-2329
    - 功能：停止弹幕定时器并清空容器内现有弹幕元素。
    - 调用关系：由 `toggleBarrage()`、`startBarrage()` 中断条件或关闭时调用。

37. `addBarrageItem(item)` — 行 2330-2365
    - 功能：在弹幕容器中创建单条弹幕节点，绑定点击查看详情（调用 `showModal`），并在超时后移除节点。
    - 调用关系：由 `startBarrage()` 周期性调用，也可在其他需要时单独调用。

-- 结束 --

后续选项：可生成机器可读的 JSON 映射或为每个函数自动添加链接到源文件行号（需要额外脚本）。
