// Chat functionality with session management
class ChatManager {
    constructor() {
        this.currentSessionId = null;
        this.messages = []; // current session's messages, mirrored from the server
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

        document.getElementById('newSessionBtn').addEventListener('click', () => this.newSession());
        document.getElementById('exportSessionBtn').addEventListener('click', () => this.exportSession());
        document.getElementById('memoryBtn').addEventListener('click', () => this.openMemoryModal());
        document.getElementById('cancelMemoryBtn').addEventListener('click', () => this.closeMemoryModal());
        document.getElementById('saveMemoryBtn').addEventListener('click', () => this.saveMemory());
    }

    // --- Assistant switch hook ---------------------------------------------

    async onAssistantSelected(assistantId) {
        await this.refreshSessions();
        const sessions = this._lastSessions || [];
        if (sessions.length > 0) {
            await this.loadSession(sessions[0].id);
        } else {
            this.currentSessionId = null;
            this.messages = [];
            this.renderMessages();
            this.updateSessionTitle('新对话');
        }
    }

    // --- Session sidebar ---------------------------------------------------

    async refreshSessions() {
        const assistantId = app.currentAssistant?.id;
        if (!assistantId) return;
        try {
            const data = await api.listSessions(assistantId);
            this._lastSessions = data.sessions || [];
            this.renderSessionList();
        } catch (e) {
            console.error('Failed to list sessions:', e);
        }
    }

