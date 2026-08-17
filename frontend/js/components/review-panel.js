/**
 * SOP Forge — Review Panel Component
 * Manager view for escalated requests with SLA countdown.
 */

const ReviewPanel = (() => {
    let pendingRequests = [];

    async function render(container) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <h1 class="page-title">Review Panel</h1>
                <p class="page-subtitle">Escalated requests awaiting your decision</p>
            </div>
            <div id="review-list">
                <div class="skeleton skeleton-card" style="height:200px;margin-bottom:16px"></div>
                <div class="skeleton skeleton-card" style="height:200px"></div>
            </div>
        `;
        loadPendingReviews();
    }

    async function loadPendingReviews() {
        try {
            pendingRequests = await API.getPendingReviews();
            renderReviewList();
        } catch (err) {
            document.getElementById('review-list').innerHTML = `
                <div class="card"><p style="color:var(--text-secondary)">Error loading reviews: ${err.message}</p></div>
            `;
        }
    }

    function renderReviewList() {
        const container = document.getElementById('review-list');

        if (!pendingRequests.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                    <h3>All caught up!</h3>
                    <p>No escalated requests pending review.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = pendingRequests.map((req, idx) => {
            const cleanRefs = formatPolicyRefs(req.policy_refs);
            const reasoning = cleanReasoning(req.evaluation_reasoning);
            const details = formatRequestDetails(req);

            return `
            <div class="card animate-slide-up" style="margin-bottom:var(--space-md);animation-delay:${idx * 0.05}s">
                <!-- Header: Employee info + SLA -->
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--space-md)">
                    <div>
                        <div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:6px">
                            <span style="font-size:var(--text-base);font-weight:600;color:var(--text-primary)">${req.employee_name}</span>
                            <span style="font-size:var(--text-xs);color:var(--text-tertiary)">${req.employee_id_code}</span>
                            <span class="badge badge-pending">${formatRequestType(req.request_type)}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:var(--space-md);font-size:var(--text-xs);color:var(--text-tertiary)">
                            ${req.department ? `<span>📍 ${req.department}</span>` : ''}
                            <span>📅 ${new Date(req.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}, ${new Date(req.created_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                    </div>
                    ${renderSLATimer(req.sla_remaining_minutes)}
                </div>

                <!-- Request Details -->
                ${details ? `
                    <div style="background:var(--bg-tertiary);border:1px solid var(--border-subtle);border-radius:var(--radius-md);padding:var(--space-md);margin-bottom:var(--space-md)">
                        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:var(--space-sm) var(--space-lg)">
                            ${details}
                        </div>
                    </div>
                ` : ''}

                <!-- Reason for Escalation -->
                ${reasoning ? `
                    <div style="margin-bottom:var(--space-md)">
                        <div style="font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Reason for Escalation</div>
                        <div class="reasoning-box">${reasoning}</div>
                    </div>
                ` : ''}

                <!-- Policy References -->
                ${cleanRefs ? `
                    <div style="margin-bottom:var(--space-md)">
                        <div style="font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Policy References</div>
                        <div>${cleanRefs}</div>
                    </div>
                ` : ''}

                <!-- Action Buttons -->
                <div style="display:flex;gap:var(--space-sm);align-items:center;padding-top:var(--space-md);border-top:1px solid var(--border-subtle)">
                    <button class="btn btn-success btn-sm" onclick="ReviewPanel.showDecisionModal('${req.id}', 'approved')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                        Approve
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="ReviewPanel.showDecisionModal('${req.id}', 'rejected')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        Reject
                    </button>
                    <button class="btn btn-warning btn-sm" onclick="ReviewPanel.showDecisionModal('${req.id}', 'routed')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        Request More Info
                    </button>
                    ${Auth.hasMinRole('manager') ? `
                        <button class="btn btn-ghost btn-sm" style="margin-left:auto;color:var(--status-escalated)" onclick="ReviewPanel.showOverrideModal('${req.id}')">
                            ⚡ Override
                        </button>
                    ` : ''}
                </div>
            </div>
            `;
        }).join('');
    }

    function formatRequestType(type) {
        const labels = { leave: 'Leave Request', reimbursement: 'Expense Claim', it_access: 'IT Access' };
        return labels[type] || type;
    }

    function formatRequestDetails(req) {
        const data = req.submitted_data;
        if (!data) return '';

        let items = [];
        if (req.request_type === 'leave') {
            if (data.leave_type) items.push({ label: 'Leave Type', value: data.leave_type.charAt(0).toUpperCase() + data.leave_type.slice(1) });
            if (data.start_date) items.push({ label: 'From', value: new Date(data.start_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) });
            if (data.end_date) items.push({ label: 'To', value: new Date(data.end_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) });
            if (data.reason) items.push({ label: 'Reason', value: data.reason });
        } else if (req.request_type === 'reimbursement') {
            if (data.category) items.push({ label: 'Category', value: data.category.charAt(0).toUpperCase() + data.category.slice(1) });
            if (data.amount) items.push({ label: 'Amount', value: `$${data.amount.toFixed(2)}` });
            if (data.description) items.push({ label: 'Description', value: data.description });
        } else if (req.request_type === 'it_access') {
            if (data.system_name) items.push({ label: 'System', value: data.system_name });
            if (data.access_level) items.push({ label: 'Access Level', value: data.access_level.charAt(0).toUpperCase() + data.access_level.slice(1) });
            if (data.justification) items.push({ label: 'Justification', value: data.justification });
        }

        return items.map(item => `
            <div>
                <span style="font-size:11px;color:var(--text-tertiary)">${item.label}</span>
                <div style="font-size:var(--text-xs);color:var(--text-primary);font-weight:500;margin-top:2px">${item.value}</div>
            </div>
        `).join('');
    }

    function cleanReasoning(reasoning) {
        if (!reasoning) return '';
        // Strip "Escalated by AI Brain:", "AI Brain:", etc.
        return reasoning
            .replace(/^Escalated by AI Brain:\s*/i, '')
            .replace(/^AI Brain:\s*/i, '')
            .replace(/^Escalated:\s*/i, '')
            .trim();
    }

    function formatPolicyRefs(refs) {
        if (!refs || !refs.length) return '';
        const clean = Array.from(new Set(refs.map(r => r.replace(/:\s*chunk\s*\d+/gi, '').trim())));
        return clean.map(ref => `<span class="policy-ref">${ref}</span>`).join('');
    }

    function renderSLATimer(minutes) {
        if (minutes == null) return '';
        const h = Math.floor(Math.abs(minutes) / 60);
        const m = Math.abs(minutes) % 60;
        const cls = minutes <= 0 ? 'urgent' : minutes <= 60 ? 'warning' : 'normal';
        const label = minutes <= 0 ? 'Overdue' : `${h}h ${m}m remaining`;
        return `<div class="sla-timer ${cls}"><span class="sla-dot"></span> SLA: ${label}</div>`;
    }

    function showDecisionModal(requestId, decision) {
        const labels = { approved: 'Approve', rejected: 'Reject', routed: 'Request More Info' };
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content" style="max-width:480px">
                <div class="modal-header">
                    <h2 class="modal-title">${labels[decision]} Request</h2>
                    <button class="btn-icon" onclick="this.closest('.modal-overlay').remove()">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
                <form id="decision-form">
                    <div class="form-group">
                        <label>Comment (required)</label>
                        <textarea id="decision-comment" placeholder="Provide your reasoning..." required minlength="5"></textarea>
                    </div>
                    <div style="display:flex;gap:var(--space-sm);justify-content:flex-end">
                        <button type="button" class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                        <button type="submit" class="btn btn-primary" id="decision-submit-btn">Submit Decision</button>
                    </div>
                </form>
            </div>
        `;
        document.body.appendChild(overlay);

        document.getElementById('decision-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const comment = document.getElementById('decision-comment').value;
            const btn = document.getElementById('decision-submit-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Processing...';

            try {
                await API.submitReview(requestId, { decision, comment });
                overlay.remove();
                App.toast('Decision submitted successfully.', 'success');
                render(document.getElementById('main-content'));
            } catch (err) {
                App.toast(`Error: ${err.message}`, 'error');
                btn.disabled = false;
                btn.textContent = 'Submit Decision';
            }
        });
    }

    function showOverrideModal(requestId) {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content" style="max-width:480px">
                <div class="modal-header">
                    <h2 class="modal-title">Executive Override</h2>
                    <button class="btn-icon" onclick="this.closest('.modal-overlay').remove()">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
                <form id="override-form">
                    <div class="form-group">
                        <label>Override Decision</label>
                        <select id="override-decision" required>
                            <option value="approved">Approve</option>
                            <option value="rejected">Reject</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Justification (required)</label>
                        <textarea id="override-justification" placeholder="Provide mandatory justification for this override..." required minlength="10"></textarea>
                    </div>
                    <div style="display:flex;gap:var(--space-sm);justify-content:flex-end">
                        <button type="button" class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                        <button type="submit" class="btn btn-primary" id="override-submit-btn">Submit Override</button>
                    </div>
                </form>
            </div>
        `;
        document.body.appendChild(overlay);

        document.getElementById('override-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const new_decision = document.getElementById('override-decision').value;
            const justification = document.getElementById('override-justification').value;
            const btn = document.getElementById('override-submit-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Processing...';

            try {
                await API.submitOverride(requestId, { new_decision, justification });
                overlay.remove();
                App.toast('Override recorded successfully.', 'success');
                render(document.getElementById('main-content'));
            } catch (err) {
                App.toast(`Error: ${err.message}`, 'error');
                btn.disabled = false;
                btn.textContent = 'Submit Override';
            }
        });
    }

    return { render, showDecisionModal, showOverrideModal };
})();
