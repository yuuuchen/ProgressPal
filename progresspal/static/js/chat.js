// 當整個頁面載入完成後再執行
document.addEventListener('DOMContentLoaded', () => {
    // 連接三個區域
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    // 連接兩個問題類型按鈕
    const directQuestionBtn = document.getElementById('direct-question-btn');
    const extendQuestionBtn = document.getElementById('extend-question-btn');

    // 儲存使用者選擇的問題類型
    let selectedQuestionType = null;

    // 問題類型：直接提問
    directQuestionBtn.addEventListener('click', () => {
        selectedQuestionType = 'direct'; 
        directQuestionBtn.classList.add('active'); 
        extendQuestionBtn.classList.remove('active');
        clearError();
    });

    // 問題類型：延伸提問
    extendQuestionBtn.addEventListener('click', () => {
        selectedQuestionType = 'extended'; 
        extendQuestionBtn.classList.add('active');
        directQuestionBtn.classList.remove('active');
        clearError();
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

        // 清除舊的錯誤提示
        clearError();

        // 檢查問題類型是否選擇
        if (!selectedQuestionType) {
            showError("請先點選『提問』或『回應延伸題目』按鈕");
            return; 
        }
        // 檢查問題內容是否輸入
        if (!messageText) {
            showError("請在下方輸入框輸入您的問題");
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
                question: messageText,
            };

            // fetch API發送請求
            const response = await fetch(`api/chat/`, { 
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', // 指定內容類型為 JSON
                    'X-CSRFToken': getCookie('csrftoken') 
                },
                body: JSON.stringify(payload)
            });

            // 收到回應
            chatHistory.removeChild(loadingElement); //移除回應中
            // Json解析為 JavaScript 物件
            const data = await response.json();
            if (data.answer) {
                appendMessage(data.answer, 'assistant');
                appendMessage(data.extended_questions, 'assistant');

                if (data.extended_questions) {
                    appendMessage(data.extended_questions, 'assistant');
                }
            } else {
                 throw new Error('從伺服器收到無效的回應');
            }

        } catch (error) { // 捕捉錯誤
            console.error('聊天請求失敗:', error);
            if (loadingElement && loadingElement.parentNode === chatHistory) {
                chatHistory.removeChild(loadingElement);
            }
            showError(`抱歉，發生錯誤: ${error.message}`);
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

    // 顯示會錯誤訊息
    function showError(message) {
        // 建立錯誤元素
        const errorElement = createMessageElement('error');
        errorElement.textContent = message;
        
        // 附加到聊天記錄
        chatHistory.appendChild(errorElement);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        // 設定 5 秒後自動移除
        setTimeout(() => {
            if (errorElement.parentNode === chatHistory) {
                // (可選) 加上淡出效果
                errorElement.style.transition = 'opacity 0.5s ease';
                errorElement.style.opacity = '0';
                setTimeout(() => {
                    if (errorElement.parentNode === chatHistory) {
                        chatHistory.removeChild(errorElement);
                    }
                }, 500); // 等淡出動畫 0.5 秒
            }
        }, 5000); // 5000 毫秒 = 5 秒
    }

    // 立即清除所有現存的錯誤訊息
    function clearError() {
        const existingErrors = chatHistory.querySelectorAll('.error-message');
        existingErrors.forEach(errorEl => {
            chatHistory.removeChild(errorEl);
        });
    }
});
