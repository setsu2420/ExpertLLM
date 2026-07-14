document.addEventListener("DOMContentLoaded", function () {
    // 加载热点榜单（话题热点，暂时没用）
  async function loadTrending() {
    const trendingList = document.getElementById('trending-list');
    const trendingTitle = document.getElementById('trending-title');
    
    if (!trendingList) return;
    
    try {
      const tz = (Intl.DateTimeFormat && Intl.DateTimeFormat().resolvedOptions && Intl.DateTimeFormat().resolvedOptions().timeZone) || '';
      const res = await fetch(tz ? `/api/trending/school?tz=${encodeURIComponent(tz)}` : '/api/trending/school');
      const data = await res.json();
      
      if (data.status !== 'success') {
        trendingList.innerHTML = `<div class="trending-placeholder">加载失败：${data.content || '未知错误'}</div>`;
        return;
      }
      
      // 更新标题
      if (trendingTitle && data.school) {
        trendingTitle.textContent = `${data.school} · 昨日热点`;
      }
      
      trendingCache = data.trending || [];
      
      if (trendingCache.length === 0) {
        trendingList.innerHTML = `
          <div class="trending-empty">
            <div class="material-symbols-outlined">sentiment_satisfied</div>
            <div>昨天暂无热点消息</div>
          </div>
        `;
        return;
      }
      
      // 渲染榜单
      trendingList.innerHTML = '';
      trendingCache.forEach((item, index) => {
        const rank = index + 1;
        const rankClass = rank <= 3 ? `top${rank}` : '';
        
        const trendingItem = document.createElement('div');
        trendingItem.className = 'trending-item';
        trendingItem.dataset.messageId = item.message_id;
        
        trendingItem.innerHTML = `
          <div class="trending-header">
            <div class="trending-rank ${rankClass}">${rank}</div>
            <div class="trending-content">${escapeHtml(item.content)}</div>
          </div>
          <div class="trending-footer">
            <div class="trending-likes">
              <span class="material-symbols-outlined">favorite</span>
              <span>${item.like_count || 0}</span>
            </div>
          </div>
          <div class="trending-details">
            <div class="trending-detail-row">
              <span class="trending-detail-label">专业：</span>
              <span class="trending-detail-value">${escapeHtml(item.profession || '未知')}</span>
            </div>
            <div class="trending-detail-row">
              <span class="trending-detail-label">学号：</span>
              <span class="trending-detail-value">${escapeHtml(item.user_id || '未知')}</span>
            </div>
            <div class="trending-detail-row">
              <span class="trending-detail-label">时间：</span>
              <span class="trending-detail-value">${item.created_at_iso ? formatLocalTime(item.created_at_iso) : (item.created_at || '')}</span>
            </div>
          </div>
        `;
        
        // 点击展开/收起详情（互斥）
        trendingItem.onclick = (e) => {
          e.stopPropagation();
          const wasExpanded = trendingItem.classList.contains('expanded');
          // 先收起所有其他项
          document.querySelectorAll('.trending-item.expanded').forEach(item => {
            item.classList.remove('expanded');
          });
          // 如果当前项原本是收起的，则展开它
          if (!wasExpanded) {
            trendingItem.classList.add('expanded');
          }
        };
        
        trendingList.appendChild(trendingItem);
      });
      
    } catch (err) {
      console.error('加载热点榜单失败:', err);
      trendingList.innerHTML = `<div class="trending-placeholder">加载失败，请稍后重试</div>`;
    }
  }
});
