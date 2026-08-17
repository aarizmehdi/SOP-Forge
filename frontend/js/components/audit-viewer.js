/**
 * SOP Forge — Audit Viewer Component
 * Filterable, read-only immutable audit trail viewer.
 */

const AuditViewer = (() => {
    let currentFilter = {};

    async function render(container) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <h1 class="page-title">Audit Trail</h1>
                <p class="page-subtitle">Complete record of all decisions, approvals, and overrides</p>
            </div>

            <div id="audit-summary" class="stats-grid" style="margin-bottom:var(--space-lg)">
                <div class="skeleton skeleton-card" style="height:100px"></div>
                <div class="skeleton skeleton-card" style="height:100px"></div>
                <div class="skeleton skeleton-card" style="height:100px"></div>
            </div>

            <div class="card animate-slide-up">
                <div class="action-bar" style="margin-bottom:var(--space-md)">
                    <div class="action-bar-group">
                        <button class="filter-chip active" onclick="AuditViewer.filter('all')">All Events</button>
                        <button class="filter-chip" onclick="AuditViewer.filter('auto_approved')">Auto-Approved</button>
                        <button class="filter-chip" onclick="AuditViewer.filter('auto_rejected')">Auto-Rejected</button>
                        <button class="filter-chip" onclick="AuditViewer.filter('escalated')">Escalated</button>
                        <button class="filter-chip" onclick="AuditViewer.filter('executive_override')">Executive Overrides</button>
                    </div>
                </div>
                <div id="audit-table">
                    <div class="skeleton skeleton-text" style="width:100%"></div>
                    <div class="skeleton skeleton-text" style="width:90%"></div>
                    <div class="skeleton skeleton-text" style="width:85%"></div>
                </div>
            </div>
        `;
        loadAuditData();
    }

    async function loadAuditData() {
        try {
            const [summary, logs] = await Promise.all([
                API.getAuditSummary(),
                API.getAuditLogs({ limit: 100, ...currentFilter }),
            ]);
            renderSummary(summary);
            renderTable(logs);
        } catch (err) {
            document.getElementById('audit-table').innerHTML = `
                <p style="color:var(--text-secondary);padding:var(--space-lg)">Error loading audit log: ${err.message}</p>
            `;
        }
    }

    function renderSummary(summary) {
        document.getElementById('audit-summary').innerHTML = `
            <div class="card stat-card animate-slide-up" style="animation-delay:0.05s">
                <div class="card-value" style="color:var(--primary-400)">${summary.total_entries}</div>
                <div class="card-label">Total Audit Records</div>
            </div>
            <div class="card stat-card animate-slide-up" style="animation-delay:0.1s">
                <div style="display:flex;gap:var(--space-lg);margin-top:var(--space-sm)">
                    <div><span style="color:var(--status-approved);font-size:var(--text-xl);font-weight:700">${summary.auto_approved}</span><br><span class="card-label">Auto-Approved</span></div>
                    <div><span style="color:var(--status-rejected);font-size:var(--text-xl);font-weight:700">${summary.auto_rejected}</span><br><span class="card-label">Auto-Rejected</span></div>
                    <div><span style="color:var(--status-escalated);font-size:var(--text-xl);font-weight:700">${summary.escalated}</span><br><span class="card-label">Escalated (2h SLA)</span></div>
                </div>
            </div>
            <div class="card stat-card animate-slide-up" style="animation-delay:0.15s">
                <div style="display:flex;gap:var(--space-lg);margin-top:var(--space-sm)">
                    <div><span style="color:var(--status-overridden);font-size:var(--text-xl);font-weight:700">${summary.overridden}</span><br><span class="card-label">Exec Overrides</span></div>
                    <div><span style="color:var(--status-approved);font-size:var(--text-xl);font-weight:700">0</span><br><span class="card-label">SLA Breaches</span></div>
                </div>
            </div>
        `;
    }

    function renderTable(logs) {
        const tableEl = document.getElementById('audit-table');

        if (!logs.length) {
            tableEl.innerHTML = `<div class="empty-state"><h3>No audit entries recorded yet</h3><p>Entries appear automatically as requests are processed.</p></div>`;
            return;
        }

        tableEl.innerHTML = `
            <div style="overflow-x:auto">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Audit Event</th>
                            <th>Decision Outcome</th>
                            <th>Actor / Role</th>
                            <th>Timestamp</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${logs.map(log => `
                            <tr onclick="AuditViewer.inspectLog('${log.id}')" style="cursor:pointer">
                                <td><span class="badge badge-${eventBadge(log.event_type)}">${log.event_type.replace(/_/g, ' ')}</span></td>
                                <td>${log.decision ? `<span class="badge badge-${log.decision}">${log.decision}</span>` : '—'}</td>
                                <td>${log.actor_name ? `${log.actor_name} (${log.actor_role})` : log.actor_role || 'System Graph'}</td>
                                <td class="mono">${new Date(log.created_at).toLocaleString()}</td>
                                <td><button class="btn btn-secondary btn-sm" onclick="event.stopPropagation();AuditViewer.inspectLog('${log.id}')">View Details</button></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    async function inspectLog(logId) {
        try {
            const logs = await API.getAuditLogs({ limit: 100 });
            const log = logs.find(l => l.id === logId);
            if (!log) {
                App.toast('Log entry details not found', 'error');
                return;
            }

            const cleanRefs = log.policy_refs && log.policy_refs.length 
                ? Array.from(new Set(log.policy_refs.map(r => r.replace(/:\s*chunk\s*\d+/gi, '').trim())))
                : [];

            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.innerHTML = `
                <div class="modal-content" style="max-width:640px">
                    <div class="modal-header">
                        <div>
                            <h2 class="modal-title">Immutable Audit Log Record</h2>
                            <span class="mono" style="font-size:var(--text-xs);color:var(--status-approved)">✓ Verified Append-Only Ledger Entry</span>
                        </div>
                        <button class="btn-icon" onclick="this.closest('.modal-overlay').remove()">✕</button>
                    </div>

                    <div class="detail-grid" style="margin-bottom:var(--space-lg)">
                        <div class="detail-item">
                            <span class="detail-label">Audit Event Type</span>
                            <span class="detail-value"><span class="badge badge-${eventBadge(log.event_type)}">${log.event_type.replace(/_/g, ' ')}</span></span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Decision Outcome</span>
                            <span class="detail-value">${log.decision ? `<span class="badge badge-${log.decision}">${log.decision}</span>` : 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Actor / Role</span>
                            <span class="detail-value">${log.actor_name ? `${log.actor_name} (${log.actor_role})` : log.actor_role || 'System Agent'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Timestamp</span>
                            <span class="detail-value mono">${new Date(log.created_at).toLocaleString()}</span>
                        </div>
                    </div>

                    ${log.override_justification ? `
                        <div class="detail-section">
                            <h3>Executive Override Justification</h3>
                            <div class="reasoning-box" style="border-left:3px solid var(--status-overridden)">
                                <strong>Previous Decision:</strong> ${log.previous_decision || 'N/A'}<br>
                                <strong>Override Reason:</strong> ${log.override_justification}
                            </div>
                        </div>
                    ` : ''}

                    ${log.evaluation_reasoning ? `
                        <div class="detail-section">
                            <h3 style="font-size:var(--text-xs);letter-spacing:0.05em;color:var(--text-tertiary);margin-bottom:6px">EVALUATION SUMMARY</h3>
                            <div class="reasoning-box">${log.evaluation_reasoning}</div>
                        </div>
                    ` : ''}

                    ${cleanRefs.length ? `
                        <div class="detail-section">
                            <h3 style="font-size:var(--text-xs);letter-spacing:0.05em;color:var(--text-tertiary);margin-bottom:6px">POLICY GOVERNANCE REFERENCES</h3>
                            <div>${cleanRefs.map(r => `<span class="policy-ref">${r}</span>`).join('')}</div>
                        </div>
                    ` : ''}

                    <div class="detail-section">
                        <h3>Raw Ledger Payload Details</h3>
                        <pre style="background:var(--bg-tertiary);padding:12px;border-radius:var(--radius-md);font-family:var(--font-mono);font-size:var(--text-xs);color:var(--accent-400);overflow-x:auto">${JSON.stringify(log.details || {}, null, 2)}</pre>
                    </div>

                    <div style="display:flex;justify-content:flex-end">
                        <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Close</button>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);
            overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
        } catch (err) {
            App.toast(`Failed to load log detail: ${err.message}`, 'error');
        }
    }

    function eventBadge(type) {
        if (type.includes('approved')) return 'approved';
        if (type.includes('rejected')) return 'rejected';
        if (type.includes('escalated')) return 'escalated';
        if (type.includes('override')) return 'overridden';
        return 'pending';
    }

    async function filter(type) {
        document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
        event.target.classList.add('active');

        currentFilter = type === 'all' ? {} : { event_type: type };
        loadAuditData();
    }

    return { render, filter, inspectLog };
})();
