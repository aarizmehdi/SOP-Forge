/**
 * SOP Forge — My Requests Component
 * Employee view to track submitted requests and their statuses.
 */

const MyRequests = (() => {
    async function render(container) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <div style="display:flex;justify-content:space-between;align-items:flex-end">
                    <div>
                        <h1 class="page-title">My Requests</h1>
                        <p class="page-subtitle">Track the status of your submitted requests</p>
                    </div>
                    <a href="#/request/new" class="btn btn-primary btn-sm">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        New Request
                    </a>
                </div>
            </div>
            <div id="my-requests-list">
                ${[1,2,3].map(() => `
                    <div class="card animate-slide-up" style="margin-bottom:var(--space-md);display:flex;justify-content:space-between;align-items:center;padding:16px 20px">
                        <div style="display:flex;flex-direction:column;gap:6px;width:70%">
                            <div class="skeleton skeleton-text" style="width:40%;height:14px;margin-bottom:4px"></div>
                            <div class="skeleton skeleton-text" style="width:60%;height:10px;margin-bottom:4px"></div>
                            <div class="skeleton skeleton-text" style="width:20%;height:10px"></div>
                        </div>
                        <div class="skeleton skeleton-avatar" style="width:70px;height:24px;border-radius:12px"></div>
                    </div>
                `).join('')}
            </div>
        `;
        loadRequests();
    }

    async function loadRequests() {
        const container = document.getElementById('my-requests-list');
        try {
            const requests = await API.getMyRequests();
            renderList(container, requests);
        } catch (err) {
            container.innerHTML = `
                <div class="card"><p style="color:var(--text-secondary)">Error loading requests: ${App.escapeHtml(err.message)}</p></div>
            `;
        }
    }

    function renderList(container, requests) {
        if (!requests.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <h3>No requests yet</h3>
                    <p>Submit your first request to get started.</p>
                    <a href="#/request/new" class="btn btn-primary btn-sm" style="margin-top:16px">Submit a Request</a>
                </div>
            `;
            return;
        }

        container.innerHTML = requests.map((req, idx) => {
            const statusInfo = getStatusInfo(req.status, req.decision);
            const typeLabel = getTypeLabel(req.request_type);
            const date = new Date(req.created_at);

            return `
            <div class="card animate-slide-up" style="margin-bottom:var(--space-sm);animation-delay:${idx * 0.03}s;cursor:pointer" onclick="MyRequests.viewDetail('${req.id}')">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div style="display:flex;align-items:center;gap:var(--space-md)">
                        <div style="width:40px;height:40px;border-radius:var(--radius-md);background:${statusInfo.bg};border:1px solid ${statusInfo.border};display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0">
                            ${statusInfo.icon}
                        </div>
                        <div>
                            <div style="font-size:var(--text-sm);font-weight:600;color:var(--text-primary)">${typeLabel}</div>
                            <div style="font-size:var(--text-xs);color:var(--text-tertiary);margin-top:2px">
                                ${date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} · ${date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
                            </div>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:var(--space-md)">
                        <span class="badge badge-${statusInfo.badge}">${statusInfo.label}</span>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
                    </div>
                </div>
            </div>
            `;
        }).join('');
    }

    function getStatusInfo(status, decision) {
        if (['resolved', 'overridden'].includes(status) && decision === 'approved') {
            return { label: 'Approved', badge: 'approved', icon: '✅', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.2)' };
        }
        if (['resolved', 'overridden'].includes(status) && decision === 'rejected') {
            return { label: 'Declined', badge: 'rejected', icon: '❌', bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.2)' };
        }
        if (status === 'escalated' || decision === 'routed') {
            return { label: 'Under Review', badge: 'escalated', icon: '⏳', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.2)' };
        }
        if (status === 'in_progress') {
            return { label: 'Processing', badge: 'pending', icon: '⚙️', bg: 'rgba(161,161,170,0.1)', border: 'rgba(161,161,170,0.2)' };
        }
        return { label: 'Pending', badge: 'pending', icon: '📋', bg: 'rgba(161,161,170,0.1)', border: 'rgba(161,161,170,0.2)' };
    }

    function getTypeLabel(type) {
        const labels = { leave: 'Leave Application', reimbursement: 'Expense Reimbursement', it_access: 'IT Access Request' };
        return labels[type] || App.escapeHtml(type);
    }

    async function viewDetail(requestId) {
        try {
            const req = await API.getRequest(requestId);
            showDetailModal(req);
        } catch (err) {
            App.toast(`Error: ${err.message}`, 'error');
        }
    }

    function showDetailModal(req) {
        const statusInfo = getStatusInfo(req.status, req.decision);
        const date = new Date(req.created_at);
        let detailsHtml = '';

        if (req.submitted_data) {
            const d = req.submitted_data;
            if (req.request_type === 'leave') {
                detailsHtml = `
                    <div class="detail-grid" style="margin-bottom:var(--space-md)">
                        ${d.leave_type ? `<div class="detail-item"><span class="detail-label">Leave Type</span><span class="detail-value">${App.escapeHtml(d.leave_type.charAt(0).toUpperCase() + d.leave_type.slice(1))}</span></div>` : ''}
                        ${d.start_date ? `<div class="detail-item"><span class="detail-label">From</span><span class="detail-value">${new Date(d.start_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span></div>` : ''}
                        ${d.end_date ? `<div class="detail-item"><span class="detail-label">To</span><span class="detail-value">${new Date(d.end_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span></div>` : ''}
                        ${d.reason ? `<div class="detail-item" style="grid-column:1/-1"><span class="detail-label">Reason</span><span class="detail-value">${App.escapeHtml(d.reason)}</span></div>` : ''}
                    </div>
                `;
            } else if (req.request_type === 'reimbursement') {
                detailsHtml = `
                    <div class="detail-grid" style="margin-bottom:var(--space-md)">
                        ${d.category ? `<div class="detail-item"><span class="detail-label">Category</span><span class="detail-value">${App.escapeHtml(d.category)}</span></div>` : ''}
                        ${d.amount ? `<div class="detail-item"><span class="detail-label">Amount</span><span class="detail-value">$${d.amount.toFixed(2)}</span></div>` : ''}
                        ${d.description ? `<div class="detail-item" style="grid-column:1/-1"><span class="detail-label">Description</span><span class="detail-value">${App.escapeHtml(d.description)}</span></div>` : ''}
                    </div>
                `;
            } else if (req.request_type === 'it_access') {
                detailsHtml = `
                    <div class="detail-grid" style="margin-bottom:var(--space-md)">
                        ${d.system_name ? `<div class="detail-item"><span class="detail-label">System</span><span class="detail-value">${App.escapeHtml(d.system_name)}</span></div>` : ''}
                        ${d.access_level ? `<div class="detail-item"><span class="detail-label">Access Level</span><span class="detail-value">${App.escapeHtml(d.access_level)}</span></div>` : ''}
                        ${d.justification ? `<div class="detail-item" style="grid-column:1/-1"><span class="detail-label">Justification</span><span class="detail-value">${App.escapeHtml(d.justification)}</span></div>` : ''}
                    </div>
                `;
            }
        }

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content" style="max-width:560px">
                <div class="modal-header">
                    <h2 class="modal-title">${getTypeLabel(req.request_type)}</h2>
                    <button class="btn-icon" onclick="this.closest('.modal-overlay').remove()">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>

                <div style="display:flex;align-items:center;gap:var(--space-md);margin-bottom:var(--space-lg)">
                    <div style="width:44px;height:44px;border-radius:var(--radius-md);background:${statusInfo.bg};border:1px solid ${statusInfo.border};display:flex;align-items:center;justify-content:center;font-size:20px">
                        ${statusInfo.icon}
                    </div>
                    <div>
                        <div style="font-size:var(--text-base);font-weight:600;color:var(--text-primary)">${statusInfo.label}</div>
                        <div style="font-size:var(--text-xs);color:var(--text-tertiary)">Submitted ${date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</div>
                    </div>
                </div>

                ${detailsHtml}

                ${req.has_evidence && req.evidence_list && req.evidence_list.length ? `
                    <div style="margin-bottom:var(--space-md);background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);border-radius:var(--radius-md);padding:10px 14px">
                        <div style="font-size:11px;font-weight:700;color:var(--primary-400);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">📎 Supporting Evidence Attached</div>
                        <div style="display:flex;flex-wrap:wrap;gap:10px">
                            ${req.evidence_list.map(ev => `
                                <button type="button" onclick="MyRequests.openEvidence('${ev.id}')" class="btn btn-ghost btn-sm" style="background:var(--bg-tertiary);border:1px solid var(--border-subtle);font-size:var(--text-xs);display:inline-flex;align-items:center;gap:6px;color:var(--primary-400)">
                                    📄 ${App.escapeHtml(ev.original_filename || 'Evidence')} (${Math.round((ev.size_bytes || 0) / 1024)} KB)
                                </button>
                            `).join('')}
                        </div>
                    </div>
                ` : `
                    <div style="margin-bottom:var(--space-md);background:var(--bg-tertiary);border:1px dashed var(--border-subtle);border-radius:var(--radius-md);padding:12px;text-align:center">
                        <input type="file" id="evidence-upload-input-${req.id}" style="display:none" onchange="MyRequests.uploadEvidence('${req.id}', this)" accept=".pdf,.jpeg,.jpg,.png">
                        <button class="btn btn-ghost btn-sm" onclick="document.getElementById('evidence-upload-input-${req.id}').click()" style="color:var(--primary-400)">
                            📎 Attach Supporting Document (PDF / JPEG / PNG)
                        </button>
                    </div>
                `}

                <div style="display:flex;justify-content:flex-end;margin-top:var(--space-lg)">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    async function uploadEvidence(requestId, fileInput) {
        if (!fileInput.files || !fileInput.files[0]) return;
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);

        try {
            App.toast('Uploading evidence document...', 'info');
            const token = Auth.getToken();
            const res = await fetch(`/api/evidence/upload/${requestId}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || 'Failed to upload file');
            }

            App.toast('Evidence uploaded successfully!', 'success');
            document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
            viewDetail(requestId);
        } catch (err) {
            App.toast(`Upload failed: ${err.message}`, 'error');
        }
    }

    async function openEvidence(id) {
        const viewer = window.open('', '_blank');
        if (viewer) viewer.opener = null;
        try {
            const response = await fetch(`/api/evidence/file/${encodeURIComponent(id)}`, {
                headers: { Authorization: `Bearer ${Auth.getToken()}` }
            });
            if (!response.ok) throw new Error('Evidence is unavailable or access was denied.');
            const url = URL.createObjectURL(await response.blob());
            if (viewer) viewer.location.href = url;
            else {
                const link = document.createElement('a');
                link.href = url;
                link.download = 'evidence';
                link.click();
            }
            setTimeout(() => URL.revokeObjectURL(url), 60000);
        } catch (error) {
            if (viewer) viewer.close();
            App.toast(error.message, 'error');
        }
    }

    return { render, viewDetail, uploadEvidence, openEvidence };
})();
