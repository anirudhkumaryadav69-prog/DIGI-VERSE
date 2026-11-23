import { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Search,
  ShieldAlert,
  Store,
  XCircle,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import AdminLayout from '../../layouts/AdminLayout';
import {
  EmptyState,
  ErrorAlert,
  LoadingState,
  Pagination,
  ToastBanner,
} from '../../components/common/StorefrontDesignSystem';
import { AdminReasonModal, AdminStatusBadge } from '../../components/admin/AdminPrimitives';
import { adminSellersApi } from '../../services/api';

const AdminSellersPage = () => {
  const [data, setData] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [modalAction, setModalAction] = useState(null);
  const [reasonInput, setReasonInput] = useState('');
  const [busy, setBusy] = useState(false);

  const loadSellers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = { page, page_size: 12 };
      if (search.trim()) params.search = search.trim();
      if (statusFilter) params.status = statusFilter;
      const res = await adminSellersApi.listSellers(params);
      setData(res);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to load sellers.');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter]);

  useEffect(() => {
    loadSellers();
  }, [loadSellers]);

  const executeReview = async (seller, action, reason = null) => {
    setBusy(true);
    setToast(null);
    try {
      await adminSellersApi.reviewSeller(seller.id, action, reason);
      setToast({
        type: 'success',
        message: `Seller "${seller.store_name}" updated (${action}).`,
      });
      setModalAction(null);
      setReasonInput('');
      loadSellers();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Seller moderation failed.',
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <AdminLayout
      title="Seller Management & Onboarding"
      subtitle="Review creator storefront applications, suspend non-compliant accounts, and reinstate verified sellers"
    >
      <div className="space-y-5">
        {error && <ErrorAlert message={error} onRetry={loadSellers} />}
        <ToastBanner toast={toast} onDismiss={() => setToast(null)} />

        <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-4 flex flex-col sm:flex-row gap-3 justify-between shadow-2xs">
          <div className="relative flex-1 max-w-md">
            <label htmlFor="admin-sellers-search" className="sr-only">
              Search sellers
            </label>
            <Search
              className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2"
              aria-hidden="true"
            />
            <input
              id="admin-sellers-search"
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search store name, slug, email..."
              className="dv-input pl-10 pr-3.5 py-2 text-[13px]"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter sellers by status"
            className="dv-input px-3.5 py-2 text-[13px] sm:w-52"
          >
            <option value="">All Seller Statuses</option>
            <option value="pending">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="suspended">Suspended</option>
          </select>
        </div>

        <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
          {loading ? (
            <LoadingState label="Loading seller applications..." />
          ) : !data.items.length ? (
            <div className="p-6">
              <EmptyState
                icon={Store}
                title="No seller profiles found"
                description="No storefront profiles matched the current search or status filter."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#18243A] border-b border-[#D5DEE8] text-[11.5px] font-semibold text-[#CBD5E1]">
                    <th className="py-3 px-4">Storefront &amp; Owner</th>
                    <th className="py-3 px-4">Business &amp; Country</th>
                    <th className="py-3 px-4">Catalog</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                  {data.items.map((s) => (
                    <tr key={s.id} className="hover:bg-[#18243A]/70 transition">
                      <td className="py-3.5 px-4">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-[#F1F5F9]">{s.store_name}</span>
                            {s.application_status === 'approved' && (
                              <Link
                                to={`/store/${s.store_slug}`}
                                title="Open public storefront"
                                className="text-[#60A5FA] hover:text-[#93C5FD] inline-flex items-center"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                              </Link>
                            )}
                          </div>
                          <p className="text-[11.5px] font-mono text-[#94A3B8]">/{s.store_slug}</p>
                          <p className="text-[12px] text-[#94A3B8]">
                            {s.seller_display_name} · {s.customer_email || s.contact_email}
                          </p>
                          {s.application_description && (
                            <p className="text-[12px] text-[#CBD5E1] line-clamp-2 max-w-md pt-1">
                              {s.application_description}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <p className="text-[#F1F5F9] font-medium">{s.business_type}</p>
                        <p className="text-[12px] text-[#94A3B8]">{s.country}</p>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[12.5px] tabular-nums text-[#F1F5F9]">
                        {s.published_product_count} live / {s.product_count} total
                      </td>
                      <td className="py-3.5 px-4">
                        <AdminStatusBadge status={s.application_status} />
                        {s.rejection_reason && (
                          <p className="text-[11px] text-red-300 mt-1 max-w-44">
                            {s.rejection_reason}
                          </p>
                        )}
                        {s.suspension_reason && (
                          <p className="text-[11px] text-[#94A3B8] mt-1 max-w-44">
                            {s.suspension_reason}
                          </p>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          {(s.application_status === 'pending' ||
                            s.application_status === 'rejected') && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => executeReview(s, 'approve')}
                              className="px-2.5 py-1.5 rounded-lg bg-[#16A34A] text-white hover:bg-[#15803D] text-[12px] font-semibold inline-flex items-center gap-1 transition disabled:opacity-50"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Approve</span>
                            </button>
                          )}
                          {s.application_status === 'pending' && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => {
                                setReasonInput('');
                                setModalAction({ seller: s, action: 'reject' });
                              }}
                              className="px-2.5 py-1.5 rounded-lg bg-[#111C30] border border-red-200 text-red-300 hover:bg-red-950/60 text-[12px] font-medium inline-flex items-center gap-1 transition disabled:opacity-50"
                            >
                              <XCircle className="w-3.5 h-3.5" />
                              <span>Reject</span>
                            </button>
                          )}
                          {s.application_status === 'approved' && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => {
                                setReasonInput('');
                                setModalAction({ seller: s, action: 'suspend' });
                              }}
                              className="px-2.5 py-1.5 rounded-lg bg-[#111C30] border border-red-200 text-red-300 hover:bg-red-950/60 text-[12px] font-medium inline-flex items-center gap-1 transition disabled:opacity-50"
                            >
                              <ShieldAlert className="w-3.5 h-3.5" />
                              <span>Suspend</span>
                            </button>
                          )}
                          {s.application_status === 'suspended' && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => executeReview(s, 'reinstate')}
                              className="px-2.5 py-1.5 rounded-lg bg-[#2563EB] text-white hover:bg-[#1D4ED8] text-[12px] font-semibold inline-flex items-center gap-1 transition disabled:opacity-50"
                            >
                              <RefreshCw className="w-3.5 h-3.5" />
                              <span>Reinstate</span>
                            </button>
                          )}
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
          itemLabel="sellers"
          onPageChange={(nextPage) => setPage(nextPage)}
        />
      </div>

      <AdminReasonModal
        open={Boolean(modalAction)}
        title={
          modalAction
            ? `${modalAction.action === 'reject' ? 'Reject' : 'Suspend'} "${modalAction.seller.store_name}"`
            : ''
        }
        description="Provide a clear administrative reason. This decision is recorded in the audit trail and shown to the seller."
        label="Moderation reason"
        placeholder={`Enter ${modalAction?.action || ''} reason...`}
        value={reasonInput}
        onChange={setReasonInput}
        confirmLabel={`Confirm ${modalAction?.action || ''}`}
        variant="danger"
        busy={busy}
        onConfirm={() =>
          executeReview(modalAction.seller, modalAction.action, reasonInput.trim())
        }
        onClose={() => setModalAction(null)}
      />
    </AdminLayout>
  );
};

export default AdminSellersPage;
