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
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (err) {
            if (err.name === 'TypeError' && err.message.includes('fetch')) {
                throw new Error('Cannot connect to server. Ensure the backend is running.');
            }
            throw err;
        }
    }

    return {
        // Auth
        login: (email, password) => request('POST', '/api/auth/login', { email, password }),
        getProfile: () => request('GET', '/api/auth/me'),

        // Requests
        submitRequest: (data) => request('POST', '/api/request/submit', data),
        sendChatAssistant: (message, history = []) => request('POST', '/api/request/assistant', { message, history }),
        getMyRequests: (limit = 50) => request('GET', `/api/request/my?limit=${limit}`),
        getLeaveBalances: () => request('GET', '/api/request/leave-balances'),
        getRequest: (id) => request('GET', `/api/request/${id}`),

        // Review
        getPendingReviews: () => request('GET', '/api/review/pending'),
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
