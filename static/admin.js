// Admin page behaviors and API calls
(function() {
  const d = document;

  const adminTableBody = () => d.querySelector('#admin-table tbody');
  const adminStatusEl = () => d.getElementById('admin-status');
  const addAdminBtn = () => d.getElementById('add-admin-btn');
  const addAdminStatusEl = () => d.getElementById('add-admin-status');
  const projectTableBody = () => d.querySelector('#project-table tbody');
  const projectStatusEl = () => d.getElementById('project-status');
  const exportBtn = () => d.getElementById('export-projects');

  const viewAdmin = () => d.getElementById('view-admin');
  const viewProjects = () => d.getElementById('view-projects');
  const sidebarButtons = () => Array.from(d.querySelectorAll('.admin-nav'));
  let IS_ADMIN = false;
  let projectCache = [];

  function setupMenuToggle() {
    const toggle = d.getElementById('menu-toggle');
    const left = d.getElementById('sidebar-left');
    if (!toggle || !left) return;
    toggle.addEventListener('click', () => {
      left.classList.toggle('hidden');
    });
  }

  async function fetchJSON(url, opts = {}) {
    const resp = await fetch(url, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
    let data;
    try { data = await resp.json(); } catch { data = {}; }
    if (!resp.ok || data.status !== 'success') {
      const msg = data.content || '请求失败';
      throw new Error(msg);
    }
    return data;
  }

  async function fetchAdminStatus() {
    try {
      const data = await fetchJSON('/admin/api/status');
      IS_ADMIN = !!data.is_admin;
      // 禁用“查询数据”按钮（无管理员权限）
      const projBtn = d.querySelector('.admin-nav[data-view="projects"]');
      if (projBtn && !IS_ADMIN) {
        projBtn.setAttribute('aria-disabled', 'true');
        projBtn.classList.add('disabled');
      }
    } catch (_) {
      IS_ADMIN = false;
    }
  }

  async function loadAdmins() {
    const status = adminStatusEl();
    const tbody = adminTableBody();
    if (status) status.textContent = '加载中...';
    if (tbody) tbody.innerHTML = '<tr><td colspan="3">加载中...</td></tr>';
    try {
      const data = await fetchJSON('/admin/api/admins');
      if (tbody) {
        if (!data.admins || data.admins.length === 0) {
          tbody.innerHTML = '<tr><td colspan="3">暂无管理员</td></tr>';
        } else {
          tbody.innerHTML = data.admins.map(a => {
            const t = a.created_at_iso ? new Date(a.created_at_iso).toLocaleString() : '';
            return `<tr><td>${a.user_id}</td><td><span class="badge">${a.level}</span></td><td>${t}</td></tr>`;
          }).join('');
        }
      }
      if (status) status.textContent = '';
      if (status) status.classList.remove('err');
    } catch (e) {
      if (status) {
        status.textContent = e.message;
        status.classList.add('err');
      }
    }
  }

  async function addAdmin() {
    const userId = (d.getElementById('new-admin-id')?.value || '').trim();
    const levelStr = d.getElementById('new-admin-level')?.value || '1';
    const level = parseInt(levelStr, 10);
    const password = d.getElementById('current-admin-password')?.value || '';
    const status = addAdminStatusEl();
    if (!userId || !password) {
      if (status) {
        status.textContent = '请填写目标 user_id 和当前管理员密码';
        status.classList.add('err');
      }
      return;
    }
    if (status) {
      status.textContent = '提交中...';
      status.classList.remove('err');
    }
    try {
      await fetchJSON('/admin/api/admins', { method: 'POST', body: JSON.stringify({ user_id: userId, level, password }) });
      if (status) status.textContent = '添加成功';
      const idEl = d.getElementById('new-admin-id');
      const pwdEl = d.getElementById('current-admin-password');
      if (idEl) idEl.value = '';
      if (pwdEl) pwdEl.value = '';
      await loadAdmins();
    } catch (e) {
      if (status) {
        status.textContent = e.message;
        status.classList.add('err');
      }
    }
  }

  function projectExpertCell(p, idx) {
    const preview = (p.expert_preview || '').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    const full = (p.expert_data || '').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    const rowId = `exp-${idx}`;
    return `
      <div>
        <div class="one-line" title="${preview}">${preview || '<span class="muted">无</span>'}</div>
        ${full ? `<button class="ghost-btn" data-toggle-exp="${rowId}" style="margin-top:6px;">查看全部</button>` : ''}
        <pre id="${rowId}" class="hidden-panel" style="margin-top:8px; white-space: pre-wrap; word-break: break-word;">${full}</pre>
      </div>
    `;
  }

  function attachExpertToggles(container) {
    container.querySelectorAll('[data-toggle-exp]')?.forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-toggle-exp');
        const pre = d.getElementById(id);
        if (!pre) return;
        pre.classList.toggle('hidden-panel');
        btn.textContent = pre.classList.contains('hidden-panel') ? '查看全部' : '收起';
      });
    });
  }

  async function loadProjects() {
    const limitStr = d.getElementById('project-limit')?.value || '50';
    const limit = parseInt(limitStr, 10);
    const status = projectStatusEl();
    const tbody = projectTableBody();
    if (status) status.textContent = '加载中...';
    if (tbody) tbody.innerHTML = '<tr><td colspan="6">加载中...</td></tr>';
    projectCache = [];
    updateExportState();
    try {
      const data = await fetchJSON(`/admin/api/projects?limit=${limit}`);
      projectCache = data.projects || [];
      if (tbody) {
        if (!projectCache.length) {
          tbody.innerHTML = '<tr><td colspan="6">暂无数据</td></tr>';
        } else {
          tbody.innerHTML = projectCache.map((p, idx) => {
            const ts = p.updated_at_iso ? new Date(p.updated_at_iso).toLocaleString() : '';
            return `<tr>
              <td>${p.project_id}</td>
              <td>${p.project_name || ''}</td>
              <td>${p.user_id || ''}</td>
              <td>${ts}</td>
              <td>${p.turn_count || 0}</td>
              <td>${projectExpertCell(p, idx)}</td>
            </tr>`;
          }).join('');
          attachExpertToggles(tbody);
        }
      }
      if (status) status.textContent = '';
      if (status) status.classList.remove('err');
      updateExportState();
    } catch (e) {
      if (status) {
        status.textContent = e.message;
        status.classList.add('err');
      }
      projectCache = [];
      updateExportState();
    }
  }

  function updateExportState() {
    const btn = exportBtn();
    if (!btn) return;
    const disabled = !projectCache || projectCache.length === 0;
    btn.disabled = disabled;
    btn.title = disabled ? '无可导出的数据' : '导出当前查询结果';
  }

  function exportProjects() {
    if (!projectCache || projectCache.length === 0) return;
    const header = ['project_id', 'project_name', 'user_id', 'updated_at_iso', 'turn_count', 'expert_preview'];
    const escape = (v) => {
      const s = (v ?? '').toString().replace(/"/g, '""');
      return `"${s}"`;
    };
    const rows = projectCache.map(p => [
      p.project_id,
      p.project_name || '',
      p.user_id || '',
      p.updated_at_iso || p.updated_at || '',
      p.turn_count ?? '',
      (p.expert_preview || '').replace(/\s+/g, ' ').trim()
    ]);
    const csv = [header.map(escape).join(','), ...rows.map(r => r.map(escape).join(','))].join('\r\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = d.createElement('a');
    a.href = url;
    a.download = 'projects.csv';
    d.body.appendChild(a);
    a.click();
    d.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function switchView(view) {
    if (view === 'projects' && !IS_ADMIN) {
      const status = projectStatusEl();
      if (status) {
        status.textContent = '需要管理员权限。请先在“添加管理员”中使用你的账号密码自举成为首位管理员。';
        status.classList.add('err');
      }
      return;
    }
    sidebarButtons().forEach(btn => btn.classList.toggle('active', btn.dataset.view === view));
    const adminView = viewAdmin();
    const projView = viewProjects();
    if (!adminView || !projView) return;
    if (view === 'projects') {
      adminView.classList.add('hidden-panel');
      projView.classList.remove('hidden-panel');
      loadProjects();
    } else {
      adminView.classList.remove('hidden-panel');
      projView.classList.add('hidden-panel');
    }
  }

  function setupSidebarNav() {
    sidebarButtons().forEach(btn => btn.addEventListener('click', () => switchView(btn.dataset.view)));
    addAdminBtn()?.addEventListener('click', addAdmin);
    d.getElementById('refresh-projects')?.addEventListener('click', loadProjects);
    exportBtn()?.addEventListener('click', exportProjects);
    updateExportState();
  }

  d.addEventListener('DOMContentLoaded', async () => {
    setupMenuToggle();
    setupSidebarNav();
    await fetchAdminStatus();
    loadAdmins();
    switchView('admin');
  });
})();
