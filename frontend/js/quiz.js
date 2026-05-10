// Quiz functionality
class QuizManager {
    constructor() {
        this.currentQuiz = null;
        this.userAnswers = {};
        this.quizResults = null;
    }

    init() {
        const generateQuizBtn = document.getElementById('generateQuizBtn');
        generateQuizBtn.addEventListener('click', () => this.showQuizOptions());
    }

    showQuizOptions() {
        const apiKey = localStorage.getItem('deepseek_api_key');
        if (!apiKey) {
            showToast('请先保存 API 密钥', 'error');
            return;
        }

        const assistantId = app.currentAssistant?.id;
        if (!assistantId) {
            showToast('请先选择助手', 'error');
            return;
        }

        // Show quiz options dialog
        const options = {
            count: 5,
            difficulty: 'medium',
            question_types: 'mixed',
            topic: ''
        };

        this.generateQuiz(apiKey, assistantId, options);
    }

    async generateQuiz(apiKey, assistantId, options) {
        showToast('正在生成测验...', 'info');

        try {
            const quiz = await api.generateQuiz(apiKey, assistantId, options);
            this.currentQuiz = quiz;
            this.userAnswers = {};
            this.quizResults = null;
            this.renderQuiz();
            this.showQuizView();
            showToast('测验生成成功', 'success');
        } catch (error) {
            console.error('Quiz generation error:', error);
            showToast(`生成测验失败: ${error.message}`, 'error');
        }
    }

    renderQuiz() {
        const container = document.getElementById('quizContainer');
        const quiz = this.currentQuiz;

        let html = `
            <div class="quiz-header">
                <h2>${quiz.title || '测验'}</h2>
                <div class="quiz-info">
                    <span>题目数量: ${quiz.questions.length}</span>
                    ${quiz.used_knowledge_base ? ' | 基于知识库生成' : ''}
                </div>
            </div>
        `;

        quiz.questions.forEach((q, index) => {
            html += this.renderQuestion(q, index);
        });

        html += `
            <div class="quiz-actions">
                <button id="submitQuizBtn" class="btn btn-primary">提交答案</button>
                <button id="cancelQuizBtn" class="btn btn-secondary">返回对话</button>
            </div>
        `;

        container.innerHTML = html;

        // Add event listeners
        document.getElementById('submitQuizBtn').addEventListener('click', () => this.submitQuiz());
        document.getElementById('cancelQuizBtn').addEventListener('click', () => {
            chatManager.showChatView();
        });

        // Add listeners for answer inputs
        quiz.questions.forEach((q, index) => {
            if (q.type === 'single_choice') {
                const radios = document.querySelectorAll(`input[name="q${index}"]`);
                radios.forEach(radio => {
                    radio.addEventListener('change', (e) => {
                        this.userAnswers[q.id] = e.target.value;
                    });
                });
            } else {
                const textarea = document.getElementById(`answer-${index}`);
                textarea.addEventListener('input', (e) => {
                    this.userAnswers[q.id] = e.target.value;
                });
            }
        });
    }

    renderQuestion(question, index) {
        const typeLabels = {
            'single_choice': '单选题',
            'short_answer': '简答题',
            'code_reading': '代码阅读题',
            'proof': '证明题'
        };

        let html = `
            <div class="question">
                <div class="question-header">
                    ${index + 1}. ${typeLabels[question.type] || question.type}
                    ${question.knowledge_point ? `<span style="color: #6b7280; font-weight: normal;"> - ${question.knowledge_point}</span>` : ''}
                </div>
                <div class="question-text">${this.formatQuestionText(question.question)}</div>
        `;

        if (question.type === 'single_choice' && question.options) {
            html += '<div class="options">';
            question.options.forEach((option, optIndex) => {
                const letter = String.fromCharCode(65 + optIndex);
                html += `
                    <label class="option">
                        <input type="radio" name="q${index}" value="${letter}">
                        ${option}
                    </label>
                `;
            });
            html += '</div>';
        } else {
            html += `
                <textarea id="answer-${index}" class="answer-input" placeholder="请输入你的答案..."></textarea>
            `;
        }

        html += '</div>';
        return html;
    }

    formatQuestionText(text) {
        // Format code blocks
        let formatted = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre><code>${code.trim()}</code></pre>`;
        });

        // Format inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');

        return formatted;
    }

    async submitQuiz() {
        const apiKey = localStorage.getItem('deepseek_api_key');
        const assistantId = app.currentAssistant?.id;

        // Check if all questions are answered
        const unanswered = this.currentQuiz.questions.filter(q => !this.userAnswers[q.id]);
        if (unanswered.length > 0) {
            if (!confirm(`还有 ${unanswered.length} 道题未作答，确定要提交吗？`)) {
                return;
            }
        }

        showToast('正在批改测验...', 'info');

        try {
            const results = await api.gradeQuiz(
                apiKey,
                assistantId,
                this.currentQuiz.questions,
                this.userAnswers
            );

            this.quizResults = results;
            this.renderResults();
            showToast('批改完成', 'success');
        } catch (error) {
            console.error('Quiz grading error:', error);
            showToast(`批改失败: ${error.message}`, 'error');
        }
    }

    renderResults() {
        const container = document.getElementById('quizContainer');
        const results = this.quizResults;

        let html = `
            <div class="quiz-header">
                <h2>测验结果</h2>
            </div>
            <div class="score-display">
                <div class="score">${(results.score * 100).toFixed(1)}%</div>
                <div>总分: ${results.total_score.toFixed(1)} / ${results.max_score}</div>
            </div>
            <div class="quiz-results">
        `;

        results.results.forEach((result, index) => {
            const statusClass = result.score === 1 ? 'correct' : (result.score === 0 ? 'incorrect' : 'partial');
            const statusText = result.score === 1 ? '✓ 正确' : (result.score === 0 ? '✗ 错误' : '△ 部分正确');

            html += `
                <div class="result-item ${statusClass}">
                    <div style="font-weight: 600; margin-bottom: 8px;">
                        ${index + 1}. ${statusText} (${result.score.toFixed(1)} 分)
                    </div>
                    <div style="margin-bottom: 8px;">
                        <strong>你的答案:</strong> ${result.user_answer || '(未作答)'}
                    </div>
                    ${result.correct_answer ? `
                        <div style="margin-bottom: 8px;">
                            <strong>参考答案:</strong> ${result.correct_answer}
                        </div>
                    ` : ''}
                    ${result.feedback ? `
                        <div style="color: #6b7280; font-size: 0.9rem;">
                            <strong>反馈:</strong> ${result.feedback}
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += `
            </div>
            <div class="quiz-actions">
                <button id="newQuizBtn" class="btn btn-primary">生成新测验</button>
                <button id="backToChatBtn" class="btn btn-secondary">返回对话</button>
            </div>
        `;

        container.innerHTML = html;

        document.getElementById('newQuizBtn').addEventListener('click', () => this.showQuizOptions());
        document.getElementById('backToChatBtn').addEventListener('click', () => chatManager.showChatView());
    }

    showQuizView() {
        document.getElementById('assistantSelectionView').classList.remove('active');
        document.getElementById('chatView').classList.remove('active');
        document.getElementById('quizView').classList.add('active');
    }
}

// Export singleton instance
const quizManager = new QuizManager();
