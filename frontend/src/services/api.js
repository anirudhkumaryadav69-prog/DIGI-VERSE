import axios from 'axios';
import { validateApiResponse } from '../utils/apiValidation';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export function resolveApiAssetUrl(pathOrUrl) {
  if (!pathOrUrl) return '';
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  if (API_BASE_URL.startsWith('http')) {
    const origin = API_BASE_URL.replace(/\/api\/?$/, '');
    return `${origin}${pathOrUrl.startsWith('/') ? '' : '/'}${pathOrUrl}`;
  }
  return pathOrUrl;
}

// In-memory CSRF token holder (never stores JWT tokens in localStorage)
let csrfTokenMemory = null;

function readCookie(name) {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : null;
}

export function getCsrfToken() {
  return csrfTokenMemory || readCookie('dv_csrf_token');
}

export function setCsrfToken(token) {
  if (token) {
    csrfTokenMemory = token;
  }
}

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

api.interceptors.request.use(
  (config) => {
    const method = (config.method || 'get').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const csrf = getCsrfToken();
      if (csrf) {
        config.headers['X-CSRF-Token'] = csrf;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

let customerRefreshPromise = null;
let adminRefreshPromise = null;

api.interceptors.response.use(
  (response) => {
    validateApiResponse(response);
    const headerCsrf = response.headers?.['x-csrf-token'];
    const bodyCsrf = response.data?.csrf_token;
    if (headerCsrf || bodyCsrf) {
      setCsrfToken(headerCsrf || bodyCsrf);
    }
    return response;
  },
  async (error) => {
    const status = error.response?.status;
    const originalRequest = error.config || {};
    const reqUrl = originalRequest.url || '';

    const isAuthLifecycleEndpoint =
      reqUrl.includes('/auth/me') ||
      reqUrl.includes('/auth/refresh') ||
      reqUrl.includes('/admin/auth/me') ||
      reqUrl.includes('/admin/auth/refresh') ||
      reqUrl.includes('/login') ||
      reqUrl.includes('/register');

    if (status === 401 && !originalRequest._retry && !isAuthLifecycleEndpoint) {
      originalRequest._retry = true;
      const isAdminReq = reqUrl.startsWith('/admin');
      try {
        if (isAdminReq) {
          if (!adminRefreshPromise) {
            adminRefreshPromise = api.post('/admin/auth/refresh').finally(() => {
              adminRefreshPromise = null;
            });
          }
          await adminRefreshPromise;
        } else {
          if (!customerRefreshPromise) {
            customerRefreshPromise = api.post('/auth/refresh').finally(() => {
              customerRefreshPromise = null;
            });
          }
          await customerRefreshPromise;
        }
        return api(originalRequest);
      } catch {
        // Fall through to emit session-expired event
      }
    }

    if (
      status === 401 &&
      typeof window !== 'undefined' &&
      !reqUrl.includes('/auth/me') &&
      !reqUrl.includes('/admin/auth/me') &&
      !reqUrl.includes('/login')
    ) {
      window.dispatchEvent(new CustomEvent('digiverse:session-expired', { detail: { url: reqUrl } }));
    }
    return Promise.reject(error);
  }
);

export const checkBackendHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

// ---------------------------------------------------------------------------
// Customer Authentication & Profile API
// ---------------------------------------------------------------------------

export const customerAuthApi = {
  getCsrf: () => api.get('/auth/csrf').then((r) => r.data),
  register: (data) => api.post('/auth/register', data).then((r) => r.data),
  login: (data) => api.post('/auth/login', data).then((r) => r.data),
  refresh: () => api.post('/auth/refresh').then((r) => r.data),
  logout: () => api.post('/auth/logout').then((r) => r.data),
  logoutAll: () => api.post('/auth/logout-all').then((r) => r.data),
  getProfile: () => api.get('/auth/me').then((r) => r.data),
  updateProfile: (data) => api.patch('/auth/profile', data).then((r) => r.data),
  requestPhoneChange: (data) => api.post('/auth/phone/change', data).then((r) => r.data),
  sendOtp: () => api.post('/auth/otp/send').then((r) => r.data),
  verifyOtp: (data) => api.post('/auth/otp/verify', data).then((r) => r.data),
  forgotPassword: (data) => api.post('/auth/forgot-password', data).then((r) => r.data),
  resetPassword: (data) => api.post('/auth/reset-password', data).then((r) => r.data),
  changePassword: (data) => api.post('/auth/change-password', data).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Administrator Authentication & Portal API
// ---------------------------------------------------------------------------

export const adminAuthApi = {
  login: (data) => api.post('/admin/auth/login', data).then((r) => r.data),
  refresh: () => api.post('/admin/auth/refresh').then((r) => r.data),
  logout: () => api.post('/admin/auth/logout').then((r) => r.data),
  getMe: () => api.get('/admin/auth/me').then((r) => r.data),
  changePassword: (data) => api.post('/admin/auth/change-password', data).then((r) => r.data),
  getDashboardOverview: () => api.get('/admin/dashboard/overview').then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Administrator Catalog, Product, Image & Discount Management API
// ---------------------------------------------------------------------------

export const adminCatalogApi = {
  listCategories: (params) => api.get('/admin/categories', { params }).then((r) => r.data),
  getCategory: (id) => api.get(`/admin/categories/${id}`).then((r) => r.data),
  createCategory: (data) => api.post('/admin/categories', data).then((r) => r.data),
  updateCategory: (id, data) => api.patch(`/admin/categories/${id}`, data).then((r) => r.data),
  deleteCategory: (id) => api.delete(`/admin/categories/${id}`).then((r) => r.data),

  uploadStandaloneImage: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api
      .post('/admin/uploads/images', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },

  listProducts: (params) => api.get('/admin/products', { params }).then((r) => r.data),
  getProduct: (id) => api.get(`/admin/products/${id}`).then((r) => r.data),
  createProduct: (data) => api.post('/admin/products', data).then((r) => r.data),
  updateProduct: (id, data) => api.patch(`/admin/products/${id}`, data).then((r) => r.data),
  updateProductStatus: (id, is_active) =>
    api.patch(`/admin/products/${id}/status`, { is_active }).then((r) => r.data),
  deleteProduct: (id) => api.delete(`/admin/products/${id}`).then((r) => r.data),

  uploadProductImage: (productId, file, { display_order, is_primary } = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    if (display_order !== undefined && display_order !== null) {
      formData.append('display_order', String(display_order));
    }
    if (is_primary !== undefined) {
      formData.append('is_primary', String(Boolean(is_primary)));
    }
    return api
      .post(`/admin/products/${productId}/images`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
  updateProductImage: (productId, imageId, data) =>
    api.patch(`/admin/products/${productId}/images/${imageId}`, data).then((r) => r.data),
  replaceProductImage: (productId, imageId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api
      .put(`/admin/products/${productId}/images/${imageId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
  deleteProductImage: (productId, imageId) =>
    api.delete(`/admin/products/${productId}/images/${imageId}`).then((r) => r.data),

  createProductSale: (productId, data) =>
    api.post(`/admin/products/${productId}/sales`, data).then((r) => r.data),
  updateProductSale: (productId, saleId, data) =>
    api.patch(`/admin/products/${productId}/sales/${saleId}`, data).then((r) => r.data),

  uploadProductAsset: (productId, file, onUploadProgress) => {
    const formData = new FormData();
    formData.append('file', file);
    return api
      .post(`/admin/products/${productId}/asset`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
        onUploadProgress,
      })
      .then((r) => r.data);
  },
  deleteProductAsset: (productId) =>
    api.delete(`/admin/products/${productId}/asset`).then((r) => r.data),
  moderateProduct: (productId, action, reason) =>
    api.post(`/admin/products/${productId}/moderate`, { action, reason }).then((r) => r.data),
};

export const adminSellersApi = {
  listSellers: (params) => api.get('/admin/sellers', { params }).then((r) => r.data),
  getSeller: (id) => api.get(`/admin/sellers/${id}`).then((r) => r.data),
  reviewSeller: (id, action, reason) =>
    api.post(`/admin/sellers/${id}/review`, { action, reason }).then((r) => r.data),
};

export const adminFinancialApi = {
  getCommission: () => api.get('/admin/financial/commission').then((r) => r.data),
  updateCommission: (data) => api.put('/admin/financial/commission', data).then((r) => r.data),
  listSellerCommissions: (params) =>
    api.get('/admin/financial/sellers', { params }).then((r) => r.data),
  getSellerCommission: (sellerId) =>
    api.get(`/admin/financial/sellers/${sellerId}/commission`).then((r) => r.data),
  updateSellerCommission: (sellerId, data) =>
    api.put(`/admin/financial/sellers/${sellerId}/commission`, data).then((r) => r.data),
  removeSellerCommission: (sellerId, reason) =>
    api
      .delete(`/admin/financial/sellers/${sellerId}/commission`, {
        params: reason ? { reason } : undefined,
      })
      .then((r) => r.data),
  getLedger: (params) => api.get('/admin/financial/ledger', { params }).then((r) => r.data),
  getCommissionReport: (params) =>
    api.get('/admin/financial/commission/report', { params }).then((r) => r.data),
};

export const sellerPayoutApi = {
  getBalance: () => api.get('/seller/payouts/balance').then((r) => r.data),
  listAccounts: () => api.get('/seller/payouts/accounts').then((r) => r.data),
  createAccount: (data) => api.post('/seller/payouts/accounts', data).then((r) => r.data),
  updateAccount: (accountId, data) =>
    api.patch(`/seller/payouts/accounts/${accountId}`, data).then((r) => r.data),
  setDefaultAccount: (accountId) =>
    api.post(`/seller/payouts/accounts/${accountId}/default`).then((r) => r.data),
  deactivateAccount: (accountId) =>
    api.delete(`/seller/payouts/accounts/${accountId}`).then((r) => r.data),
  createRequest: (data) => api.post('/seller/payouts/requests', data).then((r) => r.data),
  listRequests: (params) =>
    api.get('/seller/payouts/requests', { params }).then((r) => r.data),
  getRequest: (payoutId) =>
    api.get(`/seller/payouts/requests/${payoutId}`).then((r) => r.data),
  getAttempts: (payoutId) =>
    api.get(`/seller/payouts/requests/${payoutId}/attempts`).then((r) => r.data),
  cancelRequest: (payoutId, data) =>
    api.post(`/seller/payouts/requests/${payoutId}/cancel`, data).then((r) => r.data),
};

export const adminPayoutApi = {
  listRequests: (params) => api.get('/admin/payouts', { params }).then((r) => r.data),
  getDetail: (payoutId) => api.get(`/admin/payouts/${payoutId}/detail`).then((r) => r.data),
  getRequest: (payoutId) =>
    api.get(`/admin/payouts/${payoutId}`).then((r) => r.data),
  reviewRequest: (payoutId, data) =>
    api.post(`/admin/payouts/${payoutId}/review`, data).then((r) => r.data),
  approveRequest: (payoutId, data) =>
    api.post(`/admin/payouts/${payoutId}/approve`, data).then((r) => r.data),
  rejectRequest: (payoutId, data) =>
    api.post(`/admin/payouts/${payoutId}/reject`, data).then((r) => r.data),
  executeRequest: (payoutId, data) =>
    api.post(`/admin/payouts/${payoutId}/execute`, data).then((r) => r.data),
  retryRequest: (payoutId, data) =>
    api.post(`/admin/payouts/${payoutId}/retry`, data).then((r) => r.data),
  reconcileRequest: (payoutId, data) =>
    api.post(`/admin/payouts/${payoutId}/reconcile`, data).then((r) => r.data),
  listAttempts: (payoutId) =>
    api.get(`/admin/payouts/${payoutId}/attempts`).then((r) => r.data),
  listReconciliation: (params) =>
    api.get('/admin/payouts/reconciliation', { params }).then((r) => r.data),
  getReconciliationSummary: (params) =>
    api.get('/admin/payouts/reconciliation/summary', { params }).then((r) => r.data),
  getReconciliationDetail: (payoutId) =>
    api.get(`/admin/payouts/${payoutId}/reconciliation`).then((r) => r.data),
  resolveReconciliation: (payoutId, data) =>
    api.post(`/admin/payouts/${payoutId}/reconciliation/resolve`, data).then((r) => r.data),
  getReport: (params) => api.get('/admin/payouts/reports', { params }).then((r) => r.data),
};

export const adminPayoutAccountApi = {
  listVerification: (params) =>
    api.get('/admin/payout-accounts/verification', { params }).then((r) => r.data),
  getAccount: (accountId) =>
    api.get(`/admin/payout-accounts/${accountId}`).then((r) => r.data),
  approveAccount: (accountId, data) =>
    api.post(`/admin/payout-accounts/${accountId}/approve`, data).then((r) => r.data),
  rejectAccount: (accountId, data) =>
    api.post(`/admin/payout-accounts/${accountId}/reject`, data).then((r) => r.data),
  getHistory: (accountId, params) =>
    api.get(`/admin/payout-accounts/${accountId}/history`, { params }).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Administrator Order Management API
// ---------------------------------------------------------------------------

export const adminOrdersApi = {
  getStatistics: () => api.get('/admin/orders/statistics').then((r) => r.data),
  listOrders: (params) => api.get('/admin/orders', { params }).then((r) => r.data),
  getOrder: (orderId) => api.get(`/admin/orders/${orderId}`).then((r) => r.data),
  updateOrderStatus: (orderId, status) =>
    api.patch(`/admin/orders/${orderId}/status`, { status }).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Administrator Operations, Marketing Automation, Content & Store Settings API
// ---------------------------------------------------------------------------

export const adminOperationsApi = {
  getAnalytics: (params) => api.get('/admin/dashboard/analytics', { params }).then((r) => r.data),

  listCustomers: (params) => api.get('/admin/customers', { params }).then((r) => r.data),
  updateCustomerStatus: (customerId, account_status) =>
    api.patch(`/admin/customers/${customerId}/status`, { account_status }).then((r) => r.data),

  listBanners: () => api.get('/admin/banners').then((r) => r.data),
  createBanner: (data) => api.post('/admin/banners', data).then((r) => r.data),
  updateBanner: (bannerId, data) =>
    api.patch(`/admin/banners/${bannerId}`, data).then((r) => r.data),
  deleteBanner: (bannerId) => api.delete(`/admin/banners/${bannerId}`).then((r) => r.data),

  listVideos: () => api.get('/admin/videos').then((r) => r.data),
  createVideo: (data) => api.post('/admin/videos', data).then((r) => r.data),
  updateVideo: (videoId, data) => api.patch(`/admin/videos/${videoId}`, data).then((r) => r.data),
  deleteVideo: (videoId) => api.delete(`/admin/videos/${videoId}`).then((r) => r.data),

  listTemplates: (params) => api.get('/admin/templates', { params }).then((r) => r.data),
  createTemplate: (data) => api.post('/admin/templates', data).then((r) => r.data),
  updateTemplate: (templateId, data) =>
    api.patch(`/admin/templates/${templateId}`, data).then((r) => r.data),
  deleteTemplate: (templateId) => api.delete(`/admin/templates/${templateId}`).then((r) => r.data),

  listEmailCampaigns: () => api.get('/admin/campaigns/email').then((r) => r.data),
  createEmailCampaign: (data) => api.post('/admin/campaigns/email', data).then((r) => r.data),
  launchEmailCampaign: (campaignId) =>
    api.post(`/admin/campaigns/email/${campaignId}/launch`).then((r) => r.data),

  listWhatsAppCampaigns: () => api.get('/admin/campaigns/whatsapp').then((r) => r.data),
  createWhatsAppCampaign: (data) =>
    api.post('/admin/campaigns/whatsapp', data).then((r) => r.data),
  launchWhatsAppCampaign: (campaignId) =>
    api.post(`/admin/campaigns/whatsapp/${campaignId}/launch`).then((r) => r.data),

  scheduleCampaign: (channel, campaignId, scheduledFor = null) =>
    api
      .post(`/admin/campaigns/${channel}/${campaignId}/schedule`, scheduledFor ? { scheduled_for: scheduledFor } : undefined)
      .then((r) => r.data),
  queueCampaign: (channel, campaignId) =>
    api.post(`/admin/campaigns/${channel}/${campaignId}/queue`).then((r) => r.data),
  cancelCampaign: (channel, campaignId) =>
    api.post(`/admin/campaigns/${channel}/${campaignId}/cancel`).then((r) => r.data),
  getCampaignDetail: (channel, campaignId) =>
    api.get(`/admin/campaigns/${channel}/${campaignId}`).then((r) => r.data),
  getMarketingWorkerStatus: () =>
    api.get('/admin/marketing/worker-status').then((r) => r.data),

  listSettings: () => api.get('/admin/settings').then((r) => r.data),
  upsertSetting: (key, value) => api.put('/admin/settings', { key, value }).then((r) => r.data),
  batchUpdateSettings: (settings) =>
    api.patch('/admin/settings/batch', { settings }).then((r) => r.data),

  listAuditLogs: (params) => api.get('/admin/audit-logs', { params }).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Public Customer-Facing Catalog API
// ---------------------------------------------------------------------------

export const publicCatalogApi = {
  listCategories: (params) => api.get('/categories', { params }).then((r) => r.data),
  getCategoryBySlug: (slug) => api.get(`/categories/${slug}`).then((r) => r.data),
  listProducts: (params) => api.get('/products', { params }).then((r) => r.data),
  getProductBySlug: (slug) => api.get(`/products/${slug}`).then((r) => r.data),
  listStores: (params) => api.get('/stores', { params }).then((r) => r.data),
  getStoreBySlug: (storeSlug, params) =>
    api.get(`/stores/${storeSlug}`, { params }).then((r) => r.data),
  listBanners: () => api.get('/banners').then((r) => r.data),
  listVideos: (params) => api.get('/videos', { params }).then((r) => r.data),
  getPublicSettings: () => api.get('/settings/public').then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Multi-Vendor Seller Onboarding & Store Management API
// ---------------------------------------------------------------------------

export const sellerApi = {
  getApplication: () => api.get('/seller/application').then((r) => r.data),
  submitApplication: (data) => api.post('/seller/application', data).then((r) => r.data),
  uploadBrandingImage: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api
      .post('/seller/branding-image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },

  getOverview: () => api.get('/seller/overview').then((r) => r.data),
  getAnalytics: () => api.get('/seller/analytics').then((r) => r.data),
  getFinancialSummary: (params) =>
    api.get('/seller/financial/summary', { params }).then((r) => r.data),
  getFinancialTransactions: (params) =>
    api.get('/seller/financial/transactions', { params }).then((r) => r.data),
  getFinancialOrders: (params) =>
    api.get('/seller/financial/orders', { params }).then((r) => r.data),
  getFinancialOrderItems: (params) =>
    api.get('/seller/financial/order-items', { params }).then((r) => r.data),
  getProfile: () => api.get('/seller/profile').then((r) => r.data),
  updateProfile: (data) => api.patch('/seller/profile', data).then((r) => r.data),

  listProducts: (params) => api.get('/seller/products', { params }).then((r) => r.data),
  getProduct: (id) => api.get(`/seller/products/${id}`).then((r) => r.data),
  createProduct: (data) => api.post('/seller/products', data).then((r) => r.data),
  updateProduct: (id, data) => api.patch(`/seller/products/${id}`, data).then((r) => r.data),
  changeProductStatus: (id, action) =>
    api.patch(`/seller/products/${id}/status`, { action }).then((r) => r.data),
  deleteProduct: (id) => api.delete(`/seller/products/${id}`).then((r) => r.data),

  uploadProductImage: (productId, file, { display_order, is_primary } = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    if (display_order !== undefined && display_order !== null) {
      formData.append('display_order', String(display_order));
    }
    if (is_primary !== undefined) {
      formData.append('is_primary', String(Boolean(is_primary)));
    }
    return api
      .post(`/seller/products/${productId}/images`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
  updateProductImage: (productId, imageId, data) =>
    api.patch(`/seller/products/${productId}/images/${imageId}`, data).then((r) => r.data),
  replaceProductImage: (productId, imageId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api
      .put(`/seller/products/${productId}/images/${imageId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
  deleteProductImage: (productId, imageId) =>
    api.delete(`/seller/products/${productId}/images/${imageId}`).then((r) => r.data),

  uploadProductAsset: (productId, file, onUploadProgress) => {
    const formData = new FormData();
    formData.append('file', file);
    return api
      .post(`/seller/products/${productId}/asset`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
        onUploadProgress,
      })
      .then((r) => r.data);
  },
  deleteProductAsset: (productId) =>
    api.delete(`/seller/products/${productId}/asset`).then((r) => r.data),

  createProductSale: (productId, data) =>
    api.post(`/seller/products/${productId}/sales`, data).then((r) => r.data),
  updateProductSale: (productId, saleId, data) =>
    api.patch(`/seller/products/${productId}/sales/${saleId}`, data).then((r) => r.data),

  listOrders: (params) => api.get('/seller/orders', { params }).then((r) => r.data),
  getOrder: (orderId) => api.get(`/seller/orders/${orderId}`).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Customer Wishlist, Shopping Cart, Checkout, Payments, Orders & Downloads API
// ---------------------------------------------------------------------------

export const commerceApi = {
  getWishlist: () => api.get('/wishlist').then((r) => r.data),
  addToWishlist: (productId) => api.post(`/wishlist/${productId}`).then((r) => r.data),
  removeFromWishlist: (productId) => api.delete(`/wishlist/${productId}`).then((r) => r.data),
  clearWishlist: () => api.delete('/wishlist').then((r) => r.data),

  getCart: () => api.get('/cart').then((r) => r.data),
  addToCart: (productId, quantity = 1) =>
    api.post('/cart/items', { product_id: productId, quantity }).then((r) => r.data),
  updateCartItem: (itemId, quantity) =>
    api.patch(`/cart/items/${itemId}`, { quantity }).then((r) => r.data),
  removeCartItem: (itemId) => api.delete(`/cart/items/${itemId}`).then((r) => r.data),
  clearCart: () => api.delete('/cart').then((r) => r.data),

  checkout: (idempotencyKey) =>
    api
      .post('/checkout', idempotencyKey ? { idempotency_key: idempotencyKey } : {})
      .then((r) => r.data),
  verifyPayment: (data) => api.post('/payments/verify', data).then((r) => r.data),

  listOrders: (params) => api.get('/orders', { params }).then((r) => r.data),
  getOrder: (orderId) => api.get(`/orders/${orderId}`).then((r) => r.data),
  getOrderInvoice: (orderId) => api.get(`/orders/${orderId}/invoice`).then((r) => r.data),
  retryOrderPayment: (orderId) =>
    api.post(`/orders/${orderId}/retry-payment`).then((r) => r.data),

  listDownloads: () => api.get('/downloads').then((r) => r.data),
  requestDownload: (orderItemId) => api.post(`/downloads/${orderItemId}`).then((r) => r.data),
  getDownloadStatus: (downloadId) => api.get(`/downloads/${downloadId}/status`).then((r) => r.data),
  downloadAssetFile: async (downloadUrl, { fallbackFilename = 'digiverse-asset', onProgress } = {}) => {
    const resolvedUrl = resolveApiAssetUrl(downloadUrl);
    let response = await fetch(resolvedUrl, { method: 'GET', credentials: 'include' });
    if (response.status === 401) {
      await api.post('/auth/refresh');
      response = await fetch(resolvedUrl, { method: 'GET', credentials: 'include' });
    }
    if (!response.ok) {
      let detail = 'Digital asset download failed.';
      try {
        const errBody = await response.json();
        if (typeof errBody?.detail === 'string') {
          detail = errBody.detail;
        }
      } catch {
        // Non-JSON error response
      }
      const err = new Error(detail);
      err.status = response.status;
      throw err;
    }

    const disposition = response.headers.get('content-disposition') || '';
    const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
    const filename = (filenameMatch?.[1] || fallbackFilename || 'digiverse-asset').trim();

    const contentLen = Number(response.headers.get('content-length') || 0);
    const contentType = response.headers.get('content-type') || 'application/octet-stream';
    let blob;

    if (response.body && typeof response.body.getReader === 'function') {
      const reader = response.body.getReader();
      const chunks = [];
      let loaded = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) {
          chunks.push(value);
          loaded += value.byteLength;
          if (typeof onProgress === 'function') {
            const percent = contentLen > 0 ? Math.min(100, Math.round((loaded / contentLen) * 100)) : null;
            onProgress({ loaded, total: contentLen || null, percent });
          }
        }
      }
      blob = new Blob(chunks, { type: contentType });
    } else {
      blob = await response.blob();
    }

    const objectUrl = URL.createObjectURL(blob);
    try {
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = filename;
      anchor.rel = 'noopener';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } finally {
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    }
    return { filename, size: blob.size };
  },
};

export default api;
