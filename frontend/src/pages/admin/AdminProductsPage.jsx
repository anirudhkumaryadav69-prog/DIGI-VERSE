import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Plus,
  Search,
  Edit3,
  Trash2,
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Power,
  XCircle,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import { adminCatalogApi } from '../../services/api';

const AdminProductsPage = () => {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [ownerFilter, setOwnerFilter] = useState('');
  const [approvalFilter, setApprovalFilter] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState({ type: '', message: '' });
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    adminCatalogApi
      .listCategories({ page: 1, page_size: 100 })
      .then((res) => setCategories(res.items || []))
      .catch(() => {});
  }, []);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 10 };
      if (search.trim()) params.search = search.trim();
      if (categoryFilter) params.category_id = categoryFilter;
      if (statusFilter === 'active') params.is_active = true;
      if (statusFilter === 'inactive') params.is_active = false;
      if (ownerFilter) params.owner_type = ownerFilter;
      if (approvalFilter) params.approval_status = approvalFilter;
      const res = await adminCatalogApi.listProducts(params);
      setData(res);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to load products.',
      });
    } finally {
      setLoading(false);
    }
  }, [page, search, categoryFilter, statusFilter, ownerFilter, approvalFilter]);

  const handleModerate = async (prod, action) => {
    let reason = null;
    if (action === 'reject') {
      reason = window.prompt(`Enter rejection reason for "${prod.name}":`);
      if (!reason || !reason.trim()) return;
    }
    setToast({ type: '', message: '' });
    try {
      await adminCatalogApi.moderateProduct(prod.id, action, reason ? reason.trim() : null);
      setToast({ type: 'success', message: `Product "${prod.name}" (${action}) updated.` });
      fetchProducts();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ type: 'error', message: typeof detail === 'string' ? detail : 'Moderation failed.' });
    }
  };

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const handleToggleStatus = async (product) => {
    setToast({ type: '', message: '' });
    try {
      await adminCatalogApi.updateProductStatus(product.id, !product.is_active);
      setToast({
        type: 'success',
        message: `"${product.name}" marked as ${!product.is_active ? 'Active' : 'Inactive'}.`,
      });
      fetchProducts();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Status update failed.',
      });
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    setDeleting(true);
    setToast({ type: '', message: '' });
    try {
      await adminCatalogApi.deleteProduct(confirmDelete.id);
      setToast({ type: 'success', message: `Product "${confirmDelete.name}" deleted.` });
      setConfirmDelete(null);
      fetchProducts();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Product could not be deleted.',
      });
      setConfirmDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const formatINR = (v) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(v || 0));

  return (
    <AdminLayout
      title="Products & Discounts"
      subtitle="Manage digital assets, pricing, media galleries, private download links, and active sales"
      actions={
        <Link
          to="/admin/products/new"
          className="dv-btn-primary text-xs font-semibold uppercase tracking-wider px-4 py-2.5 flex items-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Product</span>
        </Link>
      }
    >
      {toast.message && (
        <div
          className={`mb-6 p-4 rounded-xl border text-xs flex items-center gap-2.5 ${
            toast.type === 'error'
              ? 'bg-red-50 border-red-200 text-red-700'
              : 'bg-emerald-50 border-emerald-200 text-emerald-800'
          }`}
        >
          {toast.type === 'error' ? (
            <AlertCircle className="w-4 h-4 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Search & Filters */}
      <div className="dv-card p-4 mb-6 grid grid-cols-1 md:grid-cols-6 gap-3">
        <div className="relative md:col-span-2">
          <Search className="w-4 h-4 text-[#8490A0] absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search products by name, slug, or summary..."
            className="dv-input pl-10 pr-4 py-2 text-xs"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input px-3.5 py-2 text-xs"
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <select
          value={ownerFilter}
          onChange={(e) => {
            setOwnerFilter(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by product owner"
          className="dv-input px-3.5 py-2 text-xs"
        >
          <option value="">All Owners</option>
          <option value="platform">Platform Owned</option>
          <option value="seller">Seller Owned</option>
        </select>

        <select
          value={approvalFilter}
          onChange={(e) => {
            setApprovalFilter(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by approval status"
          className="dv-input px-3.5 py-2 text-xs"
        >
          <option value="">All Moderation States</option>
          <option value="pending_review">Pending Review</option>
          <option value="published">Published</option>
          <option value="draft">Draft</option>
          <option value="rejected">Rejected</option>
          <option value="archived">Archived</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input px-3.5 py-2 text-xs"
        >
          <option value="all">All Active States</option>
          <option value="active">Active Only</option>
          <option value="inactive">Inactive Only</option>
        </select>
      </div>

      {/* Products Table */}
      <div className="dv-card overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-xs text-[#64748B] uppercase tracking-widest">
            Loading Products...
          </div>
        ) : data.items.length === 0 ? (
          <div className="p-10 text-center space-y-3">
            <p className="text-xs text-[#64748B]">No products found.</p>
            <Link
              to="/admin/products/new"
              className="inline-block text-xs font-semibold text-[#FF6B0A] hover:underline"
            >
              + Add your first digital product
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#E5E7EB] bg-[#FFF6ED] text-[#64748B] uppercase">
                  <th className="py-3 px-4">Product &amp; Owner</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Pricing</th>
                  <th className="py-3 px-4">Digital Asset</th>
                  <th className="py-3 px-4">Status &amp; Review</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB]">
                {data.items.map((prod) => (
                  <tr key={prod.id} className="hover:bg-[#FFF0E2]/45 transition">
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-3">
                        {prod.image_url ? (
                          <img
                            src={prod.image_url}
                            alt={prod.name}
                            className="w-10 h-10 rounded-lg object-cover border border-[#E5E7EB] shrink-0"
                          />
                        ) : (
                          <div className="w-10 h-10 rounded-lg bg-[#FFF6ED] border border-[#E5E7EB] flex items-center justify-center text-[10px] text-[#8490A0] shrink-0">
                            IMG
                          </div>
                        )}
                        <div className="min-w-0">
                          <p className="font-semibold text-[#1F2937] truncate">{prod.name}</p>
                          <p className="text-[11px] font-mono text-[#64748B] truncate">
                            {prod.slug}
                          </p>
                          <span className="inline-block mt-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#FFF6ED] border border-[#FFD4AE] text-[#D94300]">
                            {prod.seller?.store_name ? `Seller: ${prod.seller.store_name}` : 'Platform Owned'}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-[#243247]">
                      {prod.category?.name || 'Uncategorized'}
                    </td>
                    <td className="py-3.5 px-4 font-mono">
                      {prod.is_on_sale ? (
                        <div>
                          <span className="text-[#F4510B] font-bold">
                            {formatINR(prod.effective_price)}
                          </span>
                          <span className="line-through text-[#8490A0] text-[11px] ml-2">
                            {formatINR(prod.original_price)}
                          </span>
                          <span className="block text-[10px] text-emerald-700 font-medium">
                            -{prod.active_discount?.discount_percentage}% Live Sale
                          </span>
                        </div>
                      ) : (
                        <span className="text-[#1F2937] font-semibold">
                          {formatINR(prod.original_price)}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`text-[10px] uppercase tracking-wider rounded-full px-2.5 py-0.5 border font-medium ${
                          prod.asset?.has_asset || prod.private_download_url
                            ? 'bg-[#FFF2E6] text-[#D94300] border-[#FFD4AE]'
                            : 'bg-slate-100 text-[#64748B] border-[#E5E7EB]'
                        }`}
                      >
                        {prod.asset?.has_asset
                          ? 'File Uploaded'
                          : prod.private_download_url
                          ? 'Configured'
                          : 'Missing'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-col gap-1 items-start">
                        <span
                          className={`text-[10px] uppercase tracking-wider rounded-full px-2.5 py-0.5 border font-medium ${
                            prod.is_active
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : 'bg-slate-100 text-[#64748B] border-[#E5E7EB]'
                          }`}
                        >
                          {prod.is_active ? 'Active' : 'Inactive'}
                        </span>
                        <span className="text-[10px] uppercase tracking-wider text-[#64748B] font-semibold">
                          {prod.approval_status}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        {prod.approval_status === 'pending_review' && (
                          <>
                            <button
                              type="button"
                              onClick={() => handleModerate(prod, 'approve')}
                              title="Approve & Publish Product"
                              className="p-1.5 rounded-lg border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleModerate(prod, 'reject')}
                              title="Reject Product Submission"
                              className="p-1.5 rounded-lg border border-red-300 bg-red-50 text-red-700 hover:bg-red-100 transition"
                            >
                              <XCircle className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(prod)}
                          className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-[#FFD4AE] hover:text-[#FF6B0A] text-[#243247] transition"
                          title={prod.is_active ? 'Deactivate Product' : 'Activate Product'}
                        >
                          <Power className="w-3.5 h-3.5" />
                        </button>
                        <Link
                          to={`/admin/products/${prod.id}/edit`}
                          className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-[#FFD4AE] hover:text-[#FF6B0A] text-[#243247] transition"
                          title="Edit Product, Images & Discounts"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </Link>
                        <button
                          type="button"
                          onClick={() => setConfirmDelete(prod)}
                          className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-red-400 hover:bg-red-50 text-red-600 transition"
                          title="Delete Product"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="p-4 border-t border-[#E5E7EB] bg-[#FFF6ED] flex items-center justify-between text-xs text-[#64748B]">
          <span>
            Total: <strong className="text-[#1F2937]">{data.total}</strong> products
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white disabled:opacity-40 hover:border-[#FFD4AE] text-[#243247]"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span>
              Page {data.page} of {data.total_pages}
            </span>
            <button
              type="button"
              disabled={page >= data.total_pages}
              onClick={() => setPage((p) => p + 1)}
              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white disabled:opacity-40 hover:border-[#FFD4AE] text-[#243247]"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 bg-[#1F2937]/30 backdrop-blur-[2px] flex items-center justify-center p-4">
          <div className="bg-white border border-[#FFD4AE] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-lg">
            <h3 className="text-base font-semibold text-[#1F2937]">Delete Product</h3>
            <p className="text-xs text-[#64748B] leading-relaxed">
              Are you sure you want to delete{' '}
              <strong className="text-[#1F2937]">{confirmDelete.name}</strong>? Products referenced
              by historical customer orders are protected from deletion and should be deactivated
              instead.
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                className="dv-btn-secondary px-4 py-2 text-xs font-semibold uppercase tracking-wider"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={handleDelete}
                className="px-4 py-2 rounded-xl text-xs font-semibold uppercase tracking-wider bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? 'Deleting...' : 'Delete Product'}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
};

export default AdminProductsPage;
