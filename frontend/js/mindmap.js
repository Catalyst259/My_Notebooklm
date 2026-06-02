// Mind-map manager: per-assistant collection of jsmind-backed mind-maps with
// AI-assisted operations (generate-tree, expand-node, generate-note).
//
// Exposes window.mindmapManager. Loaded after vendor/jsmind.js.

const MINDMAP_MAX_NODES = 500;
const MINDMAP_AUTOSAVE_DEBOUNCE_MS = 2000;

class MindMapManager {
    constructor() {
        this.jm = null;                  // jsmind instance
        this.mindmaps = [];              // sidebar list
        this.currentMap = null;          // full envelope of the open map, or null
        this.dirty = false;
        this.saveTimer = null;
        this.streaming = false;
        this.streamAbort = null;
        this.selectedNodeId = null;
        this.openNoteNodeId = null;
        this._inited = false;
    }

    // ----- lifecycle -----

    init() {
        if (this._inited) return;
        this._inited = true;
        this._bindStaticListeners();
        this._initJsMind();
        window.addEventListener('beforeunload', () => this._forceFlushSync());
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') this.flushSave();
        });
    }

    _initJsMind() {
        if (typeof jsMind === 'undefined') {
            console.warn('jsMind not loaded');
            return;
        }
        const options = {
            container: 'mindmapCanvas',
            editable: true,
            theme: 'primary',
            view: { engine: 'svg', hmargin: 80, vmargin: 40 },
            layout: { hspace: 30, vspace: 20, pspace: 13 },
            shortcut: { enable: false },
        };
        this.jm = new jsMind(options);
        this.jm.add_event_listener((type, data) => this._onJsMindEvent(type, data));
    }

    _onJsMindEvent(type, data) {
        // jsMind event constants: 1=show, 2=resize, 3=edit, 4=select
        if (type === 3) {
            // structural edit (add/remove/rename via library)
            this._markDirty();
        } else if (type === 4) {
            const id = data && (data.node || data.id || data);
            if (id) this.selectedNodeId = typeof id === 'string' ? id : id.id || null;
        }
    }

    _bindStaticListeners() {
        const byId = (id) => document.getElementById(id);

        byId('openMindmapBtn')?.addEventListener('click', () => this.show());
        byId('newBlankMindmapBtn')?.addEventListener('click', () => this._openBlankModal());
        byId('newAiMindmapBtn')?.addEventListener('click', () => this._openAiModal());
        byId('emptyNewBlankBtn')?.addEventListener('click', () => this._openBlankModal());
        byId('emptyNewAiBtn')?.addEventListener('click', () => this._openAiModal());

        byId('cancelMindmapBlankBtn')?.addEventListener('click', () => this._hideModal('mindmapNewBlankModal'));
        byId('confirmMindmapBlankBtn')?.addEventListener('click', () => this._confirmBlank());
        byId('cancelMindmapAiBtn')?.addEventListener('click', () => this._hideModal('mindmapNewAiModal'));
        byId('confirmMindmapAiBtn')?.addEventListener('click', () => this._confirmAi());
        byId('cancelMindmapRenameBtn')?.addEventListener('click', () => this._hideModal('mindmapRenameModal'));
        byId('confirmMindmapRenameBtn')?.addEventListener('click', () => this._confirmRename());
        byId('cancelMindmapNodeEditBtn')?.addEventListener('click', () => this._hideModal('mindmapNodeEditModal'));
        byId('confirmMindmapNodeEditBtn')?.addEventListener('click', () => this._confirmNodeEdit());

        byId('mindmapCancelAiBtn')?.addEventListener('click', () => this.cancelStream());
        byId('mindmapExportBtn')?.addEventListener('click', () => this.exportMarkdown());
        byId('mindmapCopyBtn')?.addEventListener('click', () => this.copyMarkdown());
        byId('mindmapBackBtn')?.addEventListener('click', () => chatManager.showChatView());

        byId('mindmapNoteCloseBtn')?.addEventListener('click', () => this._hideNotePanel());
        byId('mindmapNoteAiBtn')?.addEventListener('click', () => this.generateNoteForSelected());
        byId('mindmapNoteEditBtn')?.addEventListener('click', () => this._editNoteForSelected());

        // jsmind canvas context menu for per-node actions
        const canvas = byId('mindmapCanvas');
        canvas?.addEventListener('contextmenu', (e) => this._onCanvasContextMenu(e));
    }

    // ----- view switching -----

    async show() {
        if (!window.app || !window.app.currentAssistant) {
            showToast('请先选择助手', 'error');
            return;
        }
        document.getElementById('statsView').classList.remove('active');
        document.getElementById('assistantSelectionView').classList.remove('active');
        document.getElementById('chatView').classList.remove('active');
        document.getElementById('quizView').classList.remove('active');
        document.getElementById('reviewView').classList.remove('active');
        document.getElementById('mindmapView').classList.add('active');
        if (window.app) app.setBodyMode('mindmap');
        await this.refreshList();
        if (this.mindmaps.length > 0 && !this.currentMap) {
            await this.openMap(this.mindmaps[0].id);
        } else if (this.currentMap) {
            this._renderCurrentMap();
        } else {
            this._showEmptyHint(true);
        }
    }

    hide() {
        this.flushSave();
        document.getElementById('mindmapView').classList.remove('active');
    }

    onAssistantChanged() {
        // Flush any pending save (for the previous assistant) then reset local state.
        this.flushSave();
        this.currentMap = null;
        this.mindmaps = [];
        this.dirty = false;
        if (this.saveTimer) { clearTimeout(this.saveTimer); this.saveTimer = null; }
        this.cancelStream();
        this._textBuf = '';
        this._showEmptyHint(true);
        this._renderList();
    }

    // ----- list / CRUD -----

    async refreshList() {
        const aid = window.app.currentAssistant.id;
        try {
            const data = await api.listMindmaps(aid);
            this.mindmaps = data.mindmaps || [];
            this._renderList();
        } catch (e) {
            console.error('listMindmaps failed', e);
            showToast('加载思维导图列表失败', 'error');
        }
    }

    _renderList() {
        const container = document.getElementById('mindmapList');
        if (!container) return;
        if (this.mindmaps.length === 0) {
            container.innerHTML = '<div class="mindmap-list-empty">暂无思维导图</div>';
            return;
        }
        const activeId = this.currentMap?.id;
        container.innerHTML = this.mindmaps.map(m => `
            <div class="mindmap-list-item ${m.id === activeId ? 'active' : ''}" data-id="${m.id}">
                <div class="mindmap-list-item-main">
                    <div class="mindmap-list-item-title">${escapeHtml(m.title)}</div>
                    <div class="mindmap-list-item-meta">${m.node_count} 节点 · ${formatRelativeTime(m.updated_at)}</div>
                </div>
                <div class="mindmap-list-item-actions">
                    <button class="btn-icon-xs" data-action="rename" title="重命名">
                        <span class="material-symbols-outlined" style="font-size:14px;">edit</span>
                    </button>
                    <button class="btn-icon-xs" data-action="delete" title="删除">
                        <span class="material-symbols-outlined" style="font-size:14px;">delete</span>
                    </button>
                </div>
            </div>
        `).join('');
        container.querySelectorAll('.mindmap-list-item').forEach(el => {
            const id = el.dataset.id;
            el.addEventListener('click', (e) => {
                if (e.target.closest('button')) return;
                this.openMap(id);
            });
            el.querySelector('[data-action="rename"]')?.addEventListener('click', (e) => {
                e.stopPropagation();
                this._openRenameModal(id);
            });
            el.querySelector('[data-action="delete"]')?.addEventListener('click', (e) => {
                e.stopPropagation();
                this._deleteMap(id);
            });
        });
    }

    async openMap(mapId) {
        if (this.streaming) {
            showToast('AI 正在生成，请先取消或等待完成', 'warning');
            return;
        }
        await this.flushSave();
        const aid = window.app.currentAssistant.id;
        try {
            const data = await api.getMindmap(aid, mapId);
            this.currentMap = data.mindmap;
            this._renderCurrentMap();
            this._renderList();
        } catch (e) {
            console.error('openMap failed', e);
            showToast('加载思维导图失败', 'error');
        }
    }

    _renderCurrentMap() {
        if (!this.currentMap || !this.jm) return;
        this._showEmptyHint(false);
        this.jm.show(this.currentMap.jsmind);
        document.getElementById('currentMindmapTitle').textContent = this.currentMap.title;
        this.dirty = false;
        this._renderSaveBadge('saved');
        this.selectedNodeId = null;
        this._hideNotePanel();
    }

    _showEmptyHint(show) {
        const hint = document.getElementById('mindmapEmptyHint');
        const canvas = document.getElementById('mindmapCanvas');
        if (hint) hint.style.display = show ? 'flex' : 'none';
        if (canvas) canvas.style.display = show ? 'none' : 'block';
        if (show) document.getElementById('currentMindmapTitle').textContent = '未选择';
    }

    async _deleteMap(mapId) {
        const target = this.mindmaps.find(m => m.id === mapId);
        if (!target) return;
        if (!confirm(`确定要删除「${target.title}」吗？此操作不可撤销。`)) return;
        const aid = window.app.currentAssistant.id;
        try {
            await api.deleteMindmap(aid, mapId);
            if (this.currentMap && this.currentMap.id === mapId) {
                this.currentMap = null;
                this._showEmptyHint(true);
            }
            await this.refreshList();
            showToast('已删除', 'success');
        } catch (e) {
            console.error('deleteMindmap failed', e);
            showToast('删除失败', 'error');
        }
    }

    // ----- modal handlers -----

    _showModal(id) { document.getElementById(id).style.display = 'flex'; }
    _hideModal(id) { document.getElementById(id).style.display = 'none'; }

    _openBlankModal() {
        document.getElementById('mindmapBlankTitle').value = '';
        this._showModal('mindmapNewBlankModal');
        setTimeout(() => document.getElementById('mindmapBlankTitle').focus(), 50);
    }

    async _confirmBlank() {
        const title = document.getElementById('mindmapBlankTitle').value.trim();
        if (!title) { showToast('请输入标题', 'error'); return; }
        const aid = window.app.currentAssistant.id;
        try {
            const data = await api.createMindmap(aid, title);
            this._hideModal('mindmapNewBlankModal');
            this.currentMap = data.mindmap;
            this._renderCurrentMap();
            await this.refreshList();
        } catch (e) {
            console.error(e);
            showToast('创建失败', 'error');
        }
    }

    _openAiModal() {
        document.getElementById('mindmapAiTopic').value = '';
        document.getElementById('mindmapAiTitle').value = '';
        document.getElementById('mindmapAiDepth').value = '2';
        document.getElementById('mindmapAiWidth').value = '4';
        this._showModal('mindmapNewAiModal');
        setTimeout(() => document.getElementById('mindmapAiTopic').focus(), 50);
    }

    async _confirmAi() {
        const topic = document.getElementById('mindmapAiTopic').value.trim();
        const title = document.getElementById('mindmapAiTitle').value.trim() || topic;
        const depth = parseInt(document.getElementById('mindmapAiDepth').value) || 2;
        const width = Math.max(2, Math.min(8, parseInt(document.getElementById('mindmapAiWidth').value) || 4));
        if (!topic) { showToast('请输入主题', 'error'); return; }

        const apiKey = (typeof localStorage !== 'undefined' && localStorage.getItem('deepseek_api_key')) || '';
        if (!apiKey) { showToast('请先在左侧保存 API 密钥', 'error'); return; }

        const aid = window.app.currentAssistant.id;
        try {
            // Create the map first with the chosen title and a placeholder root.
            const data = await api.createMindmap(aid, title);
            this.currentMap = data.mindmap;
            // Replace placeholder root topic with the actual topic for the generator anchor.
            this.currentMap.jsmind.data.topic = topic;
            this.currentMap.jsmind.meta.name = title;
            this.currentMap.title = title;
            this._renderCurrentMap();
            await this.refreshList();
            this._hideModal('mindmapNewAiModal');

            // Save the seeded state immediately (force-save before AI op).
            this._markDirty();
            await this.flushSave();

            // Stream tree into the root: parent anchor is the root node.
            await this._streamBullets({
                streamFn: () => api.streamGenerateTree(apiKey, aid, topic, depth, width, this._newAbortSignal()),
                anchorNodeId: this.currentMap.jsmind.data.id,
                treatFirstAsRoot: true,
            });
        } catch (e) {
            console.error(e);
            showToast(e.message || 'AI 生成失败', 'error');
        }
    }

    _openRenameModal(mapId) {
        const target = this.mindmaps.find(m => m.id === mapId);
        if (!target) return;
        this._renameTargetMapId = mapId;
        document.getElementById('mindmapRenameInput').value = target.title;
        this._showModal('mindmapRenameModal');
        setTimeout(() => document.getElementById('mindmapRenameInput').focus(), 50);
    }

    async _confirmRename() {
        const newTitle = document.getElementById('mindmapRenameInput').value.trim();
        if (!newTitle) { showToast('名称不能为空', 'error'); return; }
        const mapId = this._renameTargetMapId;
        const aid = window.app.currentAssistant.id;
        try {
            await api.saveMindmap(aid, mapId, newTitle, null);
            this._hideModal('mindmapRenameModal');
            if (this.currentMap && this.currentMap.id === mapId) {
                this.currentMap.title = newTitle;
                document.getElementById('currentMindmapTitle').textContent = newTitle;
            }
            await this.refreshList();
        } catch (e) {
            console.error(e);
            showToast('重命名失败', 'error');
        }
    }

    // ----- node-level operations -----

    _onCanvasContextMenu(e) {
        const target = e.target.closest('jmnode');
        if (!target) return;
        e.preventDefault();
        const nodeId = target.getAttribute('nodeid');
        if (!nodeId) return;
        this.selectedNodeId = nodeId;
        this.jm.select_node(nodeId);
        this._showNodeMenu(e.clientX, e.clientY, nodeId);
    }

    _showNodeMenu(x, y, nodeId) {
        document.querySelectorAll('.mindmap-node-menu').forEach(el => el.remove());
        const node = this.jm.get_node(nodeId);
        const isRoot = !node.parent;
        const menu = document.createElement('div');
        menu.className = 'mindmap-node-menu';
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;
        const items = [
            { label: '学习此节点', icon: 'school', action: () => this.learnNode(nodeId) },
            { label: '重命名节点', icon: 'edit', action: () => this._editNodeTopic(nodeId) },
            { label: '添加子节点', icon: 'add', action: () => this._addChildNode(nodeId) },
            { label: 'AI 扩展（添加 4 个子节点）', icon: 'auto_awesome', action: () => this.expandNode(nodeId, 4) },
            { label: 'AI 生成笔记', icon: 'edit_note', action: () => this.generateNote(nodeId) },
            { label: '查看/编辑笔记', icon: 'visibility', action: () => this._showNotePanel(nodeId) },
            { label: '加入复习', icon: 'event_repeat', action: () => this.addNodeToReview(nodeId) },
        ];
        if (!isRoot) {
            items.push({ label: '删除子树', icon: 'delete', action: () => this._deleteNode(nodeId), danger: true });
        }
        menu.innerHTML = items.map((it, i) => `
            <div class="mindmap-node-menu-item ${it.danger ? 'danger' : ''}" data-i="${i}">
                <span class="material-symbols-outlined" style="font-size:16px;vertical-align:middle;margin-right:6px;">${it.icon}</span>
                ${it.label}
            </div>
        `).join('');
        document.body.appendChild(menu);
        const close = (ev) => {
            if (!menu.contains(ev.target)) {
                menu.remove();
                document.removeEventListener('click', close, true);
            }
        };
        setTimeout(() => document.addEventListener('click', close, true), 0);
        menu.querySelectorAll('.mindmap-node-menu-item').forEach(el => {
            el.addEventListener('click', () => {
                const item = items[parseInt(el.dataset.i)];
                menu.remove();
                document.removeEventListener('click', close, true);
                item.action();
            });
        });
    }

    _editNodeTopic(nodeId) {
        const node = this.jm.get_node(nodeId);
        if (!node) return;
        this._nodeEditTargetId = nodeId;
        this._nodeEditMode = 'topic';
        document.getElementById('mindmapNodeEditTitle').textContent = '重命名节点';
        document.getElementById('mindmapNodeEditInput').value = node.topic || '';
        this._showModal('mindmapNodeEditModal');
        setTimeout(() => document.getElementById('mindmapNodeEditInput').focus(), 50);
    }

    _editNoteForSelected() {
        if (!this.openNoteNodeId) return;
        const node = this.jm.get_node(this.openNoteNodeId);
        if (!node) return;
        this._nodeEditTargetId = this.openNoteNodeId;
        this._nodeEditMode = 'note';
        document.getElementById('mindmapNodeEditTitle').textContent = '编辑节点笔记';
        document.getElementById('mindmapNodeEditInput').value = (node.data && node.data.note) || '';
        this._showModal('mindmapNodeEditModal');
        setTimeout(() => document.getElementById('mindmapNodeEditInput').focus(), 50);
    }

    _confirmNodeEdit() {
        const nodeId = this._nodeEditTargetId;
        const value = document.getElementById('mindmapNodeEditInput').value.trim();
        if (!nodeId) { this._hideModal('mindmapNodeEditModal'); return; }
        if (this._nodeEditMode === 'topic') {
            if (!value) { showToast('内容不能为空', 'error'); return; }
            this.jm.update_node(nodeId, value);
        } else {
            const node = this.jm.get_node(nodeId);
            if (node) {
                node.data = node.data || {};
                node.data.note = value;
                this._refreshNotePanel();
            }
        }
        this._markDirty();
        this._hideModal('mindmapNodeEditModal');
    }

    _addChildNode(parentId) {
        if (this._countNodes() >= MINDMAP_MAX_NODES) {
            showToast(`节点数已达上限 ${MINDMAP_MAX_NODES}，无法添加`, 'warning');
            return;
        }
        const newId = 'n_' + Math.random().toString(36).slice(2, 10);
        this.jm.add_node(parentId, newId, '新节点');
        this.jm.select_node(newId);
        this._markDirty();
        // Prompt for rename right away
        setTimeout(() => this._editNodeTopic(newId), 50);
    }

    _deleteNode(nodeId) {
        const node = this.jm.get_node(nodeId);
        if (!node) return;
        const subCount = this._countNodesUnder(node);
        if (subCount > 3 && !confirm(`确定要删除该子树（共 ${subCount} 个节点）吗？`)) return;
        this.jm.remove_node(nodeId);
        this._markDirty();
    }

    // ----- AI operations -----

    async expandNode(nodeId, count = 4) {
        if (this.streaming) { showToast('已有 AI 操作进行中', 'warning'); return; }
        const apiKey = localStorage.getItem('deepseek_api_key');
        if (!apiKey) { showToast('请先保存 API 密钥', 'error'); return; }
        if (this._countNodes() + count > MINDMAP_MAX_NODES) {
            showToast(`节点数已接近上限 ${MINDMAP_MAX_NODES}，无法扩展`, 'warning');
            return;
        }
        const node = this.jm.get_node(nodeId);
        if (!node) return;
        const path = this._pathToRoot(node);
        const siblings = (node.children || []).map(c => c.topic);
        const aid = window.app.currentAssistant.id;

        // Force-save before the AI op.
        await this.flushSave();

        await this._streamBullets({
            streamFn: () => api.streamExpandNode(apiKey, aid, path, siblings, count, this._newAbortSignal()),
            anchorNodeId: nodeId,
            treatFirstAsRoot: false,
            forceFlatDepth: true,
        });
    }

    async generateNote(nodeId) {
        if (this.streaming) { showToast('已有 AI 操作进行中', 'warning'); return; }
        const apiKey = localStorage.getItem('deepseek_api_key');
        if (!apiKey) { showToast('请先保存 API 密钥', 'error'); return; }
        const node = this.jm.get_node(nodeId);
        if (!node) return;
        const path = this._pathToRoot(node);
        const aid = window.app.currentAssistant.id;

        await this.flushSave();
        this._setStreaming(true);
        this._showNotePanel(nodeId);
        document.getElementById('mindmapNoteBody').textContent = '';

        let accumulated = '';
        try {
            const response = await api.streamGenerateNote(apiKey, aid, path, this._newAbortSignal());
            if (!response.ok) throw new Error('生成笔记请求失败');
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    let data;
                    try { data = JSON.parse(line.slice(6)); } catch { continue; }
                    if (data.error) throw new Error(data.error);
                    if (data.content) {
                        accumulated += data.content;
                        document.getElementById('mindmapNoteBody').textContent = accumulated;
                    }
                    if (data.done) break;
                }
            }
            node.data = node.data || {};
            node.data.note = accumulated.trim();
            this._refreshNotePanel();
            this._markDirty();
            await this.flushSave();
        } catch (e) {
            if (e.name === 'AbortError') {
                showToast('已取消，已生成部分已保留', 'info');
            } else {
                console.error(e);
                showToast(e.message || '生成笔记失败', 'error');
            }
            if (accumulated.trim()) {
                node.data = node.data || {};
                node.data.note = accumulated.trim();
                this._refreshNotePanel();
                this._markDirty();
            }
        } finally {
            this._setStreaming(false);
        }
    }

    generateNoteForSelected() {
        if (!this.openNoteNodeId) return;
        this.generateNote(this.openNoteNodeId);
    }

    // ----- streaming bullets (generate-tree / expand-node) -----

    async _streamBullets({ streamFn, anchorNodeId, treatFirstAsRoot, forceFlatDepth = false }) {
        this._setStreaming(true);
        let skippedLines = 0;
        let addedCount = 0;
        // depthStack[d] = parent node id at depth d. depth 0's parent is anchorNodeId.
        const depthStack = { 0: anchorNodeId };
        let buffer = '';

        const parseLine = (line) => {
            const m = line.match(/^(\s*)- (.+)$/);
            if (!m) return null;
            const indent = m[1];
            // require pure spaces, multiple of 2
            if (/\t/.test(indent) || indent.length % 2 !== 0) return null;
            const depth = indent.length / 2;
            return { depth, text: m[2].trim() };
        };

        try {
            const response = await streamFn();
            if (!response.ok) throw new Error('请求失败');
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let firstBulletConsumed = false;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const sseLines = buffer.split('\n');
                buffer = sseLines.pop() || '';

                for (const sseLine of sseLines) {
                    if (!sseLine.startsWith('data: ')) continue;
                    let data;
                    try { data = JSON.parse(sseLine.slice(6)); } catch { continue; }
                    if (data.error) throw new Error(data.error);
                    if (data.content) {
                        // accumulate content lines (NOT SSE lines)
                        let chunk = data.content;
                        let textBuf = (this._textBuf || '') + chunk;
                        const textLines = textBuf.split('\n');
                        this._textBuf = textLines.pop() || '';
                        for (const rawLine of textLines) {
                            if (!rawLine.trim()) continue;
                            const parsed = parseLine(rawLine);
                            if (!parsed) { skippedLines++; continue; }
                            let { depth, text } = parsed;

                            if (treatFirstAsRoot && !firstBulletConsumed && depth === 0) {
                                // Replace root topic with this bullet's text.
                                this.jm.update_node(anchorNodeId, text);
                                firstBulletConsumed = true;
                                continue;
                            }

                            // For expand-node we require flat depth=0 children of anchor.
                            if (forceFlatDepth && depth !== 0) {
                                skippedLines++;
                                continue;
                            }

                            // For generate-tree, the first non-root level is depth=1.
                            // Map depth 0 → anchor (root); for forceFlat, treat depth 0 as anchor's children.
                            const parentDepth = forceFlatDepth ? -1 : depth - 1;
                            const parentId = forceFlatDepth
                                ? anchorNodeId
                                : (depthStack[parentDepth] || anchorNodeId);

                            if (this._countNodes() >= MINDMAP_MAX_NODES) {
                                showToast(`节点数已达上限 ${MINDMAP_MAX_NODES}，已停止生成`, 'warning');
                                this.cancelStream();
                                break;
                            }

                            const newId = 'n_' + Math.random().toString(36).slice(2, 10);
                            try {
                                this.jm.add_node(parentId, newId, text);
                                addedCount++;
                                if (!forceFlatDepth) {
                                    depthStack[depth] = newId;
                                    // clear deeper levels
                                    Object.keys(depthStack).forEach(k => {
                                        if (parseInt(k) > depth) delete depthStack[k];
                                    });
                                }
                            } catch (err) {
                                skippedLines++;
                            }
                        }
                    }
                    if (data.done) break;
                }
            }

            // tail: try last buffered text line
            if (this._textBuf) {
                const parsed = parseLine(this._textBuf);
                if (parsed) {
                    // best-effort apply (same logic as inside loop)
                    const { depth, text } = parsed;
                    const parentId = forceFlatDepth
                        ? anchorNodeId
                        : (depthStack[depth - 1] || anchorNodeId);
                    try {
                        const newId = 'n_' + Math.random().toString(36).slice(2, 10);
                        this.jm.add_node(parentId, newId, text);
                        addedCount++;
                    } catch {}
                } else if (this._textBuf.trim()) {
                    skippedLines++;
                }
                this._textBuf = '';
            }

            if (addedCount === 0) {
                showToast('AI 未生成有效内容，请重试', 'warning');
            } else if (skippedLines > 0) {
                showToast(`AI 输出有 ${skippedLines} 行无法解析，已忽略`, 'info');
            }
            this._markDirty();
            await this.flushSave();
        } catch (e) {
            if (e.name === 'AbortError') {
                showToast('已取消，已生成部分已保留', 'info');
                this._markDirty();
                await this.flushSave();
            } else {
                console.error(e);
                showToast(e.message || 'AI 生成失败', 'error');
            }
        } finally {
            this._textBuf = '';
            this._setStreaming(false);
        }
    }

    _newAbortSignal() {
        this.streamAbort = new AbortController();
        return this.streamAbort.signal;
    }

    cancelStream() {
        if (this.streamAbort) {
            this.streamAbort.abort();
            this.streamAbort = null;
        }
    }

    _setStreaming(isStreaming) {
        this.streaming = isStreaming;
        const statusEl = document.getElementById('mindmapAiStatus');
        if (statusEl) statusEl.style.display = isStreaming ? 'inline-flex' : 'none';
    }

    // ----- auto-save -----

    _markDirty() {
        this.dirty = true;
        this._renderSaveBadge('dirty');
        if (this.saveTimer) clearTimeout(this.saveTimer);
        this.saveTimer = setTimeout(() => this.flushSave(), MINDMAP_AUTOSAVE_DEBOUNCE_MS);
    }

    async flushSave() {
        if (this.saveTimer) { clearTimeout(this.saveTimer); this.saveTimer = null; }
        if (!this.currentMap || !this.dirty) return;
        const aid = window.app.currentAssistant.id;
        const mapId = this.currentMap.id;
        const title = this.currentMap.title;
        const blob = this.jm ? this.jm.get_data() : this.currentMap.jsmind;
        this.currentMap.jsmind = blob;
        this._renderSaveBadge('saving');
        try {
            const data = await api.saveMindmap(aid, mapId, title, blob);
            this.currentMap = data.mindmap;
            this.dirty = false;
            this._renderSaveBadge('saved');
            // Update sidebar entry (node count, updated_at).
            await this.refreshList();
        } catch (e) {
            console.error('saveMindmap failed', e);
            this._renderSaveBadge('error');
            // keep dirty=true so the next debounce retries
            this.saveTimer = setTimeout(() => this.flushSave(), MINDMAP_AUTOSAVE_DEBOUNCE_MS);
        }
    }

    _forceFlushSync() {
        // Best-effort on tab close: use sendBeacon if dirty.
        if (!this.currentMap || !this.dirty) return;
        try {
            const blob = this.jm ? this.jm.get_data() : this.currentMap.jsmind;
            const fd = new FormData();
            fd.append('assistant_id', window.app.currentAssistant.id);
            fd.append('title', this.currentMap.title);
            fd.append('jsmind_json', JSON.stringify(blob));
            navigator.sendBeacon(
                `${api.baseUrl}/api/mindmaps/${this.currentMap.id}`,
                fd
            );
        } catch (e) { /* swallow */ }
    }

    _renderSaveBadge(state) {
        const el = document.getElementById('mindmapSaveStatus');
        if (!el) return;
        const map = {
            saved:  { text: '已保存', cls: 'saved' },
            dirty:  { text: '未保存', cls: 'dirty' },
            saving: { text: '保存中…', cls: 'saving' },
            error:  { text: '保存失败（重试中）', cls: 'error' },
        };
        const cfg = map[state] || map.saved;
        el.textContent = cfg.text;
        el.className = `mindmap-save-status ${cfg.cls}`;
    }

    // ----- note panel -----

    _showNotePanel(nodeId) {
        this.openNoteNodeId = nodeId;
        const node = this.jm.get_node(nodeId);
        if (!node) return;
        document.getElementById('mindmapNoteTitle').textContent = `笔记 · ${node.topic || ''}`;
        this._refreshNotePanel();
        document.getElementById('mindmapNotePanel').style.display = 'flex';
    }

    _hideNotePanel() {
        this.openNoteNodeId = null;
        document.getElementById('mindmapNotePanel').style.display = 'none';
    }

    // Send this node's subtree (topic + note + descendants) to chat as a
    // question and auto-fire the request. Reuses chatManager.sendMessage.
    learnNode(nodeId) {
        if (this.streaming) { showToast('思维导图 AI 正在生成，请稍候', 'warning'); return; }
        if (window.chatManager && chatManager.isStreaming) {
            showToast('请等待当前回复完成', 'warning');
            return;
        }
        const node = this.jm.get_node(nodeId);
        if (!node) return;
        const lines = [];
        this._walkMarkdown(node, 0, lines);
        const md = lines.join('\n');
        const prefix = '请围绕以下思维导图节点的内容为我讲解，并补充我笔记中遗漏的要点：';
        chatManager.showChatView();
        const input = document.getElementById('chatInput');
        input.value = `${prefix}\n\n${md}`;
        chatManager.sendMessage();
    }

    addNodeToReview(nodeId) {
        const node = this.jm.get_node(nodeId);
        if (!node || !window.reviewManager) return;
        const path = this._pathToRoot(node).join(' > ');
        const content = (node.data && node.data.note) || node.topic || '';
        reviewManager.openDraftModal(content, `来自思维导图节点：${path}`);
    }

    _refreshNotePanel() {
        if (!this.openNoteNodeId) return;
        const node = this.jm.get_node(this.openNoteNodeId);
        const body = document.getElementById('mindmapNoteBody');
        if (!node) { body.textContent = ''; return; }
        body.textContent = (node.data && node.data.note) || '（暂无笔记）';
    }

    // ----- helpers -----

    _pathToRoot(node) {
        const path = [];
        let cur = node;
        while (cur) {
            path.unshift(cur.topic);
            cur = cur.parent;
        }
        return path;
    }

    _countNodesUnder(node) {
        if (!node) return 0;
        let n = 1;
        for (const c of (node.children || [])) n += this._countNodesUnder(c);
        return n;
    }

    _countNodes() {
        if (!this.jm) return 0;
        const root = this.jm.get_root();
        return this._countNodesUnder(root);
    }

    // ----- export -----

    // Append a node's markdown (topic + note + descendants) into `lines`,
    // indented relative to `depth`. Shared by export and the learn action.
    _walkMarkdown(node, depth, lines) {
        const indent = '  '.repeat(depth);
        lines.push(`${indent}- ${node.topic}`);
        const note = node.data && node.data.note;
        if (note) {
            const noteIndent = '  '.repeat(depth + 1);
            for (const ln of String(note).split(/\r?\n/)) {
                lines.push(`${noteIndent}> ${ln}`);
            }
        }
        for (const c of (node.children || [])) this._walkMarkdown(c, depth + 1, lines);
    }

    _serializeToMarkdown() {
        if (!this.jm) return '';
        const root = this.jm.get_root();
        const lines = [`# ${this.currentMap?.title || root.topic}`, ''];
        this._walkMarkdown(root, 0, lines);
        return lines.join('\n');
    }

    exportMarkdown() {
        if (!this.currentMap) { showToast('请先选择思维导图', 'warning'); return; }
        const md = this._serializeToMarkdown();
        const safe = (this.currentMap.title || 'mindmap').replace(/[\\/:*?"<>|]/g, '_');
        const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${safe}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('已导出', 'success');
    }

    async copyMarkdown() {
        if (!this.currentMap) { showToast('请先选择思维导图', 'warning'); return; }
        const md = this._serializeToMarkdown();
        try {
            await navigator.clipboard.writeText(md);
            showToast('已复制为 Markdown', 'success');
        } catch (e) {
            // fallback
            const ta = document.createElement('textarea');
            ta.value = md;
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand('copy'); showToast('已复制为 Markdown', 'success'); }
            catch { showToast('复制失败', 'error'); }
            document.body.removeChild(ta);
        }
    }
}

function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
}

function formatRelativeTime(iso) {
    if (!iso) return '';
    const t = new Date(iso).getTime();
    if (isNaN(t)) return '';
    const diff = Date.now() - t;
    const s = Math.floor(diff / 1000);
    if (s < 60) return '刚刚';
    if (s < 3600) return `${Math.floor(s / 60)} 分钟前`;
    if (s < 86400) return `${Math.floor(s / 3600)} 小时前`;
    if (s < 86400 * 7) return `${Math.floor(s / 86400)} 天前`;
    return new Date(iso).toLocaleDateString();
}

const mindmapManager = window.mindmapManager = new MindMapManager();
