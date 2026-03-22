// 當整個頁面載入完成後再執行
document.addEventListener("DOMContentLoaded", () => {
    const videoElement = document.getElementById('webcam'); // 攝影機即時畫面
    const canvasElement = document.getElementById('captureCanvas'); 
    const resultElement = document.getElementById('emotion-display'); // 情緒
    const context = canvasElement.getContext('2d');
    let lowEngagementCounter = 0;  // 追蹤低參與度
    const PROACTIVE_THRESHOLD = 7; // 連續 5 次低參與度就觸發訊息
    const unitStartTime = Date.now();  // 紀錄進入單元的初始時間

    // 設定參數
    const INTERVAL_MS = 5000; // 5秒
    const CONFIDENCE_THRESHOLD = 0.5; // 信心門檻

    //初始情緒
    let initialEmotion = resultElement.getAttribute('data-initial-emotion');
    console.log("偵測到初始情緒屬性值:", initialEmotion);

    const startEmotion = (initialEmotion && initialEmotion !== "None" && initialEmotion !== "") 
                         ? initialEmotion 
                        : "偵測中";

    updateUI(startEmotion, 0.5, false);

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
        // 若後端回傳 error (如未偵測到臉)，不更新頁面
        if (data.error) {
            console.log("API message:", data.error); // 可在 Console 查看原因
            return; 
        }

        // 信心分數低於門檻不更新
        if (data.confidence < CONFIDENCE_THRESHOLD) {
            console.log(`Confidence too low: ${data.confidence}`);
            return;
        }

        // 計算低參與度次數
        if (data.engagement === "low") {
            lowEngagementCounter++;
            if (lowEngagementCounter === PROACTIVE_THRESHOLD) {
                sendProactiveMessage(); // 觸發主動關懷
                lowEngagementCounter = 0;
            }
        } else {
            lowEngagementCounter = 0; // 觸發後重置次數
        }

        // 信心分數高於門檻更新 
        console.log(`Engagement: ${data.engagement} `);
        console.log(`lowEngagementCounter: ${lowEngagementCounter} `);
        updateUI(data.emotion, data.engagement);
        
    }

    // 更新情緒
    function updateUI(emotion, engagement,showTip = true) {
    const emotionImages = {
        "喜悅": "/static/images/emotions/delight.png",
        "困惑": "/static/images/emotions/confusion.png",
        "無聊": "/static/images/emotions/boredom.png",
        "挫折": "/static/images/emotions/frustration.png",
        "投入": "/static/images/emotions/flow.png",
        "驚訝": "/static/images/emotions/surprise.png",
    };
    
    // 取得對應的圖片路徑
    let imageHTML = ''; // 預設為空字串
    const imagePath = emotionImages[emotion];
    // 只有當 emotionImages 裡有定義該情緒，且該情緒不是 "偵測中" 時才生成 <img>
    if (emotion !== "偵測中" && emotion !== "未知" && imagePath) {
        imageHTML = `<img src="${imagePath}" alt="${emotion}" style="width: 50px; height: 50px; flex-shrink: 0; border-radius: 50%;">`;
    }
    const timerHTML = `<div id="live-study-timer" style="color: #09384e; font-size:16px; font-weight: bold; flex-grow: 1; text-align: right; padding-right: 20px;">
                        ${getFormattedDuration()}
                        </div>`;

    resultElement.innerHTML = `
        <div style="display: flex; align-items: center; gap: 15px; width: 100%;">
            ${imageHTML}
            <div style="color: black; font-size: 16px; font-weight: bold; white-space: nowrap;">
                情緒：${emotion}
            </div>
            ${timerHTML}
        </div>
    `;

    }

    // 主動傳送關懷訊息至問答區
    function sendProactiveMessage() {
        const chatHistory = document.getElementById('chat-history');
        if (!chatHistory) return;

        const phrases = [
            "發現你好像有點累了，要不要休息 5 分鐘再繼續？休息是為了走更長遠的路喔！",
            "這部分的內容可能比較艱深，如果感到挫折是正常的。別擔心慢慢來！",
            "深呼吸一下，動一動脖子，補充水分能讓大腦更清醒喔！"
        ];
        const randomMessage = phrases[Math.floor(Math.random() * phrases.length)];

        // 建立訊息元素
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant-message proactive-caring'; // 加入自定義類別以便後續美化
        msgDiv.innerHTML = `<strong>💡小提醒：</strong><br>${randomMessage}`;

        // 插入聊天室並自動捲動到底部
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
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
        const diff = Date.now() - unitStartTime;
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

    // 啟動程式
    initCamera();


});