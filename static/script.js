document.addEventListener('DOMContentLoaded', function () {
  const inputAreaWrapper = document.querySelector('.input-area-wrapper');
  const chatContainer = document.getElementById('chat-container');
  const userPromptInput = document.getElementById('user-prompt');
  const sendBtn = document.getElementById('send-btn');
  const deepBtn = document.getElementById('deep-think-toggle-btn');
  // 发送/回车处理的统一入口（通过 attachSendHandlers 注册）
  function attachSendHandlers() {
    if (!sendBtn || !userPromptInput) return;
    sendBtn.addEventListener('click', () => {
      if (isHistoryView) return;
      if (isPublicChatView) return;
      if (isStreaming) {
        stopAllStreams();
      } else {
        if (deepBtn && deepBtn.classList.contains('selected')) {
          handleSend2();
        } else {
          handleSend();
        }
      }
    });

    userPromptInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        if (e.isComposing) return;
        e.preventDefault();
        if (isStreaming) {
          stopAllStreams();
        } else {
          if (deepBtn && deepBtn.classList.contains('selected')) {
            handleSend2();
          } else {
            handleSend();
          }
        }
      }
    });
  }

  // 立即附加处理器
  attachSendHandlers();

  // 深度思考切换按钮（切换 class 'selected'）
  if (deepBtn) {
    deepBtn.addEventListener('click', function () {
      deepBtn.classList.toggle('selected');
    });
  }
  const expertTextarea = document.getElementById('expert-data');
  const saveBtn = document.getElementById('save-btn');
  const historyList = document.getElementById('history-list');
  const selectionPopover = document.getElementById('selection-popover');
  const menuToggle = document.getElementById('menu-toggle');
  const sidebarLeft = document.getElementById('sidebar-left');
  const sidebarRight = document.getElementById('sidebar-right');
  const newChatBtn = document.getElementById('new-chat-btn');
  const projectPanelBtn = document.getElementById('project-panel-btn');
  const projectDrawer = document.getElementById('project-drawer');
  const projectDrawerClose = document.getElementById('project-drawer-close');
  const rightbarToggle = document.getElementById('rightbar-toggle');
  const userMenuBtn = document.getElementById('user-menu-btn');
  const userMenuPanel = document.getElementById('user-menu-panel');
  const userMenuClose = document.getElementById('user-menu-close');
  const userAdminLink = document.getElementById('user-admin-link');

  const miniPublicMessagesEl = document.getElementById('mini-public-messages');
  const miniPublicInput = document.getElementById('mini-public-input');
  const miniPublicSendBtn = document.getElementById('mini-public-send-btn');
  const miniTrendingPanel = document.getElementById('mini-trending-panel');

  const inputProject = document.getElementById('input-project');
  const inputUsername = document.getElementById('input-username');

  const panelMatrix = document.getElementById('panel-matrix');
  const panelExpert = document.getElementById('panel-expert');
  const hotBoard = document.getElementById('hot-board');

  const modalOverlay = document.getElementById('custom-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalBody = document.getElementById('modal-body');
  const modalInput = document.getElementById('modal-input');
  const modalConfirm = document.getElementById('modal-confirm');
  const modalCancel = document.getElementById('modal-cancel');

  // 状态
  const SESSION_STORAGE_KEY = 'expert_ai_studio_session_id';
  const USER_STORAGE_KEY = 'expert_ai_studio_user_id';
  const currentUserId = document.body?.dataset?.currentUser || '';

  let sessionId = localStorage.getItem(SESSION_STORAGE_KEY) || null;
  const storedUserId = localStorage.getItem(USER_STORAGE_KEY) || '';
  if (storedUserId !== currentUserId) {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    sessionId = null;
    localStorage.setItem(USER_STORAGE_KEY, currentUserId);
  }
  let suppressAutoScroll = false;     // 控制是否允许自动滚动到底部
  let isHistoryView = false;
  let isPublicChatView = false;
  let hasUnsavedChanges = false;
  let currentRecordId = null;         // 当前工程（自动落库）id
  let pendingModelResponses = 0;
  let publicMessagesCache = [];
  let publicSocket = null;
  let miniPublicScrollPaused = false;
  let miniPublicAutoScrollTimer = null;

// 聊天记录平滑滚动
  const PUBLIC_SCROLL_STEP = 1;  // 减小步长，使滚动更平滑
  const PUBLIC_SCROLL_INTERVAL = 50;  // 缩短间隔，增加帧率


  let trendingCache = [];              // 热点榜单缓存
  let barrageEnabled = false;          // 弹幕开启状态
  let barrageInterval = null;          // 弹幕定时器
  let barrageDataLoaded = false;       // 弹幕数据是否已加载
  const barrageToggleBtn = document.getElementById('barrage-toggle-btn');
  
  // 弹幕时间配置（单位：毫秒）
  const BARRAGE_CONFIG = {
    interval: 2000,    // 弹幕出现间隔（毫秒）
    duration: 9000     // 单个弹幕存活时间（毫秒）
  };

  // 让“摘选入库”浮层尽量不被插件遮挡
  if (selectionPopover) {
    selectionPopover.style.position = 'fixed';
    selectionPopover.style.zIndex = '2147483647';
    // 如果你 CSS 里没设置，确保可点击
    selectionPopover.style.pointerEvents = 'auto';
  }

  /**
   * 判断节点是否属于可摘选区域（模型输出或 console 内容）
   * 统一复用以避免重复判断逻辑散落在代码中。
   */
  function isInSelectableArea(node) {
    if (!node) return false;
    // 如果传入的是文本节点，取其父元素
    const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : (node.closest ? node : node);
    try {
      return !!(el && (el.closest('.model-content') || el.closest('.console-content')));
    } catch (_) {
      return false;
    }
  }

  // `safeUUID` moved to `static/utils.js`

  // 流式与发送控制
  let isStreaming = false;
  const activeStreams = new Map(); // key -> AbortController

  function setSendEnabled(enabled) {
    const loggedIn = isLoggedIn();
    const disableSend = !loggedIn || isHistoryView || (!enabled && !isStreaming);
    // 流式期间禁用输入框，防止未完成时继续输入
    const disableInput = !loggedIn || isHistoryView || isStreaming || (!enabled && !isStreaming);

    if (sendBtn) {
      sendBtn.disabled = disableSend;
      sendBtn.title = loggedIn ? (isStreaming ? '停止' : '发送') : '请先登录';
    }
    if (userPromptInput) {
      userPromptInput.disabled = disableInput;
    }
  }

  function enterStreamingMode() {
    isStreaming = true;
    if (sendBtn) {
      sendBtn.innerHTML = '<span class="material-symbols-outlined">stop</span>';
      sendBtn.title = '停止';
      sendBtn.disabled = false; // 保证可停止
    }
  }

  function exitStreamingMode() {
    isStreaming = false;
    if (sendBtn) {
      sendBtn.innerHTML = '<span class="material-symbols-outlined">send</span>';
      sendBtn.title = isLoggedIn() ? '发送' : '请先登录';
    }
    setSendEnabled(true);
  }

  // `escapeHtml` moved to `static/utils.js`

  // `formatLocalTime` moved to `static/utils.js`

  function scrollToBottomIfAllowed(force = false) {
    if (force) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
      return;
    }
    if (suppressAutoScroll) return;

    // 距离底部 <120 px 才自动滚
    const bottomGap = chatContainer.scrollHeight
                    - chatContainer.scrollTop
                    - chatContainer.clientHeight;
    if (bottomGap < 120) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }


  function scrollToDatasetTop() {
    // 历史详情：定位到“已摘选数据集”卡片顶端
    const card = document.getElementById('dataset-card');
    if (card && typeof card.scrollIntoView === 'function') {
      card.scrollIntoView({ block: 'start', behavior: 'auto' });
    } else {
      chatContainer.scrollTop = 0;
    }
  }

  function showModal(title, textOrHtml, type = 'alert', defaultValue = '') {
    return new Promise((resolve) => {
      modalTitle.innerText = title;
      modalBody.innerHTML = textOrHtml;
      modalBody.style.display = type === 'input' ? 'none' : 'block';
      modalCancel.style.display = (type === 'confirm' || type === 'input') ? 'block' : 'none';

      if (type === 'input') {
        modalInput.style.display = 'block';
        modalInput.value = defaultValue;
        setTimeout(() => modalInput.focus(), 100);
      } else {
        modalInput.style.display = 'none';
      }

      modalOverlay.style.display = 'flex';
      requestAnimationFrame(() => modalOverlay.classList.add('show'));

      const cleanup = () => {
        modalOverlay.classList.remove('show');
        setTimeout(() => { modalOverlay.style.display = 'none'; }, 300);
        modalConfirm.onclick = null;
        modalCancel.onclick = null;
      };

      modalConfirm.onclick = () => {
        const result = type === 'input' ? modalInput.value : true;
        cleanup();
        resolve(result);
      };
      modalCancel.onclick = () => { cleanup(); resolve(false); };
    });
  }

  // 单端登录：拦截 401/Unauthorized，提示并强制退出
  let forceLogoutTriggered = false;
  async function forceLogout(reason = '') {
    if (forceLogoutTriggered) return;
    forceLogoutTriggered = true;
    try {
      await showModal('提示', '账号在别处登录，请重新登录');
    } catch (_) { /* no-op */ }
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch (_) { /* no-op */ }
    // 回到登录页，避免继续操作
    window.location.href = '/api/auth/login';
  }

  const _nativeFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const res = await _nativeFetch(...args);
    // HTTP 401 直接触发退出
    if (res.status === 401) {
      forceLogout('http_401');
      return res;
    }
    // JSON 载荷中显式 Unauthorized 也触发退出
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      try {
        const cloned = res.clone();
        const data = await cloned.json();
        const msg = (data && (data.content || data.message || '') || '').toLowerCase();
        if (data && data.status === 'error' && msg.includes('unauthorized')) {
          forceLogout('json_unauthorized');
        }
      } catch (_) { /* ignore parse errors */ }
    }
    return res;
  };

  function getIconPath(key) {
    const map = {
      'gemini': 'gemini.svg', 'gpt': 'gpt.svg', 'deepseek': 'deepseek.svg',
      'kimi': 'kimi.svg', 'qwen': 'Qwen.svg', 'zai': 'zai.svg'
    };
    return `/static/assets/${map[key] || 'gpt.svg'}`;
  }

  // 菜单按钮双功能：已登录时切换侧边栏，未登录时创建新工程
  function isLoggedIn() {
    const uid = (document.body?.dataset?.currentUser || '').trim();
    return !!uid;
  }

  // 未登录时锁定输入与发送
  function applyLoginLock() {
    const loggedIn = isLoggedIn();
    if (userPromptInput) {
      userPromptInput.placeholder = loggedIn ? '在此输入专业问题...' : '请先登录后再开始使用';
    }
    // 根据登录/历史/流式状态统一控制输入与发送可用性
    setSendEnabled(loggedIn && !isHistoryView);
  }

  // 初次进入时立即根据登录状态锁定
  applyLoginLock();

  if (rightbarToggle && sidebarRight) {
    rightbarToggle.onclick = () => {
      sidebarRight.classList.toggle('collapsed');
    };
  }

  function setUserMenuVisible(show) {
    if (!userMenuPanel) return;
    userMenuPanel.classList.toggle('hidden-panel', !show);
  }

  function toggleUserMenu() {
    if (!userMenuPanel) return;
    const isHidden = userMenuPanel.classList.contains('hidden-panel');
    setUserMenuVisible(isHidden);
  }

  function closeUserMenu() {
    setUserMenuVisible(false);
  }

  if (userMenuBtn && userMenuPanel) {
    userMenuBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleUserMenu();
    });
  }

  if (userMenuClose) {
    userMenuClose.addEventListener('click', (e) => {
      e.stopPropagation();
      closeUserMenu();
    });
  }

  document.addEventListener('click', (e) => {
    if (!userMenuPanel || userMenuPanel.classList.contains('hidden-panel')) return;
    if (userMenuPanel.contains(e.target)) return;
    if (userMenuBtn && userMenuBtn.contains(e.target)) return;
    closeUserMenu();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeUserMenu();
    }
  });

  async function applyAdminVisibility() {
    if (!userAdminLink || !isLoggedIn()) return;
    try {
      const res = await fetch('/admin/api/status');
      if (!res.ok) {
        userAdminLink.classList.add('hidden-panel');
        return;
      }
      const data = await res.json();
      const isAdmin = data && data.status === 'success' && data.is_admin;
      userAdminLink.classList.toggle('hidden-panel', !isAdmin);
    } catch (err) {
      console.warn('Admin status check failed', err);
      userAdminLink.classList.add('hidden-panel');
    }
  }

  function toggleProjectDrawer(forceOpen) {
    if (!projectDrawer || !sidebarLeft) return;
    const shouldOpen = forceOpen !== undefined ? forceOpen : !projectDrawer.classList.contains('open');
    
    // 动态计算左侧边栏宽度，更新项目抽屉位置
    if (shouldOpen) {
      const sidebarRect = sidebarLeft.getBoundingClientRect();
      const sidebarWidth = sidebarLeft.classList.contains('hidden') ? 0 : sidebarRect.width;
      projectDrawer.style.left = `${sidebarWidth}px`;
      projectDrawer.classList.add('open');
    } else {
      projectDrawer.classList.remove('open');
    }
  }
  
  // 监听窗口大小变化和左侧边栏显示状态变化，动态更新项目抽屉位置
  function updateProjectDrawerPosition() {
    if (!projectDrawer || !sidebarLeft) return;
    if (projectDrawer.classList.contains('open')) {
      const sidebarRect = sidebarLeft.getBoundingClientRect();
      const sidebarWidth = sidebarLeft.classList.contains('hidden') ? 0 : sidebarRect.width;
      projectDrawer.style.left = `${sidebarWidth}px`;
    }
  }
  
  // 监听窗口大小变化
  window.addEventListener('resize', updateProjectDrawerPosition);
  
  // 监听左侧边栏显示状态变化
  if (sidebarLeft) {
    const observer = new MutationObserver(updateProjectDrawerPosition);
    observer.observe(sidebarLeft, { 
      attributes: true, 
      attributeFilter: ['class'] 
    });
  }

  if (projectPanelBtn) {
    projectPanelBtn.onclick = () => {
      if (!isLoggedIn()) {
        showModal('提示', '请先登录后再查看项目');
        return;
      }
      toggleProjectDrawer();
    };
  }
  if (projectDrawerClose) {
    projectDrawerClose.onclick = () => toggleProjectDrawer(false);
  }

  menuToggle.onclick = () => {
    if (isLoggedIn() && sidebarLeft) {
      sidebarLeft.classList.toggle('hidden');
    } else {
      // 未登录时，提示先登录
      showModal('提示', '请先登录后再开始使用');
    }
  };

  newChatBtn.onclick = async () => {
    if (hasUnsavedChanges) {
      const ok = await showModal("确认离开", "当前摘选内容未提交。历史对话已自动保存，但摘选框会清空。是否继续？", "confirm");
      if (!ok) return;
    }
    await createNewSessionAndReset();
  };

  function resetUIForNewChat() {
    if (inputAreaWrapper) inputAreaWrapper.style.display = '';
    hasUnsavedChanges = false;
    isHistoryView = false;
    isPublicChatView = false;
    currentRecordId = null;
    publicMessagesCache = [];
    miniPublicScrollPaused = false;
    if (miniPublicAutoScrollTimer) {
      clearInterval(miniPublicAutoScrollTimer);
      miniPublicAutoScrollTimer = null;
    }
    toggleProjectDrawer(false);

    // 关键：离开历史视图时恢复自动滚动
    suppressAutoScroll = false;

    panelMatrix.classList.remove('hidden-panel');
    panelExpert.classList.add('hidden-panel');
    // 新建工程页面隐藏热点榜单
    if (hotBoard) hotBoard.classList.add('hidden-panel');
    inputProject.disabled = false;

    chatContainer.innerHTML = `
      <div style="text-align: center; margin-top: 100px; opacity: 0.7;" id="welcome-msg">
        <h1>你好，我们从哪里开始？</h1><br>
        <p>请配置右侧模型，开始构建数据集</p>
      </div>
      <div id="barrage-container" class="barrage-container"></div>`;

    // 重新获取弹幕容器引用
    const newBarrageContainer = document.getElementById('barrage-container');
    if (newBarrageContainer) {
      // 如果之前有弹幕数据和启用状态，恢复显示
      if (barrageEnabled && trendingCache && trendingCache.length > 0) {
        // 清除之前的定时器并重新启动
        stopBarrage();
        startBarrage();
      }
    }

    expertTextarea.value = '';
    inputProject.value = '';
    inputUsername.value = '';
    userPromptInput.value = '';
    userPromptInput.style.height = '24px';
    
    // 启用发送功能
    pendingModelResponses = 0;
    setSendEnabled(true);
    // 未登录时保持锁定
    applyLoginLock();
    userPromptInput.focus();

    // 新工程默认顶部欢迎页，不强制滚动到底部
    chatContainer.scrollTop = 0;
  }

  // ============ 公屏聊天（Redis + 专业内聚） ============
  // 建立公屏实时连接（只建立一次，按专业房间）
  function ensurePublicSocket() {
    if (publicSocket || !isLoggedIn()) return publicSocket;
    try {
      publicSocket = io({
        withCredentials: true,
        auth: { user_id: currentUserId || undefined }
      });

      publicSocket.on('connect', () => {
        console.log('Public chat socket connected');
      });

      publicSocket.on('connect_error', (err) => {
        console.warn('Public chat socket connect error', err?.message || err);
      });

      publicSocket.on('disconnect', () => {
        console.log('Public chat socket disconnected');
      });

      publicSocket.on('public:joined', () => {
        // 连接成功并加入对应专业的房间
      });

      publicSocket.on('public:new_message', (msg) => {
        upsertPublicMessage(msg);
        renderMiniPublicMessages(publicMessagesCache);
      });

      publicSocket.on('public:vote', (msg) => {
        upsertPublicMessage(msg);
        renderMiniPublicMessages(publicMessagesCache);
      });

    } catch (e) {
      console.warn('Init public socket failed', e);
    }
    return publicSocket;
  }

  function sortMessagesAsc(msgs) {
    return (msgs || []).slice().sort((a, b) => {
      const ta = a.created_at_iso || a.created_at || '';
      const tb = b.created_at_iso || b.created_at || '';
      return ta < tb ? -1 : ta > tb ? 1 : 0;
    });
  }

  function upsertPublicMessage(msg) {
    if (!msg || !msg.message_id) return;
    const idx = publicMessagesCache.findIndex(m => m.message_id === msg.message_id);
    if (idx >= 0) {
      publicMessagesCache[idx] = { ...publicMessagesCache[idx], ...msg };
    } else {
      publicMessagesCache.push(msg);
    }
    publicMessagesCache = sortMessagesAsc(publicMessagesCache);
  }

  function renderMiniPublicMessages(msgs) {
    if (!miniPublicMessagesEl) return;
    
    // 记录滚动位置
    const wasAtBottom = miniPublicMessagesEl.scrollHeight - miniPublicMessagesEl.scrollTop - miniPublicMessagesEl.clientHeight < 40;
    
    miniPublicMessagesEl.innerHTML = '';
    if (!msgs || msgs.length === 0) {
      miniPublicMessagesEl.innerHTML = '<div class="mini-public-empty">暂无消息</div>';
      return;
    }

    msgs.forEach(msg => {
      const item = document.createElement('div');
      item.className = 'mini-public-msg';
      item.dataset.messageId = msg.message_id;
      
      // 添加悬停暂停功能
      item.addEventListener('mouseenter', () => { 
        miniPublicScrollPaused = true;
        item.classList.add('hover');
      });
      item.addEventListener('mouseleave', () => { 
        miniPublicScrollPaused = false;
        item.classList.remove('hover');
      });

      const body = document.createElement('div');
      body.className = 'mini-public-body one-line';
      body.textContent = msg.content || '';
      body.title = msg.content || '';  // 悬停显示完整内容

      const actions = document.createElement('div');
      actions.className = 'mini-public-actions inline';

      const likeBtn = document.createElement('button');
      likeBtn.className = `mini-thumb ${msg.my_vote === 'like' ? 'active' : ''}`;
      likeBtn.innerHTML = `<span class="material-symbols-outlined">thumb_up</span><span>${msg.like_count || 0}</span>`;
      likeBtn.onclick = (e) => {
        e.stopPropagation();
        handleMiniPublicVote(msg.message_id, 'like');
      };

      const dislikeBtn = document.createElement('button');
      dislikeBtn.className = `mini-thumb ${msg.my_vote === 'dislike' ? 'active' : ''}`;
      dislikeBtn.innerHTML = `<span class="material-symbols-outlined">thumb_down</span><span>${msg.dislike_count || 0}</span>`;
      dislikeBtn.onclick = (e) => {
        e.stopPropagation();
        handleMiniPublicVote(msg.message_id, 'dislike');
      };

      actions.appendChild(likeBtn);
      actions.appendChild(dislikeBtn);

      item.appendChild(body);
      item.appendChild(actions);

      miniPublicMessagesEl.appendChild(item);
    });
    
    // 如果之前在底部，自动滚动到底部
    if (wasAtBottom && !miniPublicScrollPaused) {
      miniPublicMessagesEl.scrollTop = miniPublicMessagesEl.scrollHeight;
    }
  }

  async function loadMiniPublicMessages() {
    if (!miniPublicMessagesEl) return;
    if (!isLoggedIn()) {
      miniPublicMessagesEl.innerHTML = '<div class="mini-public-empty">登录后可查看公屏消息</div>';
      return;
    }
    
    // 更新专业标签
    try {
      const res = await fetch('/api/auth/current-user');
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success' && data.profession) {
          const profEl = document.getElementById('mini-public-profession');
          if (profEl) {
            profEl.textContent = `(${data.profession})`;
          }
        }
      }
    } catch (err) {
      console.error('获取用户信息失败:', err);
    }
    
    try {
      const tz = (Intl.DateTimeFormat && Intl.DateTimeFormat().resolvedOptions && Intl.DateTimeFormat().resolvedOptions().timeZone) || '';
      const url = tz ? `/api/public/messages?limit=100&tz=${encodeURIComponent(tz)}` : '/api/public/messages?limit=100';
      const res = await fetch(url);
      const j = await res.json();
      if (j.status === 'success') {
        publicMessagesCache = sortMessagesAsc(Array.isArray(j.messages) ? j.messages : []);
        renderMiniPublicMessages(publicMessagesCache);
        startMiniPublicAutoScroll();
      } else {
        miniPublicMessagesEl.innerHTML = `<div class="mini-public-empty">${escapeHtml(j.content || '加载失败')}</div>`;
      }
    } catch (e) {
      console.error(e);
      miniPublicMessagesEl.innerHTML = '<div class="mini-public-empty">网络异常</div>';
    }
  }

  async function sendMiniPublicMessage() {
    if (!miniPublicInput || !miniPublicSendBtn) return;
    const text = (miniPublicInput.value || '').trim();
    if (!text) return;
    if (!isLoggedIn()) { showModal('提示', '请先登录后再发言'); return; }

    miniPublicSendBtn.disabled = true;
    try {
      const res = await fetch('/api/public/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text })
      });
      const j = await res.json();
      if (j.status === 'success') {
        miniPublicInput.value = '';
        // Socket事件会自动更新，不需要手动调用
      } else {
        showModal('错误', j.content || '发送失败');
      }
    } catch (e) {
      console.error(e);
      showModal('错误', '网络异常，发送失败');
    } finally {
      miniPublicSendBtn.disabled = false;
    }
  }
  
  async function handleMiniPublicVote(messageId, vote) {
    if (!isLoggedIn()) {
      showModal('提示', '请先登录后再投票');
      return;
    }
    try {
      const res = await fetch('/api/public/vote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, vote })
      });
      const j = await res.json();
      if (j.status === 'success') {
        // Socket事件会自动更新，不需要手动调用
      } else {
        showModal('错误', j.content || '投票失败');
      }
    } catch (e) {
      console.error(e);
      showModal('错误', '网络异常，投票失败');
    }
  }
  
  function startMiniPublicAutoScroll() {
    if (!miniPublicMessagesEl) return;
    if (miniPublicAutoScrollTimer) clearInterval(miniPublicAutoScrollTimer);
    
    miniPublicAutoScrollTimer = setInterval(() => {
      if (miniPublicScrollPaused) return;
      
      const atBottom = miniPublicMessagesEl.scrollTop >= miniPublicMessagesEl.scrollHeight - miniPublicMessagesEl.clientHeight - 2;
      if (!atBottom) {
        miniPublicMessagesEl.scrollTop = Math.min(
          miniPublicMessagesEl.scrollTop + PUBLIC_SCROLL_STEP, 
          miniPublicMessagesEl.scrollHeight
        );
      }
    }, PUBLIC_SCROLL_INTERVAL);
  }

  if (miniPublicSendBtn && miniPublicInput) {
    miniPublicSendBtn.onclick = () => sendMiniPublicMessage();
    miniPublicInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMiniPublicMessage();
      }
    });
  }

  // ============ 公屏聊天功能已移除，仅保留左侧边栏Mini公共聊天 ============
  // ========== 公屏聊天结束 ==========

  async function createNewSessionAndReset() {
    try {
      // 离开当前会话前自动保存（等同于点击“提交入库”）
      try {
        await autoSaveIfNeeded();
      } catch (e) {
        console.warn('autoSave failed before creating new session', e);
      }
      const r = await fetch('/api/session/new', { method: 'POST' });
      const j = await r.json();
      if (j.status !== 'success') throw new Error(j.content || 'create session failed');
      sessionId = j.session_id;
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
      localStorage.setItem(USER_STORAGE_KEY, currentUserId);
      resetUIForNewChat();
    } catch (e) {
      console.error(e);
      showModal('错误', '无法创建新 Session，请检查后端 /api/session/new。');
    }
  }

  // 输入框自适应高度（去掉前端敏感词预检）
  userPromptInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    if (this.value === '') this.style.height = '24px';

    // 移除可能残留的警告提示
    const warningEl = document.getElementById('sensitive-warning');
    if (warningEl) warningEl.remove();
  });

  // Enter 键处理由 attachSendHandlers() 统一注册

  function appendUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'message-user';
    div.innerText = text;
    
    // 添加点击事件：收起/展开下方的模型回答
    div.addEventListener('click', () => {
      // 找到下一个兄弟元素（models-block）
      let nextElement = div.nextElementSibling;
      while (nextElement && !nextElement.classList.contains('models-block')) {
        nextElement = nextElement.nextElementSibling;
      }
      
      if (nextElement && nextElement.classList.contains('models-block')) {
        nextElement.classList.toggle('collapsed');
        div.classList.toggle('collapsed');
      }
    });
    
    chatContainer.appendChild(div);

    // 正常对话：滚到底部；历史渲染：不滚（由 suppressAutoScroll 控制）
    scrollToBottomIfAllowed();
  }

  // 创建models-row这个div，并用外层容器包含 models-console + models-row
  function createModelRowUI(models, turnId, showConsoleFlag) {
    const containerDiv = document.createElement('div');
    containerDiv.className = 'models-block';
    containerDiv.dataset.turnId = turnId;

    // 显示 models-console 的决策顺序：
    // 1) 如果调用方传入 showConsoleFlag（true/false）则以此为准；
    // 2) 否则回退到深度思考按钮选中时显示（默认行为，适用于实时对话）。
    const showConsole = (typeof showConsoleFlag === 'boolean') ? showConsoleFlag : (deepBtn && deepBtn.classList && deepBtn.classList.contains('selected'));
    let consoleDiv = null;
    if (showConsole) {
      consoleDiv = document.createElement('div');
      consoleDiv.className = 'models-console';
      consoleDiv.dataset.turnId = turnId;

      // 内部框架：负责背景、圆角与内边距
      const consoleFrame = document.createElement('div');
      consoleFrame.className = 'console-frame';

      const consoleHead = document.createElement('div');
      consoleHead.className = 'console-head';
      consoleHead.textContent = '模型终端';

      const consoleContent = document.createElement('div');
      consoleContent.className = 'console-content';

      // console 内部分为：summary 列表（每次调用追加）和 log/placeholder 区域
      const consoleSummary = document.createElement('div');
      consoleSummary.className = 'console-summary';
        
      const consoleLog = document.createElement('div');
      consoleLog.className = 'console-log-area';
      consoleLog.textContent = '';

      consoleContent.appendChild(consoleSummary);
      consoleContent.appendChild(consoleLog);

      consoleFrame.appendChild(consoleHead);
      consoleFrame.appendChild(consoleContent);
      consoleDiv.appendChild(consoleFrame);
    }

    // 原有的 models-row
    const rowDiv = document.createElement('div');
    rowDiv.className = 'models-row';
    rowDiv.dataset.turnId = turnId;

    const uiMap = {};
    let draggedCol = null;

    models.forEach(config => {
      const colDiv = document.createElement('div');
      colDiv.className = 'model-col';

      const iconPath = getIconPath(config.key);
      const header = document.createElement('div');
      header.className = 'model-header';
      header.innerHTML = `
        <span class="model-order-badge">1</span>
        <div class="model-name">
          <img src="${iconPath}" class="model-logo" alt="${config.key}" draggable="false">
          ${config.key.toUpperCase()}
          <small style="opacity:0.6; font-weight:normal; margin-left:5px">(${config.displayName || config.modelName || ''})</small>
        </div>
        <button class="expand-btn" title="展开/收起"><span class="material-symbols-outlined">pan_zoom</span></button>
      `;

      const contentDiv = document.createElement('div');
      contentDiv.className = 'model-content';
      contentDiv.dataset.key = config.key;
      contentDiv.dataset.turnId = turnId;
      contentDiv.id = `model-content-${turnId}-${config.key}`;

      // 将模型输出拆成两个垂直区域：analysis 与 opinion
      const analysisEl = document.createElement('div');
      analysisEl.className = 'model-analysis';
      analysisEl.id = `model-analysis-${turnId}-${config.key}`;
      analysisEl.innerHTML = `<div class="loading-dots"><div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div></div>`;

      const opinionEl = document.createElement('div');
      opinionEl.className = 'model-opinion';
      opinionEl.id = `model-opinion-${turnId}-${config.key}`;
      opinionEl.innerHTML = '';

      if (showConsole){
         contentDiv.appendChild(analysisEl); 
      }

      contentDiv.appendChild(opinionEl);

      const expandBtn = header.querySelector('.expand-btn');
      expandBtn.onclick = (e) => {
        e.stopPropagation();
        colDiv.classList.toggle('expanded');
        if (colDiv.classList.contains('expanded')) {
          Array.from(rowDiv.children).forEach(sib => { if (sib !== colDiv) sib.classList.add('compressed'); });
        } else {
          if (!Array.from(rowDiv.children).some(c => c.classList.contains('expanded'))) {
            Array.from(rowDiv.children).forEach(sib => sib.classList.remove('compressed'));
          }
        }
      };

      // 仅允许在 model-name 处拖拽
      const dragHandle = header.querySelector('.model-name');
      if (dragHandle) {
        dragHandle.draggable = true;
        dragHandle.addEventListener('dragstart', (e) => {
          draggedCol = colDiv;
          colDiv.style.opacity = '0.5';
          e.dataTransfer.effectAllowed = 'move';
          e.dataTransfer.setData('text/plain', ''); // 一些浏览器需要 setData 才能拖拽
        });

        dragHandle.addEventListener('dragend', () => {
          draggedCol = null;
          colDiv.style.opacity = '1';
        });
      }

      colDiv.addEventListener('dragover', (e) => {
        if (!draggedCol || draggedCol === colDiv) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        colDiv.style.borderLeft = '3px solid var(--primary-blue)';
      });

      colDiv.addEventListener('dragleave', (e) => {
        colDiv.style.borderLeft = '';
      });

      colDiv.addEventListener('drop', (e) => {
        e.preventDefault();
        colDiv.style.borderLeft = '';
        if (!draggedCol || draggedCol === colDiv) return;
        // 交换两列的位置
        const allCols = Array.from(rowDiv.children);
        const draggedIndex = allCols.indexOf(draggedCol);
        const targetIndex = allCols.indexOf(colDiv);
        if (draggedIndex < targetIndex) {
          colDiv.parentNode.insertBefore(draggedCol, colDiv.nextSibling);
        } else {
          colDiv.parentNode.insertBefore(draggedCol, colDiv);
        }

        // 更新序号显示并持久化顺序
        updateModelOrderNumbers(rowDiv);
        const orderKeys = Array.from(rowDiv.children)
          .map(c => c.querySelector('.model-content')?.dataset.key)
          .filter(Boolean);
        saveTurnOrder(turnId, orderKeys);
      });

      colDiv.appendChild(header);
      colDiv.appendChild(contentDiv);
      rowDiv.appendChild(colDiv);

      uiMap[config.key] = contentDiv;
    });

    // 将 console（若创建）放到 container 顶部，再放 models-row
    if (consoleDiv) containerDiv.appendChild(consoleDiv);
    containerDiv.appendChild(rowDiv);

    chatContainer.appendChild(containerDiv);

    // 初始序号
    updateModelOrderNumbers(rowDiv);

    // 关键：历史渲染时不能在这里强制滚到底部
    scrollToBottomIfAllowed();

    return uiMap;
  }

  // 开发用文件流功能已移除：startDevStreamForTurn 不再存在

  function updateModelOrderNumbers(rowDiv) {
    Array.from(rowDiv.children).forEach((col, idx) => {
      const badge = col.querySelector('.model-order-badge');
      if (badge) badge.innerText = String(idx + 1);
    });
  }

  async function saveTurnOrder(turnId, orderKeys) {
    if (!isLoggedIn()) return; // 未登录不持久化
    if (!Array.isArray(orderKeys) || !orderKeys.length) return;
    try {
      const payload = {
        turn_id: turnId,
        model_order: orderKeys,
      };
      // 历史视图：只发 record_id，不发 session_id
      if (isHistoryView) {
        if (!currentRecordId) return;
        payload.record_id = currentRecordId;
      } else {
        // 正常对话：发 session_id（确保存在），可选发 record_id
        await initSessionIfNeeded();
        if (sessionId) payload.session_id = sessionId;
        if (currentRecordId) payload.record_id = currentRecordId;
      }
      if (!payload.session_id && !payload.record_id) return;
      
      await fetch('/api/turn/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch (e) {
      console.warn('保存列顺序失败', e);
    }
  }

  function getSelectedModels() {
    const selected = [];
    document.querySelectorAll('.model-checkbox input:checked').forEach(checkbox => {
      const key = checkbox.value;
      const select = document.querySelector(`.model-select[data-for="${key}"]`);
      const modelName = select.value;
      const modelDisplayName = select.options[select.selectedIndex].text;
      const provider = (key === 'gemini' || key === 'gpt') ? key : 'silicon';
      selected.push({ key, provider, modelName, displayName: modelDisplayName });
    });
    return selected;
  }

  async function initSessionIfNeeded() {
    if (sessionId) return;
    try {
      const r = await fetch('/api/session/new', { method: 'POST' });
      const j = await r.json();
      if (j.status === 'success') {
        sessionId = j.session_id;
        localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
        localStorage.setItem(USER_STORAGE_KEY, currentUserId);
      }
    } catch (_) { }
  }

  async function handleSend() {
    if (isPublicChatView) {
      showModal('提示', '当前为公屏聊天模式，请使用下方公屏输入框发送');
      return;
    }
    if (isHistoryView) {
      showModal('提示', '当前处于历史工程查看模式，无法继续对话。请点击“新工程”返回。');
      return;
    }

    // 未登录直接提示并返回
    if (!isLoggedIn()) {
      showModal('提示', '请先登录后再开始使用');
      return;
    }

    const prompt = userPromptInput.value.trim();
    if (!prompt) return;

    const selectedModels = getSelectedModels();
    if (selectedModels.length === 0) {
      showModal("提示", "请至少选择一个模型！");
      return;
    }

    await initSessionIfNeeded();
    if (!sessionId) {
      showModal("错误", "无法初始化 Session。");
      return;
    }

    // 正常对话：允许自动滚动到底部
    suppressAutoScroll = false;

    // 进入流式状态（按钮切换为停止）
    enterStreamingMode();
    setSendEnabled(false);
    hasUnsavedChanges = true;

    panelMatrix.classList.add('hidden-panel');
    panelExpert.classList.remove('hidden-panel');

    const welcomeMsg = document.getElementById('welcome-msg');
    if (welcomeMsg) welcomeMsg.remove();

    userPromptInput.value = '';
    userPromptInput.style.height = '24px';

    const turnId = safeUUID();
    appendUserMessage(prompt);

    const uiMap = createModelRowUI(selectedModels, turnId, (deepBtn && deepBtn.classList && deepBtn.classList.contains('selected')));
    // 新 turn：确保之前可能被隐藏的 model-analysis 区恢复显示
    try {
      selectedModels.forEach(config => {
        const anaEl = document.getElementById(`model-analysis-${turnId}-${config.key}`);
        if (anaEl) anaEl.style.display = '';
      });
    } catch (_) {}
    pendingModelResponses = selectedModels.length;

    selectedModels.forEach(config => {
      const controller = new AbortController();
      const streamKey = `${turnId}:${config.key}`;
      activeStreams.set(streamKey, controller);
      fetchModelResponse({
        sessionId,
        turnId,
        prompt,
        selectedModels,
        config,
        targetDiv: uiMap[config.key],
        controller,
        streamKey
      });
    });
  }

  async function fetchModelResponse({ sessionId, turnId, prompt, selectedModels, config, targetDiv, controller, streamKey }) {
    const el = document.getElementById(`model-content-${turnId}-${config.key}`) || targetDiv;
    const analysisEl = document.getElementById(`model-analysis-${turnId}-${config.key}`) || null;
    const opinionEl = document.getElementById(`model-opinion-${turnId}-${config.key}`) || el;

    let fullContent = '';
    let fullReasoning = '';
    let buffer = '';
    let renderScheduled = false;
    // 已渲染到 opinion 的字符数（用于增量追加，避免重复渲染整个内容）
    let lastRenderedContentLen = 0;

    const decoder = new TextDecoder('utf-8');

    function renderStreamingFrame() {
      // 隐藏 analysis 区，所有流式内容渲染到 opinion 区（增量追加）
      try { if (analysisEl) analysisEl.style.display = 'none'; } catch (_) {}

      if (!opinionEl) { scrollToBottomIfAllowed(); return; }

      // 确保 opinionEl 内有 reasoning details 与 content pre
      let reasoningDetails = opinionEl.querySelector('.stream-reasoning');
      let contentPre = opinionEl.querySelector('.stream-pre');
      if (!contentPre) {
        // 初始化结构：可折叠的 reasoning（如果有），以及内容 pre
        opinionEl.innerHTML = `
          <div class="stream-area">
            <details class="stream-reasoning" style="display:none"><summary>思考中</summary><pre class="stream-pre"></pre></details>
            <div class="stream-opinion"><pre class="stream-pre"></pre></div>
          </div>`;
        reasoningDetails = opinionEl.querySelector('.stream-reasoning');
        contentPre = opinionEl.querySelectorAll('.stream-pre')[1];
      }

      // 更新 reasoning 内容并切换显示状态
      try {
        const reasoningPre = reasoningDetails ? reasoningDetails.querySelector('.stream-pre') : null;
        if (reasoningPre) {
          reasoningPre.textContent = fullReasoning || '';
          reasoningDetails.style.display = (fullReasoning && String(fullReasoning).trim()) ? '' : 'none';
        }
      } catch (_) {}

      // 增量追加新的内容片段，避免重复渲染整个字符串
      try {
        const currentFull = fullContent || '';
        if (lastRenderedContentLen < currentFull.length) {
          const newPiece = currentFull.slice(lastRenderedContentLen);
          // 追加到 contentPre 的文本节点，保留已有内容
          contentPre.textContent = (contentPre.textContent || '') + newPiece;
          lastRenderedContentLen = currentFull.length;
        }
      } catch (e) {
        // 退回到整体替换的安全策略
        try { opinionEl.innerHTML = `<pre class="stream-pre">${escapeHtml(fullContent)}</pre>`; } catch (_) { opinionEl.textContent = fullContent || ''; }
        lastRenderedContentLen = (fullContent || '').length;
      }

      tryRenderMath(opinionEl);
      scrollToBottomIfAllowed();
    }

    function scheduleRender() {
      if (renderScheduled) return;
      renderScheduled = true;
      requestAnimationFrame(() => {
        renderScheduled = false;
        renderStreamingFrame();
      });
    }

    function buildFinalMarkdown() {
      if ((fullReasoning || '').trim()) {
        return `<details open>
  <summary>思考过程</summary>

  \`\`\`text
  ${fullReasoning}
  \`\`\`

  </details>

  ${fullContent}`;
      }
      return fullContent;
    }

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller?.signal,
        body: JSON.stringify({
          session_id: sessionId,
          turn_id: turnId,
          prompt: prompt,
          provider: config.provider,
          model: config.modelName,
          model_key: config.key,
          model_display_name: config.displayName || config.modelName,
          selected_models: selectedModels
        })
      });

      if (!response.ok) {
        // 处理各种HTTP错误
        if (response.status === 403) {
          // 敏感词拦截
          const errorData = await response.json();
          const sensitiveWord = errorData.sensitive_word || '敏感内容';
          throw new Error(`您的提问包含不允许的内容!  请修改后重新提问...`);
        }
        throw new Error(`HTTP ${response.status}`);
      }
      if (!response.body) {
        throw new Error('Browser does not support streaming response.body');
      }

      // 先清空 loading dots，进入流式显示；隐藏 analysis 区，并在 opinion 显示 loading
      fullContent = '';
      fullReasoning = '';
      lastRenderedContentLen = 0;
      try { if (analysisEl) analysisEl.style.display = 'none'; } catch (_) {}
      if (opinionEl) opinionEl.innerHTML = `<div class="loading-dots"><div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div></div>`;
      renderStreamingFrame();

      const reader = response.body.getReader();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const t = line.trim();
          if (!t) continue;

          let msg;
          try {
            msg = JSON.parse(t);
          } catch (e) {
            console.error('JSON.parse failed for line chunk', { raw: t, error: e });
            continue;
          }

          if (msg.event === 'meta') {
            // 记录 record_id（用于“提交入库”补充）
            if (!currentRecordId && msg.record_id) currentRecordId = msg.record_id;
            continue;
          }

          if (msg.event === 'delta') {
            if (msg.reasoning_delta) fullReasoning += msg.reasoning_delta;
            if (msg.delta) fullContent += msg.delta;
            scheduleRender();
            continue;
          }

          if (msg.event === 'error') {
            throw new Error(msg.content || 'Unknown error');
          }

          if (msg.event === 'done') {
            // 交给 while 循环自然结束后做最终渲染
            continue;
          }
        }
      }

      // 处理最后残留的一行（如果有）
      const tail = buffer.trim();
      if (tail) {
        try {
          const msg = JSON.parse(tail);
          if (msg.event === 'delta') {
            if (msg.reasoning_delta) fullReasoning += msg.reasoning_delta;
            if (msg.delta) fullContent += msg.delta;
          }
          if (msg.event === 'meta') {
            if (!currentRecordId && msg.record_id) currentRecordId = msg.record_id;
          }
        } catch (e) { console.error('JSON.parse failed for tail chunk', { raw: tail, error: e }); }
      }

      // 最终一次：将思考与最终内容合并渲染到 opinion（隐藏 analysis）
      try { if (analysisEl) analysisEl.style.display = 'none'; } catch (_) {}
      try {
        if (opinionEl) {
          const finalMd = buildFinalMarkdown();
          renderMarkdownTo(opinionEl, finalMd);
        }
      } catch (_) {
        if (opinionEl) opinionEl.textContent = `${fullReasoning || ''}\n\n${fullContent || ''}`;
      }

    } catch (err) {
      if (err?.name === 'AbortError') {
        el.innerHTML = `<span style="color:gray;">已停止</span>`;
      } else {
        el.innerHTML = `<span style="color:salmon;">${escapeHtml(err?.message || 'Network Error')}</span>`;
      }
    } finally {
      pendingModelResponses = Math.max(0, pendingModelResponses - 1);
      if (streamKey) activeStreams.delete(streamKey);
      if (pendingModelResponses === 0) {
        // 所有流结束或被停止
        exitStreamingMode();
        userPromptInput.focus();
      }
      scrollToBottomIfAllowed();
    }
  }

  // 串行多模型推理：handleSend2
  async function handleSend2() {
    if (isPublicChatView) {
      showModal('提示', '当前为公屏聊天模式，请使用下方公屏输入框发送');
      return;
    }
    if (isHistoryView) {
      showModal('提示', '当前处于历史工程查看模式，无法继续对话。请点击“新工程”返回。');
      return;
    }
    if (!isLoggedIn()) {
      showModal('提示', '请先登录后再开始使用');
      return;
    }
    const prompt = userPromptInput.value.trim();
    if (!prompt) return;
    const selectedModels = getSelectedModels();
    if (selectedModels.length === 0) {
      showModal("提示", "请至少选择一个模型！");
      return;
    }
    await initSessionIfNeeded();
    if (!sessionId) {
      showModal("错误", "无法初始化 Session。");
      return;
    }
    suppressAutoScroll = false;
    enterStreamingMode();
    setSendEnabled(false);
    hasUnsavedChanges = true;
    panelMatrix.classList.add('hidden-panel');
    panelExpert.classList.remove('hidden-panel');
    const welcomeMsg = document.getElementById('welcome-msg');
    if (welcomeMsg) welcomeMsg.remove();
    userPromptInput.value = '';
    userPromptInput.style.height = '24px';
    const turnId = safeUUID();
    appendUserMessage(prompt);
    const uiMap = createModelRowUI(selectedModels, turnId, (deepBtn && deepBtn.classList && deepBtn.classList.contains('selected')));
    // 开发文件流功能已移除：不再向 models-console 注入服务器端文件内容
    pendingModelResponses = selectedModels.length;

    // 新增：串行依赖数据
    let summeryList = [];
    let lastAnalysis = '';
    const consoleContent = document.querySelector(`.models-console[data-turn-id="${turnId}"] .console-content`);
    const consoleSummaryElInit = document.querySelector(`.models-console[data-turn-id="${turnId}"] .console-summary`);

    for (let i = 0; i < selectedModels.length; i++) {
      const config = selectedModels[i];
      const controller = new AbortController();
      const streamKey = `${turnId}:${config.key}`;
      activeStreams.set(streamKey, controller);
      // 进度提示：在 .console-content 中创建或更新 .console-progress，summary 保持写入 .console-summary
      if (consoleSummaryElInit) {
        // 确保 consoleContent 可用
        if (consoleContent) {
          let progressEl = consoleContent.querySelector('.console-progress');
          if (!progressEl) {
            progressEl = document.createElement('div');
            progressEl.className = 'console-progress';
            progressEl.style.color = '#7bb0f7';
            progressEl.style.marginBottom = '6px';
            consoleContent.insertBefore(progressEl, consoleSummaryElInit);
          }
          progressEl.textContent = `思考进度：${i}/${selectedModels.length}`;
        }
        // 仅渲染 summary 列表到 .console-summary
        consoleSummaryElInit.innerHTML = summeryList.map((s, idx) => `<div class="console-summary-item"><b>模型${idx+1}总结：</b>${escapeHtml(s)}</div>`).join('');
      }
      try {
        // deep 模式：传递依赖
        const result = await fetchModelDeepResponse({
          sessionId,
          turnId,
          prompt,
          selectedModels,
          config,
          targetDiv: uiMap[config.key],
          controller,
          streamKey,
          serialIndex: i,
          summeryList,
          lastAnalysis
        });
        // 结构化输出，更新依赖
        if (result && typeof result === 'object') {
          if (result.summary || result.summery) summeryList.push(result.summary || result.summery);
          if (result.analysis) lastAnalysis = result.analysis;
          // models-console 动态刷新（仅更新 summary 区，避免破坏 console-content 结构）
          if (consoleSummaryElInit) {
            if (consoleContent) {
              let progressEl = consoleContent.querySelector('.console-progress');
              if (!progressEl) {
                progressEl = document.createElement('div');
                progressEl.className = 'console-progress';
                progressEl.style.color = '#7bb0f7';
                progressEl.style.marginBottom = '6px';
                consoleContent.insertBefore(progressEl, consoleSummaryElInit);
              }
              progressEl.textContent = `思考进度：${i}/${selectedModels.length}`;
            }
            consoleSummaryElInit.innerHTML = summeryList.map((s, idx) => `<div class="console-summary-item"><b>观点${idx+1}：</b>${escapeHtml(s)}</div>`).join('');
          }
        }
      } catch (err) {
        // 详细排查 abort 错误
        if (err?.name === 'AbortError') {
          console.warn('[DeepFetch] 请求被中断:', err);
          try { const elLocal = uiMap[config.key] || document.getElementById(`model-content-${turnId}-${config.key}`); if (elLocal) elLocal.innerHTML = `<span style="color:salmon;">[文件流异常] signal is aborted${err?.message ? ': ' + escapeHtml(err.message) : ''}</span>`; } catch(_) {}
        } else {
          console.error('[DeepFetch] 请求异常:', err);
          try { const elLocal = uiMap[config.key] || document.getElementById(`model-content-${turnId}-${config.key}`); if (elLocal) elLocal.innerHTML = `<span style="color:salmon;">${escapeHtml(err?.message || 'Network Error')}</span>`; } catch(_) {}
        }
        return null;
      }
      scrollToBottomIfAllowed();
    }
    // 在所有模型串行计算完成后，额外调用一次用户选择的第一个模型
    // 该调用返回对最后一个模型的分析和总结 `analysis`/`summary`（由后端按约定返回），并把结果渲染到前端对应位置（最后一个模型的model-analysis和console-summary）。
    try {
      if (Array.isArray(selectedModels) && selectedModels.length > 0) {
        // 希望最终调用由列表第一个模型执行，但其 analysis 渲染到最后一列，且不覆盖第一列内容
        const firstCfg = selectedModels[0];
        const lastKey = selectedModels[selectedModels.length - 1].key;
        // 保持 pendingModelResponses 计数一致，fetchModelDeepResponse 的 finally 会递减
        pendingModelResponses = (pendingModelResponses || 0) + 1;
        const finalController = new AbortController();
        const finalStreamKey = `${turnId}:${firstCfg.key}:final`;
        activeStreams.set(finalStreamKey, finalController);
        try {
          await fetchModelDeepResponse({
            sessionId,
            turnId,
            prompt,
            selectedModels,
            config: firstCfg,                 // 请求仍使用第一个模型
            targetDiv: uiMap[firstCfg.key],
            controller: finalController,
            streamKey: finalStreamKey,
            serialIndex: selectedModels.length,
            summeryList,
            lastAnalysis,
            renderToKey: lastKey,            // 新增：把渲染目标设为最后一列
            changeBtn: true
          });
        } catch (e) {
          console.error('[FinalDeep] 请求异常：', e);
        } finally {
          try { activeStreams.delete(finalStreamKey); } catch(_) {}
        }
      }
    } catch (_) {}
  }
  
  // deep 串行 fetch，返回结构化 json
  async function fetchModelDeepResponse({ sessionId, turnId, prompt, selectedModels, config, targetDiv, controller, streamKey, serialIndex, summeryList, lastAnalysis, renderToKey, changeBtn }) {
    // renderToKey 优先用于定位渲染目标（允许请求某模型但把渲染放到另一个模型列）
    const renderKey = renderToKey || config.key;
    const final = changeBtn || false;
    const el = document.getElementById(`model-content-${turnId}-${renderKey}`) || targetDiv;
    const analysisEl = document.getElementById(`model-analysis-${turnId}-${renderKey}`) || null;
    const opinionEl = document.getElementById(`model-opinion-${turnId}-${renderKey}`) || el;
    const consoleSummaryEl = document.querySelector(`.models-console[data-turn-id="${turnId}"] .console-summary`);
    // loading 显示在 analysis 区
    const loadingHtml = `<div class="loading-dots"><div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div></div>`;
    if (analysisEl) analysisEl.innerHTML = loadingHtml;
    // 仅当渲染目标与请求模型相同时才清空 opinion，避免使用 renderToKey 时覆盖已有 opinion
    if (opinionEl) {
      if (!renderToKey || renderKey === config.key) {
        opinionEl.innerHTML = '';
      }
    }
    try {
      const response = await fetch('/api/chat/deep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller?.signal,
        body: JSON.stringify({
          session_id: sessionId,
          turn_id: turnId,
          prompt: prompt,
          provider: config.provider,
          model: config.modelName,
          model_key: config.key,
          model_display_name: config.displayName || config.modelName,
          selected_models: selectedModels,
          serial_index: serialIndex,
          summery_list: summeryList,
          last_analysis: lastAnalysis
        })
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      // deep 接口通常以 NDJSON 流返回多条 JSON 行；支持 streaming 或单次 JSON 两种情况
      let resultObj = null;
      let fullReasoning = '';
      let fullDelta = '';

      if (response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            const t = line.trim();
            if (!t) continue;
            try {
              const msg = JSON.parse(t);
              if (msg.event === 'meta') {
                if (!currentRecordId && msg.record_id) currentRecordId = msg.record_id;
                continue;
              }
              if (msg.event === 'delta') {
                if (msg.reasoning_delta) fullReasoning += msg.reasoning_delta;
                if (msg.delta) fullDelta += msg.delta;
                continue;
              }
              // 某些实现会在最后一行返回包含 result 的对象
              if (msg.event === 'result' || (msg.event === 'done' && msg.result) || msg.result) {
                resultObj = msg.result || msg;
              }
            } catch (e) {
              console.error('JSON.parse failed while reading deep stream line', { raw: t, error: e });
              continue;
            }
          }
        }

        // 处理尾部残留
        const tail = buffer.trim();
        if (tail) {
          try {
            const msg = JSON.parse(tail);
            if (msg.result) resultObj = msg.result;
            if (msg.event === 'delta') {
              if (msg.reasoning_delta) fullReasoning += msg.reasoning_delta;
              if (msg.delta) fullDelta += msg.delta;
            }
            if (msg.event === 'meta' && !currentRecordId && msg.record_id) currentRecordId = msg.record_id;
          } catch (e) {
            console.error('JSON.parse failed for deep stream tail', { raw: tail, error: e });
          }
        }
      } else {
        // 非流式返回，尝试一次性解析
        try {
          const data = await response.json();
          if (data && (data.status === 'success' || data.result)) {
            resultObj = data.result || data;
          }
        } catch (e) {
          throw new Error('无法解析模型返回的内容');
        }
      }

      // 渲染结果：优先使用结构化 resultObj，其次降级显示拼接内容
      if (resultObj) {
        // 兼容字段名：同时支持 `summary`（优先）和拼写错误的 `summery`
        const summaryText = (resultObj.summary || resultObj.summery || '').toString();
        console.log(summaryText);
        const ana = typeof resultObj.analysis === 'string' ? resultObj.analysis : (fullReasoning || '');
        const opi = typeof resultObj.opinion === 'string' ? resultObj.opinion : (fullDelta || '');

        // 将 summary 追加到 models-console 的 summary 区（每次调用新插入一段）
        try {
          // 如果后端没有 summary，则从 opinion（或 fullDelta）生成一个简短摘录作为回退
          let finalSummary = (summaryText || '').trim();
          if (!finalSummary) {
            const fallbackSource = (resultObj.opinion || resultObj.opi || fullDelta || fullReasoning || '').toString();
            const plain = fallbackSource.replace(/\s+/g, ' ').trim();
            if (plain) {
              finalSummary = plain.length > 220 ? plain.slice(0, 220) + '…' : plain;
            }
          }
          if (consoleSummaryEl && finalSummary) {
            const item = document.createElement('div');
            item.className = 'console-summary-item';
            try {
              const index = (consoleSummaryEl.children && consoleSummaryEl.children.length) ? consoleSummaryEl.children.length + 1 : 1;
              item.innerHTML = `<b>观点${index}：</b>${escapeHtml(finalSummary)}`;
            } catch (_) {
              item.textContent = finalSummary;
            }
            consoleSummaryEl.appendChild(item);
          }
        } catch (_) {}

        // 分别渲染 analysis 与 opinion 到两个独立区域
        try {
          // 如果是串行调用的后续模型，只同步写入前一个模型的 analysis 区，不在当前模型的 analysis 中重复显示
          try {
            // 串行调用时默认把当前模型的 analysis 写入到上一个模型的 analysis 区。
            // 如果传入了 renderToKey，则优先写入指定的渲染键对应的 analysis 区。
            try {
              let targetAnalysisKey = null;
              if (renderToKey) {
                targetAnalysisKey = renderToKey;
              } else if (typeof serialIndex === 'number' && serialIndex > 0 && Array.isArray(selectedModels)) {
                const prevCfg = selectedModels[serialIndex - 1];
                if (prevCfg && prevCfg.key) targetAnalysisKey = prevCfg.key;
              }

              if (targetAnalysisKey) {
                const prevAnalysisEl = document.getElementById(`model-analysis-${turnId}-${targetAnalysisKey}`);
                if (prevAnalysisEl) {
                  try { renderMarkdownTo(prevAnalysisEl, ana || ''); } catch (_) { prevAnalysisEl.textContent = ana || ''; }
                }
              } else {
                // 回退到当前 renderKey 对应的 analysis 区
                if (analysisEl) renderMarkdownTo(analysisEl, ana || '');
              }
            } catch (_) {}
          } catch (_) {}
        } catch (_) { if (analysisEl) analysisEl.textContent = ana || ''; }
        try {
          // 当使用 renderToKey 将渲染定向到非请求模型时，避免覆盖目标列已有的 opinion。
          // 仅当目标 opinion 为空时才写入；否则保留原有 opinion。
          const allowOpinionOverwrite = !renderToKey;
          try {
            if (opinionEl) {
              const hasExistingOpinion = opinionEl.innerHTML && opinionEl.innerHTML.trim() !== '';
              if (allowOpinionOverwrite || !hasExistingOpinion) {
                renderMarkdownTo(opinionEl, opi || '');
              }
            }
          } catch (e) {
            if (opinionEl && (allowOpinionOverwrite || !opinionEl.innerHTML || opinionEl.innerHTML.trim() === '')) opinionEl.textContent = opi || '';
          }
        } catch (_) { if (opinionEl && (!renderToKey || !opinionEl.innerHTML || opinionEl.innerHTML.trim() === '')) opinionEl.textContent = opi || ''; }

        scrollToBottomIfAllowed();
        return resultObj;
      } else {
        // 完全没有结构化结果，则显示降级信息到 opinion 区
        const fallback = (fullReasoning || fullDelta) ? `分析：${escapeHtml(fullReasoning)}<br>内容：${escapeHtml(fullDelta)}` : '模型未返回结构化结果';
        if (opinionEl) {
          opinionEl.innerHTML = `<span style="color:salmon;">${escapeHtml(fallback)}</span>`;
        } else if (analysisEl) {
          analysisEl.innerHTML = `<span style="color:salmon;">${escapeHtml(fallback)}</span>`;
        } else {
          el.innerHTML = `<span style="color:salmon;">${escapeHtml(fallback)}</span>`;
        }
        return null;
      }
    } catch (err) {
      el.innerHTML = `<span style="color:salmon;">${escapeHtml(err?.message || 'Network Error')}</span>`;
      return null;
    }
    finally {
      // 清理串行模式下的流状态，保持与并行路径一致
      if (final) {
        // console.log('final clean');

        // 这里写的比较特殊，正常情况下exitStreamingMode();和userPromptInput.focus(); 应该是在pendingModelResponses===0时触发
        // pendingModelResponses===0意味着用户选择的模型都已经思考完成
        // 但是为了深度思考模式额外多了一次请求（总结的请求），所以不可以在===0时停止，要延后一次
      // console.log(pendingModelResponses)
      // if (pendingModelResponses === 0 ) {
      //   exitStreamingMode();
      //   userPromptInput.focus(); 
      // }

        pendingModelResponses = Math.max(0, pendingModelResponses - 1);
        if (streamKey) activeStreams.delete(streamKey);
        exitStreamingMode();
        userPromptInput.focus(); 
        scrollToBottomIfAllowed();
      }
    }
  }

  function stopAllStreams() {
    // 终止所有正在进行的流
    for (const [, controller] of activeStreams.entries()) {
      try { controller.abort(); } catch (_) {}
    }
    activeStreams.clear();
    pendingModelResponses = 0;
    exitStreamingMode();
  }


  // 摘选
  let selectedText = '';
  chatContainer.addEventListener('scroll', () => {
    selectionPopover.style.display = 'none';

    // 距离底部 > 120 px 时停用自动滚动，反之恢复
    const bottomGap = chatContainer.scrollHeight
                    - chatContainer.scrollTop
                    - chatContainer.clientHeight;
    suppressAutoScroll = bottomGap > 20;
  });


  document.addEventListener('mouseup', (e) => {
    const selection = window.getSelection();
    const text = selection.toString().trim();
    if (!text || e.target === selectionPopover || selectionPopover.contains(e.target)) {
      if (!text) selectionPopover.style.display = 'none';
      return;
    }
    const anchor = selection.anchorNode && selection.anchorNode.parentElement;
    const contentDiv = anchor ? (anchor.closest('.model-content') || anchor.closest('.console-content')) : null;
    if (!contentDiv) { selectionPopover.style.display = 'none'; return; }

    selectedText = text;
    const rect = selection.getRangeAt(0).getBoundingClientRect();

    selectionPopover.style.display = 'flex';
    // position: fixed -> 不要再加 window.scrollY
    selectionPopover.style.top = `${rect.bottom + 10}px`;
    selectionPopover.style.left = `${rect.left + (rect.width / 2)}px`;
  });

  // 禁用模型输出/console 区域的浏览器右键菜单（统一判断）
  document.addEventListener('contextmenu', (e) => {
    try {
      if (isInSelectableArea(e.target)) {
        e.preventDefault();
      }
    } catch (_) {}
  });

  // 禁用模型输出区域的快捷复制/剪切（Ctrl/Cmd + C/X）
  document.addEventListener('keydown', (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    const key = e.key?.toLowerCase();
    if (key !== 'c' && key !== 'x') return;

    const sel = window.getSelection();
    if (!sel || !sel.toString().trim()) return;

    const anchor = sel.anchorNode && sel.anchorNode.parentElement;
    if (isInSelectableArea(anchor)) {
      e.preventDefault();
    }
  });

  selectionPopover.addEventListener('mousedown', (e) => {
    e.preventDefault();
    if (selectedText) {
      const currentVal = expertTextarea.value;
      expertTextarea.value = currentVal ? currentVal + "\n\n" + selectedText : selectedText;
      expertTextarea.scrollTop = expertTextarea.scrollHeight;
      selectionPopover.style.display = 'none';
      window.getSelection().removeAllRanges();
      hasUnsavedChanges = true;
    }
  });

  // 复制内容按钮
  const copyBtn = document.getElementById('copy-btn');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      const expertData = expertTextarea.value.trim();
      
      if (!expertData) {
        showModal('提示', '专家精选集为空，无内容可复制');
        return;
      }

      try {
        // 使用现代 Clipboard API
        await navigator.clipboard.writeText(expertData);
        
        // 显示成功提示
        const originalText = copyBtn.innerText;
        copyBtn.innerText = '已复制';
        setTimeout(() => {
          copyBtn.innerText = originalText;
        }, 2000);
      } catch (err) {
        // 降级方案：使用传统 document.execCommand
        try {
          const textarea = document.createElement('textarea');
          textarea.value = expertData;
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand('copy');
          document.body.removeChild(textarea);
          
          const originalText = copyBtn.innerText;
          copyBtn.innerText = '已复制';
          setTimeout(() => {
            copyBtn.innerText = originalText;
          }, 2000);
        } catch (fallbackErr) {
          showModal('错误', '复制失败，请手动复制');
        }
      }
    });
  }

  // 提交入库（补充字段）
  saveBtn.addEventListener('click', async () => {
    const username = inputUsername.value;
    const projectName = inputProject.value;
    const expertData = expertTextarea.value;

    saveBtn.innerText = '提交中...';
    try {
      const payload = {
        username: username,
        project_name: projectName,
        expert_data: expertData
      };

      if (isHistoryView && currentRecordId) {
        payload.record_id = currentRecordId;
      } else {
        await initSessionIfNeeded();
        payload.session_id = sessionId;
        if (currentRecordId) payload.record_id = currentRecordId;
      }

      const res = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'success') {
        hasUnsavedChanges = false;
        saveBtn.innerText = '提交入库';
        await loadHistory();
        showModal("完成", "已提交入库");
      } else {
        showModal("错误", data.content || "提交失败");
        saveBtn.innerText = '提交入库';
      }
    } catch (e) {
      showModal("错误", "网络错误");
      saveBtn.innerText = '提交入库';
    }
  });

  // 自动保存函数（与提交入库相同逻辑）
  async function doSavePayload(payload) {
    try {
      const res = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'success') {
        hasUnsavedChanges = false;
        await loadHistory();
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  async function autoSaveIfNeeded() {
    if (!hasUnsavedChanges) return true;
    const username = inputUsername.value;
    const projectName = inputProject.value;
    const expertData = expertTextarea.value;

    const payload = { username: username, project_name: projectName, expert_data: expertData };
    if (isHistoryView && currentRecordId) {
      payload.record_id = currentRecordId;
      return await doSavePayload(payload);
    }

    // 确保 sessionId
    try {
      await initSessionIfNeeded();
    } catch (_) { }
    if (sessionId) payload.session_id = sessionId;
    if (currentRecordId) payload.record_id = currentRecordId;

    return await doSavePayload(payload);
  }

  // 在卸载/刷新时尽量使用 sendBeacon 发送同步保存
  window.addEventListener('beforeunload', (e) => {
    if (!hasUnsavedChanges) return;
    try {
      const username = inputUsername.value || '';
      const projectName = inputProject.value || '';
      const expertData = expertTextarea.value || '';
      const payload = { username: username, project_name: projectName, expert_data: expertData };
      if (sessionId) payload.session_id = sessionId;
      if (currentRecordId) payload.record_id = currentRecordId;
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/save', blob);
        hasUnsavedChanges = false;
      }
    } catch (_) {
      // ignore
    }
  });

  // 历史列表加载
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      const list = await res.json();
      
      // 创建搜索框（如果不存在）
      let searchContainer = document.getElementById('history-search-container');
      if (!searchContainer && historyList) {
        searchContainer = document.createElement('div');
        searchContainer.id = 'history-search-container';
        searchContainer.style.marginBottom = '12px';
        searchContainer.innerHTML = `
          <input type="text" id="history-search-input" placeholder="搜索历史记录..." 
                 style="width: 100%; padding: 8px 12px; background: var(--bg-color); 
                        border: 1px solid var(--border-color); border-radius: 8px; 
                        color: var(--text-main); font-size: 13px; font-family: inherit;" />
        `;
        historyList.parentNode.insertBefore(searchContainer, historyList);
        
        // 添加搜索事件
        const searchInput = document.getElementById('history-search-input');
        if (searchInput) {
          searchInput.addEventListener('input', (e) => {
            const keyword = e.target.value.trim().toLowerCase();
            filterAndRenderHistory(list, keyword);
          });
        }
      }
      
      // 获取搜索关键词
      const searchInput = document.getElementById('history-search-input');
      const keyword = searchInput ? searchInput.value.trim().toLowerCase() : '';
      
      filterAndRenderHistory(list, keyword);
    } catch (err) {
      console.error('加载历史失败:', err);
      if (historyList) {
        historyList.innerHTML = `<div class="history-item">加载失败</div>`;
      }
    }
  }

  function filterAndRenderHistory(list, keyword) {
    if (!historyList) return;
    historyList.innerHTML = '';

    if (!Array.isArray(list) || list.length === 0) {
      historyList.innerHTML = `<div class="history-item">暂无记录</div>`;
      return;
    }

    // 过滤和排序
    let filteredList = list;
    if (keyword) {
      // 计算每个项目的关键词匹配度
      filteredList = list.map(item => {
        const projectName = (item.project_name || '').toLowerCase();
        const username = (item.username || '').toLowerCase();
        const searchText = `${projectName} ${username}`;
        
        // 计算关键词出现次数
        const keywordCount = (searchText.match(new RegExp(keyword, 'g')) || []).length;
        
        return { ...item, _keywordCount: keywordCount };
      }).filter(item => item._keywordCount > 0)
        .sort((a, b) => b._keywordCount - a._keywordCount);
    }

    const formatLocal = (iso) => {
      try {
        if (!iso) return '';
        const d = new Date(iso);
        if (isNaN(d.getTime())) return '';
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const da = String(d.getDate()).padStart(2, '0');
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        const ss = String(d.getSeconds()).padStart(2, '0');
        return `${y}-${m}-${da} ${hh}:${mm}:${ss}`;
      } catch (_) { return ''; }
    };

    if (filteredList.length === 0) {
      historyList.innerHTML = `<div class="history-item">未找到匹配的记录</div>`;
      return;
    }

    filteredList.forEach(item => {
        const div = document.createElement('div');
        div.className = 'history-item';
        // 使用 record_id 作为唯一标识
        const recordId = item.record_id || item.id;
        div.dataset.id = recordId; // 存储ID用于后续操作

        const badge = item.has_expert_data ? '' : `<span style="margin-left:8px; font-size:11px; opacity:0.65;">(未摘选)</span>`;
        
        const displayTime = item.timestamp_iso ? formatLocal(item.timestamp_iso) : (item.timestamp || '');
        div.innerHTML = `
          <div class="history-text-col">
            <div class="project-name-text" style="font-weight:500; color:#E3E3E3">${escapeHtml(item.project_name || '未命名')}${badge}</div>
            <div style="font-size:11px; opacity:0.7">${displayTime}</div>
          </div>
          <button class="history-more-btn">
            <span class="material-symbols-outlined" style="font-size:18px;">more_vert</span>
          </button>
          <div class="action-menu">
            <button class="rename-btn">重命名</button>
            <button class="delete-btn">删除</button>
          </div>
        `;

        // 1. 点击整行打开详情 (排除点击按钮的情况)
        div.onclick = async (e) => {
          if (e.target.closest('.history-more-btn') || e.target.closest('.action-menu')) return;
          if (hasUnsavedChanges) {
            // 自动保存后再打开历史
            try {
              await autoSaveIfNeeded();
            } catch (err) {
              console.warn('autoSave failed before opening history', err);
            }
          }
          await openHistoryDetail(recordId);
        };

        // 2. 三个点菜单切换
        const moreBtn = div.querySelector('.history-more-btn');
        const menu = div.querySelector('.action-menu');
        moreBtn.onclick = (e) => {
          e.stopPropagation();
          // 先关闭其他打开的菜单
          document.querySelectorAll('.action-menu.show').forEach(m => {
            if (m !== menu) m.classList.remove('show');
          });
          menu.classList.toggle('show');
        };

        // 3. 重命名逻辑
        div.querySelector('.rename-btn').onclick = async (e) => {
          e.stopPropagation();
          menu.classList.remove('show');
          const oldName = item.project_name || '未命名';
          const newName = await showModal("重命名工程", `请输入新的工程名称：`, "input", oldName);
          if (newName && newName.trim() !== "" && newName !== oldName) {
            handleRename(recordId, newName.trim());
          }
        };

        // 4. 删除逻辑
        div.querySelector('.delete-btn').onclick = async (e) => {
          e.stopPropagation();
          menu.classList.remove('show');
          const confirmed = await showModal("确认删除", `确定要删除工程 "${item.project_name || '未命名'}" 吗？此操作不可撤销。`, "confirm");
          if (confirmed) {
            handleDelete(recordId);
          }
        };

        historyList.appendChild(div);
      });
  }

  function enhanceSingleCount(count, rank) {
    const percent =  0.1;       // 百分比放大
    const rankBonus = 50;    // 排名加成基数
    const logFactor = 1.1;   // log平滑系数
    const randomRange = [1.0, 1.05]; // 随机浮动

    // 第一步：排名加成 + 百分比放大
    let count_aug = count * (1 + percent) + rankBonus / rank;

    // 第二步：log平滑 + 小随机浮动
    let logVal = Math.exp(Math.log(count_aug + 1) * logFactor) - 1;
    let rand = Math.random() * (randomRange[1] - randomRange[0]) + randomRange[0];

    return Math.round(logVal * rand);
  }

  // mini 热搜榜（语义热点问句）
  async function loadMiniTrendingQuestions() {
    const listEl = document.getElementById('mini-trending-list');
    if (!miniTrendingPanel || !listEl) return;

    // 初始或再次加载时的占位文案
    if (!listEl.querySelector('.mini-trending-empty')) {
      listEl.innerHTML = '<div class="mini-trending-empty">加载中...</div>';
    } else {
      const emptyEl = listEl.querySelector('.mini-trending-empty');
      if (emptyEl) emptyEl.textContent = '加载中...';
    }
    try {
      const res = await fetch('/api/trending/questions');
      const data = await res.json();
      if (data.status !== 'success') {
        const msg = escapeHtml(data.content || '加载失败');
        listEl.innerHTML = `<div class="mini-trending-empty">${msg}</div>`;
        return;
      }
      const list = Array.isArray(data.trending) ? data.trending : [];
      if (list.length === 0) {
        listEl.innerHTML = '<div class="mini-trending-empty">暂时没有热点问句</div>';
        return;
      }
      const lines = list.map((item, idx) => {
        const rank = idx + 1;
        const rawPrompt = (item && item.prompt) ? String(item.prompt) : '';
        const title = escapeHtml(rawPrompt);
        let count = item && typeof item.count === 'number' ? item.count : undefined;
        
        // 让提问的人数显得多一点
        count = enhanceSingleCount(count, rank)
        
        

        const meta = count != null ? ` · ${count}人提问` : '';
        const promptAttr = escapeHtml(rawPrompt);
        return `<div class="mini-trending-item" data-prompt="${promptAttr}"><span class="mini-trending-rank">${rank}</span><span class="mini-trending-text">${title}${meta}</span></div>`;
      });
      listEl.innerHTML = lines.join('');

      // 点击热搜条目可一键填入问句
      listEl.querySelectorAll('.mini-trending-item').forEach((el) => {
        el.addEventListener('click', () => {
          const prompt = el.dataset.prompt || '';
          if (!prompt || !userPromptInput) return;
          userPromptInput.value = prompt;
          userPromptInput.focus();
          userPromptInput.dispatchEvent(new Event('input'));
        });
      });
    } catch (e) {
      console.error('加载语义热点问句失败:', e);
      listEl.innerHTML = '<div class="mini-trending-empty">加载失败，请稍后重试</div>';
    }
  }

  // 处理重命名提交
  async function handleRename(id, newName) {
    try {
      const res = await fetch('/api/history/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id, new_name: newName })
      });
      const data = await res.json();
      if (data.status === 'success') {
        await loadHistory(); // 刷新列表
      } else {
        showModal("错误", "重命名失败");
      }
    } catch (e) {
      showModal("错误", "网络请求异常");
    }
  }

  // 处理删除提交
  async function handleDelete(id) {
    try {
      const res = await fetch('/api/history/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id })
      });
      const data = await res.json();
      if (data.status === 'success') {
        // 如果删除的是当前正在查看的记录，则重置UI
        if (currentRecordId === id) {
          resetUIForNewChat();
        }
        await loadHistory(); // 刷新列表
      } else {
        showModal("错误", "删除失败");
      }
    } catch (e) {
      showModal("错误", "网络请求异常");
    }
  }

  async function openHistoryDetail(recordId) {
    try {
      const res = await fetch(`/api/history/detail?id=${encodeURIComponent(recordId)}`);
      const j = await res.json();
      if (j.status !== 'success') {
        showModal("错误", j.content || "读取详情失败");
        return;
      }
      renderHistoryDetail(j.record);
    } catch (e) {
      console.error(e);
      showModal("错误", "网络错误（历史详情）");
    }
  }

  function renderHistoryDetail(record) {
    // 历史渲染：抑制一切“自动滚到底部”
    suppressAutoScroll = true;

    if (inputAreaWrapper) inputAreaWrapper.style.display = 'none';
    hasUnsavedChanges = false;
    isHistoryView = true;
    isPublicChatView = false;
    setSendEnabled(false);
    // 接口返回 record_id，保持为全局当前工程标识
    currentRecordId = record.record_id;

    // 历史模式：需要继续更新数据集，所以显示“摘选入库”面板
    panelMatrix.classList.add('hidden-panel');
    panelExpert.classList.remove('hidden-panel');
    if (hotBoard) hotBoard.classList.add('hidden-panel');

    chatContainer.innerHTML = '';
    chatContainer.scrollTop = 0;

    expertTextarea.value = record.expert_data || '';
    inputProject.value = record.project_name || '未命名';
    inputUsername.value = record.username || '未填写';

    // 摘选预览（微软雅黑）
    const datasetCard = document.createElement('div');
    datasetCard.id = 'dataset-card';
    datasetCard.style.margin = "16px";
    datasetCard.style.padding = "14px";
    datasetCard.style.border = "1px solid rgba(255,255,255,0.10)";
    datasetCard.style.borderRadius = "12px";
    datasetCard.style.background = "rgba(0,0,0,0.25)";
    datasetCard.style.fontFamily = '"Microsoft YaHei","微软雅黑",sans-serif';

    const expert = (record.expert_data || "").trim();
    datasetCard.innerHTML = `
      <div style="font-weight:600; margin-bottom:8px;">已摘选数据集</div>
      ${
        expert
          ? `<pre style="white-space:pre-wrap; margin:0; opacity:0.9; line-height:1.5; font-family:'Microsoft YaHei','微软雅黑',sans-serif;">${escapeHtml(record.expert_data)}</pre>`
          : `<div style="opacity:0.75; line-height:1.6;">上次未摘选。你可以在下方历史对话中选中文本并“摘选入库”，然后点击右下角“提交入库”。</div>`
      }
    `;
    chatContainer.appendChild(datasetCard);

    // 后端返回字段为 record.turns（兼容旧字段 chat_turns）
    const turns = Array.isArray(record.turns)
      ? record.turns
      : (Array.isArray(record.chat_turns) ? record.chat_turns : []);
    if (turns.length === 0) {
      const empty = document.createElement('div');
      empty.style.padding = "16px";
      empty.style.color = "#888";
      empty.innerText = "该工程暂无对话。";
      chatContainer.appendChild(empty);

      // 渲染完成：定位到数据集顶端
      requestAnimationFrame(() => {
        suppressAutoScroll = false;
        scrollToDatasetTop();
      });
      return;
    }
    turns.forEach(t => {

      appendUserMessage(t.prompt || '');

      const responses = t.responses || {};
      const selectedModels = Array.isArray(t.selected_models) ? t.selected_models : [];

      // 优先按 selected_models 固定列；没有就退化按 responses
      let modelsForDisplay = [];
      if (selectedModels.length > 0) {
        modelsForDisplay = selectedModels.map(m => ({
          key: m.key,
          provider: m.provider,
          modelName: m.modelName,
          displayName: m.displayName
        }));
      } else {
        modelsForDisplay = Object.keys(responses).map(k => {
          const rr = responses[k] || {};
          return { key: k, provider: rr.provider, modelName: rr.model, displayName: rr.model_display_name || rr.model };
        });
      }

      const turnId = t.id || safeUUID();
      // 决定本行是否展示 models-console（仅当该 turn 有结构化 JSON 数据时展示）
      let showConsoleForTurn = false;
      try {
        // 检查 responses 中最后的 assistant 是否标注为结构化
        for (const k of Object.keys(responses || {})) {
          const rr = responses[k];
          if (Array.isArray(rr)) {
            const assistantMsgs = rr.filter(x => x && x.role === 'assistant');
            const lastAssistant = assistantMsgs.length ? assistantMsgs[assistantMsgs.length - 1] : rr[rr.length - 1];
            if (lastAssistant && lastAssistant.is_structured) { showConsoleForTurn = true; break; }
          }
        }
        // 检查 messages_ 表返回的数据
        if (!showConsoleForTurn && Array.isArray(t._messages_) && t._messages_.length > 0) {
          for (const mm of t._messages_) {
            if (!mm) continue;
            if (mm.is_structured || mm.parsed) { showConsoleForTurn = true; break; }
          }
        }
      } catch (e) { /* ignore */ }

      const uiMap = createModelRowUI(modelsForDisplay, turnId, showConsoleForTurn);

      // 预先选择 finalMsg（若有），以便避免将其 summary 重复加入 console
      let preselectedFinalMsg = null;
      try {
        if (Array.isArray(t._messages_) && t._messages_.length > 0 && modelsForDisplay && modelsForDisplay.length > 0) {
          const firstKey = (modelsForDisplay[0] && modelsForDisplay[0].key) ? modelsForDisplay[0].key.toString().toLowerCase() : null;
          if (firstKey) {
            preselectedFinalMsg = t._messages_.find(m => (m.model_key || '').toString().toLowerCase() === firstKey) || null;
          }
          if (!preselectedFinalMsg) preselectedFinalMsg = t._messages_.find(m => m && m.is_structured && m.parsed) || t._messages_[0] || null;
        }
      } catch (_) { preselectedFinalMsg = null; }

      // console summary 区（若存在）
      const consoleSummaryEl = document.querySelector(`.models-console[data-turn-id="${turnId}"] .console-summary`);

      modelsForDisplay.forEach(m => {
        const rr = responses[m.key];

        // 兼容：后端可能返回数组或对象
        let contentText = '';
        let lastAssistant = null;
        if (Array.isArray(rr)) {
          const assistantMsgs = rr.filter(x => x && x.role === 'assistant');
          lastAssistant = assistantMsgs.length ? assistantMsgs[assistantMsgs.length - 1] : (rr.length ? rr[rr.length - 1] : null);
          contentText = (lastAssistant?.content || (rr[rr.length - 1] && rr[rr.length - 1].content) || '');
        } else if (rr && typeof rr === 'object') {
          lastAssistant = rr;
          contentText = rr.content || '';
        }

        const idx = modelsForDisplay.findIndex(x => (x.key || '').toString().toLowerCase() === (m.key || '').toString().toLowerCase());
        const analysisEl = document.getElementById(`model-analysis-${turnId}-${m.key}`);
        const opinionEl = document.getElementById(`model-opinion-${turnId}-${m.key}`);

        if (contentText) {
          let isStructured = lastAssistant && lastAssistant.is_structured;
          let parsed = isStructured ? lastAssistant.parsed : null;

          if (isStructured && parsed && typeof parsed === 'object') {
            // 按用户要求的映射：
            // - parsed.summary -> 追加到 console
            // - parsed.analysis -> 写入上一列的 analysis（idx>0），若上一列不存在则写入当前列；以追加方式避免替换已有内容
            // - parsed.opinion -> 写入当前列 opinion（仅当 opinion 为空时写入，以避免覆盖）

            // summary -> console
            try {
              // 避免将第一个模型（idx===0）的 summary 写入 console（第一列优先作为 opinion），
              // 也避免重复写入 finalMsg 的 summary（finalMsg 会在后处理追加一次）
              const normalizedKey = (m.key || '').toString().toLowerCase();
              const finalMsgKey = preselectedFinalMsg && preselectedFinalMsg.model_key ? preselectedFinalMsg.model_key.toString().toLowerCase() : null;
              const shouldAppendSummary = parsed.summary && consoleSummaryEl && idx !== 0 && normalizedKey !== finalMsgKey;
              if (shouldAppendSummary) {
                const item = document.createElement('div');
                item.className = 'console-summary-item';
                const index = (consoleSummaryEl.children && consoleSummaryEl.children.length) ? consoleSummaryEl.children.length + 1 : 1;
                item.innerHTML = `<b>观点${index}：</b>${escapeHtml((parsed.summary || '').toString())}`;
                consoleSummaryEl.appendChild(item);
              }
            } catch (_) {}

            // analysis -> previous column's analysis (append)
            try {
              if (parsed.analysis) {
                let targetAnalysisKey = null;
                if (idx > 0 && modelsForDisplay[idx - 1]) targetAnalysisKey = modelsForDisplay[idx - 1].key;
                else targetAnalysisKey = m.key;

                const targetAnalysisEl = document.getElementById(`model-analysis-${turnId}-${targetAnalysisKey}`);
                if (targetAnalysisEl) {
                  // 移除加载占位点（若存在），因为我们即将追加真实分析内容
                  const ld = targetAnalysisEl.querySelector('.loading-dots');
                  if (ld) try { ld.remove(); } catch (_) {}

                  const wrapper = document.createElement('div');
                  wrapper.className = 'appended-analysis';
                  try {
                    wrapper.innerHTML = (typeof marked !== 'undefined') ? marked.parse((parsed.analysis || '').toString()) : escapeHtml((parsed.analysis || '').toString());
                    targetAnalysisEl.appendChild(wrapper);
                    tryRenderMath(wrapper);
                  } catch (e) {
                    wrapper.textContent = (parsed.analysis || '').toString();
                    targetAnalysisEl.appendChild(wrapper);
                  }
                }
              }
            } catch (_) {}

            // opinion -> current column opinion (only if empty)
            try {
              if (parsed.opinion && opinionEl) {
                const hasExisting = opinionEl.innerHTML && opinionEl.innerHTML.trim() !== '';
                if (!hasExisting) {
                  renderMarkdownTo(opinionEl, (parsed.opinion || '').toString());
                }
              }
            } catch (_) { if (opinionEl && (!opinionEl.innerHTML || opinionEl.innerHTML.trim() === '')) opinionEl.textContent = (parsed.opinion || '').toString(); }

          } else {
            // 非结构化：按 stream 风格渲染到 opinion（仅在空时写入）
            try {
              const hasExisting = opinionEl && opinionEl.innerHTML && opinionEl.innerHTML.trim() !== '';
              if (opinionEl) {
                if (!hasExisting) renderMarkdownTo(opinionEl, contentText);
              } else if (uiMap[m.key]) {
                if (!hasExisting) renderMarkdownTo(uiMap[m.key], contentText);
              }
            } catch (_) { if (opinionEl && (!opinionEl.innerHTML || opinionEl.innerHTML.trim() === '')) opinionEl.textContent = contentText; }
          }
        } else {
          // 没有记录
          if (uiMap[m.key]) uiMap[m.key].innerHTML = `<span style="opacity:0.65;">该模型本轮未记录（旧数据/并发覆盖导致）。更新代码后新对话将完整保存。</span>`;
        }
      });

      // 如果后端返回了 messages_ 表的深度结果，仅把最终 deep 的 summary 追加到 console，
      // 并把最终 deep 的 analysis 追加到最后一列的 analysis（不覆盖已有内容）。
      if (Array.isArray(t._messages_) && t._messages_.length > 0) {
        try {
          if (modelsForDisplay && modelsForDisplay.length > 0) {
            // 选择 finalMsg：优先匹配 selected_models 的第一个模型（约定的最终调用者），否则选择第一个结构化结果或首条
            let finalMsg = null;
            const firstKey = (modelsForDisplay[0] && modelsForDisplay[0].key) ? modelsForDisplay[0].key.toString().toLowerCase() : null;
            if (firstKey) {
              finalMsg = t._messages_.find(m => (m.model_key || '').toString().toLowerCase() === firstKey);
            }
            if (!finalMsg) {
              finalMsg = t._messages_.find(m => m && m.is_structured && m.parsed) || t._messages_[0];
            }

            // 追加 final summary 到 console
            if (finalMsg && finalMsg.parsed && finalMsg.parsed.summary && consoleSummaryEl) {
              try {
                const item = document.createElement('div');
                item.className = 'console-summary-item';
                const index = (consoleSummaryEl.children && consoleSummaryEl.children.length) ? consoleSummaryEl.children.length + 1 : 1;
                item.innerHTML = `<b>观点${index}：</b>${escapeHtml((finalMsg.parsed.summary || '').toString())}`;
                consoleSummaryEl.appendChild(item);
              } catch (_) {}
            }

            // 追加 final analysis 到最后一列 analysis（append）
            if (finalMsg && finalMsg.parsed && finalMsg.parsed.analysis) {
              const lastKey = modelsForDisplay[modelsForDisplay.length - 1].key;
              const lastAnalysisEl = document.getElementById(`model-analysis-${turnId}-${lastKey}`);
              if (lastAnalysisEl) {
                // 移除加载占位点（若存在）
                const ld = lastAnalysisEl.querySelector('.loading-dots');
                if (ld) try { ld.remove(); } catch (_) {}

                try {
                  const wrap = document.createElement('div');
                  wrap.className = 'appended-analysis';
                  wrap.innerHTML = (typeof marked !== 'undefined') ? marked.parse((finalMsg.parsed.analysis || '').toString()) : escapeHtml((finalMsg.parsed.analysis || '').toString());
                  lastAnalysisEl.appendChild(wrap);
                  tryRenderMath(wrap);
                } catch (_) {
                  const wrap = document.createElement('div');
                  wrap.className = 'appended-analysis';
                  wrap.textContent = (finalMsg.parsed.analysis || '').toString();
                  lastAnalysisEl.appendChild(wrap);
                }
              }
            }
          }
        } catch (_) {}
      }
    });

    // 关键：历史渲染结束后，强制定位到“已摘选数据集”顶部
    requestAnimationFrame(() => {
      // 释放自动滚动锁（否则离开历史页后正常对话可能不滚动）
      suppressAutoScroll = false;
      scrollToDatasetTop();
    });
  }

  window.addEventListener('beforeunload', (e) => {
    if (hasUnsavedChanges) {
      e.preventDefault();
      e.returnValue = '摘选内容未提交，确定关闭吗？';
      return e.returnValue;
    }
  });

  async function init() {
    // 没 session 也不强制创建，首次对话时会创建；但为了体验也可以提前建
    if (!sessionId) {
      try {
        const r = await fetch('/api/session/new', { method: 'POST' });
        const j = await r.json();
        if (j.status === 'success') {
          sessionId = j.session_id;
          localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
        }
      } catch (_) { }
    }

    await loadHistory();

    await applyAdminVisibility();
    // 加载语义热点问句
    if (miniTrendingPanel) {
      loadMiniTrendingQuestions();
    }
    
    // 初始化公共聊天Socket连接
    if (isLoggedIn()) {
      ensurePublicSocket();
    }
    
    await loadMiniPublicMessages();
    
    // 初始化时隐藏热点榜单，只在进入公聊界面时显示
    if (hotBoard) {
      hotBoard.classList.add('hidden-panel');
    }
    
    // 加载弹幕数据（用于初始化）
    if (isLoggedIn()) {
      loadBarrageData();
    }
    
    // 弹幕按钮事件
    if (barrageToggleBtn) {
      barrageToggleBtn.addEventListener('click', toggleBarrage);
    }
    // 初始根据登录状态锁定输入与发送
    applyLoginLock();

    // 发送按钮事件由 attachSendHandlers() 统一注册

    // 主输入栏点击/聚焦时自动收起遮挡的侧边栏和抽屉
    function closeOverlappingPanels() {
      // 关闭项目抽屉
      if (projectDrawer && projectDrawer.classList.contains('open')) {
        toggleProjectDrawer(false);
      }
      // 如果左侧边栏遮挡了主输入栏，也关闭它（在窄窗口下）
      if (sidebarLeft && !sidebarLeft.classList.contains('hidden')) {
        const inputBoxRect = inputAreaWrapper?.getBoundingClientRect();
        const sidebarRect = sidebarLeft.getBoundingClientRect();
        if (inputBoxRect && sidebarRect && sidebarRect.right > inputBoxRect.left) {
          sidebarLeft.classList.add('hidden');
        }
      }
    }

    // 为主输入栏和输入区域添加点击和聚焦事件
    if (userPromptInput) {
      userPromptInput.addEventListener('click', closeOverlappingPanels);
      userPromptInput.addEventListener('focus', closeOverlappingPanels);
    }
    if (inputAreaWrapper) {
      inputAreaWrapper.addEventListener('click', (e) => {
        // 如果点击的是输入区域本身或输入框，则关闭遮挡的界面
        if (e.target === inputAreaWrapper || e.target.closest('.input-box')) {
          closeOverlappingPanels();
        }
      });
    }

    // 为主界面（main-area）添加点击事件，点击任意非次级页面部分时关闭次级页面
    const mainArea = document.querySelector('.main-area');
    if (mainArea) {
      mainArea.addEventListener('click', (e) => {
        // 如果点击的不是次级页面（project-drawer, sidebar-right, sidebar-left）或其子元素
        const target = e.target;
        const isSecondaryPage = target.closest('.project-drawer') || 
                                target.closest('.sidebar-right') || 
                                target.closest('.sidebar-left') ||
                                target.closest('#menu-toggle') ||
                                target.closest('#rightbar-toggle') ||
                                target.closest('.topbar');
        
        if (!isSecondaryPage) {
          closeOverlappingPanels();
        }
      });
    }
  }
  
  // ============ 弹幕数据加载 ============
  async function loadBarrageData() {
    try {
      const tz2 = (Intl.DateTimeFormat && Intl.DateTimeFormat().resolvedOptions && Intl.DateTimeFormat().resolvedOptions().timeZone) || '';
      const res = await fetch(tz2 ? `/api/trending/school?tz=${encodeURIComponent(tz2)}` : '/api/trending/school');
      if (!res.ok) return;
      
      const data = await res.json();
      if (data.status === 'success' && data.trending) {
        trendingCache = data.trending;
        barrageDataLoaded = true;
      }
    } catch (err) {
      console.error('加载弹幕数据失败:', err);
    }
  }
  
  // ============ 弹幕功能 ============
  function toggleBarrage() {
    if (!barrageDataLoaded || !trendingCache || trendingCache.length === 0) {
      showModal('提示', '暂无热点数据或数据加载中，请稍候');
      tryRenderMath(el);
      scrollToBottomIfAllowed();
    }
    
    barrageEnabled = !barrageEnabled;
    if (barrageToggleBtn) {
      barrageToggleBtn.classList.toggle('active', barrageEnabled);
    }
    
    if (barrageEnabled) {
      startBarrage();
    } else {
      stopBarrage();
    }
  }
  
  function startBarrage() {
    // 清除之前的定时器
    if (barrageInterval) {
      clearInterval(barrageInterval);
    }
    
    // 定时添加弹幕
    barrageInterval = setInterval(() => {
      if (!barrageEnabled || !trendingCache || trendingCache.length === 0) {
        clearInterval(barrageInterval);
        barrageInterval = null;
        return;
      }
      
      const randomItem = trendingCache[Math.floor(Math.random() * trendingCache.length)];
      addBarrageItem(randomItem);
    }, BARRAGE_CONFIG.interval);
  }
  
  function stopBarrage() {
    if (barrageInterval) {
      clearInterval(barrageInterval);
      barrageInterval = null;
    }
    const currentBarrageContainer = document.getElementById('barrage-container');
    if (currentBarrageContainer) {
      currentBarrageContainer.innerHTML = '';
    }
  }
  
  function addBarrageItem(item) {
    const currentBarrageContainer = document.getElementById('barrage-container');
    if (!currentBarrageContainer || !barrageEnabled) return;
    
    const barrageItem = document.createElement('div');
    barrageItem.className = 'barrage-item scrolling';
    barrageItem.textContent = `${item.content?.substring(0, 40)}...`;
    barrageItem.dataset.messageId = item.message_id;
    
    // 点击弹幕查看详情
    barrageItem.addEventListener('click', () => {
      // 转换时间为用户本地时区
      const displayTime = item.created_at_iso ? formatLocalTime(item.created_at_iso) : (item.created_at || '');
      showModal('热点消息详情', `
        <div style="text-align: left;">
          <p><strong>内容：</strong> ${escapeHtml(item.content)}</p>
          <p><strong>专业：</strong> ${escapeHtml(item.profession || '未知')}</p>
          <p><strong>学号：</strong> ${escapeHtml(item.user_id || '未知')}</p>
          <p><strong>时间：</strong> ${displayTime}</p>
          <p><strong>点赞：</strong> ${item.like_count || 0}</p>
        </div>
      `);
    });
    
    currentBarrageContainer.appendChild(barrageItem);
    
    // 动画完成后删除元素
    setTimeout(() => {
      barrageItem.remove();
    }, BARRAGE_CONFIG.duration);
  }

  init();

})
