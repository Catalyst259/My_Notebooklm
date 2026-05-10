// Main application logic
class App {
    constructor() {
        this.assistants = [];
        this.currentAssistant = null;
    }

    async init() {
        // Initialize managers
        chatManager.init();
        quizManager.init();
        uploadManager.init();

        // Setup event listeners
        this.setupEventListeners();

        // Load API key from localStorage
        this.loadApiKey();

        // Load assistants
        await this.loadAssistants();

        // Check backend health
        this.checkBackendHealth();
    }

    setupEventListeners() {
        // API Key
        document.getElementById('saveApiKeyBtn').addEventListener('click', () => this.saveApiKey());

        // Assistant selector
        document.getElementById('changeAssistantBtn').addEventListener('click', () => {
            this.showAssistantSelection();
        });

        // Create assistant
        document.getElementById('createAssistantBtn').addEventListener('click', () => {
            document.getElementById('createAssistantModal').style.display = 'flex';
        });
        document.getElementById('cancelCreateBtn').addEventListener('click', () => {
            document.getElementById('createAssistantModal').style.display = 'none';
            document.getElementById('newAssistantName').value = '';
            document.getElementById('newAssistantDesc').value = '';
        });
        document.getElementById('confirmCreateBtn').addEventListener('click', () => this.createAssistant());

        // Stats
        document.getElementById('refreshStatsBtn').addEventListener('click', () => this.refreshStats());

        // Actions
        document.getElementById('clearHistoryBtn').addEventListener('click', () => this.clearHistory());
        document.getElementById('clearKbBtn').addEventListener('click', () => this.clearKnowledgeBase());
    }

    loadApiKey() {
        const apiKey = localStorage.getItem('deepseek_api_key');
        if (apiKey) {
            document.getElementById('apiKeyInput').value = apiKey;
            const statusDiv = document.getElementById('apiKeyStatus');
            statusDiv.textContent = '✓ API 密钥已保存';
            statusDiv.className = 'status-text success';
        }
    }

    saveApiKey() {
        const apiKeyInput = document.getElementById('apiKeyInput');
        const apiKey = apiKeyInput.value.trim();

        if (!apiKey) {
            showToast('请输入 API 密钥', 'error');
            return;
        }

        localStorage.setItem('deepseek_api_key', apiKey);

        const statusDiv = document.getElementById('apiKeyStatus');
        statusDiv.textContent = '✓ API 密钥已保存';
        statusDiv.className = 'status-text success';

        showToast('API 密钥已保存', 'success');
    }

    async loadAssistants() {
        try {
            const data = await api.getAssistants();
            this.assistants = data.assistants;
            this.renderAssistantCards();
        } catch (error) {
            console.error('Failed to load assistants:', error);
            showToast('加载助手列表失败', 'error');
        }
    }

