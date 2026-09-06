/**
 * SOP Forge — API Client Module
 * Handles all HTTP communication with the FastAPI backend.
 */

const API = (() => {
    const BASE_URL = window.location.origin;

    function getHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        const token = localStorage.getItem('sopforge_token');
        if (token) headers['Authorization'] = `Bearer ${token}`;
        return headers;
    }

    async function request(method, path, body = null) {
        const options = { method, headers: getHeaders() };
        if (body && method !== 'GET') {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${BASE_URL}${path}`, options);

            if (response.status === 401) {
                Auth.logout();
                throw new Error('Session expired. Please login again.');
            }

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Request failed' }));
                const detail = error.detail;
                const message = typeof detail === 'object' ? detail.message : detail;
                const problem = new Error(message || `HTTP ${response.status}`);
                problem.code = typeof detail === 'object' ? detail.code : null;
                problem.details = detail;
                throw problem;
            }

            return await response.json();
        } catch (err) {
            if (err.name === 'TypeError' && err.message.includes('fetch')) {
                throw new Error('Cannot connect to server. Ensure the backend is running.');
            }
            throw err;
        }
    }

    async function uploadChatEvidence(conversationId, file) {
        const form = new FormData();
        form.append('file', file);
        const token = localStorage.getItem('sopforge_token');
        const response = await fetch(`${BASE_URL}/api/evidence/draft/${conversationId}`, {
            method: 'POST',
            headers: token ? {Authorization: `Bearer ${token}`} : {},
            body: form,
        });
        const result = await response.json().catch(() => ({detail: 'Upload failed'}));
        if (!response.ok) {
            const detail = result.detail;
            throw new Error(typeof detail === 'object' ? detail.message : detail);
        }
        return result;
    }

    return {
        // Auth
        login: (email, password) => request('POST', '/api/auth/login', { email, password }),
        getProfile: () => request('GET', '/api/auth/me'),

        // Requests
        submitRequest: (data) => request('POST', '/api/request/submit', data),
        startChatConversation: domain => request('POST', '/api/request/assistant/start', {domain}),
        sendChatAssistant: (message, conversation_id) => request('POST', '/api/request/assistant', {message, conversation_id}),
        uploadChatEvidence,
        skipChatEvidence: conversationId => request('POST', `/api/evidence/draft/${conversationId}/skip`),
        getMyRequests: (limit = 50) => request('GET', `/api/request/my?limit=${limit}`),
        getLeaveBalances: () => request('GET', '/api/request/leave-balances'),
        getRequest: (id) => request('GET', `/api/request/${id}`),

        // Review
        getPendingReviews: (statusFilter = 'escalated') => request('GET', `/api/review/pending?status_filter=${statusFilter}`),
        submitReview: (id, data) => request('POST', `/api/review/${id}/decide`, data),
        submitOverride: (id, data) => request('POST', `/api/review/${id}/override`, data),

        // Admin
        listSOPDocs: () => request('GET', '/api/admin/sop'),
        createSOPDoc: (data) => request('POST', '/api/admin/sop', data),
        getSOPDoc: (id) => request('GET', `/api/admin/sop/${id}`),
        updateSOPDoc: (id, data) => request('PUT', `/api/admin/sop/${id}`, data),
        deleteSOPDoc: (id) => request('DELETE', `/api/admin/sop/${id}`),
        getSOPChunks: (id) => request('GET', `/api/admin/sop/${id}/chunks`),

        // Audit
        getAuditLogs: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return request('GET', `/api/audit/logs${query ? '?' + query : ''}`);
        },
        getRequestAudit: (id) => request('GET', `/api/audit/logs/${id}`),
        getAuditSummary: () => request('GET', '/api/audit/summary'),

        // Incidents
        getIncidents: () => request('GET', '/api/incidents'),
        dismissIncident: (id) => request('PUT', `/api/incidents/${id}/dismiss`),

        // Speech
        getSpeechToken: () => request('GET', '/api/speech/token'),

        // Health
        health: () => request('GET', '/health'),
    };
})();
