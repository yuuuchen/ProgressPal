// 當整個頁面載入完成後再執行
document.addEventListener("DOMContentLoaded", () => {
    const videoElement = document.getElementById('webcam'); // 攝影機即時畫面
    const canvasElement = document.getElementById('captureCanvas'); 
    const resultElement = document.getElementById('emotion-display'); // 情緒
    const context = canvasElement.getContext('2d');

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

            if (!response.ok) {
                console.warn(`API Error: ${response.status}`);
                return;
            }

            const data = await response.json();
            handleResponse(data);

        } catch (error) {
            console.error("Upload failed:", error);
        }
    }

    // 處理回應
    function handleResponse(data) {
        // 若後端回傳 error (如未偵測到臉)，不更新頁面
        if (data.error) {
            console.log("API message:", data.error); // 可在 Console 查看原因
            return; 
        }

        // 信心分數低於門檻不更新
        if (data.confidence < CONFIDENCE_THRESHOLD) {
            console.log(`Confidence too low: ${data.confidence} (Ignored)`);
            return;
        }

        // 信心分數高於門檻更新 
        updateUI(data.emotion, data.confidence);
    }

    // 更新情緒
    function updateUI(emotion, confidence) {
    const emotionImages = {
        "喜悅": "/static/images/emotions/delight.png",
        "困惑": "/static/images/emotions/confusion.png",
        "無聊": "/static/images/emotions/boredom.png",
        "挫折": "/static/images/emotions/frustration.png",
        "投入": "/static/images/emotions/flow.png",
        "驚訝": "/static/images/emotions/surprise.png",
        "unknown": "/static/images/emotions/neutral.png" 
    };

    // 取得對應的圖片路徑，若無對應則使用預設
    const imagePath = emotionImages[emotion] || emotionImages["unknown"];

    // 更新 HTML 內容，加入圖片顯示
    // 這裡使用 flex 佈局讓圖片和文字排版更好看
    resultElement.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="${imagePath}" alt="${emotion}" style="width: 50px; height: 50px; object-fit: contain;">
            <div>
                <span style="color: blue; font-size: 1.2em;">${emotion}</span> 
            </div>
        </div>
    `;

    console.log(`UI Updated: ${emotion} (${confidence}%)`);
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

    // 啟動程式
    initCamera();
});