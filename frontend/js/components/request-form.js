/**
 * SOP Forge — Request Form Component
 * Dynamic form for submitting SOP-governed requests.
 */

const RequestForm = (() => {
    async function render(container) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <h1 class="page-title">Submit New Request</h1>
                <p class="page-subtitle">Submit an SOP-governed request for AI evaluation</p>
            </div>
            <div class="card animate-slide-up">
                <form id="request-form">
                    <div class="form-group">
                        <label for="request-type">Request Type</label>
                        <select id="request-type" required>
                            <option value="">Select request type...</option>
                            <option value="leave">Leave Application</option>
                            <option value="reimbursement">Reimbursement</option>
                            <option value="it_access">IT Access Request</option>
                        </select>
                    </div>
                    <div id="dynamic-fields"></div>
                    <div style="display:flex;gap:var(--space-md);margin-top:var(--space-lg)">
                        <button type="submit" id="submit-request-btn" class="btn btn-primary" disabled>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
                            Submit for AI Evaluation
                        </button>
                        <a href="#/dashboard" class="btn btn-secondary">Cancel</a>
                    </div>
                </form>
            </div>
        `;

        document.getElementById('request-type').addEventListener('change', onTypeChange);
        document.getElementById('request-form').addEventListener('submit', onSubmit);
    }

    function onTypeChange(e) {
        const type = e.target.value;
        const fieldsEl = document.getElementById('dynamic-fields');
        const submitBtn = document.getElementById('submit-request-btn');
        submitBtn.disabled = !type;

        if (type === 'leave') {
            fieldsEl.innerHTML = `
                <div class="form-group animate-fade">
                    <label for="leave-type">Leave Type</label>
                    <select id="leave-type" required>
                        <option value="annual">Annual Leave</option>
                        <option value="sick">Sick Leave</option>
                        <option value="casual">Casual Leave</option>
                        <option value="unpaid">Unpaid Leave</option>
                    </select>
                </div>
                <div class="form-row animate-fade">
                    <div class="form-group">
                        <label for="start-date">Start Date</label>
                        <input type="date" id="start-date" required>
                    </div>
                    <div class="form-group">
                        <label for="end-date">End Date</label>
                        <input type="date" id="end-date" required>
                    </div>
                </div>
                <div class="form-group animate-fade">
                    <label class="form-checkbox">
                        <input type="checkbox" id="half-day">
                        Half Day Leave
                    </label>
                </div>
                <div class="form-group animate-fade">
                    <label for="leave-reason">Reason</label>
                    <textarea id="leave-reason" placeholder="Please describe the reason for your leave..." required minlength="5"></textarea>
                </div>
                <div class="form-group animate-fade">
                    <label for="leave-contact">Contact During Leave (optional)</label>
                    <input type="text" id="leave-contact" placeholder="Phone or email">
                </div>
            `;
            // Set default dates
            const today = new Date();
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 7);
            document.getElementById('start-date').value = tomorrow.toISOString().split('T')[0];
            const endDate = new Date(tomorrow);
            endDate.setDate(endDate.getDate() + 1);
            document.getElementById('end-date').value = endDate.toISOString().split('T')[0];
        } else if (type === 'reimbursement') {
            fieldsEl.innerHTML = `
                <div class="form-group animate-fade">
                    <label for="reimb-category">Category</label>
                    <select id="reimb-category" required>
                        <option value="travel">Travel</option>
                        <option value="medical">Medical</option>
                        <option value="equipment">Equipment</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                <div class="form-row animate-fade">
                    <div class="form-group">
                        <label for="reimb-amount">Amount (USD)</label>
                        <input type="number" id="reimb-amount" min="0.01" step="0.01" required placeholder="0.00">
                    </div>
                    <div class="form-group">
                        <label for="reimb-receipt">Receipt Reference</label>
                        <input type="text" id="reimb-receipt" placeholder="INV-12345">
                    </div>
                </div>
                <div class="form-group animate-fade">
                    <label for="reimb-description">Description</label>
                    <textarea id="reimb-description" placeholder="Describe the expense..." required minlength="5"></textarea>
                </div>
            `;
        } else if (type === 'it_access') {
            fieldsEl.innerHTML = `
                <div class="form-group animate-fade">
                    <label for="it-system">System Name</label>
                    <input type="text" id="it-system" placeholder="e.g., GitHub, AWS, Jira" required>
                </div>
                <div class="form-group animate-fade">
                    <label for="it-access-level">Access Level</label>
                    <select id="it-access-level" required>
                        <option value="read">Read Only</option>
                        <option value="write">Read/Write</option>
                        <option value="admin">Admin</option>
                    </select>
                </div>
                <div class="form-group animate-fade">
                    <label for="it-duration">Duration (days, leave blank for permanent)</label>
                    <input type="number" id="it-duration" min="1" placeholder="e.g., 30">
                </div>
                <div class="form-group animate-fade">
                    <label for="it-justification">Justification</label>
                    <textarea id="it-justification" placeholder="Why do you need this access?" required minlength="10"></textarea>
                </div>
            `;
        } else {
            fieldsEl.innerHTML = '';
        }
    }

    async function onSubmit(e) {
        e.preventDefault();
        const type = document.getElementById('request-type').value;
        let submitted_data = {};

        if (type === 'leave') {
            submitted_data = {
                leave_type: document.getElementById('leave-type').value,
                start_date: document.getElementById('start-date').value,
                end_date: document.getElementById('end-date').value,
                half_day: document.getElementById('half-day').checked,
                reason: document.getElementById('leave-reason').value,
                contact_during_leave: document.getElementById('leave-contact').value || null,
            };
        } else if (type === 'reimbursement') {
            submitted_data = {
                category: document.getElementById('reimb-category').value,
                amount: parseFloat(document.getElementById('reimb-amount').value),
                description: document.getElementById('reimb-description').value,
                receipt_ref: document.getElementById('reimb-receipt').value || null,
            };
        } else if (type === 'it_access') {
            submitted_data = {
                system_name: document.getElementById('it-system').value,
                access_level: document.getElementById('it-access-level').value,
                duration_days: parseInt(document.getElementById('it-duration').value) || null,
                justification: document.getElementById('it-justification').value,
            };
        }

        const btn = document.getElementById('submit-request-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Processing...';

        try {
            await API.submitRequest({ request_type: type, submitted_data });
            App.toast('Request submitted! AI evaluation is in progress.', 'success');
            Router.navigate('/requests');
        } catch (err) {
            App.toast(`Submission failed: ${err.message}`, 'error');
            btn.disabled = false;
            btn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
                Submit for AI Evaluation
            `;
        }
    }

    return { render };
})();
