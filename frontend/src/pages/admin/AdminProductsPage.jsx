import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckCircle2,
  Edit3,
  Package,
  Plus,
  Power,
  Search,
  Trash2,
  XCircle,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  LoadingState,
  Pagination,
  ToastBanner,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import { AdminReasonModal, AdminStatusBadge } from '../../components/admin/AdminPrimitives';
import { adminCatalogApi } from '../../services/api';
import { resolveProductThumbnailUrl } from '../../utils/productThumbnails';

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
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [rejectTarget, setRejectTarget] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [moderating, setModerating] = useState(false);

  useEffect(() => {
    adminCatalogApi
      .listCategories({ page: 1, page_size: 100 })
      .then((res) => setCategories(res.items || []))
      .catch(() => {});
  }, []);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError('');
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
      setError(typeof detail === 'string' ? detail : 'Failed to load products.');
    } finally {
      setLoading(false);
    }
  }, [page, search, categoryFilter, statusFilter, ownerFilter, approvalFilter]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const handleModerate = async (prod, action, reason = null) => {
    setModerating(true);
    setToast(null);
    try {
      await adminCatalogApi.moderateProduct(prod.id, action, reason ? reason.trim() : null);
      setToast({ type: 'success', message: `Product "${prod.name}" (${action}) updated.` });
      setRejectTarget(null);
      setRejectReason('');
      fetchProducts();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Moderation failed.',
      });
    } finally {
      setModerating(false);
    }
  };

  const handleToggleStatus = async (product) => {
    setToast(null);
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
    setToast(null);
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

  return (
    <AdminLayout
      title="Products & Discounts"
      subtitle="Manage digital assets, pricing, media galleries, private download links, and active sales"
      actions={
        <Link
          to="/admin/products/new"
          className="dv-btn-primary text-[12px] font-semibold px-4 py-2 inline-flex items-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Product</span>
        </Link>
      }
    >
      {error && <ErrorAlert message={error} onRetry={fetchProducts} className="mb-5" />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-5" />

      {/* Search & Filters */}
      <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-4 mb-5 grid grid-cols-1 md:grid-cols-6 gap-3 shadow-2xs">
        <div className="relative md:col-span-2">
          <label htmlFor="admin-products-search" className="sr-only">
            Search products
          </label>
          <Search
            className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2"
            aria-hidden="true"
          />
          <input
            id="admin-products-search"
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search products by name, slug, or summary..."
            className="dv-input pl-10 pr-4 py-2 text-[13px]"
          />
        </div>

        <select
          aria-label="Filter by category"
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input px-3.5 py-2 text-[13px]"
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
          className="dv-input px-3.5 py-2 text-[13px]"
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
          className="dv-input px-3.5 py-2 text-[13px]"
        >
          <option value="">All Moderation States</option>
          <option value="pending_review">Pending Review</option>
          <option value="published">Published</option>
          <option value="draft">Draft</option>
          <option value="rejected">Rejected</option>
          <option value="archived">Archived</option>
        </select>

        <select
          aria-label="Filter by active status"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input px-3.5 py-2 text-[13px]"
        >
          <option value="all">All Active States</option>
          <option value="active">Active Only</option>
          <option value="inactive">Inactive Only</option>
        </select>
      </div>

      {/* Products Table */}
      <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
        {loading ? (
          <LoadingState label="Loading products..." />
        ) : data.items.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={Package}
              title="No products found"
              description="No digital products matched your current filter settings."
              action={
                <Link
                  to="/admin/products/new"
                  className="dv-btn-primary text-[12px] font-semibold px-4 py-2 inline-flex items-center gap-1.5"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Product</span>
                </Link>
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#D5DEE8] bg-[#18243A] text-[#CBD5E1] text-[11.5px] font-semibold">
                  <th className="py-3 px-4">Product &amp; Owner</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Pricing</th>
                  <th className="py-3 px-4">Digital Asset</th>
                  <th className="py-3 px-4">Status &amp; Review</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                {data.items.map((prod) => (
                  <tr key={prod.id} className="hover:bg-[#18243A]/70 transition">
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-3">
                        <img
                          src={resolveProductThumbnailUrl(prod, prod.image_url, 0)}
                          alt={prod.name}
                          loading="lazy"
                          className="w-14 h-9 rounded-lg object-cover border border-[#D5DEE8] shrink-0 bg-[#18243A]"
                        />
                        <div className="min-w-0">
                          <p className="font-semibold text-[#F1F5F9] truncate max-w-[260px]">
                            {prod.name}
                          </p>
                          <p className="text-[11.5px] font-mono text-[#94A3B8] truncate max-w-[260px]">
                            {prod.slug}
                          </p>
                          <span className="inline-block mt-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#18243A] border border-[#BFDBFE] text-[#93C5FD]">
                            {prod.seller?.store_name
                              ? `Seller: ${prod.seller.store_name}`
                              : 'DIGI-VERSE Official'}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-[#F1F5F9] whitespace-nowrap">
                      {prod.category?.name || 'Uncategorized'}
                    </td>
                    <td className="py-3.5 px-4 font-mono tabular-nums whitespace-nowrap">
                      {prod.is_on_sale ? (
                        <div>
                          <span className="text-[#93C5FD] font-bold">
                            {formatINR(prod.effective_price)}
                          </span>
                          <span className="line-through text-[#94A3B8] text-[11.5px] ml-2">
                            {formatINR(prod.original_price)}
                          </span>
                          <span className="block text-[11px] text-emerald-300 font-sans font-medium mt-0.5">
                            -{Math.round(Number(prod.active_discount?.discount_percentage || 0))}%
                            Live Sale
                          </span>
                        </div>
                      ) : (
                        <span className="text-[#F1F5F9] font-semibold">
                          {formatINR(prod.original_price)}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <AdminStatusBadge
                        status={
                          prod.asset?.has_asset || prod.private_download_url
                            ? 'processing'
                            : 'neutral'
                        }
                        label={
                          prod.asset?.has_asset
                            ? 'File Uploaded'
                            : prod.private_download_url
                            ? 'Configured'
                            : 'Missing'
                        }
                      />
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-col gap-1 items-start">
                        <AdminStatusBadge status={prod.is_active ? 'active' : 'inactive'} />
                        <AdminStatusBadge status={prod.approval_status} />
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        {prod.approval_status === 'pending_review' && (
                          <>
                            <button
                              type="button"
                              disabled={moderating}
                              onClick={() => handleModerate(prod, 'approve')}
                              title="Approve & Publish Product"
                              aria-label={`Approve ${prod.name}`}
                              className="p-1.5 rounded-lg border border-emerald-200 bg-emerald-950/50 text-emerald-300 hover:bg-emerald-950/80 transition disabled:opacity-45"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              disabled={moderating}
                              onClick={() => {
                                setRejectReason('');
                                setRejectTarget(prod);
                              }}
                              title="Reject Product Submission"
                              aria-label={`Reject ${prod.name}`}
                              className="p-1.5 rounded-lg border border-red-200 bg-red-950/50 text-red-300 hover:bg-red-950/80 transition disabled:opacity-45"
                            >
                              <XCircle className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(prod)}
                          className="p-1.5 rounded-lg border border-[#D5DEE8] bg-[#111C30] hover:border-[#93C5FD] hover:bg-[#18243A] hover:text-[#60A5FA] text-[#F1F5F9] transition"
                          title={prod.is_active ? 'Deactivate Product' : 'Activate Product'}
                          aria-label={prod.is_active ? `Deactivate ${prod.name}` : `Activate ${prod.name}`}
                        >
                          <Power className="w-3.5 h-3.5" />
                        </button>
                        <Link
                          to={`/admin/products/${prod.id}/edit`}
                          className="p-1.5 rounded-lg border border-[#D5DEE8] bg-[#111C30] hover:border-[#93C5FD] hover:bg-[#18243A] hover:text-[#60A5FA] text-[#F1F5F9] transition"
                          title="Edit Product, Images & Discounts"
                          aria-label={`Edit ${prod.name}`}
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </Link>
                        <button
                          type="button"
                          onClick={() => setConfirmDelete(prod)}
                          className="p-1.5 rounded-lg border border-[#D5DEE8] bg-[#111C30] hover:border-red-300 hover:bg-red-950/60 text-red-300 transition"
                          title="Delete Product"
                          aria-label={`Delete ${prod.name}`}
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
      </div>

      <Pagination
        page={data.page}
        totalPages={data.total_pages}
        totalItems={data.total}
        itemLabel="products"
        onPageChange={(nextPage) => setPage(nextPage)}
      />

      {/* Styled Rejection Reason Modal */}
      <AdminReasonModal
        open={Boolean(rejectTarget)}
        title={`Reject "${rejectTarget?.name || ''}"`}
        description="Provide a clear reason for rejecting this product submission. The seller will see this feedback."
        label="Rejection reason *"
        placeholder="e.g. Digital asset archive is missing documentation or preview images..."
        value={rejectReason}
        onChange={setRejectReason}
        confirmLabel="Confirm Rejection"
        variant="danger"
        busy={moderating}
        onConfirm={() => rejectTarget && handleModerate(rejectTarget, 'reject', rejectReason)}
        onClose={() => setRejectTarget(null)}
      />

      {/* Destructive Delete Safeguard Dialog */}
      <ConfirmDialog
        open={Boolean(confirmDelete)}
        title={`Delete "${confirmDelete?.name}"?`}
        description="Products referenced by historical customer orders are protected from deletion and should be deactivated instead."
        confirmLabel={deleting ? 'Deleting...' : 'Delete Product'}
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(null)}
      />
    </AdminLayout>
  );
};

export default AdminProductsPage;
