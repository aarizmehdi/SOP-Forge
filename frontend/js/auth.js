/**
 * SOP Forge — Auth Module
 * Handles authentication state, login, and logout.
 */

const Auth = (() => {
    let currentUser = null;

    function getStoredAuth() {
        return {
            token: localStorage.getItem('sopforge_token'),
            user: JSON.parse(localStorage.getItem('sopforge_user') || 'null'),
        };
    }

    function storeAuth(token, user) {
        localStorage.setItem('sopforge_token', token);
        localStorage.setItem('sopforge_user', JSON.stringify(user));
        currentUser = user;
    }

    function clearAuth() {
        localStorage.removeItem('sopforge_token');
        localStorage.removeItem('sopforge_user');
        currentUser = null;
    }

    async function login(email, password) {
        const data = await API.login(email, password);
        const user = {
            id: data.user_id,
            name: data.name,
            role: data.role,
            employeeId: data.employee_id,
        };
        storeAuth(data.access_token, user);
        return user;
    }

    function logout() {
        clearAuth();
        document.getElementById('app-screen').style.display = 'none';
        document.getElementById('login-screen').style.display = 'flex';
        document.getElementById('login-screen').classList.add('active');
    }

    function isAuthenticated() {
        return !!getStoredAuth().token;
    }

    function getUser() {
        if (!currentUser) {
            currentUser = getStoredAuth().user;
        }
        return currentUser;
    }

    function getRole() {
        const user = getUser();
        return user ? user.role : null;
    }

    function hasMinRole(required) {
        const hierarchy = { employee: 0, manager: 1, executive: 2, admin: 3 };
        const userLevel = hierarchy[getRole()] ?? -1;
        const requiredLevel = hierarchy[required] ?? 999;
        return userLevel >= requiredLevel;
    }

    function getInitials(name) {
        return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }

    return { login, logout, isAuthenticated, getUser, getRole, hasMinRole, getInitials };
})();
