/**
 * SOP Forge — Incidents Component
 * HR view for flagged inappropriate chats.
 */

const Incidents = (() => {
    let incidents = [];

    async function render(container) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <h1 class="page-title" style="color: var(--status-escalated);">HR Incidents</h1>
                <p class="page-subtitle">Flagged inappropriate chats requiring review</p>
            </div>
            <div id="incidents-list">
                <div class="skeleton skeleton-card" style="height:150px;margin-bottom:16px"></div>
                <div class="skeleton skeleton-card" style="height:150px"></div>
            </div>
        `;
        loadIncidents();
    }

    async function loadIncidents() {
        try {
            incidents = await API.getIncidents();
            renderIncidentsList();
        } catch (err) {
            document.getElementById('incidents-list').innerHTML = `
                <div class="card"><p style="color:var(--status-escalated)">Error loading incidents: ${err.message}</p></div>
            `;
        }
    }

    function renderIncidentsList() {
        const container = document.getElementById('incidents-list');

        if (!incidents.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="1.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                    <h3>All clear!</h3>
                    <p>No HR incidents to review.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = incidents.map((inc, idx) => {
            const isOpen = inc.status === 'open';
            const statusColor = isOpen ? 'var(--status-escalated)' : 'var(--text-tertiary)';
            const borderStyle = isOpen ? 'border-left: 4px solid var(--status-escalated);' : 'opacity: 0.7;';

            return `
            <div class="card animate-slide-up" style="margin-bottom:var(--space-md);animation-delay:${idx * 0.05}s; ${borderStyle}">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--space-md)">
                    <div>
                        <div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:6px">
                            <span style="font-size:var(--text-base);font-weight:600;color:var(--text-primary)">Employee ID: ${inc.employee_id}</span>
                            <span class="badge" style="background-color: ${isOpen ? 'rgba(239, 68, 68, 0.1)' : 'var(--bg-tertiary)'}; color: ${statusColor}">${inc.status.toUpperCase()}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:var(--space-md);font-size:var(--text-xs);color:var(--text-tertiary)">
                            <span>📅 ${new Date(inc.created_at).toLocaleString('en-GB')}</span>
                        </div>
                    </div>
                </div>

                <div style="background:var(--bg-tertiary);border:1px solid var(--border-subtle);border-radius:var(--radius-md);padding:var(--space-md);margin-bottom:var(--space-md)">
                    <div style="font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">User Message</div>
                    <div style="font-family:var(--font-mono);font-size:var(--text-sm);color:var(--text-primary);white-space:pre-wrap;">${escapeHtml(inc.message)}</div>
                </div>

                ${inc.ai_reasoning ? `
                    <div style="margin-bottom:var(--space-md)">
                        <div style="font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">AI Reasoning</div>
                        <div class="reasoning-box">${escapeHtml(inc.ai_reasoning)}</div>
                    </div>
                ` : ''}

                ${isOpen ? `
                    <div style="display:flex;gap:var(--space-sm);align-items:center;padding-top:var(--space-md);border-top:1px solid var(--border-subtle)">
                        <button class="btn btn-secondary btn-sm" onclick="Incidents.dismiss('${inc.id}')">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                            Dismiss / Mark as Reviewed
                        </button>
                    </div>
                ` : ''}
            </div>
            `;
        }).join('');
    }

    async function dismiss(id) {
        if (!confirm('Are you sure you want to mark this incident as reviewed?')) return;
        
        try {
            await API.dismissIncident(id);
            App.toast('Incident dismissed.', 'success');
            loadIncidents();
        } catch (err) {
            App.toast(`Error: ${err.message}`, 'error');
        }
    }

    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    return { render, dismiss };
})();
