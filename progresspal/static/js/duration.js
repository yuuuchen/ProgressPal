// duration.js

// 1. 取得 Django CSRF Token 的輔助函式
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// 2. 核心發送邏輯
async function sendDurationUpdate() {
    // 檢查 camera.js 傳過來的 unitStartTime 是否存在
    if (typeof unitStartTime === 'undefined') {
        console.warn("duration.js: 找不到 unitStartTime，請檢查 camera.js 是否已載入。");
        return;
    }

    const recordId = window.RECORD_ID;
    const endUrl = window.END_URL;

    if (recordId && endUrl) {
        const durationSeconds = Math.floor((Date.now() - unitStartTime) / 1000);
        
        try {
            await fetch(endUrl, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') 
                },
                body: JSON.stringify({ 
                    id: recordId, 
                    duration_seconds: durationSeconds 
                }),
                keepalive: true // 確保頁面切換時請求能發送完成
            });
            console.log(`存檔紀錄 (${recordId}) 成功: ${durationSeconds} 秒`);
        } catch (e) {
            console.warn("存檔失敗:", e);
        }
    }
}

// 3. 供 HTML 按鈕使用的跳轉函式
async function saveAndNavigate(targetUrl) {
    // 如果還沒送過結束紀錄，就在跳轉前送一次
    if (!window.HAS_SENT_RECORD) {
        await sendDurationUpdate();
        window.HAS_SENT_RECORD = true; // 避免跳轉中又觸發心跳
    }
    window.location.href = targetUrl;
}

// 4. 心跳機制：每 10 秒跑一次
function startHeartbeat() {
    setInterval(async () => {
        // 如果還沒執行跳轉存檔，就繼續跑心跳
        if (!window.HAS_SENT_RECORD) {
            await sendDurationUpdate();
        }
    }, 10000); 
}

// 頁面載入後啟動心跳
document.addEventListener("DOMContentLoaded", () => {
    startHeartbeat();
});

// 5. 終極備援：直接關閉分頁（不按按鈕）
window.addEventListener("pagehide", () => {
    if (!window.HAS_SENT_RECORD) {
        sendDurationUpdate();
    }
});