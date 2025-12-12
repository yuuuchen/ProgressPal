// 當整個頁面載入完成後再執行
document.addEventListener("DOMContentLoaded", () => {
    const questionTextEl = document.getElementById('question-text'); // 題目文字
    const optionsContainer = document.getElementById('options-container'); // 選項
    const confirmBtn = document.getElementById('confirm-btn'); // 確認按鈕
    const nextBtn = document.getElementById('next-btn'); // 下一題按鈕
    const restartBtn = document.getElementById('restart-btn'); // 重新測驗
    const currentQEl = document.getElementById('current-q'); // 當前題號
    const quizCard = document.getElementById('quiz-card'); // 測驗卡片
    const resultCard = document.getElementById('result-card'); // 成績卡片
    const feedbackMsg = document.getElementById('feedback-msg'); // 答對或答錯的文字提示
    
    let questions = []; // 存放從後端拿到的題目
    let currentQuestionIndex = 0; // 目前在第幾題
    let score = 0; // 分數
    let selectedOptionIndex = null; // 使用者當前選的答案

    // 綁定按鈕點擊事件
    confirmBtn.addEventListener('click', checkAnswer);
    nextBtn.addEventListener('click', nextQuestion);
    restartBtn.addEventListener('click', restartQuiz);

    // 從後端獲取資料
    async function getQuestions() {
        const response = await fetch('api');
        // 得到後端回傳的資料
        const data = await response.json(); 
        return data;
    }

    // 初始化題目
    async function initQuiz() {
        try {
            questions = await getQuestions();
            loadQuestion();
        } catch (error) {
            questionTextEl.innerText = "載入題目失敗";
            console.error(error);
        }
    }

    // 渲染題目 
    function loadQuestion() {
        const currentData = questions[currentQuestionIndex];
        
        // 更新題號與題目文字
        currentQEl.innerText = currentQuestionIndex + 1;
        questionTextEl.innerText = currentData.question;
        feedbackMsg.innerText = ""; // 清空上一題的回饋訊息
        feedbackMsg.style.color = "";

        // 清空舊選項
        optionsContainer.innerHTML = '';
        
        // 產生新的選項
        currentData.options.forEach((option, index) => {
            const btn = document.createElement('div');
            btn.classList.add('option-btn');
            // 建立前面的圈圈
            const circle = document.createElement('div');
            circle.classList.add('circle'); 

            // 建立文字部分
            const text = document.createElement('span');
            text.innerText = option;

            // 把圈圈和文字都加入按鈕中
            btn.appendChild(circle);
            btn.appendChild(text);
    
            // 點擊事件 (點擊整條按鈕都會觸發)
            btn.onclick = () => selectOption(index);
            optionsContainer.appendChild(btn);
        });

        // 重置按鈕狀態
        selectedOptionIndex = null;
        confirmBtn.disabled = true;
        confirmBtn.classList.remove('hidden'); // 顯示確認按鈕
        nextBtn.classList.add('hidden'); // 隱藏下一題按鈕
    }

    // 使用者點選某個選項
    function selectOption(index) {
        // 如果已經確認過答案，就不能再選
        if (!confirmBtn.classList.contains('hidden')) {
            selectedOptionIndex = index;
            
            // 移除所有選項的選中樣式
            const buttons = optionsContainer.children;
            for (let btn of buttons) {
                btn.classList.remove('selected');
            }
            buttons[index].classList.add('selected');
            
            // 啟用確認按鈕
            confirmBtn.disabled = false;
        }
    }

    // 按下「確認」
    function checkAnswer() {
        const currentData = questions[currentQuestionIndex];
        const buttons = optionsContainer.children;
        const correctIdx = currentData.correctIndex;

        // 鎖定所有選項 (移除點擊事件效果)
        // 這裡我們透過邏輯控制，下面直接顯示結果樣式
        
        // 顯示結果樣式
        if (selectedOptionIndex === correctIdx) {
            // 答對
            score++;
            buttons[selectedOptionIndex].classList.add('correct');
            feedbackMsg.innerText = "答對了！";
            feedbackMsg.style.color = "#2ecc71";
        } else {
            // 答錯
            buttons[selectedOptionIndex].classList.add('wrong'); // 選錯的標紅
            buttons[correctIdx].classList.add('correct'); // 正確的標綠
            feedbackMsg.innerText = "答錯了!";
            feedbackMsg.style.color = "#e74c3c";
        }

        // 切換按鈕
        confirmBtn.classList.add('hidden');
        nextBtn.classList.remove('hidden');
    }

    // 按「下一題」
    function nextQuestion() {
        currentQuestionIndex++;
        
        if (currentQuestionIndex < questions.length) {
            loadQuestion();
        } else {
            showResults(); //顯示結果
        }
    }

    // 成績結算頁面
    function showResults() {
        quizCard.classList.add('hidden');
        resultCard.classList.remove('hidden');
        
        const finalScoreEl = document.getElementById('final-score');
        finalScoreEl.innerText = `${score} / ${questions.length}`;
    }

    function restartQuiz() {
        currentQuestionIndex = 0;
        score = 0;
        resultCard.classList.add('hidden');
        quizCard.classList.remove('hidden');
        loadQuestion();
    }

    // 啟動程式
    initQuiz();
});  
