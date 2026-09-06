// 完全載入並解析完成後才執行
document.addEventListener('DOMContentLoaded', () => {
    const materialCard = document.getElementById('material-card');

    if (materialCard) {
        const contentAreas = materialCard.querySelectorAll('.markdown-render');

        contentAreas.forEach(area => {
            // 取得後端傳來的原始字串 (textContent 會抓取純文字，無視 HTML 標籤)
            const rawMarkdown = area.textContent.trim();

            if (rawMarkdown) {
                // 使用 marked.js 將原始文字解析為 HTML 並重新注入
                area.innerHTML = marked.parse(rawMarkdown);
            }
        });

        // 如果你的 base.html 有引入 highlight.js，則觸發高亮，讓 Python 代碼變漂亮
        if (window.hljs) {
            hljs.highlightAll();
        }
        
        setTimeout(() => {
            // 教材淡入
            materialCard.classList.add('visible');
            
        }, 100); // 100 毫秒的延遲
        
    } else {
        console.warn('找不到 material-card');
    }
});
