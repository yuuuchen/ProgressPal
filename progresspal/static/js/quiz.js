document.addEventListener("DOMContentLoaded", () => {
    // DOM 元素選取 
    const quizCard = document.getElementById('quiz-card'); // 測驗卡片
    const resultCard = document.getElementById('result-card'); // 結果卡片
    
    // 測驗區元素
    const currentQEl = document.getElementById('current-q'); // 當前題號
    const questionTextEl = document.getElementById('question-text'); // 問題
    const optionsContainer = document.getElementById('options-container'); // 選項
    const nextBtn = document.getElementById('next-btn');  // 下一題按鈕
    const prevBtn = document.getElementById('prev-btn');  // 上一題按鈕
    const submitBtn = document.getElementById('submit-btn');  // 完成作答按鈕
    
    // 結果區元素
    const finalScoreEl = document.getElementById('final-score'); // 成績
    const reviewContainer = document.getElementById('review-container'); // 詳解

    // 變數初始化
    let questionsData = [];      // 存放題目
    let currentQuestionIndex = 0; 
    let userAnswersMap = {};     // 暫存使用者的答案 

    // CSRF Token
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

    // 獲取所有題目
    async function initQuiz() {
        try {
            const response = await fetch('api');
            if (!response.ok) throw new Error('Network response was not ok');
            
            questionsData = await response.json();
            
            if (questionsData.length > 0) {
                loadQuestion();
            } else {
                questionTextEl.innerText = "目前沒有題目";
            }
        } catch (error) {
            console.error("載入題目失敗:", error);
            questionTextEl.innerText = "載入失敗，請重新整理頁面";
        }
    }

    // 作答過程
    function loadQuestion() {
        const currentData = questionsData[currentQuestionIndex];
        const qId = currentData.question_id;

        // 更新介面文字
        currentQEl.innerText = currentQuestionIndex + 1;
        questionTextEl.innerText = currentData.question;
        optionsContainer.innerHTML = ''; // 清空選項

        // 檢查這一題是否已經答過
        const savedChoice = userAnswersMap[qId];

        // 產生選項按鈕
        currentData.options.forEach((optionText, index) => {
            const btn = document.createElement('div');
            btn.classList.add('option-btn');

            // 將 Index (0,1,2) 轉成字母 (A,B,C) 
            const currentLabel = String.fromCharCode(65 + index);

            // 如果之前選過這個，加上 selected 樣式
            if (savedChoice === currentLabel) {
                btn.classList.add('selected');
            }

            // HTML 結構：圈圈 + 文字
            btn.innerHTML = `<div class="circle"></div><span>${optionText}</span>`;
            
            // 綁定點擊事件
            btn.onclick = () => selectOption(qId, index);
            optionsContainer.appendChild(btn);
        });

        // 按鈕狀態控制：必須有選擇答案才能按「下一題」或「交卷」
        updateNavButtons(savedChoice !== undefined);
    }

    function selectOption(qId, index) {
        // 將 Index 轉成 ABCD 儲存
        const label = String.fromCharCode(65 + index);
        // 記錄答案
        userAnswersMap[qId] = label;

        // 更新選項視覺 (單選)
        const buttons = optionsContainer.children;
        for (let btn of buttons) btn.classList.remove('selected');
        buttons[index].classList.add('selected');

        // 3. 啟用按鈕
        updateNavButtons(true);
    }

    function updateNavButtons(hasAnswer) {
        // 判斷是否為最後一題
        const isLastQuestion = currentQuestionIndex === questionsData.length - 1;
        // 判斷是否為第一題
        const isFirstQuestion = currentQuestionIndex === 0;

        // --- 控制「上一題」按鈕 ---
        if (isFirstQuestion) {
            prevBtn.classList.add('hidden'); // 第一題不能按上一題
        } else {
            prevBtn.classList.remove('hidden'); 
        }

        // 控制下一題 / 交卷按鈕
        if (isLastQuestion) {
            nextBtn.classList.add('hidden'); 
            submitBtn.classList.remove('hidden');  // 顯示繳交按鈕
            submitBtn.disabled = !hasAnswer; // 沒作答不能交卷
        } else {
            nextBtn.classList.remove('hidden');
            submitBtn.classList.add('hidden');
            nextBtn.disabled = !hasAnswer;   // 沒作答不能下一題
        }
    }

    // 下一題按鈕事件
    nextBtn.addEventListener('click', () => {
        currentQuestionIndex++;
        loadQuestion();
    });

    // 上一題按鈕事件
    prevBtn.addEventListener('click', () => {
        if (currentQuestionIndex > 0) {
            currentQuestionIndex--; 
            loadQuestion();   
        }
    });

    // 交卷 
    submitBtn.addEventListener('click', submitAll);

    async function submitAll() {
        // 鎖定按鈕防止重複提交
        submitBtn.disabled = true;

        try {
            // 整理傳送資料格式
            // { "answers": [ { "question_id": 101, "selected_index": 0 }, ... ] }
            const payload = {
                answers: Object.keys(userAnswersMap).map(qId => ({
                    question_id: parseInt(qId),
                    selected_index: userAnswersMap[qId]
                }))
            };

            // 發送 POST 請求
            const response = await fetch('api', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error('Submission failed');

            // 接收後端回傳的詳解資料
            // Response: { score: 80, results: [ {question_id, user_answer, answer, explanation...}, ... ] }
            const resultData = await response.json();

            // 4. 顯示結果頁面
            renderResultPage(resultData);

        } catch (error) {
            console.error("交卷錯誤:", error);
            submitBtn.disabled = false;
            submitBtn.innerText = "送出答案";
            alert("交卷發生錯誤，請稍後再試");
        }
    }

    // 渲染結果與詳解
    function renderResultPage(data) {
        // 切換卡片顯示(quizCard -> resultCard)
        quizCard.classList.add('hidden');
        resultCard.classList.remove('hidden');

        // 顯示總成績
        finalScoreEl.innerText = `總分：${data.score} / 10`; // 假設後端回傳的是分數或 "答對題數"

        // 渲染每一題的詳解列表
        reviewContainer.innerHTML = ''; // 清空

        data.results.forEach((item, idx) => {
            const reviewItem = document.createElement('div');
            reviewItem.classList.add('review-item'); 

            // 建立該題的 HTML 結構
            let htmlContent = `
                <div class="review-question">
                    <strong>第 ${idx + 1} 題：${item.question}</strong>
                </div>
                <div class="review-options">
            `;

            // 迴圈渲染選項，並標示顏色
            item.options.forEach((opt, optIdx) => {
                let classList = 'option-review-btn'; // 基本樣式

                const currentLabel = String.fromCharCode(65 + optIdx);
                
                // 邏輯：
                // 如果這個選項是「正確答案」 -> 綠色 (correct)
                // 如果這個選項是「使用者選的」但「選錯了」 -> 紅色 (wrong)
                // 如果是使用者選的且選對了 -> 綠色 
                
                if (currentLabel === item.answer) {
                    classList += ' correct'; // 綠色樣式
                } else if (currentLabel === item.user_answer) {
                    classList += ' wrong';   // 紅色樣式
                }

                htmlContent += `<div class="${classList}">${opt}</div>`;
            });

            htmlContent += `
                </div>
                <div class="review-explanation">
                    <strong>詳解：</strong>${item.explaination}
                </div>
                <hr>
            `;

            reviewItem.innerHTML = htmlContent;
            reviewContainer.appendChild(reviewItem);
        });
    }

    // 啟動程式
    initQuiz();
});
