// Utility helpers

export function formatCurrency(amount) {
    if (amount == null || isNaN(amount)) return '0 ₫';
    return new Intl.NumberFormat('vi-VN', {
        style: 'decimal',
        maximumFractionDigits: 0,
    }).format(amount) + ' ₫';
}

export function formatNumber(num) {
    if (num == null || isNaN(num)) return '0';
    return new Intl.NumberFormat('vi-VN').format(num);
}

export function formatDate(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
    });
}

export function formatDateTime(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

export function getRoleText(role) {
    switch (role) {
        case 'admin': return 'Quản trị viên';
        case 'manager': return 'Quản lý';
        default: return 'Nhân viên';
    }
}

export function getRoleBadgeClass(role) {
    switch (role) {
        case 'admin': return 'admin';
        case 'manager': return 'manager';
        default: return 'user';
    }
}

// Toast notification
let toastTimeout = null;
export function showToast(message, type = 'success') {
    let toast = document.getElementById('app-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'app-toast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    clearTimeout(toastTimeout);
    toast.className = `toast ${type}`;
    toast.textContent = message;
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });
    toastTimeout = setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Confirm dialog
export function showConfirm(title, message) {
    return new Promise((resolve) => {
        let overlay = document.getElementById('confirm-dialog');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'confirm-dialog';
            overlay.className = 'dialog-overlay';
            overlay.innerHTML = `
        <div class="dialog-box">
          <div class="dialog-title" id="dialog-title"></div>
          <div class="dialog-message" id="dialog-message"></div>
          <div class="dialog-actions">
            <button class="btn btn-ghost btn-sm" id="dialog-cancel">Hủy</button>
            <button class="btn btn-primary btn-sm" id="dialog-confirm">Xác nhận</button>
          </div>
        </div>
      `;
            document.body.appendChild(overlay);
        }
        document.getElementById('dialog-title').textContent = title;
        document.getElementById('dialog-message').textContent = message;

        const onConfirm = () => { cleanup(); resolve(true); };
        const onCancel = () => { cleanup(); resolve(false); };
        const cleanup = () => {
            overlay.classList.remove('show');
            document.getElementById('dialog-confirm').removeEventListener('click', onConfirm);
            document.getElementById('dialog-cancel').removeEventListener('click', onCancel);
        };

        document.getElementById('dialog-confirm').addEventListener('click', onConfirm);
        document.getElementById('dialog-cancel').addEventListener('click', onCancel);
        requestAnimationFrame(() => overlay.classList.add('show'));
    });
}

// Offline detection
export function setupOfflineDetection() {
    const bar = document.getElementById('offline-bar');
    if (!bar) return;
    const update = () => {
        if (navigator.onLine) {
            bar.classList.remove('show');
        } else {
            bar.classList.add('show');
        }
    };
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    update();
}

// Session helpers
export function getSession() {
    try {
        return JSON.parse(localStorage.getItem('pwa_user') || 'null');
    } catch { return null; }
}

export function setSession(user) {
    localStorage.setItem('pwa_user', JSON.stringify(user));
}

export function clearSession() {
    localStorage.removeItem('pwa_user');
}
