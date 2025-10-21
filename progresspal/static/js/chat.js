// 當整個頁面載入完成後再執行
document.addEventListener('DOMContentLoaded', () => {
    // 連接三個區域
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    // 點擊送出按鈕執行 sendMessage
    sendBtn.addEventListener('click', sendMessage);
    // 按下 Enter 鍵送出訊息
    chatInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // 防止換行
            sendMessage();
        }
    });

    // 送出訊息sendMessage
    async function sendMessage() {
        const messageText = chatInput.value.trim(); //取得輸入的文字
        if (messageText === '') return;

        // 在畫面上顯示使用者自己的訊息
        appendMessage(messageText, 'user');
        chatInput.value = ''; //清空輸入框

        // 建立一個空的 AI 回覆訊息框接收串流內容
        const assistantMessageElement = createMessageElement('assistant');
        chatHistory.appendChild(assistantMessageElement);
        // 確保畫面捲動到最下方
        chatHistory.scrollTop = chatHistory.scrollHeight;

        try {
            // 發送 Fetch 請求到後端的串流 API
            const response = await fetch('/learning/api/chat/stream/', { // 注意 URL 不同
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ message: messageText }),
            });

            if (!response.ok) {
                throw new Error(`HTTP 錯誤! 狀態: ${response.status}`);
            }

            // 處理串流回應
            const reader = response.body.getReader();
            const decoder = new TextDecoder(); // 用來將接收到的 Uint8Array 轉成文字

            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    break;
                }
                // 將收到的每一小段文字即時附加到訊息框中
                const chunk = decoder.decode(value);
                assistantMessageElement.textContent += chunk;
                // 捲動畫面
                chatHistory.scrollTop = chatHistory.scrollHeight;
            }

        } catch (error) {
            console.error('串流請求失敗:', error);
            assistantMessageElement.textContent = '抱歉，連線時發生錯誤。';
            assistantMessageElement.classList.add('error'); 
        }
    }

    // 建立訊息元素
    function createMessageElement(sender) {
        const messageWrapper = document.createElement('div');
        messageWrapper.classList.add('message', `${sender}-message`);
        return messageWrapper;
    }
    
    // 將完成的訊息附加到歷史紀錄
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
