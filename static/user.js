// 用户中心前端逻辑
document.addEventListener("DOMContentLoaded", function () {
    window.console.log("用户中心脚本已加载");
    
    // 菜单切换功能
    const menuToggle = document.getElementById('menu-toggle');
    const sidebarLeft = document.getElementById('sidebar-left');
    if (menuToggle && sidebarLeft) {
        menuToggle.addEventListener('click', function() {
            sidebarLeft.classList.toggle('hidden');
        });
    }
    
    // 左侧菜单切换
    document.querySelectorAll('.user-nav').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.user-nav').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const view = btn.getAttribute('data-view');
            document.querySelectorAll('.panel-section').forEach(sec => sec.classList.add('hidden-panel'));
            document.getElementById('view-' + view).classList.remove('hidden-panel');
            
            // 切换到历史记录时加载数据
            if (view === 'history') {
                loadHistoryRecords();
            }
        });
    });

    window.console.log("用户中心脚本已加载");
    // 1. 读取用户信息
    fetch('/api/user/profile').then(res => res.json()).then(data => {
        if (data.status === 'success' && data.user) {
            document.getElementById('profile-user-id').value = data.user.user_id || '';
            document.getElementById('profile-school').value = data.user.school || '';
            document.getElementById('profile-major').value = data.user.major || '';
            document.getElementById('profile-created-at').value = data.user.created_at || '';
        }
    });

    // 2. 修改密码
    const pwdForm = document.getElementById('change-password-form');
    if (pwdForm) {
        const profileNewPassword = document.getElementById('profile-new-password');
        const profilePasswordBar = document.getElementById('profile-password-strength-bar');
        const profilePasswordText = document.getElementById('profile-password-strength-text');

        function scorePassword(pw) {
            let score = 0;
            if (!pw) return 0;
            score += Math.min(40, pw.length * 2);
            if (/[a-z]/.test(pw)) score += 10;
            if (/[A-Z]/.test(pw)) score += 15;
            if (/\d/.test(pw)) score += 15;
            if (/[^A-Za-z0-9]/.test(pw)) score += 20;
            return Math.min(100, score);
        }

        function updateStrength(pw) {
            const s = scorePassword(pw);
            if (profilePasswordBar) profilePasswordBar.value = s;
            if (!pw) {
                if (profilePasswordText) profilePasswordText.textContent = '密码强度：—';
                return;
            }
            if (s < 40) {
                if (profilePasswordText) profilePasswordText.textContent = '密码强度：弱';
            } else if (s < 70) {
                if (profilePasswordText) profilePasswordText.textContent = '密码强度：中';
            } else {
                if (profilePasswordText) profilePasswordText.textContent = '密码强度：强';
            }
        }

        if (profileNewPassword) {
            profileNewPassword.addEventListener('input', function () { updateStrength(profileNewPassword.value); });
            // initialize
            updateStrength(profileNewPassword.value);
        }

        pwdForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const oldPassword = document.getElementById('profile-old-password').value.trim();
            const newPassword = document.getElementById('profile-new-password').value.trim();
            const statusEl = document.getElementById('profile-status');
            console.log('Changing password:', oldPassword, newPassword, statusEl);
            if (!oldPassword || !newPassword) {
                statusEl.textContent = '请输入原密码和新密码';
                return;
            }
            if (oldPassword === newPassword) {
                statusEl.textContent = '新密码不能与原密码相同';
                return;
            }
            // 前端简单检查：不允许空白字符且不超过 128
            if (/\s/.test(newPassword) || newPassword.length > 128) {
                statusEl.textContent = '新密码格式不正确，请不要包含空白字符，最长 128 字符';
                return;
            }
            statusEl.textContent = '提交中...';
            fetch('/api/user/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
            }).then(res => res.json()).then(data => {
                if (data.status === 'success') {
                    statusEl.textContent = '密码修改成功';
                } else {
                    statusEl.textContent = data.content || '密码修改失败';
                }
            }).catch(() => {
                statusEl.textContent = '网络错误';
            });
        });
    } else {
        console.warn('change-password-form not found in DOM');
    }

    // 3. 历史记录功能
    function loadHistoryRecords() {
        const historyListEl = document.getElementById('user-history-list');
        if (!historyListEl) return;
        
        historyListEl.innerHTML = '<div style="text-align: center; color: var(--text-sub); padding: 20px;">加载中...</div>';
        
        fetch('/user/history')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.projects && data.projects.length > 0) {
                    // 创建搜索框（如果不存在）
                    let searchContainer = document.getElementById('user-history-search-container');
                    if (!searchContainer) {
                        const viewHistory = document.getElementById('view-history');
                        if (viewHistory) {
                            searchContainer = document.createElement('div');
                            searchContainer.id = 'user-history-search-container';
                            searchContainer.style.marginBottom = '16px';
                            searchContainer.innerHTML = `
                                <input type="text" id="user-history-search-input" placeholder="搜索历史记录..." 
                                       style="width: 100%; padding: 10px 14px; background: var(--bg-color); 
                                              border: 1px solid var(--border-color); border-radius: 10px; 
                                              color: var(--text-main); font-size: 14px; font-family: inherit;" />
                            `;
                            viewHistory.insertBefore(searchContainer, historyListEl);
                            
                            // 添加搜索事件
                            const searchInput = document.getElementById('user-history-search-input');
                            if (searchInput) {
                                searchInput.addEventListener('input', (e) => {
                                    const keyword = e.target.value.trim().toLowerCase();
                                    filterAndRenderHistoryProjects(data.projects, keyword);
                                });
                            }
                        }
                    }
                    
                    // 获取搜索关键词
                    const searchInput = document.getElementById('user-history-search-input');
                    const keyword = searchInput ? searchInput.value.trim().toLowerCase() : '';
                    filterAndRenderHistoryProjects(data.projects, keyword);
                } else {
                    historyListEl.innerHTML = '<div style="text-align: center; color: var(--text-sub); padding: 20px;">暂无历史记录</div>';
                }
            })
            .catch(err => {
                console.error('加载历史记录失败:', err);
                historyListEl.innerHTML = '<div style="text-align: center; color: var(--danger-color); padding: 20px;">加载失败，请刷新重试</div>';
            });
    }

    function filterAndRenderHistoryProjects(projects, keyword) {
        const historyListEl = document.getElementById('user-history-list');
        if (!historyListEl) return;
        
        let filteredProjects = projects;
        if (keyword) {
            // 计算每个项目的关键词匹配度
            filteredProjects = projects.map(project => {
                const projectName = (project.project_name || '').toLowerCase();
                const username = (project.username || '').toLowerCase();
                let keywordCount = 0;
                
                // 在项目名称和用户名中搜索
                keywordCount += (projectName.match(new RegExp(keyword, 'g')) || []).length;
                keywordCount += (username.match(new RegExp(keyword, 'g')) || []).length;
                
                // 在对话内容中搜索
                if (project.turns && Array.isArray(project.turns)) {
                    project.turns.forEach(turn => {
                        const prompt = (turn.prompt || '').toLowerCase();
                        keywordCount += (prompt.match(new RegExp(keyword, 'g')) || []).length;
                        
                        if (turn.responses) {
                            Object.values(turn.responses).forEach(responses => {
                                if (Array.isArray(responses)) {
                                    responses.forEach(response => {
                                        if (response.content) {
                                            const content = response.content.toLowerCase();
                                            keywordCount += (content.match(new RegExp(keyword, 'g')) || []).length;
                                        }
                                    });
                                }
                            });
                        }
                    });
                }
                
                return { ...project, _keywordCount: keywordCount };
            }).filter(project => project._keywordCount > 0)
              .sort((a, b) => b._keywordCount - a._keywordCount);
        }
        
        if (filteredProjects.length === 0) {
            historyListEl.innerHTML = '<div style="text-align: center; color: var(--text-sub); padding: 20px;">未找到匹配的记录</div>';
            return;
        }
        
        renderHistoryProjects(filteredProjects);
    }

    function renderHistoryProjects(projects) {
        const historyListEl = document.getElementById('user-history-list');
        if (!historyListEl) return;
        
        historyListEl.innerHTML = '';
        
        projects.forEach((project, projectIdx) => {
            const projectEl = document.createElement('div');
            projectEl.className = 'user-history-project';
            
            const projectTitle = project.project_name || `项目 ${projectIdx + 1}`;
            const projectDate = project.updated_at || project.created_at || '';
            
            projectEl.innerHTML = `
                <div class="user-history-project-header">
                    <div class="user-history-project-title-row">
                        <span class="user-history-project-title">${escapeHtml(projectTitle)}</span>
                        <span class="user-history-project-date">${formatDate(projectDate)}</span>
                    </div>
                    ${project.turns && project.turns.length > 0 ? `
                        <div class="user-history-project-stats">共 ${project.turns.length} 轮对话</div>
                    ` : ''}
                </div>
                <div class="user-history-turns-container" id="turns-${projectIdx}"></div>
            `;
            
            historyListEl.appendChild(projectEl);
            
            // 添加折叠/展开功能
            const projectHeader = projectEl.querySelector('.user-history-project-header');
            if (projectHeader) {
                projectHeader.addEventListener('click', function() {
                    projectEl.classList.toggle('collapsed');
                });
            }
            
            // 渲染对话轮次
            const turnsContainer = projectEl.querySelector(`#turns-${projectIdx}`);
            if (project.turns && project.turns.length > 0) {
                project.turns.forEach((turn, turnIdx) => {
                    renderTurn(turnsContainer, turn, projectIdx, turnIdx);
                });
            } else {
                turnsContainer.innerHTML = '<div style="color: var(--text-sub); padding: 10px; font-size: 0.9em;">暂无对话内容</div>';
            }
        });
    }

    function renderTurn(container, turn, projectIdx, turnIdx) {
        const turnEl = document.createElement('div');
        turnEl.className = 'user-history-turn';
        
        const prompt = turn.prompt || '';
        const responses = turn.responses || {};
        const modelKeys = Object.keys(responses);
        
        let responsesHtml = '';
        if (modelKeys.length > 0) {
            modelKeys.forEach(modelKey => {
                const modelResponses = responses[modelKey] || [];
                modelResponses.forEach(response => {
                    if (response.role === 'assistant' && response.content) {
                        responsesHtml += `
                            <div class="user-history-response-item">
                                <div class="user-history-response-header">
                                    <span class="user-history-model-badge">${escapeHtml(modelKey.toUpperCase())}</span>
                                    <button class="copy-btn" data-copy="${escapeHtml(response.content)}" title="复制回答">
                                        <span class="material-symbols-outlined">content_copy</span>
                                    </button>
                                </div>
                                <div class="user-history-response-content">${formatMarkdown(response.content)}</div>
                            </div>
                        `;
                    }
                });
            });
        } else {
            responsesHtml = '<div class="user-history-response-empty">暂无回答</div>';
        }
        
        turnEl.innerHTML = `
            <div class="user-history-turn-header">
                <div class="user-history-question-row">
                    <span class="material-symbols-outlined user-history-icon">question_mark</span>
                    <span class="user-history-question-text">${escapeHtml(prompt)}</span>
                    <button class="copy-btn" data-copy="${escapeHtml(prompt)}" title="复制问题">
                        <span class="material-symbols-outlined">content_copy</span>
                    </button>
                </div>
                <span class="user-history-turn-date">${formatDate(turn.timestamp)}</span>
            </div>
            <div class="user-history-responses">
                ${responsesHtml}
            </div>
        `;
        
        container.appendChild(turnEl);
        
        // 默认收起回答区域，并绑定标题点击切换折叠
        try {
            const headerEl = turnEl.querySelector('.user-history-turn-header');
            const responsesEl = turnEl.querySelector('.user-history-responses');
            if (responsesEl) {
                // 默认折叠
                turnEl.classList.add('collapsed');
                // 点击标题切换
                if (headerEl) {
                    headerEl.style.cursor = 'pointer';
                    headerEl.addEventListener('click', (e) => {
                        // 阻止在点击复制按钮时触发折叠
                        if (e.target && e.target.closest && e.target.closest('.copy-btn')) return;
                        turnEl.classList.toggle('collapsed');
                    });
                }
            }
        } catch (_) {}

        // 绑定复制按钮事件
        turnEl.querySelectorAll('.copy-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const text = this.getAttribute('data-copy');
                copyToClipboard(text, this);
            });
        });
    }

    function copyToClipboard(text, buttonEl) {
        if (!text) return;
        
        // 优先使用现代 Clipboard API
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                showCopySuccess(buttonEl);
            }).catch(err => {
                console.error('复制失败:', err);
                fallbackCopy(text, buttonEl);
            });
        } else {
            // 回退到传统方法
            fallbackCopy(text, buttonEl);
        }
    }

    function fallbackCopy(text, buttonEl) {
        // 创建临时textarea元素
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        textarea.setSelectionRange(0, 99999); // 移动设备支持
        
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                showCopySuccess(buttonEl);
            } else {
                alert('复制失败，请手动选择文本复制');
            }
        } catch (err) {
            console.error('复制失败:', err);
            alert('复制失败，请手动选择文本复制');
        } finally {
            document.body.removeChild(textarea);
        }
    }

    function showCopySuccess(buttonEl) {
        const originalHTML = buttonEl.innerHTML;
        buttonEl.innerHTML = '<span class="material-symbols-outlined">check</span>';
        buttonEl.style.color = 'var(--accent-color)';
        setTimeout(() => {
            buttonEl.innerHTML = originalHTML;
            buttonEl.style.color = '';
        }, 1500);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr);
            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return dateStr;
        }
    }

    function formatMarkdown(text) {
        if (!text) return '';
        // 简单的markdown渲染（保留换行，处理代码块）
        let html = escapeHtml(text);
        // 处理换行（保留连续换行）
        html = html.replace(/\n\n+/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');
        if (!html.startsWith('<p>')) {
            html = '<p>' + html + '</p>';
        }
        // 处理代码块 ```...```
        html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        // 处理行内代码 `...`
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        return html;
    }
});
