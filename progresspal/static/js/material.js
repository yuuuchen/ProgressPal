// 完全載入並解析完成後才執行
document.addEventListener('DOMContentLoaded', () => {
    const materialCard = document.getElementById('material-card');

    if (materialCard) {
        setTimeout(() => {
            // 教材淡入
            materialCard.classList.add('visible');
            
        }, 100); // 100 毫秒的延遲
        
    } else {
        console.warn('找不到 material-card');
    }
});
