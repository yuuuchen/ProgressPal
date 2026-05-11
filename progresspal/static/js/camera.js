// 當整個頁面載入完成後再執行
document.addEventListener("DOMContentLoaded", () => {
    const videoElement = document.getElementById('webcam'); // 攝影機即時畫面
    const canvasElement = document.getElementById('captureCanvas'); 
    const resultElement = document.getElementById('emotion-display'); // 情緒
    const context = canvasElement.getContext('2d');
    //const unitStartTime = Date.now();  // 紀錄進入單元的初始時間
    window.unitStartTime = Date.now();  // 綁定到 window 變成全域變數

    // 設定參數
    const INTERVAL_MS = 5000; // 5秒
    const CONFIDENCE_THRESHOLD = 0.5; // 信心門檻

    // 啟動 Webcam
    async function initCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true }); // 請求使用者的攝影機權限
            videoElement.srcObject = stream;
            
            // 確保影片載入後開始定時截圖
            videoElement.onloadedmetadata = () => {
                console.log("Webcam started.");
                setInterval(captureAndSend, INTERVAL_MS); // 每5秒呼叫一次
            };
        } catch (err) {
            console.error("無法存取 Webcam:", err);
            resultElement.innerText = "無法存取攝影機，請檢查權限。";
        }
    }

    // 截圖並傳給後端
    function captureAndSend() {
        // 確保有畫面
        if (videoElement.videoWidth === 0 || videoElement.videoHeight === 0) return;

        // 設定 Canvas 大小與 Video 一致
        canvasElement.width = videoElement.videoWidth;
        canvasElement.height = videoElement.videoHeight;

        // 將當前 Video 畫面繪製到 Canvas
        context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);

        // 轉為 Blob (JPG)
        canvasElement.toBlob((blob) => {
            if (blob) {
                uploadImage(blob); 
            }
        }, 'image/jpeg', 0.7); // 圖片品質
    }

    // 上傳圖片至 API
    async function uploadImage(imageBlob) {
        const formData = new FormData();
        formData.append('image', imageBlob, 'snapshot.jpg');

        try {
            const response = await fetch(`/emotion/detect/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')  // CSRF Token
                },
                body: formData // Content-Type 為 multipart/form-data
            });

            let data;
            try {
                data = await response.json();
            } catch (e) {
                console.error("無法解析回應 (可能不是 JSON):", e);
                return;
            }

            if (!response.ok) {
                console.warn(`API Error: ${response.status}`, data.error);
                return;
            }

            handleResponse(data);

        } catch (error) {
            console.error("Upload failed:", error);
        }
    }

    // 處理回應
    function handleResponse(data) {
        if (data.error) return;
        updateUI(data.emotion, data.engagement);
        console.log(`後端已接收情緒：${data.emotion}, 參與度：${data.engagement}`);
        
    }

    // 更新學習時間
    function updateUI(emotion, engagement,showTip = true) {

    const timerHTML = `<div id="live-study-timer" style="color: #09384e; font-size:16px; font-weight: bold; flex-grow: 1; text-align: right; padding-right: 20px;">
                        ${getFormattedDuration()}
                        </div>`;

    resultElement.innerHTML = `
        <div style="display: flex; align-items: center; gap: 15px; width: 100%;">
            ${timerHTML}
        </div>
    `;

    }


    // Django CSRF
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

    // 轉換為 hh:mm:ss 格式的函式
    function getFormattedDuration() {
        //const diff = Date.now() - unitStartTime;
        const diff = Date.now() - window.unitStartTime;
        const seconds = Math.floor((diff / 1000) % 60);
        const minutes = Math.floor((diff / (1000 * 60)) % 60);
        const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);

        const h = hours > 0 ? `${hours.toString().padStart(2, '0')}:` : "";
        const m = minutes.toString().padStart(2, '0');
        const s = seconds.toString().padStart(2, '0');
        
        return `單元學習時間：${h}${m}:${s}`;
    }

    // 每秒更新一次計時器文字
    setInterval(() => {
        const timerElement = document.getElementById('live-study-timer');
        if (timerElement) {
            timerElement.innerText = getFormattedDuration();
        }
    }, 1000);

    updateUI();
    // 啟動程式
    initCamera();


});