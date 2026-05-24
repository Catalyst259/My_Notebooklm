// API Client for backend communication
const API_BASE_URL = 'http://127.0.0.1:8000';

class APIClient {
    constructor() {
        this.baseUrl = API_BASE_URL;
    }

    // Health check
    async healthCheck() {
        const response = await fetch(`${this.baseUrl}/api/health`);
        return await response.json();
    }

    // Get list of assistants
    async getAssistants() {
        const response = await fetch(`${this.baseUrl}/api/assistants`);
        if (!response.ok) throw new Error('Failed to fetch assistants');
        return await response.json();
    }

    // Get knowledge base statistics
    async getStats(assistantId) {
        const response = await fetch(`${this.baseUrl}/api/stats?assistant_id=${assistantId}`);
        if (!response.ok) throw new Error('Failed to fetch stats');
        return await response.json();
    }

    // Upload file
    async uploadFile(file, assistantId) {
        const formData = new FormData();
        formData.append('files', file);
        formData.append('assistant_id', assistantId);

        const response = await fetch(`${this.baseUrl}/api/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        return await response.json();
    }

    async uploadFiles(files, assistantId) {
        const formData = new FormData();
        for (const file of files) {
            formData.append('files', file);
        }
        formData.append('assistant_id', assistantId);

        const response = await fetch(`${this.baseUrl}/api/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        return await response.json();
    }

    async getFiles(assistantId) {
        const response = await fetch(`${this.baseUrl}/api/files?assistant_id=${assistantId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch files');
        }
        return await response.json();
    }

    async deleteFile(fileUuid, assistantId) {
        const response = await fetch(
            `${this.baseUrl}/api/files/${fileUuid}?assistant_id=${assistantId}`,
            { method: 'DELETE' }
        );
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete file');
        }
        return await response.json();
    }

    // Chat with streaming (returns EventSource)
    createChatStream(message, apiKey, assistantId, sessionId = '') {
        const formData = new FormData();
        formData.append('message', message);
        formData.append('api_key', apiKey);
        formData.append('assistant_id', assistantId);
        formData.append('session_id', sessionId || '');

        // Use fetch for POST, then create EventSource-like handler
        return fetch(`${this.baseUrl}/api/chat`, {
            method: 'POST',
            body: formData
        });
    }

    // Regenerate the last assistant reply for a session (streams like /api/chat)
    regenerateLast(sessionId, apiKey, assistantId) {
        const formData = new FormData();
        formData.append('api_key', apiKey);
        formData.append('assistant_id', assistantId);
        return fetch(`${this.baseUrl}/api/sessions/${sessionId}/regenerate`, {
            method: 'POST',
            body: formData
        });
    }

    // Sessions
    async listSessions(assistantId) {
        const response = await fetch(`${this.baseUrl}/api/sessions?assistant_id=${assistantId}`);
        if (!response.ok) throw new Error('Failed to list sessions');
        return await response.json();
    }

    async createSession(assistantId, title = '') {
        const formData = new FormData();
        formData.append('assistant_id', assistantId);
        if (title) formData.append('title', title);
        const response = await fetch(`${this.baseUrl}/api/sessions`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) throw new Error('Failed to create session');
        return await response.json();
    }

    async getSession(sessionId, assistantId) {
        const response = await fetch(
            `${this.baseUrl}/api/sessions/${sessionId}?assistant_id=${assistantId}`
        );
        if (!response.ok) throw new Error('Failed to fetch session');
        return await response.json();
    }

    async renameSession(sessionId, assistantId, title) {
        const formData = new FormData();
        formData.append('assistant_id', assistantId);
        formData.append('title', title);
        const response = await fetch(`${this.baseUrl}/api/sessions/${sessionId}`, {
            method: 'PATCH',
            body: formData
        });
        if (!response.ok) throw new Error('Failed to rename session');
        return await response.json();
    }

    async deleteSession(sessionId, assistantId) {
        const response = await fetch(
            `${this.baseUrl}/api/sessions/${sessionId}?assistant_id=${assistantId}`,
            { method: 'DELETE' }
        );
        if (!response.ok) throw new Error('Failed to delete session');
        return await response.json();
    }

    async deleteMessage(sessionId, index, assistantId) {
        const response = await fetch(
            `${this.baseUrl}/api/sessions/${sessionId}/messages/${index}?assistant_id=${assistantId}`,
            { method: 'DELETE' }
        );
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: '删除失败' }));
            throw new Error(error.detail || 'Failed to delete message');
        }
        return await response.json();
    }

    // Memory note
    async getMemory(assistantId) {
        const response = await fetch(`${this.baseUrl}/api/memory?assistant_id=${assistantId}`);
        if (!response.ok) throw new Error('Failed to fetch memory');
        return await response.json();
    }

    async saveMemory(assistantId, memory) {
        const formData = new FormData();
        formData.append('assistant_id', assistantId);
        formData.append('memory', memory);
        const response = await fetch(`${this.baseUrl}/api/memory`, {
            method: 'PUT',
            body: formData
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: '保存失败' }));
            throw new Error(error.detail || 'Failed to save memory');
        }
        return await response.json();
    }

    // Clear conversation history (deprecated; deletes most-recent session)
    async clearHistory(assistantId) {
        const formData = new FormData();
        formData.append('assistant_id', assistantId);

        const response = await fetch(`${this.baseUrl}/api/clear`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Failed to clear history');
        return await response.json();
    }

    // Generate quiz
    async generateQuiz(apiKey, assistantId, options = {}) {
        const formData = new FormData();
        formData.append('api_key', apiKey);
        formData.append('assistant_id', assistantId);
        formData.append('count', options.count || 5);
        formData.append('difficulty', options.difficulty || 'medium');
        formData.append('question_types', options.question_types || 'mixed');
        formData.append('topic', options.topic || '');

        const response = await fetch(`${this.baseUrl}/api/quiz/generate`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Quiz generation failed');
        }

        return await response.json();
    }

    // Grade quiz
    async gradeQuiz(apiKey, assistantId, questions, answers) {
        const formData = new FormData();
        formData.append('api_key', apiKey);
        formData.append('assistant_id', assistantId);
        formData.append('questions_json', JSON.stringify(questions));
        formData.append('answers_json', JSON.stringify(answers));

        const response = await fetch(`${this.baseUrl}/api/quiz/grade`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Quiz grading failed');
        }

        return await response.json();
    }

    // Clear knowledge base
    async clearKnowledgeBase(assistantId) {
        const formData = new FormData();
        formData.append('assistant_id', assistantId);

        const response = await fetch(`${this.baseUrl}/api/kb/clear`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Failed to clear knowledge base');
        return await response.json();
    }

    // Create a new custom assistant
    async createAssistant(name, description) {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('description', description);

        const response = await fetch(`${this.baseUrl}/api/assistants/create`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: '创建失败' }));
            throw new Error(error.detail || 'Failed to create assistant');
        }
        return await response.json();
    }

    // Delete an assistant
    async deleteAssistant(assistantId) {
        const formData = new FormData();
        formData.append('assistant_id', assistantId);

        const response = await fetch(`${this.baseUrl}/api/assistants/delete`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: '删除失败' }));
            throw new Error(error.detail || 'Failed to delete assistant');
        }
        return await response.json();
    }

    // --- Mind-maps ---

    async listMindmaps(assistantId) {
        const response = await fetch(`${this.baseUrl}/api/mindmaps?assistant_id=${assistantId}`);
        if (!response.ok) throw new Error('Failed to list mindmaps');
        return await response.json();
    }

    async createMindmap(assistantId, title) {
        const formData = new FormData();
        formData.append('assistant_id', assistantId);
        if (title) formData.append('title', title);
        const response = await fetch(`${this.baseUrl}/api/mindmaps`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) throw new Error('Failed to create mindmap');
        return await response.json();
    }

    async getMindmap(assistantId, mapId) {
        const response = await fetch(
            `${this.baseUrl}/api/mindmaps/${mapId}?assistant_id=${assistantId}`
        );
        if (!response.ok) throw new Error('Failed to fetch mindmap');
        return await response.json();
    }

    async saveMindmap(assistantId, mapId, title, jsmindJson) {
        const formData = new FormData();
        formData.append('assistant_id', assistantId);
        if (title) formData.append('title', title);
        if (jsmindJson) formData.append('jsmind_json', JSON.stringify(jsmindJson));
        const response = await fetch(`${this.baseUrl}/api/mindmaps/${mapId}`, {
            method: 'PUT',
            body: formData
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: '保存失败' }));
            throw new Error(error.detail || 'Failed to save mindmap');
        }
        return await response.json();
    }

    async deleteMindmap(assistantId, mapId) {
        const response = await fetch(
            `${this.baseUrl}/api/mindmaps/${mapId}?assistant_id=${assistantId}`,
            { method: 'DELETE' }
        );
        if (!response.ok) throw new Error('Failed to delete mindmap');
        return await response.json();
    }

    // AI streaming endpoints. Each returns a Response whose body must be consumed via
    // the shared SSE consumer. Pass an AbortSignal to allow cancellation.
    streamGenerateTree(apiKey, assistantId, topic, depth, width, signal) {
        const formData = new FormData();
        formData.append('api_key', apiKey);
        formData.append('assistant_id', assistantId);
        formData.append('topic', topic);
        formData.append('depth', String(depth || 2));
        formData.append('width', String(width || 4));
        return fetch(`${this.baseUrl}/api/mindmaps/ai/generate-tree`, {
            method: 'POST',
            body: formData,
            signal
        });
    }

    streamExpandNode(apiKey, assistantId, path, siblings, count, signal) {
        const formData = new FormData();
        formData.append('api_key', apiKey);
        formData.append('assistant_id', assistantId);
        formData.append('path_json', JSON.stringify(path || []));
        formData.append('siblings_json', JSON.stringify(siblings || []));
        formData.append('count', String(count || 4));
        return fetch(`${this.baseUrl}/api/mindmaps/ai/expand-node`, {
            method: 'POST',
            body: formData,
            signal
        });
    }

    streamGenerateNote(apiKey, assistantId, path, signal) {
        const formData = new FormData();
        formData.append('api_key', apiKey);
        formData.append('assistant_id', assistantId);
        formData.append('path_json', JSON.stringify(path || []));
        return fetch(`${this.baseUrl}/api/mindmaps/ai/generate-note`, {
            method: 'POST',
            body: formData,
            signal
        });
    }
}

// Export singleton instance
const api = new APIClient();
