/**
 * SOP Forge — SPA Router
 * Hash-based routing with role-based route guards.
 */

const Router = (() => {
    const routes = {
        '/dashboard': { component: Dashboard, minRole: 'manager' },
        '/chat': { component: ChatAssistant, minRole: 'employee' },
        '/requests': { component: MyRequests, minRole: 'employee' },
        '/request/new': { component: RequestForm, minRole: 'employee' },
        '/review': { component: ReviewPanel, minRole: 'manager' },
        '/admin': { component: AdminPanel, minRole: 'admin' },
        '/audit': { component: AuditViewer, minRole: 'manager' },
        '/incidents': { component: Incidents, minRole: 'manager' },
    };

    function init() {
        window.addEventListener('hashchange', handleRoute);
        // Don't auto-navigate on init — App.init handles this
    }

    function navigate(path) {
        window.location.hash = path;
    }

    function getDefaultRoute() {
        const user = Auth.getUser();
        return (user && user.role === 'employee') ? '/chat' : '/dashboard';
    }

    function handleRoute() {
        const hash = window.location.hash.slice(1) || getDefaultRoute();
        const path = hash.split('?')[0];

        const route = routes[path];
        if (!route) {
            navigate(getDefaultRoute());
            return;
        }

        // Role guard
        if (!Auth.hasMinRole(route.minRole)) {
            App.toast('You don\'t have permission to access that page.', 'warning');
            navigate('/dashboard');
            return;
        }

        // Update active nav
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.route === path.split('/')[1]);
        });

        // Render component
        const container = document.getElementById('main-content');
        container.innerHTML = ''; // Clear
        route.component.render(container);
    }

    function getCurrentRoute() {
        return window.location.hash.slice(1) || getDefaultRoute();
    }

    return { init, navigate, handleRoute, getCurrentRoute, getDefaultRoute };
})();
