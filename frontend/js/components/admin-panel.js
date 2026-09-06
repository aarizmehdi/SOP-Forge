/**
 * SOP Forge — Admin Panel Component
 * Premium UI for SOP Administration.
 */

const AdminPanel = (() => {
    let documents = [];
    let editingDoc = null;

    async function render(container) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <div style="display:flex;justify-content:space-between;align-items:flex-end">
                    <div>
                        <h1 class="page-title">SOP Administration</h1>
                        <p class="page-subtitle">Manage and deploy AI policy configurations</p>
                    </div>
                    <button class="btn btn-primary" onclick="AdminPanel.showCreateForm()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        New SOP Document
                    </button>
                </div>
            </div>

            <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.25);border-radius:10px;padding:12px 18px;margin-bottom:24px;font-size:13px;color:var(--primary-200);display:flex;align-items:center;gap:12px">
                <span style="font-size:18px">ℹ️</span>
                <div>
                    <strong>System Architecture Note:</strong> SOP documents uploaded here are embedded into vector space and used by the AI Copilot for policy retrieval and answers. Executable approval decision rules are governed separately by the system's deterministic DMN engine.
                </div>
            </div>
            
            <div id="admin-content" style="position:relative">
                <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(320px, 1fr));gap:24px;">
                    ${[1,2,3].map(() => `
                        <div class="card" style="display:flex;flex-direction:column;border:1px solid var(--border-default);background:var(--bg-secondary);border-radius:16px;overflow:hidden;height:240px">
                            <div style="height:4px;width:100%;background:var(--bg-tertiary)"></div>
                            <div style="padding:24px;flex:1;display:flex;flex-direction:column">
                                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px">
                                    <div class="skeleton skeleton-avatar" style="width:48px;height:48px;border-radius:12px"></div>
                                    <div class="skeleton skeleton-text" style="width:60px;height:20px;border-radius:10px"></div>
                                </div>
                                <div class="skeleton skeleton-text" style="width:70%;height:20px;margin-bottom:12px"></div>
                                <div style="display:flex;gap:8px;margin-bottom:24px">
                                    <div class="skeleton skeleton-text" style="width:60px;height:16px;border-radius:4px;margin-bottom:0"></div>
                                    <div class="skeleton skeleton-text" style="width:80px;height:16px;border-radius:4px;margin-bottom:0"></div>
                                </div>
                            </div>
                            <div style="border-top:1px solid var(--border-subtle);background:var(--bg-tertiary);display:grid;grid-template-columns:1fr 1fr;height:48px">
                                <div style="border-right:1px solid var(--border-subtle)"></div>
                                <div></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        loadDocuments();
    }

    async function loadDocuments() {
        try {
            documents = await API.listSOPDocs();
            renderDocList();
        } catch (err) {
            document.getElementById('admin-content').innerHTML = `
                <div class="card"><p style="color:var(--status-rejected)">Failed to load documents: ${App.escapeHtml(err.message)}</p></div>
            `;
        }
    }

    function getCategoryIcon(cat) {
        if (cat === 'leave') return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
        if (cat === 'it_access') return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`;
        if (cat === 'reimbursement') return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`;
        return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
    }

    function renderDocList() {
        const contentEl = document.getElementById('admin-content');

        if (!documents.length) {
            contentEl.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    <h3>No SOP configurations found</h3>
                    <p>Create your first policy to configure the AI Brain.</p>
                    <button class="btn btn-primary" onclick="AdminPanel.showCreateForm()">Deploy First Policy</button>
                </div>
            `;
            return;
        }

        contentEl.innerHTML = `
            <div style="margin-bottom:24px;font-size:12px;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:1px;font-weight:600">
                ${documents.length} Configured Polic${documents.length !== 1 ? 'ies' : 'y'}
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(320px, 1fr));gap:24px;">
                ${documents.map((doc, idx) => `
                    <div class="card animate-slide-up" style="animation-delay:${idx * 0.05}s;display:flex;flex-direction:column;border:1px solid var(--border-default);background:var(--bg-secondary);border-radius:16px;overflow:hidden;position:relative;transition:transform 0.2s, box-shadow 0.2s;box-shadow:var(--shadow-sm)" 
                         onmouseover="this.style.transform='translateY(-4px)';this.style.boxShadow='var(--shadow-lg)';this.style.borderColor='var(--border-hover)'"
                         onmouseout="this.style.transform='translateY(0)';this.style.boxShadow='var(--shadow-sm)';this.style.borderColor='var(--border-default)'">
                        
                        <!-- Top Accent Line -->
                        <div style="height:4px;width:100%;background:linear-gradient(90deg, var(--text-tertiary), transparent)"></div>

                        <div style="padding:24px;flex:1;display:flex;flex-direction:column">
                            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px">
                                <div style="width:48px;height:48px;border-radius:12px;background:var(--bg-tertiary);border:1px solid var(--border-subtle);display:flex;align-items:center;justify-content:center;color:var(--text-primary)">
                                    ${getCategoryIcon(doc.category)}
                                </div>
                                <span class="badge ${doc.is_active ? 'badge-approved' : 'badge-rejected'}" style="padding:4px 10px">
                                    ${doc.is_active ? 'Active' : 'Inactive'}
                                </span>
                            </div>

                            <h3 style="font-size:18px;font-weight:700;color:var(--text-primary);margin-bottom:8px;line-height:1.3">${App.escapeHtml(doc.title)}</h3>
                            
                            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px">
                                <span style="font-size:11px;font-weight:600;color:var(--text-tertiary);background:var(--bg-tertiary);padding:4px 8px;border-radius:4px;text-transform:uppercase">
                                    ${App.escapeHtml(doc.category.replace('_', ' '))}
                                </span>
                                <span style="font-size:11px;font-weight:600;color:var(--text-tertiary);background:var(--bg-tertiary);padding:4px 8px;border-radius:4px">
                                    Version v${App.escapeHtml(doc.version)}
                                </span>
                            </div>

                            <div style="margin-top:auto;font-family:var(--font-mono);font-size:11px;color:var(--text-tertiary)">
                                Last synced: ${new Date(doc.updated_at).toLocaleDateString('en-GB')}
                            </div>
                        </div>

                        <!-- Card Actions -->
                        <div style="border-top:1px solid var(--border-subtle);background:var(--bg-tertiary);display:grid;grid-template-columns:1fr 1fr;height:48px">
                            <button onclick="AdminPanel.showEditor('${doc.id}')" style="background:transparent;border:none;border-right:1px solid var(--border-subtle);color:var(--text-primary);font-weight:600;font-size:13px;cursor:pointer;transition:background 0.2s" onmouseover="this.style.background='var(--bg-elevated)'" onmouseout="this.style.background='transparent'">
                                Configure
                            </button>
                            <button onclick="AdminPanel.deleteDoc('${doc.id}')" style="background:transparent;border:none;color:var(--status-rejected);font-weight:600;font-size:13px;cursor:pointer;transition:background 0.2s" onmouseover="this.style.background='rgba(239, 68, 68, 0.1)'" onmouseout="this.style.background='transparent'">
                                ${doc.is_active ? 'Deactivate' : 'Delete'}
                            </button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function buildFormHTML(doc = null) {
        return `
            <div class="card animate-slide-up" style="max-width:800px;margin:0 auto;border-radius:16px;padding:32px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:32px;border-bottom:1px solid var(--border-subtle);padding-bottom:20px">
                    <div>
                        <h2 style="font-size:24px;font-weight:700">${doc ? 'Configure SOP Policy' : 'Deploy New SOP Policy'}</h2>
                        <p style="font-size:13px;color:var(--text-tertiary);margin-top:4px">${doc ? `Editing v${doc.version} • Neural chunks: ${doc.chunk_count || '?'}` : 'Paste raw policy text to generate embeddings'}</p>
                    </div>
                    <button class="btn btn-ghost" onclick="AdminPanel.loadDocuments()">✕ Cancel</button>
                </div>
                
                <form id="sop-form">
                    <div class="form-row" style="margin-bottom:24px">
                        <div class="form-group">
                            <label for="sop-title">Policy Title</label>
                            <input type="text" id="sop-title" value="${doc ? App.escapeHtml(doc.title) : ''}" placeholder="e.g. Remote Work Hardware Policy" required style="font-size:15px;padding:12px;background:var(--bg-tertiary)">
                        </div>
                        <div class="form-group">
                            <label for="sop-category">Routing Category</label>
                            <select id="sop-category" required style="font-size:15px;padding:12px;background:var(--bg-tertiary)">
                                <option value="leave" ${doc && doc.category === 'leave' ? 'selected' : ''}>Leave</option>
                                <option value="reimbursement" ${doc && doc.category === 'reimbursement' ? 'selected' : ''}>Reimbursement</option>
                                <option value="it_access" ${doc && doc.category === 'it_access' ? 'selected' : ''}>IT Access</option>
                                <option value="general" ${doc && doc.category === 'general' ? 'selected' : ''}>General Operations</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label style="display:flex;justify-content:space-between">
                            <span>Policy Content</span>
                            <span style="font-size:11px;color:var(--status-approved);font-weight:normal;text-transform:none;letter-spacing:0">✓ Auto-embed enabled</span>
                        </label>
                        <div style="border:1px solid var(--border-default);border-radius:12px;overflow:hidden;background:#0d0d0f;box-shadow:inset 0 2px 10px rgba(0,0,0,0.5)">
                            <div style="background:var(--bg-tertiary);padding:8px 16px;border-bottom:1px solid var(--border-subtle);display:flex;gap:8px">
                                <div style="width:10px;height:10px;border-radius:50%;background:#ef4444"></div>
                                <div style="width:10px;height:10px;border-radius:50%;background:#f59e0b"></div>
                                <div style="width:10px;height:10px;border-radius:50%;background:#10b981"></div>
                            </div>
                            <textarea id="sop-content" required minlength="50" style="width:100%;min-height:400px;background:transparent;border:none;color:var(--primary-200);font-family:var(--font-mono);font-size:13px;padding:24px;line-height:1.6;resize:vertical;outline:none" placeholder="Paste the raw text of your standard operating procedure here. The AI Brain will automatically chunk, vectorize, and embed this document for retrieval during decision evaluations...">${doc ? App.escapeHtml(doc.content_text) : ''}</textarea>
                        </div>
                    </div>

                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:32px;padding-top:24px;border-top:1px solid var(--border-subtle)">
                        ${doc ? `<button type="button" class="btn btn-secondary" onclick="AdminPanel.viewChunks('${doc.id}')">View Embedded Vectors</button>` : '<div></div>'}
                        <button type="submit" class="btn btn-primary" style="padding:12px 24px;font-size:14px;box-shadow:var(--shadow-glow)">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                            ${doc ? 'Sync & Re-Embed Policy' : 'Deploy & Embed Policy'}
                        </button>
                    </div>
                </form>
            </div>
        `;
    }

    function showCreateForm() {
        editingDoc = null;
        document.getElementById('admin-content').innerHTML = buildFormHTML();
        
        document.getElementById('sop-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button[type=submit]');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Deploying...';

            try {
                await API.createSOPDoc({
                    title: document.getElementById('sop-title').value,
                    category: document.getElementById('sop-category').value,
                    content_text: document.getElementById('sop-content').value,
                });
                App.toast('Policy deployed and embedded into vector space!', 'success');
                loadDocuments();
            } catch (err) {
                App.toast(`Deployment failed: ${err.message}`, 'error');
                btn.disabled = false;
                btn.textContent = 'Deploy & Embed Policy';
            }
        });
    }

    async function showEditor(docId) {
        try {
            editingDoc = await API.getSOPDoc(docId);
            document.getElementById('admin-content').innerHTML = buildFormHTML(editingDoc);

            document.getElementById('sop-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = e.target.querySelector('button[type=submit]');
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner"></span> Syncing...';
                try {
                    await API.updateSOPDoc(docId, {
                        title: document.getElementById('sop-title').value,
                        category: document.getElementById('sop-category').value,
                        content_text: document.getElementById('sop-content').value,
                    });
                    App.toast('Policy synced and vectors updated.', 'success');
                    loadDocuments();
                } catch (err) {
                    App.toast(`Sync failed: ${err.message}`, 'error');
                    btn.disabled = false;
                    btn.textContent = 'Sync & Re-Embed Policy';
                }
            });
        } catch (err) {
            App.toast(`Failed to load configuration: ${err.message}`, 'error');
            loadDocuments();
        }
    }

    async function viewChunks(docId) {
        try {
            const chunks = await API.getSOPChunks(docId);
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.innerHTML = `
                <div class="modal-content" style="max-width:760px;border-radius:16px;box-shadow:var(--shadow-lg)">
                    <div class="modal-header" style="border-bottom:1px solid var(--border-subtle);padding-bottom:16px;margin-bottom:20px">
                        <div>
                            <h2 class="modal-title" style="font-size:20px;font-weight:700">Vector Embeddings</h2>
                            <span style="font-size:13px;color:var(--text-tertiary)">${chunks.length} extracted semantic chunks</span>
                        </div>
                        <button class="btn-icon" onclick="this.closest('.modal-overlay').remove()">✕</button>
                    </div>
                    <div style="max-height:65vh;overflow-y:auto;padding-right:8px" class="custom-scrollbar">
                        <div style="display:flex;flex-direction:column;gap:16px">
                            ${chunks.map(chunk => `
                                <div style="background:var(--bg-tertiary);border:1px solid var(--border-subtle);border-radius:12px;overflow:hidden">
                                    <div style="display:flex;justify-content:space-between;align-items:center;background:rgba(255,255,255,0.02);padding:12px 16px;border-bottom:1px solid var(--border-subtle)">
                                        <div style="display:flex;align-items:center;gap:12px">
                                            <span style="font-family:var(--font-mono);font-size:12px;font-weight:600;color:var(--text-secondary)">#${String(chunk.chunk_index).padStart(3, '0')}</span>
                                            <span class="badge ${chunk.has_embedding ? 'badge-approved' : 'badge-rejected'}" style="padding:2px 8px;font-size:10px">
                                                ${chunk.has_embedding ? 'VECTORIZED' : 'FAILED'}
                                            </span>
                                        </div>
                                    </div>
                                    <div style="padding:16px;font-size:13px;line-height:1.6;color:var(--text-primary);white-space:pre-wrap;font-family:var(--font-sans)">${App.escapeHtml(chunk.chunk_text)}</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div style="margin-top:24px;display:flex;justify-content:flex-end">
                        <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Close Viewer</button>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);
            overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
        } catch (err) {
            App.toast(`Failed to load vector data: ${err.message}`, 'error');
        }
    }

    async function deleteDoc(docId) {
        const title = documents.find(doc => doc.id === docId)?.title || 'this policy';
        if (!confirm(`Are you sure you want to deactivate "${title}"?\nThe AI Brain will immediately stop retrieving policies from this document during evaluations.`)) return;
        try {
            await API.deleteSOPDoc(docId);
            App.toast(`"${title}" deactivated from vector space.`, 'success');
            loadDocuments();
        } catch (err) {
            App.toast(`Failed to deactivate: ${err.message}`, 'error');
        }
    }

    return { render, showCreateForm, showEditor, viewChunks, deleteDoc, loadDocuments };
})();
