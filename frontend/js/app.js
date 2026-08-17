/**
 * SOP Forge — Main Application Module
 * Orchestrates login, navigation, role-based UI, and notifications.
 */

const App = (() => {
    function init() {
        Router.init();

        // Check existing auth
        if (Auth.isAuthenticated()) {
            showApp();
        }

        // Login form handler
        document.getElementById('login-form').addEventListener('submit', handleLogin);

        // Logout handler
        document.getElementById('logout-btn').addEventListener('click', () => {
            Auth.logout();
            toast('Signed out successfully.', 'info');
        });
    }

    async function handleLogin(e) {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const errorEl = document.getElementById('login-error');
        const btn = document.getElementById('login-btn');

        errorEl.style.display = 'none';
        btn.querySelector('.btn-text').style.display = 'none';
        btn.querySelector('.btn-loader').style.display = 'inline-flex';
        btn.disabled = true;

        try {
            await Auth.login(email, password);
            window.location.hash = Router.getDefaultRoute();
            showApp();
            toast(`Welcome back, ${Auth.getUser().name}!`, 'success');
        } catch (err) {
            errorEl.textContent = err.message;
            errorEl.style.display = 'block';
        } finally {
            btn.querySelector('.btn-text').style.display = 'inline';
            btn.querySelector('.btn-loader').style.display = 'none';
            btn.disabled = false;
        }
    }

    function showApp() {
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('login-screen').classList.remove('active');
        document.getElementById('app-screen').style.display = 'flex';

        const user = Auth.getUser();

        // Update user info in sidebar
        document.getElementById('user-name').textContent = user.name;
        document.getElementById('user-role').textContent = user.role;
        document.getElementById('user-avatar').textContent = Auth.getInitials(user.name);

        // Show/hide nav items based on role
        const dashboardNav = document.getElementById('nav-dashboard');
        const chatNav = document.getElementById('nav-chat');
        const newReqNav = document.getElementById('nav-new-request');
        const reviewNav = document.getElementById('nav-review');
        const adminNav = document.getElementById('nav-admin');
        const auditNav = document.getElementById('nav-audit');
        const incidentsNav = document.getElementById('nav-incidents');

        const isEmployee = user.role === 'employee';

        // Employee: AI Assistant + New Request only (no dashboard/review/admin/audit)
        // Manager/Executive/Admin: Dashboard + Review + Audit (no AI Assistant / New Request)
        dashboardNav.style.display = isEmployee ? 'none' : 'flex';
        chatNav.style.display = isEmployee ? 'flex' : 'none';
        newReqNav.style.display = isEmployee ? 'flex' : 'none';
        reviewNav.style.display = Auth.hasMinRole('manager') ? 'flex' : 'none';
        adminNav.style.display = Auth.hasMinRole('admin') ? 'flex' : 'none';
        auditNav.style.display = Auth.hasMinRole('manager') ? 'flex' : 'none';
        incidentsNav.style.display = Auth.hasMinRole('manager') ? 'flex' : 'none';

        // Load review badge count for managers
        if (Auth.hasMinRole('manager')) {
            loadReviewBadge();
        }

        // Navigate to current route or dashboard
        Router.handleRoute();
    }

    async function loadReviewBadge() {
        try {
            const pending = await API.getPendingReviews();
            const badge = document.getElementById('review-badge');
            if (pending.length > 0) {
                badge.textContent = pending.length;
                badge.style.display = 'inline-flex';
            } else {
                badge.style.display = 'none';
            }
        } catch {
            // Silently fail — badge is non-critical
        }
    }

    function toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
        `;
        container.appendChild(toast);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    return { init, toast };
})();

// ── Helper: Fill login from demo hint chips ──
function fillLogin(el) {
    document.getElementById('login-email').value = el.dataset.email;
    document.getElementById('login-password').value = 'password123';
}

// ── Boot ──
document.addEventListener('DOMContentLoaded', App.init);
