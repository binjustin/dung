import api from './api.js';
import { formatCurrency, formatNumber, getSession, clearSession, getRoleText, getRoleBadgeClass, setupOfflineDetection, showConfirm } from './utils.js';

setupOfflineDetection();

// Auth check
const user = getSession();
if (!user) window.location.href = '/pwa/';

// Populate sidebar
document.getElementById('sidebar-name').textContent = user.full_name || user.username;
document.getElementById('sidebar-username').textContent = `@${user.username}`;
const roleBadge = document.getElementById('sidebar-role-badge');
roleBadge.textContent = getRoleText(user.role);
roleBadge.className = `role-badge ${getRoleBadgeClass(user.role)}`;

// Sidebar toggle
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('sidebar-overlay');
document.getElementById('menu-btn').addEventListener('click', () => {
    sidebar.classList.add('open');
    overlay.classList.add('open');
});
overlay.addEventListener('click', closeSidebar);
function closeSidebar() {
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
}

// Logout
document.getElementById('logout-btn').addEventListener('click', async () => {
    const yes = await showConfirm('Đăng xuất', 'Bạn có chắc chắn muốn đăng xuất?');
    if (yes) {
        try { await api.logout(); } catch { }
        clearSession();
        window.location.href = '/pwa/';
    }
});

// Load stats
async function loadStats() {
    try {
        const res = await api.getStatistics();
        if (!res || !res.success) return;
        const s = res.statistics;

        document.getElementById('stat-total-invoices').textContent = formatNumber(s.total_invoices);
        document.getElementById('stat-total-money').textContent = formatCurrency(s.total_money);
        document.getElementById('stat-paid-invoices').textContent = formatNumber(s.total_paid_invoices);
        document.getElementById('stat-unpaid-invoices').textContent = formatNumber(s.total_unpaid_invoices);
        document.getElementById('stat-paid-money').textContent = formatCurrency(s.total_paid);
        document.getElementById('stat-unpaid-money').textContent = formatCurrency(s.total_unpaid);

        // Ma Lo stats
        const maLoList = document.getElementById('ma-lo-stats-list');
        const maLoStats = s.ma_lo_stats;
        if (!maLoStats || Object.keys(maLoStats).length === 0) {
            maLoList.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📊</div>
          <h3>Chưa có dữ liệu</h3>
        </div>`;
            return;
        }

        maLoList.innerHTML = Object.entries(maLoStats)
            .sort((a, b) => b[1].total - a[1].total)
            .map(([maLo, stat]) => {
                const paidPct = stat.total > 0 ? Math.round((stat.paid / stat.total) * 100) : 0;
                return `
          <div class="card" style="margin-bottom: 10px; padding: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <span style="font-weight: 700; font-size: 0.95rem;">${maLo}</span>
              <span style="font-size: 0.78rem; color: var(--text-secondary);">${stat.count} HĐ</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 8px;">
              <span style="color: var(--text-secondary);">Tổng: <strong style="color: var(--accent-amber-light);">${formatCurrency(stat.total)}</strong></span>
              <span style="color: var(--text-secondary);">Thu: <strong style="color: var(--accent-green-light);">${formatCurrency(stat.paid)}</strong></span>
            </div>
            <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;">
              <div style="width: ${paidPct}%; height: 100%; background: linear-gradient(90deg, var(--accent-green), var(--accent-green-light)); border-radius: 3px; transition: width 0.6s ease;"></div>
            </div>
            <div style="text-align: right; font-size: 0.72rem; color: var(--text-muted); margin-top: 4px;">${paidPct}% đã thu</div>
          </div>`;
            }).join('');
    } catch (err) {
        console.error('Load stats error:', err);
    }
}

// Refresh
document.getElementById('refresh-btn').addEventListener('click', loadStats);

loadStats();
