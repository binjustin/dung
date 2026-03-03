import api from './api.js';
import { setSession, getSession, setupOfflineDetection } from './utils.js';

setupOfflineDetection();

// If already logged in, redirect
const session = getSession();
if (session) {
    window.location.href = '/pwa/dashboard.html';
}

const form = document.getElementById('login-form');
const errorDiv = document.getElementById('login-error');
const btn = document.getElementById('login-btn');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    if (!username || !password) {
        showError('Vui lòng nhập đầy đủ thông tin');
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Đang đăng nhập...';
    errorDiv.classList.remove('show');

    try {
        const res = await api.login(username, password);
        if (res && res.success) {
            setSession(res.user);
            window.location.href = '/pwa/dashboard.html';
        } else {
            showError(res?.message || 'Sai tên đăng nhập hoặc mật khẩu');
        }
    } catch (err) {
        showError('Không thể kết nối đến máy chủ');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Đăng nhập';
    }
});

function showError(msg) {
    errorDiv.textContent = msg;
    errorDiv.classList.add('show');
}
