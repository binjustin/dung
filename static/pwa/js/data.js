import api from './api.js';
import {
    formatCurrency, formatNumber, formatDateTime,
    getSession, clearSession, getRoleText, getRoleBadgeClass,
    setupOfflineDetection, showToast, showConfirm
} from './utils.js';

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
overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
});

// Logout
document.getElementById('logout-btn').addEventListener('click', async () => {
    const yes = await showConfirm('Đăng xuất', 'Bạn có chắc chắn muốn đăng xuất?');
    if (yes) {
        try { await api.logout(); } catch { }
        clearSession();
        window.location.href = '/pwa/';
    }
});

// Filters toggle
const filtersPanel = document.getElementById('filters-panel');
document.getElementById('toggle-filters-btn').addEventListener('click', () => {
    filtersPanel.classList.toggle('hidden');
});

// State
let currentPage = 1;
const perPage = 15;

// Load data
async function loadData() {
    const list = document.getElementById('invoice-list');
    list.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

    try {
        const params = {
            page: currentPage,
            perPage,
            searchTenKhachHang: document.getElementById('filter-name').value.trim(),
            searchMaLo: document.getElementById('filter-ma-lo').value,
            searchTrangThai: document.getElementById('filter-status').value,
            searchNgayThu: document.getElementById('filter-date').value,
        };

        const filterUser = document.getElementById('filter-user');
        if (filterUser.style.display !== 'none' && filterUser.value) {
            params.searchUser = filterUser.value;
        }

        const res = await api.getViewData(params);
        if (!res || !res.success) {
            list.innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>Lỗi tải dữ liệu</h3></div>';
            return;
        }

        const { items, pagination, summary, filters, users } = res.data;

        // Update summary
        document.getElementById('summary-count').textContent = formatNumber(summary.total_invoices);
        document.getElementById('summary-amount').textContent = formatCurrency(summary.total_amount);

        // Populate filter dropdowns (first load)
        populateFilters(filters, users);

        // Render items
        if (!items || items.length === 0) {
            list.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <h3>Không có dữ liệu</h3>
          <p>Thử thay đổi bộ lọc tìm kiếm</p>
        </div>`;
        } else {
            list.innerHTML = items.map((item, i) => renderInvoiceItem(item, i)).join('');
            // Attach action handlers
            list.querySelectorAll('[data-action]').forEach(btn => {
                btn.addEventListener('click', handleAction);
            });
        }

        // Pagination
        renderPagination(pagination);
    } catch (err) {
        console.error('Load data error:', err);
        list.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><h3>Không thể kết nối máy chủ</h3></div>';
    }
}

function renderInvoiceItem(item, index) {
    const isPaid = item.trang_thai === 'Đã thanh toán';
    const statusClass = isPaid ? 'paid' : 'unpaid';
    const statusText = isPaid ? '✓ Đã thu' : '⏳ Chưa thu';

    let actionBtn = '';
    if (isPaid) {
        actionBtn = `<button class="btn btn-danger btn-sm" data-action="cancel" data-id="${item.id}">Hủy gạch nợ</button>`;
    } else {
        actionBtn = `<button class="btn btn-success btn-sm" data-action="pay" data-id="${item.id}">Gạch nợ</button>`;
    }

    return `
    <div class="invoice-item" style="animation-delay: ${index * 0.03}s">
      <div class="invoice-item-header">
        <div class="invoice-customer">${item.ten_khach_hang}</div>
        <span class="invoice-status ${statusClass}">${statusText}</span>
      </div>
      <div class="invoice-details">
        <div>
          <div class="invoice-detail-label">Mã KH</div>
          <div>${item.ma_khach_hang}</div>
        </div>
        <div>
          <div class="invoice-detail-label">Mã lộ</div>
          <div>${item.ma_lo}</div>
        </div>
        <div>
          <div class="invoice-detail-label">Điện năng</div>
          <div>${formatNumber(item.kwh)} kWh</div>
        </div>
        <div>
          <div class="invoice-detail-label">Ngày thu</div>
          <div>${formatDateTime(item.ngay_thu)}</div>
        </div>
      </div>
      ${item.dia_chi ? `<div style="font-size:0.78rem; color:var(--text-muted); margin-top:6px;">📍 ${item.dia_chi}</div>` : ''}
      <div class="invoice-amount">
        <span>${formatCurrency(item.tong_tien)}</span>
        <div class="invoice-actions">${actionBtn}</div>
      </div>
    </div>`;
}

let filtersPopulated = false;
function populateFilters(filters, users) {
    if (filtersPopulated) return;
    filtersPopulated = true;

    // Ma Lo
    const maLoSelect = document.getElementById('filter-ma-lo');
    if (filters && filters.ma_lo_list) {
        filters.ma_lo_list.forEach(ml => {
            const opt = document.createElement('option');
            opt.value = ml;
            opt.textContent = ml;
            maLoSelect.appendChild(opt);
        });
    }

    // Users (for admin/manager)
    if (users && users.length > 1) {
        const userSelect = document.getElementById('filter-user');
        userSelect.style.display = '';
        users.forEach(u => {
            const opt = document.createElement('option');
            opt.value = u.username;
            const prefix = u.role === 'manager' ? '👤 ' : '  └ ';
            opt.textContent = prefix + u.username;
            userSelect.appendChild(opt);
        });
    }
}

function renderPagination(pagination) {
    const container = document.getElementById('pagination');
    if (!pagination || pagination.total_pages <= 1) {
        container.innerHTML = '';
        return;
    }

    const { current_page, total_pages } = pagination;
    let html = '';

    // Prev
    html += `<button class="pagination-btn" ${current_page <= 1 ? 'disabled' : ''} data-page="${current_page - 1}">‹</button>`;

    // Page numbers
    const maxVisible = 5;
    let start = Math.max(1, current_page - Math.floor(maxVisible / 2));
    let end = Math.min(total_pages, start + maxVisible - 1);
    if (end - start < maxVisible - 1) start = Math.max(1, end - maxVisible + 1);

    if (start > 1) {
        html += `<button class="pagination-btn" data-page="1">1</button>`;
        if (start > 2) html += `<span class="pagination-info">…</span>`;
    }

    for (let i = start; i <= end; i++) {
        html += `<button class="pagination-btn ${i === current_page ? 'active' : ''}" data-page="${i}">${i}</button>`;
    }

    if (end < total_pages) {
        if (end < total_pages - 1) html += `<span class="pagination-info">…</span>`;
        html += `<button class="pagination-btn" data-page="${total_pages}">${total_pages}</button>`;
    }

    // Next
    html += `<button class="pagination-btn" ${current_page >= total_pages ? 'disabled' : ''} data-page="${current_page + 1}">›</button>`;

    container.innerHTML = html;

    // Event listeners
    container.querySelectorAll('[data-page]').forEach(btn => {
        btn.addEventListener('click', () => {
            currentPage = parseInt(btn.dataset.page);
            loadData();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
}

// Action handlers (mark paid / cancel)
async function handleAction(e) {
    const btn = e.currentTarget;
    const action = btn.dataset.action;
    const id = parseInt(btn.dataset.id);

    if (action === 'pay') {
        const yes = await showConfirm('Xác nhận gạch nợ', 'Đánh dấu hóa đơn này là đã thanh toán?');
        if (!yes) return;
        btn.disabled = true;
        btn.textContent = '...';
        try {
            const res = await api.markAsPaid(id);
            if (res.success) {
                showToast('Đã gạch nợ thành công', 'success');
                loadData();
            } else {
                showToast(res.message || 'Lỗi', 'error');
                btn.disabled = false;
                btn.textContent = 'Gạch nợ';
            }
        } catch {
            showToast('Không thể kết nối', 'error');
            btn.disabled = false;
            btn.textContent = 'Gạch nợ';
        }
    } else if (action === 'cancel') {
        const yes = await showConfirm('Hủy gạch nợ', 'Bạn muốn hủy thanh toán hóa đơn này?');
        if (!yes) return;
        btn.disabled = true;
        btn.textContent = '...';
        try {
            const res = await api.cancelMarkAsPaid(id);
            if (res.success) {
                showToast('Đã hủy gạch nợ', 'success');
                loadData();
            } else {
                showToast(res.message || 'Lỗi', 'error');
                btn.disabled = false;
                btn.textContent = 'Hủy gạch nợ';
            }
        } catch {
            showToast('Không thể kết nối', 'error');
            btn.disabled = false;
            btn.textContent = 'Hủy gạch nợ';
        }
    }
}

// Filter handlers
document.getElementById('apply-filters').addEventListener('click', () => {
    currentPage = 1;
    filtersPopulated = false; // Allow filter refresh
    loadData();
});

document.getElementById('clear-filters').addEventListener('click', () => {
    document.getElementById('filter-name').value = '';
    document.getElementById('filter-ma-lo').value = '';
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-date').value = '';
    document.getElementById('filter-user').value = '';
    currentPage = 1;
    filtersPopulated = false;
    loadData();
});

// Search on Enter key
document.getElementById('filter-name').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        currentPage = 1;
        filtersPopulated = false;
        loadData();
    }
});

// Initial load
loadData();
