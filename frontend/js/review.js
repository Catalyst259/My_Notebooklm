class ReviewManager {
    constructor() {
        this.todayQueue = null;
        this.todayItems = {};
        this.allItems = [];
        this.currentItemIndex = 0;
        this.currentItem = null;
        this.activeTab = 'today';
    }

    init() {
        document.getElementById('openReviewBtn')?.addEventListener('click', () => this.show());
        document.getElementById('reviewTabToday')?.addEventListener('click', () => this.switchTab('today'));
        document.getElementById('reviewTabAll')?.addEventListener('click', () => this.switchTab('all'));
        document.getElementById('cancelReviewDraftBtn')?.addEventListener('click', () => this.closeDraftModal());
        document.getElementById('saveReviewDraftBtn')?.addEventListener('click', () => this.saveDraft());
    }

    onAssistantChanged() {
        this.todayQueue = null;
        this.todayItems = {};
        this.allItems = [];
        this.currentItemIndex = 0;
        this.currentItem = null;
    }

    async show() {
        if (!window.app || !window.app.currentAssistant) {
            showToast('请先选择助手', 'error');
            return;
        }
        document.getElementById('assistantSelectionView').classList.remove('active');
        document.getElementById('chatView').classList.remove('active');
        document.getElementById('quizView').classList.remove('active');
        document.getElementById('mindmapView').classList.remove('active');
        document.getElementById('reviewView').classList.add('active');
        if (window.app) app.setBodyMode('review');
        await this.switchTab('today');
    }

    async switchTab(tab) {
        this.activeTab = tab;
        document.getElementById('reviewTabToday').classList.toggle('btn-primary', tab === 'today');
        document.getElementById('reviewTabToday').classList.toggle('btn-secondary', tab !== 'today');
        document.getElementById('reviewTabAll').classList.toggle('btn-primary', tab === 'all');
        document.getElementById('reviewTabAll').classList.toggle('btn-secondary', tab !== 'all');
        document.getElementById('reviewTodayPanel').hidden = tab !== 'today';
        document.getElementById('reviewAllPanel').hidden = tab !== 'all';
        if (tab === 'today') await this.loadTodayQueue();
        else await this.loadAllItems();
    }

    async loadTodayQueue() {
        const aid = window.app.currentAssistant.id;
        try {
            const data = await api.getTodayReview(aid);
            this.todayQueue = data.queue || { entries: [] };
            this.todayItems = data.items || {};
            this.currentItemIndex = this.todayQueue.entries.findIndex(e => e.status !== 'done');
            if (this.currentItemIndex < 0) this.currentItemIndex = this.todayQueue.entries.length;
            this.renderTodayQueue();
            this.renderReviewSidebar();
        } catch (e) {
            console.error(e);
            showToast('加载今日复习失败', 'error');
        }
    }

    renderReviewSidebar() {
        const container = document.getElementById('reviewList');
        if (!container) return;
        const entries = this.todayQueue?.entries || [];
        if (!entries.length) {
            container.innerHTML = '<div class="mindmap-list-empty">今日无任务</div>';
            return;
        }
        container.innerHTML = entries.map((entry, idx) => {
            const item = this.todayItems[entry.item_id] || {};
            const preview = escapeHtml((item.snapshot && item.snapshot.front) || entry.item_id);
            const active = idx === this.currentItemIndex ? 'active' : '';
            const meta = entry.status === 'done' ? '已完成' : '待复习';
            return `
                <div class="mindmap-list-item ${active}" data-index="${idx}">
                    <div class="mindmap-list-item-main">
                        <div class="mindmap-list-item-title">${preview}</div>
                        <div class="mindmap-list-item-meta">${meta}</div>
                    </div>
                </div>
            `;
        }).join('');
        container.querySelectorAll('.mindmap-list-item').forEach(el => {
            el.addEventListener('click', () => {
                this.currentItemIndex = Number(el.dataset.index || 0);
                this.renderTodayQueue();
                this.renderReviewSidebar();
            });
        });
    }

    renderTodayQueue() {
        const container = document.getElementById('reviewTodayPanel');
        const entries = this.todayQueue?.entries || [];
        if (!entries.length) {
            container.innerHTML = '<div class="mindmap-empty-hint"><p>今日无复习任务</p></div>';
            return;
        }
        const entry = entries[this.currentItemIndex];
        if (!entry) {
            this.renderSummary(container);
            return;
        }
        const item = this.todayItems[entry.item_id];
        if (!item) {
            container.innerHTML = '<div class="mindmap-empty-hint"><p>项目不存在</p></div>';
            return;
        }
        this.currentItem = item;
        this.renderCurrentItem(container);
    }

    renderCurrentItem(container) {
        const item = this.currentItem;
        const snapshot = item.snapshot || {};
        const front = escapeHtml(snapshot.front || '');
        const back = escapeHtml(snapshot.back || snapshot.answer_key || '');
        const options = Array.isArray(snapshot.options) ? snapshot.options : [];

        let body = '';
        if (item.type === 'mcq') {
            body = `
                <div class="review-card-front">${front}</div>
                <div class="options">
                    ${options.map((opt, idx) => {
                        const letter = String.fromCharCode(65 + idx);
                        return `<label class="option"><input type="radio" name="reviewMcq" value="${letter}"> ${escapeHtml(opt)}</label>`;
                    }).join('')}
                </div>
                <button id="reviewSubmitMcqBtn" class="btn btn-primary">提交</button>
            `;
        } else if (item.type === 'qa') {
            body = `
                <div class="review-card-front">${front}</div>
                <textarea id="reviewQaAnswer" class="answer-input" placeholder="输入你的答案..."></textarea>
                <div class="review-card-actions">
                    <button id="reviewSubmitQaBtn" class="btn btn-primary">提交</button>
                    <button class="btn btn-danger" data-self="again">不会</button>
                    <button class="btn btn-secondary" data-self="hard">模糊</button>
                    <button class="btn btn-primary" data-self="good">会</button>
                </div>
            `;
        } else {
            body = `
                <div class="review-card-front">${front}</div>
                <div id="reviewCardBack" class="review-card-back" style="display:none;">${back}</div>
                <div class="review-card-actions">
                    <button id="reviewShowBtn" class="btn btn-primary">查看答案</button>
                    <div id="reviewRatingBtns" style="display:none; gap:8px;">
                        <button class="btn btn-danger" data-self="again">不会</button>
                        <button class="btn btn-secondary" data-self="hard">模糊</button>
                        <button class="btn btn-primary" data-self="good">会</button>
                    </div>
                </div>
            `;
        }

        container.innerHTML = `
            <div class="review-card">
                <div class="file-meta">${escapeHtml(item.source?.label || item.source?.type || '')}</div>
                ${body}
                <div id="reviewFeedback" class="review-card-back" style="display:none;"></div>
                <div class="review-card-actions">
                    <button id="reviewArchiveBtn" class="btn btn-secondary">已掌握</button>
                </div>
            </div>
        `;

        document.getElementById('reviewArchiveBtn')?.addEventListener('click', () => this.archiveCurrentItem());

        if (item.type === 'mcq') {
            document.getElementById('reviewSubmitMcqBtn')?.addEventListener('click', async () => {
                const checked = document.querySelector('input[name="reviewMcq"]:checked');
                if (!checked) {
                    showToast('请选择答案', 'error');
                    return;
                }
                await this.submitResponse({ answer: checked.value });
            });
        } else if (item.type === 'qa') {
            document.getElementById('reviewSubmitQaBtn')?.addEventListener('click', async () => {
                const answer = document.getElementById('reviewQaAnswer').value.trim();
                await this.submitResponse({ answer });
            });
            container.querySelectorAll('[data-self]').forEach(btn => {
                btn.addEventListener('click', async () => this.submitResponse({ self_rating: btn.dataset.self }));
            });
        } else {
            document.getElementById('reviewShowBtn')?.addEventListener('click', () => {
                document.getElementById('reviewCardBack').style.display = 'block';
                document.getElementById('reviewShowBtn').style.display = 'none';
                document.getElementById('reviewRatingBtns').style.display = 'flex';
            });
            container.querySelectorAll('[data-self]').forEach(btn => {
                btn.addEventListener('click', async () => this.submitResponse({ self_rating: btn.dataset.self }));
            });
        }
    }

    async submitResponse(payload) {
        const apiKey = localStorage.getItem('deepseek_api_key') || '';
        const aid = window.app.currentAssistant.id;
        try {
            const data = await api.gradeReviewItem(apiKey, aid, this.currentItem.id, payload);
            const grade = data.grade || {};
            const feedbackEl = document.getElementById('reviewFeedback');
            if (feedbackEl) {
                feedbackEl.style.display = 'block';
                feedbackEl.innerHTML = `${escapeHtml(grade.feedback || '')}<br><br><strong>参考答案:</strong> ${escapeHtml(grade.reference_answer || '')}`;
            }
            showToast('已提交', 'success');
            this.todayQueue.entries[this.currentItemIndex].status = 'done';
            this.todayQueue.entries[this.currentItemIndex].grade = grade.score;
            this.currentItemIndex = this.todayQueue.entries.findIndex(e => e.status !== 'done');
            if (this.currentItemIndex < 0) this.currentItemIndex = this.todayQueue.entries.length;
            this.renderReviewSidebar();
            setTimeout(() => this.renderTodayQueue(), 800);
        } catch (e) {
            console.error(e);
            showToast(e.message || '提交失败', 'error');
        }
    }

    renderSummary(container) {
        const entries = this.todayQueue?.entries || [];
        const done = entries.filter(e => e.status === 'done');
        const correct = done.filter(e => e.grade >= 1).length;
        const partial = done.filter(e => e.grade === 0.5).length;
        const wrong = done.filter(e => e.grade === 0).length;
        const weak = done.filter(e => e.grade < 1).map(e => this.todayItems[e.item_id]).filter(Boolean);
        container.innerHTML = `
            <div class="review-card">
                <div class="review-card-front">今天完成 ${done.length} 条 · 答对 ${correct} · 模糊 ${partial} · 答错 ${wrong}</div>
                <div class="review-card-back">${weak.map(it => escapeHtml(it.snapshot?.front || '')).join('<br>') || '无重点回看项'}</div>
            </div>
        `;
    }

    async loadAllItems() {
        const aid = window.app.currentAssistant.id;
        try {
            const data = await api.listReviewItems(aid, true);
            this.allItems = data.items || [];
            this.renderAllItems();
        } catch (e) {
            console.error(e);
            showToast('加载失败', 'error');
        }
    }

    renderAllItems() {
        const container = document.getElementById('reviewAllPanel');
        if (!this.allItems.length) {
            container.innerHTML = '<div class="mindmap-empty-hint"><p>暂无复习项</p></div>';
            return;
        }
        container.innerHTML = this.allItems.map(it => `
            <div class="file-item">
                <div class="file-info">
                    <div class="file-name">${escapeHtml(it.front_preview || '(无预览)')}</div>
                    <div class="file-meta">${it.type} · ${it.status} · 下次复习: ${it.next_review}</div>
                </div>
                <div style="display:flex; gap:8px;">
                    <button class="btn-icon-xs" data-action="toggle" data-id="${it.id}" data-status="${it.status}" title="切换状态">
                        <span class="material-symbols-outlined" style="font-size:14px;">${it.status === 'archived' ? 'undo' : 'archive'}</span>
                    </button>
                    <button class="file-delete-btn" data-action="delete" data-id="${it.id}">
                        <span class="material-symbols-outlined" style="font-size:16px;">delete</span>
                    </button>
                </div>
            </div>
        `).join('');
        container.querySelectorAll('[data-action="delete"]').forEach(btn => {
            btn.addEventListener('click', () => this.deleteItem(btn.dataset.id));
        });
        container.querySelectorAll('[data-action="toggle"]').forEach(btn => {
            btn.addEventListener('click', () => this.toggleArchive(btn.dataset.id, btn.dataset.status));
        });
    }

    async archiveCurrentItem() {
        if (!this.currentItem) return;
        await this.toggleArchive(this.currentItem.id, 'active');
        this.todayQueue.entries[this.currentItemIndex].status = 'done';
        this.currentItemIndex = this.todayQueue.entries.findIndex(e => e.status !== 'done');
        if (this.currentItemIndex < 0) this.currentItemIndex = this.todayQueue.entries.length;
        this.renderReviewSidebar();
        this.renderTodayQueue();
    }

    async toggleArchive(itemId, status) {
        const aid = window.app.currentAssistant.id;
        try {
            if (status === 'archived') await api.reactivateReviewItem(aid, itemId);
            else await api.archiveReviewItem(aid, itemId);
            await this.loadAllItems();
            showToast(status === 'archived' ? '已重新加入复习' : '已标记为掌握', 'success');
        } catch (e) {
            console.error(e);
            showToast('操作失败', 'error');
        }
    }

    async deleteItem(itemId) {
        if (!confirm('确定删除？')) return;
        const aid = window.app.currentAssistant.id;
        try {
            await api.deleteReviewItem(aid, itemId);
            await this.loadAllItems();
            showToast('已删除', 'success');
        } catch (e) {
            console.error(e);
            showToast('删除失败', 'error');
        }
    }

    openDraftModal(sourceContent, sourceContext = '') {
        this._draftSource = sourceContent;
        this._draftContext = sourceContext;
        document.getElementById('reviewDraftFront').value = '';
        document.getElementById('reviewDraftBack').value = '';
        document.getElementById('reviewDraftStatus').textContent = 'AI 正在起草...';
        document.getElementById('reviewDraftModal').style.display = 'flex';
        this.runDraft();
    }

    async runDraft() {
        const apiKey = localStorage.getItem('deepseek_api_key');
        if (!apiKey) {
            document.getElementById('reviewDraftStatus').textContent = '未配置 API Key，请手动填写。';
            return;
        }
        const aid = window.app.currentAssistant.id;
        try {
            const result = await api.draftReviewCard(apiKey, aid, this._draftSource, this._draftContext);
            document.getElementById('reviewDraftFront').value = result.front || '';
            document.getElementById('reviewDraftBack').value = result.back || '';
            document.getElementById('reviewDraftStatus').textContent = 'AI 已生成，可编辑后保存。';
        } catch (e) {
            console.error(e);
            document.getElementById('reviewDraftStatus').textContent = `生成失败: ${e.message}`;
        }
    }

    closeDraftModal() {
        document.getElementById('reviewDraftModal').style.display = 'none';
    }

    async saveDraft() {
        const front = document.getElementById('reviewDraftFront').value.trim();
        const back = document.getElementById('reviewDraftBack').value.trim();
        if (!front || !back) {
            showToast('正面和背面不能为空', 'error');
            return;
        }
        const aid = window.app.currentAssistant.id;
        try {
            await api.createReviewItem(aid, 'card', { front, back }, { type: 'manual', ref: '', label: this._draftContext || '' });
            this.closeDraftModal();
            showToast('已加入复习', 'success');
        } catch (e) {
            console.error(e);
            showToast('保存失败', 'error');
        }
    }
}

const reviewManager = window.reviewManager = new ReviewManager();
