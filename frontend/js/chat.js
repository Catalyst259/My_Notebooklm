// Chat functionality
class ChatManager {
    constructor() {
        this.messages = [];
        this.isStreaming = false;
    }

    init() {
        const sendBtn = document.getElementById('sendBtn');
        const chatInput = document.getElementById('chatInput');

        sendBtn.addEventListener('click', () => this.sendMessage());
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }

    async sendMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput.value.trim();

        if (!message || this.isStreaming) return;

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

        // Clear input
        chatInput.value = '';

        // Add user message to UI
        this.addMessage('user', message);

        // Start streaming
        this.isStreaming = true;
        const sendBtn = document.getElementById('sendBtn');
        sendBtn.disabled = true;
        sendBtn.textContent = '回复中...';

        try {
            const response = await api.createChatStream(message, apiKey, assistantId);

            if (!response.ok) {
                throw new Error('Chat request failed');
            }

            // Read streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let assistantMessage = '';
            let messageElement = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.error) {
                                throw new Error(data.error);
                            }

                            if (data.content) {
                                assistantMessage += data.content;

                                // Create or update message element
                                if (!messageElement) {
                                    messageElement = this.addMessage('assistant', assistantMessage);
                                } else {
                                    this.updateMessage(messageElement, assistantMessage);
                                }
                            }

                            if (data.done) {
                                break;
                            }
                        } catch (e) {
                            // Skip invalid JSON
                        }
                    }
                }
            }

            // Store message in history
            this.messages.push({ role: 'user', content: message });
            this.messages.push({ role: 'assistant', content: assistantMessage });

        } catch (error) {
            console.error('Chat error:', error);
            this.addMessage('system', `错误: ${error.message}`);
            showToast('发送消息失败', 'error');
        } finally {
            this.isStreaming = false;
            sendBtn.disabled = false;
            sendBtn.textContent = '发送';
        }
    }

    addMessage(role, content) {
        const messagesContainer = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        messageDiv.innerHTML = this.formatMessage(content);
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return messageDiv;
    }

    updateMessage(element, content) {
        element.innerHTML = this.formatMessage(content);
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    formatMessage(content) {
        // Simple markdown-like formatting
        let formatted = content
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks
        formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre><code>${code.trim()}</code></pre>`;
        });

        // Inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');

        return formatted;
    }

    clearMessages() {
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = '';
        this.messages = [];
    }

    showChatView() {
        document.getElementById('assistantSelectionView').classList.remove('active');
        document.getElementById('chatView').classList.add('active');
        document.getElementById('quizView').classList.remove('active');
    }
}

// Export singleton instance
const chatManager = new ChatManager();
