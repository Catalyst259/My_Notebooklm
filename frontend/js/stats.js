class StatsManager {
    constructor() {
        this._chart = null;
        this._assistantId = null;
    }

    init() {
        document.getElementById('openStatsBtn')?.addEventListener('click', () => this.show());
        document.getElementById('statsBackBtn')?.addEventListener('click', () => {
            chatManager.showChatView();
        });
    }

    onAssistantChanged(assistantId) {
        this._assistantId = assistantId;
    }

    async show(assistantId) {
        if (!window.app || !window.app.currentAssistant) {
            showToast('请先选择助手', 'error');
            return;
        }
        this._assistantId = assistantId || window.app.currentAssistant.id;

        document.getElementById('assistantSelectionView').classList.remove('active');
        document.getElementById('chatView').classList.remove('active');
        document.getElementById('quizView').classList.remove('active');
        document.getElementById('mindmapView').classList.remove('active');
        document.getElementById('reviewView').classList.remove('active');
        document.getElementById('statsView').classList.add('active');
        if (window.app) app.setBodyMode('stats');

        await this._load();
    }

    async _load() {
        if (!this._assistantId) return;
        try {
            const [userStats, dashStats] = await Promise.all([
                api.getUserStats(),
                api.getDashboardStats(this._assistantId, _localDateStr()),
            ]);
            this._renderStreak(userStats);
            this._renderHeatmap(userStats.activity_log || {});
            this._renderQuizChart(dashStats.quiz_history || []);
            this._renderReviewRate(dashStats.review || {});
            this._renderKb(dashStats.kb || {});
        } catch (err) {
            console.error('Stats load failed:', err);
        }
    }

    _renderStreak(stats) {
        const streak = stats.streak || {};
        document.getElementById('streakCurrent').textContent = streak.current ?? 0;
        document.getElementById('streakMax').textContent = streak.max ?? 0;
    }

    _renderHeatmap(activityLog) {
        const container = document.getElementById('statsHeatmap');
        container.innerHTML = '';

        const today = new Date();
        const days = 28;
        const cells = [];

        for (let i = days - 1; i >= 0; i--) {
            const d = new Date(today);
            d.setDate(today.getDate() - i);
            const key = _dateToStr(d);
            const count = activityLog[key] || 0;
            cells.push({ key, count });
        }

        const max = Math.max(1, ...cells.map(c => c.count));

        cells.forEach(({ key, count }) => {
            const cell = document.createElement('div');
            cell.className = 'heatmap-cell';
            const intensity = count === 0 ? 0 : Math.ceil((count / max) * 4);
            cell.dataset.level = intensity;
            cell.title = `${key}: ${count} 次活动`;
            container.appendChild(cell);
        });
    }

    _renderQuizChart(records) {
        const canvas = document.getElementById('statsQuizChart');
        const noData = document.getElementById('statsNoQuiz');

        if (!records.length) {
            canvas.style.display = 'none';
            noData.style.display = 'block';
            return;
        }
        canvas.style.display = 'block';
        noData.style.display = 'none';

        const labels = records.map((r, i) => `第${i + 1}次`);
        const data = records.map(r => Math.round(r.score * 100));

        if (this._chart) {
            this._chart.destroy();
            this._chart = null;
        }

        this._chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: '得分 %',
                    data,
                    borderColor: '#8AB4F8',
                    backgroundColor: 'rgba(138,180,248,0.10)',
                    pointBackgroundColor: '#8AB4F8',
                    tension: 0.3,
                    fill: true,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        min: 0, max: 100,
                        ticks: { color: '#9AA0A6', font: { size: 11 } },
                        grid: { color: 'rgba(255,255,255,0.05)' },
                    },
                    x: {
                        ticks: { color: '#9AA0A6', font: { size: 11 } },
                        grid: { display: false },
                    }
                }
            }
        });
    }

    _renderReviewRate(review) {
        const bar = document.getElementById('statsRateBar');
        const text = document.getElementById('statsRateText');
        const detail = document.getElementById('statsRateDetail');

        const { total = 0, done = 0, rate } = review;
        if (total === 0) {
            bar.style.width = '0%';
            text.textContent = '今日无复习任务';
            detail.textContent = '';
            return;
        }
        const pct = rate != null ? Math.round(rate * 100) : 0;
        bar.style.width = `${pct}%`;
        text.textContent = `${pct}%`;
        detail.textContent = `已完成 ${done} / ${total} 张`;
    }

    _renderKb(kb) {
        const el = document.getElementById('statsKbInfo');
        el.innerHTML = `
            <div class="kb-stat-item"><span class="kb-stat-val">${kb.total_files ?? 0}</span><span class="kb-stat-label">文件</span></div>
            <div class="kb-stat-item"><span class="kb-stat-val">${kb.total_chunks ?? 0}</span><span class="kb-stat-label">知识块</span></div>
            <div class="kb-stat-item"><span class="kb-stat-val">${_fmtTokens(kb.total_tokens)}</span><span class="kb-stat-label">Token</span></div>
        `;
    }
}

function _dateToStr(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

function _fmtTokens(n) {
    if (!n) return '0';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return String(n);
}

const statsManager = new StatsManager();
