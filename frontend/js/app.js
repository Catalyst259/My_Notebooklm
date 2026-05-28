// Main application logic
const ASSISTANT_ICONS = {
    data_structures: 'account_tree',
    computer_systems: 'developer_board',
    discrete_math: 'function',
    machine_learning: 'smart_toy',
};

function iconForAssistant(assistant) {
    return ASSISTANT_ICONS[assistant.id] || 'school';
}

class App {
    constructor() {
        this.assistants = [];
        this.currentAssistant = null;
    }

    async init() {
        chatManager.init();
        quizManager.init();
        uploadManager.init();
        mindmapManager.init();
        reviewManager.init();

        this.setupEventListeners();
        this.loadApiKey();
        await this.loadAssistants();
        this.checkBackendHealth();

        this.setBodyMode('selection');
    }

    setupEventListeners() {
        // API Key
        document.getElementById('saveApiKeyBtn').addEventListener('click', () => this.saveApiKey());

        // Settings drawer
        document.getElementById('openSettingsBtn').addEventListener('click', () => this.openSettings());
        document.getElementById('closeSettingsBtn').addEventListener('click', () => this.closeSettings());
        document.getElementById('settingsDrawer').addEventListener('click', (e) => {
            if (e.target.id === 'settingsDrawer') this.closeSettings();
        });

        // Assistant selector
        document.getElementById('changeAssistantBtn').addEventListener('click', () => {
            this.closeSettings();
            this.showAssistantSelection();
        });

        // Create assistant
        document.getElementById('createAssistantBtn').addEventListener('click', () => {
            document.getElementById('createAssistantModal').style.display = 'flex';
        });
        const cancelCreate = () => {
            document.getElementById('createAssistantModal').style.display = 'none';
            document.getElementById('newAssistantName').value = '';
            document.getElementById('newAssistantDesc').value = '';
        };
        document.getElementById('cancelCreateBtn').addEventListener('click', cancelCreate);
        document.getElementById('cancelCreateBtnIcon')?.addEventListener('click', cancelCreate);
        document.getElementById('confirmCreateBtn').addEventListener('click', () => this.createAssistant());

        // Stats
        document.getElementById('refreshStatsBtn').addEventListener('click', () => this.refreshStats());

        // Actions
        document.getElementById('clearHistoryBtn').addEventListener('click', () => this.clearHistory());
        document.getElementById('clearKbBtn').addEventListener('click', () => this.clearKnowledgeBase());

        // Mobile drawer toggles
        document.getElementById('mobileSourcesBtn')?.addEventListener('click', () => {
            document.getElementById('sourcesPanel').classList.toggle('open');
            document.getElementById('studioPanel').classList.remove('open');
        });
        document.getElementById('mobileStudioBtn')?.addEventListener('click', () => {
            document.getElementById('studioPanel').classList.toggle('open');
            document.getElementById('sourcesPanel').classList.remove('open');
        });
        // Close drawers when clicking main panel on mobile
        document.querySelector('.main-panel')?.addEventListener('click', () => {
            if (window.innerWidth <= 767) {
                document.getElementById('sourcesPanel')?.classList.remove('open');
                document.getElementById('studioPanel')?.classList.remove('open');
            }
        });
    }

    setBodyMode(mode) {
        // mode: 'selection' | 'chat' | 'quiz' | 'mindmap' | 'review'
        const body = document.body;
        body.classList.remove('is-assistant-selection', 'is-quiz-fullscreen', 'is-chat', 'is-mindmap', 'is-review');
        if (mode === 'selection') body.classList.add('is-assistant-selection');
        else if (mode === 'quiz') body.classList.add('is-quiz-fullscreen');
        else if (mode === 'chat') body.classList.add('is-chat');
        else if (mode === 'mindmap') body.classList.add('is-mindmap');
        else if (mode === 'review') body.classList.add('is-review');

        const sessions = document.getElementById('sessionListContainer');
        const maps = document.getElementById('mindmapListContainer');
        const reviews = document.getElementById('reviewListContainer');
        if (sessions && maps && reviews) {
            sessions.hidden = mode !== 'chat';
            maps.hidden = mode !== 'mindmap';
            reviews.hidden = mode !== 'review';
        }
    }

    openSettings() {
        document.getElementById('settingsDrawer').style.display = 'flex';
    }
    closeSettings() {
        document.getElementById('settingsDrawer').style.display = 'none';
    }

    loadApiKey() {
        const apiKey = localStorage.getItem('deepseek_api_key');
        if (apiKey) {
            document.getElementById('apiKeyInput').value = apiKey;
            this._setApiKeyStatus(true);
        } else {
            this._setApiKeyStatus(false);
        }
    }

    _setApiKeyStatus(isSet) {
        const dot = document.getElementById('apiKeyStatus');
        if (!dot) return;
        dot.classList.toggle('is-set', isSet);
        dot.classList.toggle('is-unset', !isSet);
        dot.title = isSet ? 'API Key 已配置' : 'API Key 未配置';
    }

