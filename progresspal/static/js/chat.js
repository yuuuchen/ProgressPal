// 當整個頁面載入完成後再執行
document.addEventListener('DOMContentLoaded', () => {
    // 連接三個區域
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    // 連接兩個問題類型按鈕
    const directQuestionBtn = document.getElementById('direct-question-btn');
    const extendQuestionBtn = document.getElementById('extend-question-btn');
    //HTML元素
    const chatWrapper = document.getElementById('chat-wrapper'); 

    // 儲存最新情緒序列的變數 
    let EmotionSequence = []; 
    // 監聽來自 camera.js 的情緒序列更新事件
    window.addEventListener('emotionSequenceUpdate', (event) => {
        if (event.detail && Array.isArray(event.detail.sequence)) {
            EmotionSequence = event.detail.sequence;
        }
    });

    // 讀取章節和單元
    let chapterCode = 0; 
    let unitCode = 0;      
    if (chatWrapper) {
        chapterCode = chatWrapper.dataset.chapterCode || chapterCode; // 從 data 屬性讀取，若無則用預設
        unitCode = chatWrapper.dataset.unitCode || unitCode;       // 從 data 屬性讀取，若無則用預設
    } else {
        console.error("無法讀取章節/單元");
    }

    // 儲存使用者選擇的問題類型
    let selectedQuestionType = null;

    // 問題類型：直接提問
    directQuestionBtn.addEventListener('click', () => {
        selectedQuestionType = 'direct'; 
        // (可選) 提供視覺回饋，例如改變按鈕樣式
        directQuestionBtn.classList.add('active'); 
        extendQuestionBtn.classList.remove('active');
    });

    // 問題類型：延伸提問
    extendQuestionBtn.addEventListener('click', () => {
        selectedQuestionType = 'extended'; 
        extendQuestionBtn.classList.add('active');
        directQuestionBtn.classList.remove('active');
    });

    // 送出按鈕
    sendBtn.addEventListener('click', handleSendAttempt);
    chatInput.addEventListener('keydown', (event) => {
        // 只按enter也可以送出
        if (event.key === 'Enter' && !event.shiftKey) { 
            event.preventDefault();
            handleSendAttempt(); // 呼叫處理送出嘗試函式
        }
    });

    // 處理送出嘗試函式
    function handleSendAttempt() {
        const messageText = chatInput.value.trim();

        // 檢查問題類型是否選擇
        if (!selectedQuestionType) {
            return; 
        }
        // 檢查問題內容是否輸入
        if (!messageText) {
            return; 
        }

        // 如果檢查都輸入才真正呼叫 sendMessage
        sendMessage(messageText, selectedQuestionType);

        // 送出成功後的操作
        chatInput.value = ''; // 清空輸入框
        selectedQuestionType = null; 
        // 移除按鈕的 active 狀態
        directQuestionBtn.classList.remove('active');
        extendQuestionBtn.classList.remove('active');
    }

    // 送出訊息sendMessage
    async function sendMessage(messageText, questionType) {
        // 送出訊息
        appendMessage(messageText, 'user');
        const loadingElement = createMessageElement('assistant');
        loadingElement.textContent = '回應中...';
        chatHistory.appendChild(loadingElement);
        chatHistory.scrollTop = chatHistory.scrollHeight; // 捲動到底部

        try {
            // 傳送給後端的資料
            const payload = {
                question_choice: questionType, // direct/extended
                user_question: messageText,
                emotions: emotionSequence || [] // 直接傳送陣列
            };

            // fetch API發送請求
            const response = await fetch(`/lesson/${chaptercode}/${unitcode}/study/api/chat/`, { 
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', // 指定內容類型為 JSON
                    'X-CSRFToken': getCookie('csrftoken') 
                },
                body: JSON.stringify(payload)
            });

            // 收到回應
            chatHistory.removeChild(loadingElement); //移除回應中
            if (!response.ok) throw new Error(`伺服器錯誤! 狀態碼: ${response.status}`);
            // Json解析為 JavaScript 物件
            const data = await response.json();
            if (data.success && data.reply) {
                appendMessage(data.reply, 'assistant');
            } else {
                 throw new Error(data.error || '從伺服器收到無效的回應');
            }

        } catch (error) { // 捕捉錯誤
            console.error('聊天請求失敗:', error);
            if (loadingElement && loadingElement.parentNode === chatHistory) {
                chatHistory.removeChild(loadingElement);
            }
            appendMessage(`抱歉，發生錯誤: ${error.message}`, 'error');
        }
    }

    // 建立空的訊息元素(sender:user/assistant/error)
    function createMessageElement(sender) {
        const messageWrapper = document.createElement('div');
        messageWrapper.classList.add('message', `${sender}-message`);
        return messageWrapper;
    }
    
    // 將完成的訊息加到歷史紀錄(sender:user/assistant/error)
    function appendMessage(text, sender) {
        const messageElement = createMessageElement(sender);
        messageElement.textContent = text;
        chatHistory.appendChild(messageElement);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // 取得 Django 的 CSRF token
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
});
