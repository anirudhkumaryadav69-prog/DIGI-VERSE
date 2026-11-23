import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Archive,
  ChevronLeft,
  ChevronRight,
  Edit3,
  EyeOff,
  Plus,
  Search,
  Send,
  Trash2,
} from 'lucide-react';
import SellerLayout from '../../layouts/SellerLayout';
import {
  Badge,
  ConfirmDialog,
  LoadingState,
  ToastBanner,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import { sellerApi } from '../../services/api';

const STATUS_BADGE = {
  published: { label: 'Published', variant: 'success' },
  pending_review: { label: 'Pending Review', variant: 'warning' },
  draft: { label: 'Draft', variant: 'neutral' },
  rejected: { label: 'Rejected', variant: 'danger' },
  archived: { label: 'Archived', variant: 'neutral' },
};

const SellerProductsPage = () => {
  const [data, setData] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState({ type: '', message: '' });
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [busyId, setBusyId] = useState('');

  const loadProducts = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 10 };
      if (search.trim()) params.search = search.trim();
      if (statusFilter) params.approval_status = statusFilter;
      const res = await sellerApi.listProducts(params);
      setData(res);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to load seller products.',
      });
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  const handleStatusAction = async (product, action, label) => {
    setBusyId(product.id);
    setToast({ type: '', message: '' });
    try {
      await sellerApi.changeProductStatus(product.id, action);
      setToast({ type: 'success', message: `"${product.name}" updated (${label}).` });
      loadProducts();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ type: 'error', message: typeof detail === 'string' ? detail : 'Action failed.' });
    } finally {
      setBusyId('');
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    setBusyId(confirmDelete.id);
    try {
      await sellerApi.deleteProduct(confirmDelete.id);
      setToast({ type: 'success', message: `Product "${confirmDelete.name}" deleted.` });
      setConfirmDelete(null);
      loadProducts();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not delete product.',
      });
    } finally {
      setBusyId('');
    }
  };

  return (
    <SellerLayout
      title="My Products"
      subtitle="Manage your digital product listings, review submissions, and asset status"
      actions={
        <Link to="/seller/products/new" className="dv-btn-primary px-4 py-2 text-xs inline-flex items-center gap-1.5">
          <Plus className="w-4 h-4" />
          <span>Add Product</span>
        </Link>
      }
    >
      <div className="space-y-5">
        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
        />

        <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-4 flex flex-col sm:flex-row gap-3 justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              aria-label="Search your products"
              placeholder="Search your products..."
              className="dv-input pl-10 pr-3.5 py-2 text-[13px]"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter products by approval status"
            className="dv-input text-xs sm:w-52"
          >
            <option value="">All Statuses</option>
            <option value="published">Published</option>
            <option value="pending_review">Pending Review</option>
            <option value="draft">Draft</option>
            <option value="rejected">Rejected</option>
            <option value="archived">Archived</option>
          </select>
        </div>

        <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl overflow-hidden shadow-xs">
          {loading ? (
            <LoadingState label="Loading your catalog..." />
          ) : !data.items.length ? (
            <div className="p-10 text-center space-y-3">
              <p className="text-sm font-semibold text-[#F1F5F9]">No seller products found</p>
              <p className="text-xs text-[#94A3B8]">
                Create your first digital asset listing and submit it for administrator approval.
              </p>
              <Link to="/seller/products/new" className="dv-btn-primary px-5 py-2.5 text-xs inline-block">
                Create Product
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-[#18243A] border-b border-[#E5E7EB] text-[#94A3B8] font-semibold text-[12px]">
                    <th className="py-3.5 px-4">Product</th>
                    <th className="py-3.5 px-4">Price</th>
                    <th className="py-3.5 px-4">Digital Asset</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB]">
                  {data.items.map((p) => {
                    const st = STATUS_BADGE[p.approval_status] || STATUS_BADGE.draft;
                    return (
                      <tr key={p.id} className="hover:bg-[#18243A]">
                        <td className="py-3.5 px-4">
                          <div className="min-w-0">
                            <p className="font-semibold text-[#F1F5F9]">{p.name}</p>
                            <p className="text-[11px] font-mono text-[#94A3B8]">{p.slug}</p>
                            {p.approval_status === 'rejected' && p.rejection_reason && (
                              <p className="text-[11px] text-red-300 mt-1">
                                Rejection reason: {p.rejection_reason}
                              </p>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 font-mono">
                          <span className="font-bold text-[#93C5FD]">{formatINR(p.effective_price)}</span>
                          {p.is_on_sale && (
                            <span className="text-[#94A3B8] line-through ml-1.5 text-[11px]">
                              {formatINR(p.original_price)}
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          <Badge variant={p.asset?.has_asset ? 'accent' : 'neutral'}>
                            {p.asset?.has_asset ? p.asset.filename : 'Missing File'}
                          </Badge>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex flex-col gap-1 items-start">
                            <Badge variant={st.variant}>{st.label}</Badge>
                            {p.approval_status === 'published' && !p.is_active && (
                              <span className="text-[11px] text-[#94A3B8]">Unpublished (hidden)</span>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="inline-flex items-center gap-1.5">
                            {(p.approval_status === 'draft' || p.approval_status === 'rejected') && (
                              <button
                                type="button"
                                disabled={busyId === p.id}
                                onClick={() =>
                                  handleStatusAction(p, 'submit_for_review', 'Submitted for Review')
                                }
                                title="Submit for Admin Review"
                                className="px-2.5 py-1.5 rounded-lg border border-[#BFDBFE] bg-[#18243A] text-[#93C5FD] hover:bg-[#0D1424] font-semibold inline-flex items-center gap-1"
                              >
                                <Send className="w-3 h-3" />
                                <span>Submit</span>
                              </button>
                            )}
                            {p.approval_status === 'published' && p.is_active && (
                              <button
                                type="button"
                                disabled={busyId === p.id}
                                onClick={() => handleStatusAction(p, 'unpublish', 'Unpublished')}
                                title="Unpublish listing"
                                className="p-1.5 rounded-lg border border-[#E5E7EB] bg-[#111C30] hover:border-[#93C5FD] text-[#F1F5F9]"
                              >
                                <EyeOff className="w-3.5 h-3.5" />
                              </button>
                            )}
                            {p.approval_status !== 'archived' && (
                              <button
                                type="button"
                                disabled={busyId === p.id}
                                onClick={() => handleStatusAction(p, 'archive', 'Archived')}
                                title="Archive product"
                                className="p-1.5 rounded-lg border border-[#E5E7EB] bg-[#111C30] hover:border-[#93C5FD] text-[#F1F5F9]"
                              >
                                <Archive className="w-3.5 h-3.5" />
                              </button>
                            )}
                            <Link
                              to={`/seller/products/${p.id}/edit`}
                              title="Edit Product & Assets"
                              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-[#111C30] hover:border-[#93C5FD] text-[#F1F5F9]"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </Link>
                            <button
                              type="button"
                              onClick={() => setConfirmDelete(p)}
                              title="Delete Product"
                              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-[#111C30] hover:border-red-400 text-red-300"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="p-4 border-t border-[#E5E7EB] bg-[#18243A] flex items-center justify-between text-xs text-[#94A3B8]">
            <span>
              Total: <strong className="text-[#F1F5F9]">{data.total}</strong> products
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-1.5 rounded-lg border border-[#E5E7EB] bg-[#111C30] disabled:opacity-40"
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
                className="p-1.5 rounded-lg border border-[#E5E7EB] bg-[#111C30] disabled:opacity-40"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(confirmDelete)}
        title="Delete Seller Product"
        description={`Delete "${confirmDelete?.name}"? Products referenced by paid orders cannot be deleted and should be archived instead.`}
        confirmLabel="Delete Product"
        variant="danger"
        busy={Boolean(busyId)}
        onCancel={() => setConfirmDelete(null)}
        onConfirm={handleDelete}
      />
    </SellerLayout>
  );
};

export default SellerProductsPage;
