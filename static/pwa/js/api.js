// API Service — Wraps fetch + session cookies
const API_BASE = '/api';

const api = {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    };
    if (config.body && typeof config.body === 'object') {
      config.body = JSON.stringify(config.body);
    }
    try {
      const res = await fetch(url, config);
      if (res.status === 401) {
        window.location.href = '/pwa/';
        return null;
      }
      const data = await res.json();
      return data;
    } catch (err) {
      console.error('API Error:', err);
      throw err;
    }
  },

  // Auth
  login(username, password) {
    return this.request('/login', {
      method: 'POST',
      body: { username, password },
    });
  },

  logout() {
    return this.request('/logout', { method: 'POST' });
  },

  // Statistics
  getStatistics(searchUser = '') {
    const params = searchUser ? `?search_user=${encodeURIComponent(searchUser)}` : '';
    return this.request(`/statistics${params}`);
  },

  // View Data
  getViewData({ page = 1, perPage = 10, searchUser, searchMaLo, searchTrangThai, searchTenKhachHang, searchNgayThu } = {}) {
    const params = new URLSearchParams();
    params.set('page', page);
    params.set('per_page', perPage);
    if (searchUser) params.set('search_user', searchUser);
    if (searchMaLo) params.set('search_ma_lo', searchMaLo);
    if (searchTrangThai) params.set('search_trang_thai', searchTrangThai);
    if (searchTenKhachHang) params.set('search_ten_khach_hang', searchTenKhachHang);
    if (searchNgayThu) params.set('search_ngay_thu', searchNgayThu);
    return this.request(`/data/view?${params.toString()}`);
  },

  // Mark as paid
  markAsPaid(id) {
    return fetch(`/mark_as_paid/${id}`, {
      method: 'POST',
      credentials: 'same-origin',
    }).then(r => r.json());
  },

  // Cancel mark as paid
  cancelMarkAsPaid(id) {
    return fetch(`/cancel_mark_as_paid/${id}`, {
      method: 'POST',
      credentials: 'same-origin',
    }).then(r => r.json());
  },

  // Check payment status
  checkPaymentStatus(invoiceId) {
    return this.request(`/invoice/check-payment-status/${invoiceId}`);
  },
};

export default api;