    renderSessionList() {
        const container = document.getElementById('sessionList');
        container.innerHTML = '';
        const sessions = this._lastSessions || [];
        if (sessions.length === 0) {
            container.innerHTML = '<div class="session-empty">还没有对话</div>';
            return;
        }
        sessions.forEach(s => {
            const item = document.createElement('div');
            item.className = 'session-item';
            if (s.id === this.currentSessionId) item.classList.add('active');

            const title = document.createElement('div');
            title.className = 'session-item-title';
            title.textContent = s.title || '新对话';
            title.title = s.title || '新对话';

            const meta = document.createElement('div');
            meta.className = 'session-item-meta';
            meta.textContent = `${s.message_count} 条消息`;

            const actions = document.createElement('div');
            actions.className = 'session-item-actions';

            const renameBtn = document.createElement('button');
            renameBtn.className = 'session-action-btn';
            renameBtn.title = '重命名';
            renameBtn.textContent = '✎';
            renameBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.renameSession(s);
            });

            const delBtn = document.createElement('button');
            delBtn.className = 'session-action-btn danger';
            delBtn.title = '删除对话';
            delBtn.textContent = '✕';
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteSession(s);
            });

            actions.appendChild(renameBtn);
            actions.appendChild(delBtn);

            const body = document.createElement('div');
            body.className = 'session-item-body';
            body.appendChild(title);
            body.appendChild(meta);

            item.appendChild(body);
            item.appendChild(actions);

            item.addEventListener('click', () => this.loadSession(s.id));
            container.appendChild(item);
        });
    }

    async newSession() {
        const assistantId = app.currentAssistant?.id;
        if (!assistantId) return;
        try {
            const data = await api.createSession(assistantId);
            this.currentSessionId = data.session.id;
            this.messages = [];
            this.renderMessages();
            this.updateSessionTitle(data.session.title);
            await this.refreshSessions();
        } catch (e) {
            console.error(e);
            showToast('新建对话失败', 'error');
        }
    }

    async loadSession(sessionId) {
        const assistantId = app.currentAssistant?.id;
        if (!assistantId) return;
        try {
            const data = await api.getSession(sessionId, assistantId);
            this.currentSessionId = data.session.id;
            this.messages = data.session.messages || [];
            this.renderMessages();
            this.updateSessionTitle(data.session.title);
            this.renderSessionList(); // re-highlight active
        } catch (e) {
            console.error(e);
            showToast('加载对话失败', 'error');
        }
    }

    async renameSession(session) {
        const next = prompt('重命名对话：', session.title || '新对话');
        if (next === null) return;
        const title = next.trim();
        if (!title) return;
        try {
            await api.renameSession(session.id, app.currentAssistant.id, title);
            if (session.id === this.currentSessionId) this.updateSessionTitle(title);
            await this.refreshSessions();
        } catch (e) {
            console.error(e);
            showToast('重命名失败', 'error');
        }
    }

    async deleteSession(session) {
        if (!confirm(`确定要删除「${session.title || '新对话'}」吗？`)) return;
        try {
            await api.deleteSession(session.id, app.currentAssistant.id);
            if (session.id === this.currentSessionId) {
                this.currentSessionId = null;
                this.messages = [];
                this.renderMessages();
                this.updateSessionTitle('新对话');
            }
            await this.refreshSessions();
            // If we just nuked the active one, auto-load the next most-recent.
            if (!this.currentSessionId && this._lastSessions && this._lastSessions.length > 0) {
                await this.loadSession(this._lastSessions[0].id);
            }
        } catch (e) {
            console.error(e);
            showToast('删除对话失败', 'error');
        }
    }

    updateSessionTitle(title) {
        const el = document.getElementById('currentSessionTitle');
        if (el) el.textContent = title || '新对话';
    }

    // --- Message rendering -------------------------------------------------

    renderMessages() {
        const container = document.getElementById('chatMessages');
        container.innerHTML = '';
        this.messages.forEach((m, i) => this.renderMessage(m, i));
        container.scrollTop = container.scrollHeight;
    }

    renderMessage(message, index) {
        const container = document.getElementById('chatMessages');
        const wrap = document.createElement('div');
        wrap.className = `message ${message.role}`;
        wrap.dataset.index = String(index);

        const body = document.createElement('div');
        body.className = 'message-body';
        body.innerHTML = this.formatMessage(message.content || '');
        wrap.appendChild(body);

        // Action buttons (visible on hover via CSS) — system messages get nothing.
        if (message.role === 'user' || message.role === 'assistant') {
            const actions = document.createElement('div');
            actions.className = 'message-actions';

            const delBtn = document.createElement('button');
            delBtn.className = 'msg-action-btn';
            delBtn.title = '删除该轮对话';
            delBtn.textContent = '✕';
            delBtn.addEventListener('click', () => this.deleteMessage(index));
            actions.appendChild(delBtn);

            // Regenerate only on the *last* assistant message
            const isLastAssistant = (
                message.role === 'assistant' &&
                index === this.messages.length - 1
            );
            if (isLastAssistant) {
                const regenBtn = document.createElement('button');
                regenBtn.className = 'msg-action-btn';
                regenBtn.title = '重新生成回答';
                regenBtn.textContent = '↻';
                regenBtn.addEventListener('click', () => this.regenerate());
                actions.appendChild(regenBtn);
            }

            wrap.appendChild(actions);
        }

        container.appendChild(wrap);
        return wrap;
    }

    addStreamingMessage(role) {
        // Used during streaming — the streamed message is not yet in this.messages
        // (it gets added on completion via session reload).
        const container = document.getElementById('chatMessages');
        const wrap = document.createElement('div');
        wrap.className = `message ${role} streaming`;
        const body = document.createElement('div');
        body.className = 'message-body';
        wrap.appendChild(body);
        container.appendChild(wrap);
        container.scrollTop = container.scrollHeight;
        return wrap;
    }

    updateStreamingMessage(element, content) {
        const body = element.querySelector('.message-body');
        body.innerHTML = this.formatMessage(content);
        const container = document.getElementById('chatMessages');
        container.scrollTop = container.scrollHeight;
    }

    addSystemMessage(content) {
        const container = document.getElementById('chatMessages');
        const wrap = document.createElement('div');
        wrap.className = 'message system';
        wrap.innerHTML = `<div class="message-body">${this.formatMessage(content)}</div>`;
        container.appendChild(wrap);
        container.scrollTop = container.scrollHeight;
    }

    // Compat shim: older code paths (app.js welcome message) still call this.
    addMessage(role, content) {
        if (role === 'system') return this.addSystemMessage(content);
        // Append to current view only; persistent storage happens server-side on chat.
        this.messages.push({ role, content });
        return this.renderMessage({ role, content }, this.messages.length - 1);
    }

    clearMessages() {
        this.messages = [];
        const container = document.getElementById('chatMessages');
        if (container) container.innerHTML = '';
    }

    // --- Sending -----------------------------------------------------------

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

        chatInput.value = '';

        // Optimistically render the user turn; the server will persist it.
        this.messages.push({ role: 'user', content: message });
        this.renderMessages();

        this.isStreaming = true;
        const sendBtn = document.getElementById('sendBtn');
        sendBtn.disabled = true;
        sendBtn.textContent = '回复中...';

        try {
            const response = await api.createChatStream(
                message, apiKey, assistantId, this.currentSessionId || ''
            );
            if (!response.ok) throw new Error('Chat request failed');
            await this._consumeStream(response);
            await this.refreshSessions();
        } catch (error) {
            console.error('Chat error:', error);
            this.addSystemMessage(`错误: ${error.message}`);
            showToast('发送消息失败', 'error');
        } finally {
            this.isStreaming = false;
            sendBtn.disabled = false;
            sendBtn.textContent = '发送';
        }
    }

    async _consumeStream(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantMessage = '';
        let messageElement = null;
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // keep partial line

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                let data;
                try { data = JSON.parse(line.slice(6)); } catch { continue; }

                if (data.session_id && !this.currentSessionId) {
                    this.currentSessionId = data.session_id;
                }
                if (data.error) throw new Error(data.error);
                if (data.content) {
                    assistantMessage += data.content;
                    if (!messageElement) {
                        messageElement = this.addStreamingMessage('assistant');
                    }
                    this.updateStreamingMessage(messageElement, assistantMessage);
                }
                if (data.done) {
                    // Reload from server to get the authoritative message list with timestamps.
                    if (this.currentSessionId) {
                        try {
                            const sess = await api.getSession(this.currentSessionId, app.currentAssistant.id);
                            this.messages = sess.session.messages || [];
                            this.renderMessages();
                            this.updateSessionTitle(sess.session.title);
                        } catch (e) { console.error(e); }
                    }
                    return;
                }
            }
        }
    }

    // --- Edit / regenerate / export ---------------------------------------

    async deleteMessage(index) {
        if (!this.currentSessionId) return;
        if (!confirm('确定要删除该轮对话吗？（包含对应的提问/回答）')) return;
        try {
            const data = await api.deleteMessage(
                this.currentSessionId, index, app.currentAssistant.id
            );
            this.messages = data.session.messages || [];
            this.renderMessages();
            await this.refreshSessions();
        } catch (e) {
            console.error(e);
            showToast('删除失败', 'error');
        }
    }

    async regenerate() {
        if (!this.currentSessionId || this.isStreaming) return;
        const apiKey = localStorage.getItem('deepseek_api_key');
        if (!apiKey) {
            showToast('请先保存 API 密钥', 'error');
            return;
        }

        // Drop the last assistant message visually; the server pops it too.
        if (this.messages.length && this.messages[this.messages.length - 1].role === 'assistant') {
            this.messages.pop();
            this.renderMessages();
        }

        this.isStreaming = true;
        const sendBtn = document.getElementById('sendBtn');
        sendBtn.disabled = true;
        sendBtn.textContent = '重新生成...';
        try {
            const response = await api.regenerateLast(
                this.currentSessionId, apiKey, app.currentAssistant.id
            );
            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: '请求失败' }));
                throw new Error(error.detail || '重新生成失败');
            }
            await this._consumeStream(response);
            await this.refreshSessions();
        } catch (e) {
            console.error(e);
            this.addSystemMessage(`错误: ${e.message}`);
            showToast('重新生成失败', 'error');
        } finally {
            this.isStreaming = false;
            sendBtn.disabled = false;
            sendBtn.textContent = '发送';
        }
    }

    exportSession() {
        if (!this.messages.length) {
            showToast('当前对话为空', 'error');
            return;
        }
        const assistantName = app.currentAssistant?.name || '助手';
        const title = document.getElementById('currentSessionTitle').textContent || '对话';
        const lines = [`# ${title}`, ``, `> 助手：${assistantName}`, ``];
        this.messages.forEach(m => {
            const tag = m.role === 'user' ? '🧑 我' : (m.role === 'assistant' ? '🤖 助手' : 'ℹ 系统');
            lines.push(`## ${tag}`, '', m.content || '', '');
        });
        const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const safeTitle = title.replace(/[\\/:*?"<>|]+/g, '_').slice(0, 50);
        a.href = url;
        a.download = `${safeTitle}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // --- Memory note modal -------------------------------------------------

    async openMemoryModal() {
        const assistantId = app.currentAssistant?.id;
        if (!assistantId) {
            showToast('请先选择助手', 'error');
            return;
        }
        try {
            const data = await api.getMemory(assistantId);
            document.getElementById('memoryNoteInput').value = data.memory || '';
            document.getElementById('memoryModal').style.display = 'flex';
        } catch (e) {
            console.error(e);
            showToast('加载备忘失败', 'error');
        }
    }

    closeMemoryModal() {
        document.getElementById('memoryModal').style.display = 'none';
    }

    async saveMemory() {
        const assistantId = app.currentAssistant?.id;
        if (!assistantId) return;
        const text = document.getElementById('memoryNoteInput').value;
        try {
            await api.saveMemory(assistantId, text);
            this.closeMemoryModal();
            showToast('备忘已保存', 'success');
        } catch (e) {
            console.error(e);
            showToast(e.message || '保存失败', 'error');
        }
    }

    // --- Formatting --------------------------------------------------------

    formatMessage(content) {
        let formatted = (content || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre><code>${code.trim()}</code></pre>`;
        });
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/\n/g, '<br>');
        return formatted;
    }

    showChatView() {
        document.getElementById('assistantSelectionView').classList.remove('active');
        document.getElementById('chatView').classList.add('active');
        document.getElementById('quizView').classList.remove('active');
    }
}

// Export singleton instance
const chatManager = new ChatManager();
