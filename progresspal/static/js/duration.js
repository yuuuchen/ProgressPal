// duration.js
// 必須由 HTML 裡的 <script> 注入 RECORD_ID 與 END_URL

window.addEventListener("beforeunload", function () {
    if (!window.RECORD_ID || !window.END_URL) {
        console.warn("duration.js missing RECORD_ID or END_URL");
        return;
    }

    const data = JSON.stringify({
        id: window.RECORD_ID
    });

    // sendBeacon 是非同步但保證會送出
    navigator.sendBeacon(window.END_URL, data);
});
