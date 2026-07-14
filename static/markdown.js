// markdown.js - Markdown 渲染与公式高亮工具
// 依赖 marked、highlight.js、KaTeX（auto-render）

// marked 配置：代码高亮
if (typeof marked !== 'undefined' && typeof hljs !== 'undefined') {
  marked.setOptions({
    highlight: function (code, lang) {
      const language = hljs.getLanguage(lang) ? lang : 'plaintext';
      return hljs.highlight(code, { language }).value;
    },
    langPrefix: 'hljs language-'
  });
}

// 公式渲染
function tryRenderMath(el) {
  if (!el) return;
  if (typeof renderMathInElement !== 'function') return;
  try {
    renderMathInElement(el, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '\\[', right: '\\]', display: true },
        { left: '$', right: '$', display: false },
        { left: '\\(', right: '\\)', display: false }
      ],
      throwOnError: false
    });
  } catch (e) {}
}

// 通用渲染函数：将 mdText 渲染到 el，并自动高亮/公式
function renderMarkdownTo(el, mdText) {
  if (!el) return;
  if (typeof marked === 'undefined') {
    el.innerText = mdText;
    return;
  }
  el.innerHTML = marked.parse(mdText || '');
  tryRenderMath(el);
}

// 导出
window.renderMarkdownTo = renderMarkdownTo;
window.tryRenderMath = tryRenderMath;
