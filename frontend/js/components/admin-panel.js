/**
 * SOP Forge — Admin Panel Component
 * No-code SOP rule editor for HR/Compliance.
 */

const AdminPanel = (() => {
    let documents = [];
    let editingDoc = null;

    async function render(container) {
        container.innerHTML = `
            <div class="page-header animate-slide-down">
                <h1 class="page-title">SOP Administration</h1>
                <p class="page-subtitle">Manage SOP policy documents — changes are reflected immediately</p>
            </div>
            <div class="action-bar animate-slide-down">
                <div class="action-bar-group">
                    <span style="font-size:var(--text-sm);color:var(--text-secondary)" id="doc-count">Loading...</span>
                </div>
                <button class="btn btn-primary btn-sm" onclick="AdminPanel.showCreateForm()">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    New SOP Document
                </button>
            </div>
            <div id="admin-content">
                <div class="skeleton skeleton-card" style="height:80px;margin-bottom:8px"></div>
                <div class="skeleton skeleton-card" style="height:80px"></div>
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
                <div class="card"><p style="color:var(--text-secondary)">Error: ${err.message}</p></div>
            `;
        }
    }

    function renderDocList() {
        const contentEl = document.getElementById('admin-content');
        document.getElementById('doc-count').textContent = `${documents.length} document${documents.length !== 1 ? 's' : ''}`;

        if (!documents.length) {
            contentEl.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    <h3>No SOP documents</h3>
                    <p>Create your first SOP document to get started.</p>
                </div>
            `;
            return;
        }

        contentEl.innerHTML = `<div class="sop-doc-list">${documents.map((doc, idx) => `
            <div class="sop-doc-item animate-slide-up" style="animation-delay:${idx * 0.03}s" onclick="AdminPanel.showEditor('${doc.id}')">
                <div class="sop-doc-info">
                    <h4>${doc.title}</h4>
                    <div class="sop-doc-meta">
                        <span>Category: ${doc.category}</span>
                        <span>Version: v${doc.version}</span>
                        <span>${doc.is_active ? '🟢 Active' : '🔴 Inactive'}</span>
                        <span>Updated: ${new Date(doc.updated_at).toLocaleDateString()}</span>
                    </div>
                </div>
                <div style="display:flex;gap:var(--space-sm)">
                    <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation();AdminPanel.showEditor('${doc.id}')">Edit</button>
                    <button class="btn btn-ghost btn-sm" style="color:var(--status-rejected)" onclick="event.stopPropagation();AdminPanel.deleteDoc('${doc.id}', '${doc.title}')">Deactivate</button>
                </div>
            </div>
        `).join('')}</div>`;
    }

    function showCreateForm() {
        editingDoc = null;
        const contentEl = document.getElementById('admin-content');
        contentEl.innerHTML = `
            <div class="card animate-slide-up">
                <h3 style="margin-bottom:var(--space-lg)">Create New SOP Document</h3>
                <form id="sop-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="sop-title">Title</label>
                            <input type="text" id="sop-title" placeholder="e.g., Company Leave Policy SOP" required>
                        </div>
                        <div class="form-group">
                            <label for="sop-category">Category</label>
                            <select id="sop-category" required>
                                <option value="leave">Leave</option>
                                <option value="reimbursement">Reimbursement</option>
                                <option value="it_access">IT Access</option>
                                <option value="general">General</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="sop-content">Policy Content</label>
                        <div class="sop-editor">
                            <div class="sop-editor-toolbar">
                                <span style="font-size:var(--text-xs);color:var(--text-tertiary)">Plain text — will be chunked and embedded automatically</span>
                            </div>
                            <div class="sop-editor-content">
                                <textarea id="sop-content" placeholder="Paste or type the full SOP policy text here..." required minlength="50"></textarea>
                            </div>
                        </div>
                    </div>
                    <div style="display:flex;gap:var(--space-sm)">
                        <button type="submit" class="btn btn-primary">Create & Embed</button>
                        <button type="button" class="btn btn-secondary" onclick="AdminPanel.loadDocuments()">Cancel</button>
                    </div>
                </form>
            </div>
        `;

        document.getElementById('sop-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button[type=submit]');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Embedding...';

            try {
                await API.createSOPDoc({
                    title: document.getElementById('sop-title').value,
                    category: document.getElementById('sop-category').value,
                    content_text: document.getElementById('sop-content').value,
                });
                App.toast('SOP document created and embedded!', 'success');
                loadDocuments();
            } catch (err) {
                App.toast(`Failed: ${err.message}`, 'error');
                btn.disabled = false;
                btn.textContent = 'Create & Embed';
            }
        });
    }

    async function showEditor(docId) {
        try {
            editingDoc = await API.getSOPDoc(docId);
            const contentEl = document.getElementById('admin-content');
            contentEl.innerHTML = `
                <div class="card animate-slide-up">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-lg)">
                        <div>
                            <h3>${editingDoc.title}</h3>
                            <span style="font-size:var(--text-xs);color:var(--text-tertiary)">v${editingDoc.version} • ${editingDoc.chunk_count || '?'} chunks • ${editingDoc.is_active ? 'Active' : 'Inactive'}</span>
                        </div>
                        <button class="btn btn-ghost btn-sm" onclick="AdminPanel.loadDocuments()">← Back</button>
                    </div>
                    <form id="sop-edit-form">
                        <div class="form-row">
                            <div class="form-group">
                                <label for="edit-title">Title</label>
                                <input type="text" id="edit-title" value="${editingDoc.title}">
                            </div>
                            <div class="form-group">
                                <label for="edit-category">Category</label>
                                <input type="text" id="edit-category" value="${editingDoc.category}">
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="edit-content">Policy Content</label>
                            <div class="sop-editor">
                                <div class="sop-editor-toolbar">
                                    <span style="font-size:var(--text-xs);color:var(--text-tertiary)">Editing will trigger re-embedding on save</span>
                                </div>
                                <div class="sop-editor-content">
                                    <textarea id="edit-content">${editingDoc.content_text}</textarea>
                                </div>
                            </div>
                        </div>
                        <div style="display:flex;gap:var(--space-sm)">
                            <button type="submit" class="btn btn-primary">Save & Re-Embed</button>
                            <button type="button" class="btn btn-secondary" onclick="AdminPanel.viewChunks('${docId}')">View Chunks</button>
                            <button type="button" class="btn btn-secondary" onclick="AdminPanel.loadDocuments()">Cancel</button>
                        </div>
                    </form>
                </div>
            `;

            document.getElementById('sop-edit-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = e.target.querySelector('button[type=submit]');
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner"></span> Re-Embedding...';
                try {
                    await API.updateSOPDoc(docId, {
                        title: document.getElementById('edit-title').value,
                        category: document.getElementById('edit-category').value,
                        content_text: document.getElementById('edit-content').value,
                    });
                    App.toast('SOP updated and re-embedded!', 'success');
                    loadDocuments();
                } catch (err) {
                    App.toast(`Failed: ${err.message}`, 'error');
                    btn.disabled = false;
                    btn.textContent = 'Save & Re-Embed';
                }
            });
        } catch (err) {
            App.toast(`Failed to load document: ${err.message}`, 'error');
        }
    }

    async function viewChunks(docId) {
        try {
            const chunks = await API.getSOPChunks(docId);
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.innerHTML = `
                <div class="modal-content" style="max-width:720px">
                    <div class="modal-header">
                        <h2 class="modal-title">Embedded Chunks (${chunks.length})</h2>
                        <button class="btn-icon" onclick="this.closest('.modal-overlay').remove()">✕</button>
                    </div>
                    <div style="max-height:60vh;overflow-y:auto">
                        ${chunks.map(chunk => `
                            <div style="margin-bottom:var(--space-md);padding:var(--space-md);background:var(--bg-tertiary);border-radius:var(--radius-md)">
                                <div style="display:flex;justify-content:space-between;margin-bottom:var(--space-sm)">
                                    <span class="badge badge-pending">Chunk ${chunk.chunk_index}</span>
                                    <span style="font-size:var(--text-xs);color:${chunk.has_embedding ? 'var(--status-approved)' : 'var(--status-rejected)'}">
                                        ${chunk.has_embedding ? '✓ Embedded' : '✗ No embedding'}
                                    </span>
                                </div>
                                <p style="font-size:var(--text-sm);color:var(--text-secondary);white-space:pre-wrap">${chunk.chunk_text.slice(0, 300)}${chunk.chunk_text.length > 300 ? '...' : ''}</p>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);
            overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
        } catch (err) {
            App.toast(`Failed to load chunks: ${err.message}`, 'error');
        }
    }

    async function deleteDoc(docId, title) {
        if (!confirm(`Deactivate "${title}"? This will exclude it from AI evaluations.`)) return;
        try {
            await API.deleteSOPDoc(docId);
            App.toast(`"${title}" deactivated.`, 'success');
            loadDocuments();
        } catch (err) {
            App.toast(`Failed: ${err.message}`, 'error');
        }
    }

    return { render, showCreateForm, showEditor, viewChunks, deleteDoc, loadDocuments };
})();
