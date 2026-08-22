/**
 * SOP Forge — Dashboard
 * Dual-View: Team Action Center (Managers) and Executive Command Center (Admins/Execs).
 */

const Dashboard = (() => {
    async function render(container) {
        const user = Auth.getUser();
        
        // If Executive or Admin, show the high-level Command Center
        if (Auth.hasMinRole('executive')) {
            renderExecutiveView(container, user);
        } else {
            // Otherwise, show the Manager "To-Do" view
            renderManagerView(container, user);
        }
    }

    // ==========================================
    // 1. EXECUTIVE COMMAND CENTER
    // ==========================================
    function renderExecutiveView(container, user) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <div style="display:flex;justify-content:space-between;align-items:flex-end">
                    <div>
                        <h1 class="page-title" style="background: linear-gradient(90deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Executive Command Center</h1>
                        <p class="page-subtitle">Organizational AI throughput, efficiency metrics, and SLA compliance.</p>
                    </div>
                </div>
            </div>

            <div id="exec-stats-grid" class="stats-grid" style="margin-bottom:var(--space-xl)">
                ${[1,2,3,4].map(() => `
                    <div class="card stat-card" style="border-top:3px solid transparent">
                        <div class="card-header" style="margin-bottom:8px">
                            <div class="skeleton skeleton-avatar" style="width:36px;height:36px;border-radius:8px"></div>
                        </div>
                        <div class="skeleton skeleton-text" style="width:40%;height:10px;margin-bottom:12px"></div>
                        <div class="skeleton skeleton-text" style="width:30%;height:32px;margin-bottom:8px"></div>
                        <div class="skeleton skeleton-text" style="width:80%;height:10px"></div>
                    </div>
                `).join('')}
            </div>

            <div class="card animate-slide-up" style="animation-delay: 0.2s">
                <div class="card-header">
                    <h2 class="card-title">Recent System Activity</h2>
                    <span style="font-size:var(--text-xs);color:var(--text-tertiary)">Live audit trail of AI and Manager decisions</span>
                </div>
                <div id="exec-audit-table">
                    <table class="table" style="width:100%;text-align:left;border-collapse:collapse;">
                        <thead>
                            <tr style="border-bottom:1px solid var(--border-subtle)">
                                <th style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:40px"></div></th>
                                <th style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:80px"></div></th>
                                <th style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:60px"></div></th>
                                <th style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:120px"></div></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${[1,2,3].map(() => `
                                <tr>
                                    <td style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:50px"></div></td>
                                    <td style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:100px;height:20px;border-radius:4px"></div></td>
                                    <td style="padding:12px 16px">
                                        <div class="skeleton skeleton-text" style="width:90px"></div>
                                        <div class="skeleton skeleton-text" style="width:50px;margin-bottom:0"></div>
                                    </td>
                                    <td style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:80%"></div></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        
        loadExecutiveData();
    }

    async function loadExecutiveData() {
        try {
            const [summary, logs] = await Promise.all([
                API.getAuditSummary(),
                API.getAuditLogs({ limit: 6 })
            ]);
            renderExecStats(summary);
            renderExecTable(logs);
        } catch (err) {
            document.getElementById('exec-stats-grid').innerHTML = `
                <div class="card stat-card">
                    <p style="color:var(--status-escalated);font-size:var(--text-sm)">
                        Unable to load executive metrics. ${err.message}
                    </p>
                </div>
            `;
        }
    }

    function renderExecStats(summary) {
        const total = summary.total_entries || 1; // Prevent div by 0
        const autoApprovedRate = Math.round((summary.auto_approved / total) * 100);
        const autoRejectedRate = Math.round((summary.auto_rejected / total) * 100);
        const aiResolutionRate = autoApprovedRate + autoRejectedRate;
        const escRate = Math.round((summary.escalated / total) * 100);

        document.getElementById('exec-stats-grid').innerHTML = `
            <div class="card stat-card animate-slide-up" style="animation-delay:0.05s; border-top: 3px solid #3b82f6; background: linear-gradient(180deg, rgba(59,130,246,0.05) 0%, transparent 100%);">
                <div class="card-header" style="margin-bottom: 8px;">
                    <div class="stat-icon processing" style="background:rgba(59,130,246,0.1); color:#3b82f6; opacity: 1;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                    </div>
                </div>
                <div class="card-label" style="font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">AI Resolution Rate</div>
                <div class="card-value" style="color:#3b82f6; font-size: 2.5rem; margin: 4px 0;">${aiResolutionRate}%</div>
                <div style="font-size:var(--text-xs); color:var(--text-secondary);">Requests handled without human input</div>
            </div>
            
            <div class="card stat-card animate-slide-up" style="animation-delay:0.1s; border-top: 3px solid var(--status-approved); background: linear-gradient(180deg, rgba(16,185,129,0.05) 0%, transparent 100%);">
                <div class="card-header" style="margin-bottom: 8px;">
                    <div class="stat-icon processing" style="background:var(--status-approved-bg); color:var(--status-approved); opacity: 1;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                    </div>
                </div>
                <div class="card-label" style="font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Total Volume</div>
                <div class="card-value" style="color:var(--text-primary); font-size: 2.5rem; margin: 4px 0;">${summary.total_entries}</div>
                <div style="font-size:var(--text-xs); color:var(--text-secondary);">Total organizational requests processed</div>
            </div>

            <div class="card stat-card animate-slide-up" style="animation-delay:0.15s; border-top: 3px solid #8b5cf6; background: linear-gradient(180deg, rgba(139,92,246,0.05) 0%, transparent 100%);">
                <div class="card-header" style="margin-bottom: 8px;">
                    <div class="stat-icon processing" style="background:rgba(139,92,246,0.1); color:#8b5cf6; opacity: 1;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="7.5 4.21 12 6.81 16.5 4.21"/><polyline points="7.5 19.79 7.5 14.6 3 12"/><polyline points="21 12 16.5 14.6 16.5 19.79"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                    </div>
                </div>
                <div class="card-label" style="font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Escalation Rate</div>
                <div class="card-value" style="color:#8b5cf6; font-size: 2.5rem; margin: 4px 0;">${escRate}%</div>
                <div style="font-size:var(--text-xs); color:var(--text-secondary);">Requests routed to manual review</div>
            </div>

            <div class="card stat-card animate-slide-up" style="animation-delay:0.2s; border-top: 3px solid ${summary.sla_breaches > 0 ? 'var(--status-escalated)' : 'var(--status-approved)'}; background: linear-gradient(180deg, rgba(239,68,68,0.05) 0%, transparent 100%);">
                <div class="card-header" style="margin-bottom: 8px;">
                    <div class="stat-icon processing" style="background:${summary.sla_breaches > 0 ? 'var(--status-escalated-bg)' : 'var(--status-approved-bg)'}; color:${summary.sla_breaches > 0 ? 'var(--status-escalated)' : 'var(--status-approved)'}; opacity: 1;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    </div>
                </div>
                <div class="card-label" style="font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">SLA Breaches</div>
                <div class="card-value" style="color:${summary.sla_breaches > 0 ? 'var(--status-escalated)' : 'var(--status-approved)'}; font-size: 2.5rem; margin: 4px 0;">${summary.sla_breaches}</div>
                <div style="font-size:var(--text-xs); color:var(--text-secondary);">Manager reviews exceeding time limits</div>
            </div>
        `;
    }

    function renderExecTable(logs) {
        const container = document.getElementById('exec-audit-table');
        if (!logs || logs.length === 0) {
            container.innerHTML = `<div style="padding: 20px; color: var(--text-tertiary);">No system activity found.</div>`;
            return;
        }

        const rows = logs.map(log => {
            const date = new Date(log.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute:'2-digit' });
            let actionColor = 'var(--text-primary)';
            let bgColor = 'var(--border-subtle)';
            if (log.event_type === 'AUTO_APPROVED' || log.event_type === 'APPROVED') { actionColor = 'var(--status-approved)'; bgColor = 'var(--status-approved-bg)'; }
            if (log.event_type === 'ESCALATED') { actionColor = 'var(--accent-400)'; bgColor = 'rgba(139,92,246,0.1)'; }
            if (log.event_type === 'AUTO_REJECTED' || log.event_type === 'DECLINED') { actionColor = 'var(--status-escalated)'; bgColor = 'var(--status-escalated-bg)'; }

            return `
                <tr class="table-row-hover" onclick="window.location.hash='#/audit'" style="cursor:pointer; border-bottom:1px solid rgba(255,255,255,0.03);">
                    <td style="padding: 16px; color:var(--text-tertiary); font-size:var(--text-sm); font-weight:500;">
                        ${date}
                    </td>
                    <td style="padding: 16px;">
                        <span style="display:inline-flex; align-items:center; color:${actionColor}; font-weight:600; font-size:12px; background:${bgColor}; padding: 6px 12px; border-radius: 6px; letter-spacing:0.5px; text-transform:uppercase;">
                            ${log.event_type.replace('_', ' ')}
                        </span>
                    </td>
                    <td style="padding: 16px;">
                        <div style="font-size:var(--text-base); font-weight:500; color:var(--text-primary); margin-bottom:2px;">
                            ${log.actor_name || 'AI Engine'}
                        </div>
                        <div style="font-size:12px; color:var(--text-tertiary); font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">
                            ${log.actor_role || 'System'}
                        </div>
                    </td>
                    <td style="padding: 16px; font-size:var(--text-sm); color:var(--text-secondary); max-width:250px;">
                        <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                            ${log.evaluation_reasoning || 'No details provided'}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        container.innerHTML = `
            <div style="overflow-x:auto;">
                <table class="table" style="width:100%;text-align:left;border-collapse:collapse;">
                    <thead>
                        <tr style="border-bottom:1px solid rgba(255,255,255,0.08);color:var(--text-secondary);font-size:11px;text-transform:uppercase;letter-spacing:1px;">
                            <th style="padding:16px;font-weight:600;width:15%;">Time</th>
                            <th style="padding:16px;font-weight:600;width:25%;">Action Event</th>
                            <th style="padding:16px;font-weight:600;width:25%;">Actor</th>
                            <th style="padding:16px;font-weight:600;width:35%;">System Reasoning</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
        `;
    }


    // ==========================================
    // 2. MANAGER TEAM ACTION CENTER
    // ==========================================
    function renderManagerView(container, user) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <div style="display:flex;justify-content:space-between;align-items:flex-end">
                    <div>
                        <h1 class="page-title">Team Action Center</h1>
                        <p class="page-subtitle">Welcome back, ${user.name.split(' ')[0]}. Here is what needs your attention today.</p>
                    </div>
                </div>
            </div>

            <div id="dashboard-stats" class="stats-grid" style="margin-bottom:var(--space-xl)">
                ${[1,2].map(() => `
                    <div class="card stat-card">
                        <div class="card-header" style="margin-bottom:8px">
                            <div class="skeleton skeleton-avatar" style="width:36px;height:36px;border-radius:8px"></div>
                        </div>
                        <div class="skeleton skeleton-text" style="width:20%;height:28px;margin-bottom:8px"></div>
                        <div class="skeleton skeleton-text" style="width:50%;height:12px;margin-bottom:8px"></div>
                        <div class="skeleton skeleton-text" style="width:40%;height:10px"></div>
                    </div>
                `).join('')}
            </div>

            <div class="card animate-slide-up" style="animation-delay: 0.2s">
                <div class="card-header">
                    <h2 class="card-title">Action Needed (Pending Approvals)</h2>
                    <span style="font-size:var(--text-xs);color:var(--text-tertiary)">Requests escalated to you for manual review</span>
                </div>
                <div id="recent-requests-table">
                    <table class="table" style="width:100%;text-align:left;border-collapse:collapse;">
                        <thead>
                            <tr style="border-bottom:1px solid var(--border-subtle)">
                                <th style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:60px"></div></th>
                                <th style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:90px"></div></th>
                                <th style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:50px"></div></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${[1,2,3].map(() => `
                                <tr>
                                    <td style="padding:12px 16px">
                                        <div class="skeleton skeleton-text" style="width:100px"></div>
                                        <div class="skeleton skeleton-text" style="width:60px;margin-bottom:0"></div>
                                    </td>
                                    <td style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:120px"></div></td>
                                    <td style="padding:12px 16px"><div class="skeleton skeleton-text" style="width:80px;height:20px;border-radius:4px"></div></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        loadManagerData();
    }

    async function loadManagerData() {
        try {
            const [pendingReviews, incidents] = await Promise.all([
                API.getPendingReviews().catch(() => []),
                API.getIncidents ? API.getIncidents().catch(() => []) : Promise.resolve([]),
            ]);
            
            renderManagerStats(pendingReviews, incidents);
            renderManagerActionTable(pendingReviews);
        } catch (err) {
            document.getElementById('dashboard-stats').innerHTML = `
                <div class="card stat-card"><p style="color:var(--status-escalated);">Unable to load data. ${err.message}</p></div>
            `;
        }
    }

    function renderManagerStats(pendingReviews, incidents) {
        const reviewCount = pendingReviews.length;
        const incidentCount = incidents.filter(i => i.status === 'open').length;

        document.getElementById('dashboard-stats').innerHTML = `
            <div class="card stat-card animate-slide-up" style="animation-delay:0.05s; cursor: pointer; transition: transform 0.2s, border-color 0.2s;" onclick="window.location.hash='#/review'" onmouseover="this.style.transform='translateY(-2px)'; this.style.borderColor='#3b82f6'" onmouseout="this.style.transform=''; this.style.borderColor=''">
                <div class="card-header">
                    <div class="stat-icon processing" style="background:rgba(59,130,246,0.1); color:#3b82f6; opacity: 1;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                    </div>
                </div>
                <div class="card-value" style="color:var(--text-primary)">${reviewCount}</div>
                <div class="card-label">Pending Team Reviews</div>
                <div style="font-size:var(--text-xs); color:var(--text-tertiary); margin-top:8px;">Click to open Review Panel &rarr;</div>
            </div>
            
            <div class="card stat-card animate-slide-up" style="animation-delay:0.1s; cursor: pointer; transition: transform 0.2s, border-color 0.2s;" onclick="window.location.hash='#/incidents'" onmouseover="this.style.transform='translateY(-2px)'; this.style.borderColor='var(--status-escalated)'" onmouseout="this.style.transform=''; this.style.borderColor=''">
                <div class="card-header">
                    <div class="stat-icon escalated" style="background:var(--status-escalated-bg); color:var(--status-escalated); opacity: 1;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    </div>
                </div>
                <div class="card-value" style="color:var(--text-primary)">${incidentCount}</div>
                <div class="card-label">Open HR Incidents</div>
                <div style="font-size:var(--text-xs); color:var(--text-tertiary); margin-top:8px;">Click to view Flagged Chats &rarr;</div>
            </div>
        `;
    }

    function renderManagerActionTable(reviews) {
        const container = document.getElementById('recent-requests-table');
        
        if (!reviews || reviews.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
                    </svg>
                    <h3>All caught up!</h3>
                    <p>There are no team requests requiring your approval right now.</p>
                </div>
            `;
            return;
        }

        const rows = reviews.slice(0, 5).map(req => {
            const date = new Date(req.created_at).toLocaleDateString(undefined, { 
                month: 'short', day: 'numeric' 
            });
            const type = req.request_type ? req.request_type.replace('_', ' ') : 'General Request';
            const urgency = req.sla_remaining_minutes !== null 
                ? (req.sla_remaining_minutes < 60 ? 'critical' : 'normal')
                : 'normal';

            return `
                <tr class="table-row-hover" onclick="window.location.hash='#/review'" style="cursor:pointer;">
                    <td>
                        <div style="font-weight:500">${req.employee_name}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary)">${date}</div>
                    </td>
                    <td>
                        <span style="text-transform:capitalize">${type}</span>
                    </td>
                    <td>
                        <span class="status-badge" style="background: ${urgency === 'critical' ? 'var(--status-escalated)' : '#3b82f6'}; color: white; opacity: 0.9; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
                            ${urgency === 'critical' ? 'Urgent Review' : 'Pending Review'}
                        </span>
                    </td>
                </tr>
            `;
        }).join('');

        container.innerHTML = `
            <table class="table" style="width:100%;text-align:left;border-collapse:collapse;">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-subtle);color:var(--text-secondary);font-size:var(--text-xs);text-transform:uppercase;">
                        <th style="padding:12px 16px;font-weight:500;">Employee</th>
                        <th style="padding:12px 16px;font-weight:500;">Request Type</th>
                        <th style="padding:12px 16px;font-weight:500;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
            ${reviews.length > 5 ? `
                <div style="text-align:center; padding:12px; border-top:1px solid var(--border-subtle);">
                    <a href="#/review" style="color:var(--primary-400); font-size:var(--text-sm); text-decoration:none; font-weight: 500;">View all ${reviews.length} pending items &rarr;</a>
                </div>
            ` : ''}
        `;
    }

    return { render };
})();