    renderAssistantCards() {
        const container = document.getElementById('assistantCards');
        container.innerHTML = '';

        this.assistants.forEach(assistant => {
            const card = document.createElement('div');
            card.className = 'assistant-card';
            card.style.borderColor = assistant.color;

            card.innerHTML = `
                <button class="card-delete-btn" title="删除助手">&times;</button>
                <div class="icon">${assistant.icon}</div>
                <div class="name">${assistant.name}</div>
                <div class="description">${assistant.description}</div>
            `;

            card.addEventListener('click', () => this.selectAssistant(assistant));
            card.querySelector('.card-delete-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteAssistant(assistant);
            });
            container.appendChild(card);
        });
    }

    async createAssistant() {
        const nameInput = document.getElementById('newAssistantName');
        const descInput = document.getElementById('newAssistantDesc');
        const name = nameInput.value.trim();
        const description = descInput.value.trim();

        if (!name) {
            showToast('请输入助手名称', 'error');
            return;
        }
        if (!description) {
            showToast('请输入助手描述', 'error');
            return;
        }

        try {
            await api.createAssistant(name, description);
            document.getElementById('createAssistantModal').style.display = 'none';
            nameInput.value = '';
            descInput.value = '';
            await this.loadAssistants();
            showToast(`助手「${name}」创建成功`, 'success');
        } catch (error) {
            console.error('Failed to create assistant:', error);
            showToast(error.message || '创建助手失败', 'error');
        }
    }

    async deleteAssistant(assistant) {
        if (!confirm(`确定要删除「${assistant.name}」助手吗？此操作将同时清除该助手的知识库和上传文件，不可恢复！`)) return;

        try {
            await api.deleteAssistant(assistant.id);
            if (this.currentAssistant && this.currentAssistant.id === assistant.id) {
                this.currentAssistant = null;
                document.getElementById('assistantSelectorSection').style.display = 'none';
                document.getElementById('uploadSection').style.display = 'none';
                document.getElementById('statsSection').style.display = 'none';
                document.getElementById('actionsSection').style.display = 'none';
                this.showAssistantSelection();
            }
            await this.loadAssistants();
            showToast(`助手「${assistant.name}」已删除`, 'success');
        } catch (error) {
            console.error('Failed to delete assistant:', error);
            showToast(error.message || '删除助手失败', 'error');
        }
    }

    selectAssistant(assistant) {
        this.currentAssistant = assistant;

        // Update current assistant display
        const currentAssistantDiv = document.getElementById('currentAssistant');
        currentAssistantDiv.innerHTML = `
            <div class="name" style="color: ${assistant.color};">
                ${assistant.icon} ${assistant.name}
            </div>
            <div class="desc">${assistant.description}</div>
        `;

        // Show sidebar sections
        document.getElementById('assistantSelectorSection').style.display = 'block';
        document.getElementById('uploadSection').style.display = 'block';
        document.getElementById('statsSection').style.display = 'block';
        document.getElementById('actionsSection').style.display = 'block';

        // Switch to chat view
        chatManager.showChatView();

        // Clear previous chat
        chatManager.clearMessages();

        // Add welcome message
        chatManager.addMessage('system', `已切换到 ${assistant.name} 助手。你可以上传学习资料或直接提问。`);

        // Refresh stats
        this.refreshStats();

        showToast(`已选择 ${assistant.name}`, 'success');
    }

    showAssistantSelection() {
        document.getElementById('assistantSelectionView').classList.add('active');
        document.getElementById('chatView').classList.remove('active');
        document.getElementById('quizView').classList.remove('active');
    }

    async refreshStats() {
        if (!this.currentAssistant) return;

        try {
            const stats = await api.getStats(this.currentAssistant.id);
            const statsDiv = document.getElementById('kbStats');

            statsDiv.innerHTML = `
                <div><strong>文本块数:</strong> ${stats.total_chunks}</div>
                <div><strong>文件数:</strong> ${stats.total_files}</div>
                <div><strong>索引大小:</strong> ${this.formatBytes(stats.index_size)}</div>
            `;
        } catch (error) {
            console.error('Failed to refresh stats:', error);
        }
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    async clearHistory() {
        if (!this.currentAssistant) return;

        if (!confirm('确定要清空对话历史吗？')) return;

        try {
            await api.clearHistory(this.currentAssistant.id);
            chatManager.clearMessages();
            chatManager.addMessage('system', '对话历史已清空');
            showToast('对话历史已清空', 'success');
        } catch (error) {
            console.error('Failed to clear history:', error);
            showToast('清空对话历史失败', 'error');
        }
    }

    async clearKnowledgeBase() {
        if (!this.currentAssistant) return;

        if (!confirm('确定要清空知识库吗？此操作不可恢复！')) return;

        try {
            await api.clearKnowledgeBase(this.currentAssistant.id);
            await this.refreshStats();
            chatManager.addMessage('system', '知识库已清空');
            showToast('知识库已清空', 'success');
        } catch (error) {
            console.error('Failed to clear knowledge base:', error);
            showToast('清空知识库失败', 'error');
        }
    }

    async checkBackendHealth() {
        try {
            await api.healthCheck();
            console.log('Backend is healthy');
        } catch (error) {
            console.error('Backend health check failed:', error);
            showToast('无法连接到后端服务，请确保后端已启动', 'error');
        }
    }
}

// Toast notification helper
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast show';

    // Auto hide after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Initialize app when DOM is ready
const app = new App();
document.addEventListener('DOMContentLoaded', () => {
    app.init();
});
