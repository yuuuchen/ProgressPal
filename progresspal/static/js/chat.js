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
    const hintTopBtn = document.getElementById('hint-top-btn');
    const hintIcon = document.getElementById('hint-icon');
    
    // 預設為未使用提示
    window.HINT_USED = false;

    //儲存點擊提示的時間
    let hintClickTime = null;

    // 儲存當前最新問題的提示文字
    let currentHintText = window.LATEST_HINT || '';

    function setHintButtonEnabled(isEnabled) {
        if (!hintTopBtn || !hintIcon) return;

        if (isEnabled) {
            hintTopBtn.disabled = false;
            hintTopBtn.style.setProperty('background-color', '#ffffff');
            hintTopBtn.style.color = '#000000'; // 啟用時，文字維持黑色
            hintIcon.style.color = "#ffe46b"; // 可按
        } else {
            hintTopBtn.disabled = true;
            hintTopBtn.style.setProperty('background-color', '#b2bec3', 'important');
            hintTopBtn.style.color = '#6a6e70'; // 禁用時，文字變成灰色（配合按鈕背景）
            hintIcon.style.color = "#6a6e70"; // 不可按
        }
    }
    
    // 初始化顯現按鈕
    if (currentHintText && currentHintText.trim() !== '') {
        setHintButtonEnabled(true);
    } else {
        setHintButtonEnabled(false);
    }

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

    // 點擊提示按鈕，將提示輸入對話中
    if (hintTopBtn) {
        hintTopBtn.addEventListener('click', () => {
            if (!currentHintText) return;

            // 1. 記錄使用者已查看提示（下次 fetch 會傳給後端）
            window.HINT_USED = true;
            // 當下擷取時間
            hintClickTime = new Date().toISOString(); 
            console.log("提示查看時間:", hintClickTime);

            // 2. 建立提示區塊並利用系統現有的 appendMessage 刷進對話歷史紀錄中
            const hintPrefix = '<strong style="color: #264773;">💡 延伸提問小提示：</strong><br>';
            appendMessage(hintPrefix + currentHintText, 'assistant');

            // 3. 點擊後將按鈕設為不可按狀態
            setHintButtonEnabled(false);
        });
    }

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
        hintClickTime = null;

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
                click_time: hintClickTime,
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
            
                if (data.hint && data.hint.trim() !== '') {
                    currentHintText = data.hint; 
                    setHintButtonEnabled(true);  // 有提示，設為可按
                } else {
                    currentHintText = '';
                    setHintButtonEnabled(false); // 沒提示，設為不可按
                }
                window.HINT_USED = false;
            }

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


    });
