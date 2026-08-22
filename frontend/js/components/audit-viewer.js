/**
 * SOP Forge — Audit Viewer Component
 * Filterable, read-only immutable audit trail viewer.
 */

const AuditViewer = (() => {
    let currentFilter = { event_type: 'all', days: 'all' };
    let currentLogs = []; // Store logs for CSV export

    async function render(container) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <div style="display:flex;justify-content:space-between;align-items:flex-end">
                    <div>
                        <h1 class="page-title">Audit Trail</h1>
                        <p class="page-subtitle">Complete record of all decisions, approvals, and overrides</p>
                    </div>
                    <button class="btn btn-secondary" onclick="AuditViewer.exportCSV()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Export CSV
                    </button>
                </div>
            </div>

            <div id="audit-summary" class="stats-grid" style="margin-bottom:var(--space-lg)">
                <div class="skeleton skeleton-card" style="height:100px"></div>
                <div class="skeleton skeleton-card" style="height:100px"></div>
                <div class="skeleton skeleton-card" style="height:100px"></div>
            </div>

            <div class="card animate-slide-up">
                <div class="action-bar" style="margin-bottom:var(--space-md);justify-content:space-between">
                    <div class="action-bar-group" id="event-filters">
                        <button class="filter-chip active" onclick="AuditViewer.filterEvent('all', this)">All Events</button>
                        <button class="filter-chip" onclick="AuditViewer.filterEvent('auto_approved', this)">Auto-Approved</button>
                        <button class="filter-chip" onclick="AuditViewer.filterEvent('auto_rejected', this)">Auto-Rejected</button>
                        <button class="filter-chip" onclick="AuditViewer.filterEvent('escalated', this)">Escalated</button>
                        <button class="filter-chip" onclick="AuditViewer.filterEvent('executive_override', this)">Executive Overrides</button>
                    </div>
                    <div class="form-group" style="margin:0;width:180px">
                        <select id="time-filter" onchange="AuditViewer.filterTime(this.value)" style="padding:6px 12px;font-size:12px;height:auto">
                            <option value="all">All Time</option>
                            <option value="30">Past 1 Month</option>
                            <option value="90">Past 3 Months</option>
                            <option value="180">Past 6 Months</option>
                            <option value="365">Past 1 Year</option>
                        </select>
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
            const queryParams = { limit: 200 };
            if (currentFilter.event_type !== 'all') queryParams.event_type = currentFilter.event_type;
            if (currentFilter.days !== 'all') queryParams.days = parseInt(currentFilter.days);

            const [summary, logs] = await Promise.all([
                API.getAuditSummary(),
                API.getAuditLogs(queryParams),
            ]);
            currentLogs = logs; // Save for CSV export
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
                    <div><span style="color:var(--status-escalated);font-size:var(--text-xl);font-weight:700">${summary.escalated}</span><br><span class="card-label">Escalated</span></div>
                </div>
            </div>
            <div class="card stat-card animate-slide-up" style="animation-delay:0.15s">
                <div style="display:flex;gap:var(--space-lg);margin-top:var(--space-sm)">
                    <div><span style="color:var(--status-overridden);font-size:var(--text-xl);font-weight:700">${summary.overridden}</span><br><span class="card-label">Exec Overrides</span></div>
                    <div><span style="color:var(--status-approved);font-size:var(--text-xl);font-weight:700">${summary.sla_breaches}</span><br><span class="card-label">SLA Breaches</span></div>
                </div>
            </div>
        `;
    }

    function renderTable(logs) {
        const tableEl = document.getElementById('audit-table');

        if (!logs.length) {
            tableEl.innerHTML = `<div class="empty-state"><h3>No audit entries found</h3><p>Try adjusting your filters.</p></div>`;
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
                        ${logs.map(log => {
                            const decisionStr = log.decision ? log.decision.charAt(0).toUpperCase() + log.decision.slice(1) : 'Logged';
                            const actorLabel = log.actor_name ? `${log.actor_name} (${log.actor_role})` : (log.actor_role || 'System Agent');
                            
                            return `
                                <tr onclick="AuditViewer.inspectLog('${log.id}')" style="cursor:pointer">
                                    <td><span class="badge badge-${eventBadge(log.event_type)}">${log.event_type.replace(/_/g, ' ')}</span></td>
                                    <td style="font-weight:500;color:var(--text-primary)">${decisionStr}</td>
                                    <td>${actorLabel}</td>
                                    <td class="mono">${new Date(log.created_at).toLocaleString('en-GB')}</td>
                                    <td>
                                        <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation();AuditViewer.inspectLog('${log.id}')">
                                            View Details
                                        </button>
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    async function inspectLog(logId) {
        try {
            const log = currentLogs.find(l => l.id === logId);
            if (!log) return;

            const cleanRefs = log.policy_refs && log.policy_refs.length 
                ? Array.from(new Set(log.policy_refs.map(r => r.replace(/:\s*chunk\s*\d+/gi, '').trim())))
                : [];

            const decisionStr = log.decision ? log.decision.charAt(0).toUpperCase() + log.decision.slice(1) : 'N/A';

            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.innerHTML = `
                <div class="modal-content" style="max-width:640px;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.5)">
                    <div class="modal-header" style="border-bottom:1px solid var(--border-subtle);padding-bottom:16px;margin-bottom:20px">
                        <div>
                            <h2 class="modal-title" style="font-size:20px;font-weight:700">Audit Log Record</h2>
                            <span style="font-size:12px;color:var(--text-tertiary);font-family:var(--font-mono)">ID: ${log.id}</span>
                        </div>
                        <button class="btn-icon" onclick="this.closest('.modal-overlay').remove()">✕</button>
                    </div>

                    <div class="detail-grid" style="margin-bottom:var(--space-lg);background:var(--bg-tertiary);padding:16px;border-radius:8px">
                        <div class="detail-item">
                            <span class="detail-label">Event Type</span>
                            <span class="detail-value"><span class="badge badge-${eventBadge(log.event_type)}">${log.event_type.replace(/_/g, ' ')}</span></span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Decision Outcome</span>
                            <span class="detail-value" style="font-weight:600;color:var(--text-primary)">${decisionStr}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Actor / Role</span>
                            <span class="detail-value">${log.actor_name ? `${log.actor_name} (${log.actor_role})` : log.actor_role || 'System Agent'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Timestamp</span>
                            <span class="detail-value mono">${new Date(log.created_at).toLocaleString('en-GB')}</span>
                        </div>
                    </div>

                    ${log.override_justification ? `
                        <div class="detail-section" style="margin-bottom:20px">
                            <h3 style="font-size:12px;text-transform:uppercase;color:var(--text-tertiary);margin-bottom:8px">Executive Override Justification</h3>
                            <div class="reasoning-box" style="border-left:3px solid var(--status-overridden);background:var(--bg-tertiary)">
                                <strong style="color:var(--text-primary)">Previous Decision:</strong> ${log.previous_decision || 'N/A'}<br>
                                <strong style="color:var(--text-primary)">Override Reason:</strong> ${log.override_justification}
                            </div>
                        </div>
                    ` : ''}

                    ${log.evaluation_reasoning ? `
                        <div class="detail-section" style="margin-bottom:20px">
                            <h3 style="font-size:12px;text-transform:uppercase;color:var(--text-tertiary);margin-bottom:8px">Evaluation Summary</h3>
                            <div class="reasoning-box" style="background:var(--bg-tertiary)">${log.evaluation_reasoning}</div>
                        </div>
                    ` : ''}

                    ${cleanRefs.length ? `
                        <div class="detail-section" style="margin-bottom:20px">
                            <h3 style="font-size:12px;text-transform:uppercase;color:var(--text-tertiary);margin-bottom:8px">Policy Governance References</h3>
                            <div>${cleanRefs.map(r => `<span class="policy-ref" style="background:var(--bg-secondary);border:1px solid var(--border-subtle)">${r}</span>`).join('')}</div>
                        </div>
                    ` : ''}

                    <div class="detail-section">
                        <h3 style="font-size:12px;text-transform:uppercase;color:var(--text-tertiary);margin-bottom:8px">Raw Ledger Payload Details</h3>
                        <pre style="background:var(--bg-secondary);padding:12px;border:1px solid var(--border-subtle);border-radius:6px;font-family:var(--font-mono);font-size:11px;color:var(--text-secondary);overflow-x:auto">${JSON.stringify(log.details || {}, null, 2)}</pre>
                    </div>

                    <div style="display:flex;justify-content:flex-end;margin-top:24px;border-top:1px solid var(--border-subtle);padding-top:16px">
                        <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Close Window</button>
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

    function filterEvent(type, btnElement) {
        document.querySelectorAll('#event-filters .filter-chip').forEach(c => c.classList.remove('active'));
        btnElement.classList.add('active');
        currentFilter.event_type = type;
        loadAuditData();
    }

    function filterTime(days) {
        currentFilter.days = days;
        loadAuditData();
    }

    function exportCSV() {
        if (!currentLogs.length) {
            App.toast('No logs to export', 'error');
            return;
        }

        const headers = ['Audit ID', 'Request ID', 'Event Type', 'Decision', 'Actor Name', 'Actor Role', 'Timestamp', 'Confidence', 'Reasoning'];
        const rows = currentLogs.map(log => [
            log.id,
            log.request_id || '',
            log.event_type,
            log.decision || '',
            log.actor_name || '',
            log.actor_role || '',
            new Date(log.created_at).toISOString(),
            log.confidence || '',
            (log.evaluation_reasoning || '').replace(/"/g, '""') // Escape quotes for CSV
        ]);

        const csvContent = [
            headers.join(','),
            ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `audit_trail_export_${new Date().getTime()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        App.toast('Export downloaded successfully', 'success');
    }

    return { render, filterEvent, filterTime, inspectLog, exportCSV };
})();
