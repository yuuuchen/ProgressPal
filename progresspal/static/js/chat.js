// 當整個頁面載入完成後再執行
document.addEventListener('DOMContentLoaded', () => {
    // 連接三個區域
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatSection = document.getElementById('chat-section-wrapper');
    
    // 連接問題類型按鈕
    const directQuestionBtn = document.getElementById('direct-question-btn');
    const extendQuestionBtn = document.getElementById('extend-question-btn');
    
    
    // 預設為未使用提示
    window.HINT_USED = false;

    // 儲存使用者選擇的問題類型
    let selectedQuestionType = null;

    // 解析頁面載入時的初始延伸提問 
    const initialQuestionDiv = document.querySelector('.initial-extended-question');
    if (initialQuestionDiv) {
        const rawText = initialQuestionDiv.textContent.trim();
        if (rawText) {
            initialQuestionDiv.innerHTML = marked.parse(rawText);
        }
    }
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

        if (chatSection && !chatSection.classList.contains('fullscreen-active')) {
            // 直接呼叫全螢幕切換函數 (需確保函數可存取)
            toggleFullscreenUI(); 
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
        loadingElement.textContent = '思考中...';
        chatHistory.appendChild(loadingElement);
        chatHistory.scrollTop = chatHistory.scrollHeight; // 捲動到底部

        try {
            // 傳送給後端的資料
            const payload = {
                question_choice: questionType, // direct/extended
                user_question: messageText,
                hint_is_used: window.HINT_USED,
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
                let extendedText = `<strong>延伸提問：</strong>\n${data.extended_questions}`;
                appendMessage(extendedText, 'assistant', 'extended-mode');
            
            if (data.hint) {
                window.LATEST_HINT = data.hint;
                console.log("提示文字已暫存：", window.LATEST_HINT);
            }

            } else {
                 throw new Error('從伺服器收到無效的回應');
            }

            // 成功傳送後重置狀態
            window.HINT_USED = false;

        } catch (error) { // 捕捉錯誤
            console.error('聊天請求失敗:', error);
            if (loadingElement && loadingElement.parentNode === chatHistory) {
                chatHistory.removeChild(loadingElement);
            }
            showError(`抱歉，發生錯誤`);
            console.log("發生錯誤：", error.message);
        }
    }

    // 建立空的訊息元素(sender:user/assistant/error)
    function createMessageElement(sender, extraClass = null) {
        const messageWrapper = document.createElement('div');
        messageWrapper.classList.add('message', `${sender}-message`);
        if (extraClass) {
            messageWrapper.classList.add(extraClass);
        }
        
        return messageWrapper;
    }
    
    // 將完成的訊息加到歷史紀錄(sender:user/assistant/error)
    function appendMessage(text, sender, extraClass = null) {
        const messageElement = createMessageElement(sender, extraClass);
        messageElement.innerHTML = marked.parse(text);
        chatHistory.appendChild(messageElement);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        if (window.MathJax && typeof MathJax.typesetPromise === 'function') {
            MathJax.typesetPromise([messageElement]).catch((err) => console.log('MathJax error:', err));
        }
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

    function toggleFullscreenUI() {
        const chatSection = document.getElementById('chat-section-wrapper');
        const teachingSection = document.querySelector('.teaching-section');
        const fsIcon = document.getElementById('fs-icon');
        const unitNav = document.getElementById('unit-navigation');

        if (chatSection && teachingSection) {
            chatSection.classList.add('fullscreen-active'); // 改為 add 確保一定是開啟
            teachingSection.classList.add('is-hidden');
            // 隱藏下方的單元導覽按鈕
            if (unitNav) {
                        unitNav.classList.add('d-none');
            }
            // 更新全螢幕圖示
            if (fsIcon){
                fsIcon.innerText = 'fullscreen_exit';
            } 
        }
        
    }

    // 監聽來自 camera.js 的低參與度觸發事件
    window.addEventListener('show-learning-hint', (event) => {
        const hintText = event.detail.hint;
        if (hintText) {
            appendHintButton(hintText);
        }
    });

    // 產生「查看提示」按鈕
    window.appendHintButton = function(hintText) {
        const chatHistory = document.getElementById('chat-history');
        
        // 建立訊息外框 (套用 assistant 樣式)
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant-message hint-box animate-up'; 
        
        // 建立按鈕：讓使用者自主決定是否查看
        const btn = document.createElement('button');
        const primaryBlue = '#264773'; // 你系統定義的深藍色
        const hoverBlue = '#1a3252';   // 更深一點的藍色
        
        btn.className = 'btn btn-sm w-100 fw-bold py-2';
        btn.style.border = `2px solid ${primaryBlue}`;
        btn.style.color = '#000000'; // 黑色字
        btn.style.backgroundColor = 'transparent';
        btn.style.transition = 'all 0.2s ease'; // 平滑過渡動畫
        btn.innerHTML = '<span class="material-symbols-outlined fs-6 align-middle"></span> 需要幫助嗎？點擊查看提示';
        
        // 加入滑鼠懸停 (Hover) 效果
        btn.onmouseenter = () => {
            btn.style.backgroundColor = hoverBlue;
            btn.style.color = '#ffffff'; // 變色時字體轉白以保持對比度
        };
        btn.onmouseleave = () => {
            btn.style.backgroundColor = 'transparent';
            btn.style.color = '#000000';
        };
        
        // 建立隱藏的提示內容
        const content = document.createElement('div');
        content.className = 'mt-2 d-none text-dark';

        // 使用 marked 解析 Markdown 格式
        const hintPrefix = '<strong style="color: #264773;">💡延伸提問小提示：</strong>';
        const parsedHint = typeof marked !== 'undefined' ? marked.parse(hintText) : hintText;
    content.innerHTML = hintPrefix + parsedHint;
        
        // 點擊邏輯：HCI 自主權原則
        btn.onclick = () => {
            window.HINT_USED = true;  // <-- 【關鍵】記錄使用者已查看提示
            content.classList.remove('d-none');
            btn.classList.add('d-none'); 
            chatHistory.scrollTop = chatHistory.scrollHeight;
        };

        msgDiv.appendChild(btn);
        msgDiv.appendChild(content);
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
    });
