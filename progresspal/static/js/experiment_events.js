// 實驗事件紀錄：把前端發生的事件送到後端 EventLog（見 docs/SPEC_實驗資料與部署.md R5）
// 用法：window.logExperimentEvent('hint_click', { source: 'manual' })
(function () {
    function getCookie(name) {
        const match = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith(name + '='));
        return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
    }

    // 從網址 /lesson/<章>/<單元>/... 取出目前的章節與單元
    function currentUnit() {
        const m = window.location.pathname.match(/\/lesson\/(\d+)\/(\d+)\//);
        return m ? { chapter_code: m[1], unit_code: m[2] } : {};
    }

    window.logExperimentEvent = function (eventType, detail) {
        try {
            fetch('/events/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify(Object.assign({ event_type: eventType, detail: detail || {} }, currentUnit())),
                keepalive: true, // 即使正要離開頁面也送得出去
            }).catch(err => console.warn('事件紀錄失敗：', eventType, err));
        } catch (err) {
            console.warn('事件紀錄失敗：', eventType, err);
        }
    };

    // navbar 的表單連結（data-form-link="pretest" / "posttest"）
    document.addEventListener('click', function (event) {
        const link = event.target.closest && event.target.closest('a[data-form-link]');
        if (link) {
            window.logExperimentEvent('form_link_click', { form: link.dataset.formLink });
        }
    });
})();