    saveApiKey() {
        const apiKeyInput = document.getElementById('apiKeyInput');
        const apiKey = apiKeyInput.value.trim();
        if (!apiKey) {
            showToast('请输入 API 密钥', 'error');
            return;
        }
        localStorage.setItem('deepseek_api_key', apiKey);
        this._setApiKeyStatus(true);
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

            const iconName = iconForAssistant(assistant);
            card.innerHTML = `
                <button class="card-delete-btn" title="删除助手">
                    <span class="material-symbols-outlined" style="font-size:16px;">close</span>
                </button>
                <div class="badge" style="background:${assistant.color};">
                    <span class="material-symbols-outlined">${iconName}</span>
                </div>
                <div class="name">${escapeText(assistant.name)}</div>
                <div class="description">${escapeText(assistant.description)}</div>
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
        if (!name) { showToast('请输入助手名称', 'error'); return; }
        if (!description) { showToast('请输入助手描述', 'error'); return; }

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

        // Header current
        const headerCurrent = document.getElementById('headerCurrent');
        if (headerCurrent) {
            headerCurrent.innerHTML = `
                <span class="brand-dot" style="background:${assistant.color};"></span>
                <span>${escapeText(assistant.name)}</span>
            `;
        }

        // Settings drawer "current assistant" content
        const currentAssistantDiv = document.getElementById('currentAssistant');
        if (currentAssistantDiv) {
            const iconName = iconForAssistant(assistant);
            currentAssistantDiv.innerHTML = `
                <div class="name">
                    <span class="material-symbols-outlined" style="color:${assistant.color};">${iconName}</span>
                    <span>${escapeText(assistant.name)}</span>
                </div>
                <div class="desc">${escapeText(assistant.description)}</div>
            `;
        }

        // Show drawer sections that require an assistant
        document.getElementById('assistantSelectorSection').style.display = 'flex';
        document.getElementById('actionsSection').style.display = 'flex';

        // Set brand color on chat assistant avatars (CSS var on chat container)
        const chatView = document.getElementById('chatView');
        if (chatView) chatView.style.setProperty('--brand-color', assistant.color);

        chatManager.showChatView();
        chatManager.onAssistantSelected(assistant.id);

        if (window.mindmapManager) mindmapManager.onAssistantChanged();
        if (window.reviewManager && reviewManager.onAssistantChanged) reviewManager.onAssistantChanged();

        this.refreshStats();
        this.refreshFileList();

        showToast(`已选择 ${assistant.name}`, 'success');
    }

    showAssistantSelection() {
        if (window.mindmapManager) mindmapManager.flushSave();
        document.getElementById('assistantSelectionView').classList.add('active');
        document.getElementById('chatView').classList.remove('active');
        document.getElementById('quizView').classList.remove('active');
        document.getElementById('mindmapView').classList.remove('active');
        document.getElementById('reviewView').classList.remove('active');
        this.setBodyMode('selection');
        const headerCurrent = document.getElementById('headerCurrent');
        if (headerCurrent) headerCurrent.innerHTML = '';
    }

    async refreshStats() {
        if (!this.currentAssistant) return;
        try {
            const stats = await api.getStats(this.currentAssistant.id);
            const statsDiv = document.getElementById('kbStats');
            statsDiv.innerHTML = `
                <div><strong>文本块:</strong> ${stats.total_chunks}</div>
                <div><strong>文件:</strong> ${stats.total_files}</div>
                <div><strong>索引:</strong> ${this.formatBytes(stats.index_size)}</div>
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

    async refreshFileList() {
        if (!this.currentAssistant) return;
        try {
            const data = await api.getFiles(this.currentAssistant.id);
            const fileListDiv = document.getElementById('fileList');

            if (data.files.length === 0) {
                fileListDiv.innerHTML = '<p style="color: var(--text-mute); font-size: var(--fs-xs); padding: var(--sp-2) 0;">暂无文件</p>';
                return;
            }

            fileListDiv.innerHTML = '';
            data.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'file-item';

                const uploadDate = new Date(file.upload_date).toLocaleString('zh-CN');
                const fileSize = this.formatBytes(file.file_size);

                item.innerHTML = `
                    <div class="file-info">
                        <div class="file-name">${escapeText(file.original_name)}</div>
                        <div class="file-meta">
                            ${file.chunk_count} 块 · ${fileSize} · ${uploadDate}
                        </div>
                    </div>
                    <button class="file-delete-btn" data-uuid="${file.file_uuid}" title="删除">
                        <span class="material-symbols-outlined" style="font-size:16px;">delete</span>
                    </button>
                `;

                item.querySelector('.file-delete-btn').addEventListener('click', () => {
                    this.deleteFile(file);
                });

                fileListDiv.appendChild(item);
            });
        } catch (error) {
            console.error('Failed to refresh file list:', error);
        }
    }

    async deleteFile(file) {
        if (!confirm(`确定要删除「${file.original_name}」吗？此操作不可恢复！`)) return;
        try {
            await api.deleteFile(file.file_uuid, this.currentAssistant.id);
            await this.refreshStats();
            await this.refreshFileList();
            showToast(`文件「${file.original_name}」已删除`, 'success');
        } catch (error) {
            console.error('Failed to delete file:', error);
            showToast('删除文件失败', 'error');
        }
    }

    async clearHistory() {
        if (!this.currentAssistant) return;
        if (!confirm('确定要清空当前对话吗？')) return;
        try {
            if (chatManager.currentSessionId) {
                await api.deleteSession(chatManager.currentSessionId, this.currentAssistant.id);
            }
            await chatManager.refreshSessions();
            chatManager.currentSessionId = null;
            chatManager.clearMessages();
            chatManager.updateSessionTitle('新对话');
            this.closeSettings();
            showToast('对话已清空', 'success');
        } catch (error) {
            console.error('Failed to clear history:', error);
            showToast('清空对话失败', 'error');
        }
    }

    async clearKnowledgeBase() {
        if (!this.currentAssistant) return;
        if (!confirm('确定要清空知识库吗？此操作不可恢复！')) return;
        try {
            await api.clearKnowledgeBase(this.currentAssistant.id);
            await this.refreshStats();
            chatManager.addMessage('system', '知识库已清空');
            this.closeSettings();
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

function escapeText(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast show';
    setTimeout(() => { toast.classList.remove('show'); }, 3000);
}

const app = window.app = new App();
document.addEventListener('DOMContentLoaded', () => { app.init(); });
