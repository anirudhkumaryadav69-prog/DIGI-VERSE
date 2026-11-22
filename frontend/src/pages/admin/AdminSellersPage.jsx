import { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  RefreshCw,
  Search,
  ShieldAlert,
  Store,
  XCircle,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import AdminLayout from '../../layouts/AdminLayout';
import { adminSellersApi } from '../../services/api';

const STATUS_STYLES = {
  pending: 'bg-[#FFF2E6] text-[#D94300] border-[#FFD4AE]',
  approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  rejected: 'bg-red-50 text-red-700 border-red-200',
  suspended: 'bg-slate-100 text-slate-700 border-slate-300',
};

const AdminSellersPage = () => {
  const [data, setData] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState({ type: '', message: '' });
  const [modalAction, setModalAction] = useState(null); // { seller, action }
  const [reasonInput, setReasonInput] = useState('');
  const [busy, setBusy] = useState(false);

  const loadSellers = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 12 };
      if (search.trim()) params.search = search.trim();
      if (statusFilter) params.status = statusFilter;
      const res = await adminSellersApi.listSellers(params);
      setData(res);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to load sellers.',
      });
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter]);

  useEffect(() => {
    loadSellers();
  }, [loadSellers]);

  const executeReview = async (seller, action, reason = null) => {
    setBusy(true);
    setToast({ type: '', message: '' });
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
        {toast.message && (
          <div
            className={`px-4 py-3 rounded-xl border text-xs font-medium flex items-center justify-between ${
              toast.type === 'error'
                ? 'bg-red-50 border-red-200 text-red-700'
                : 'bg-emerald-50 border-emerald-200 text-emerald-700'
            }`}
          >
            <span>{toast.message}</span>
            <button type="button" onClick={() => setToast({ type: '', message: '' })} className="underline">
              Dismiss
            </button>
          </div>
        )}

        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4 flex flex-col sm:flex-row gap-3 justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-[#8490A0] absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search store name, slug, email..."
              className="dv-input pl-10 text-sm"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter sellers by status"
            className="dv-input text-xs sm:w-52"
          >
            <option value="">All Seller Statuses</option>
            <option value="pending">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="suspended">Suspended</option>
          </select>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-2xl overflow-hidden shadow-xs">
          {loading ? (
            <div className="p-10 text-center text-xs text-[#64748B]">Loading seller applications...</div>
          ) : !data.items.length ? (
            <div className="p-10 text-center space-y-2">
              <Store className="w-7 h-7 text-[#FF6B0A] mx-auto" />
              <p className="text-sm font-semibold text-[#1F2937]">No seller profiles found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-[#FFF6ED] border-b border-[#E5E7EB] text-[10px] uppercase tracking-wider text-[#64748B]">
                    <th className="py-3.5 px-4">Storefront & Owner</th>
                    <th className="py-3.5 px-4">Business & Country</th>
                    <th className="py-3.5 px-4">Products</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB]">
                  {data.items.map((s) => (
                    <tr key={s.id} className="hover:bg-[#FFFAF5]">
                      <td className="py-3.5 px-4">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-[#1F2937]">{s.store_name}</span>
                            {s.application_status === 'approved' && (
                              <Link
                                to={`/store/${s.store_slug}`}
                                className="text-[#FF6B0A] hover:underline inline-flex items-center gap-0.5 text-[11px]"
                              >
                                <ExternalLink className="w-3 h-3" />
                              </Link>
                            )}
                          </div>
                          <p className="text-[11px] font-mono text-[#64748B]">/{s.store_slug}</p>
                          <p className="text-[11px] text-[#64748B]">
                            {s.seller_display_name} · {s.customer_email || s.contact_email}
                          </p>
                          {s.application_description && (
                            <p className="text-[11px] text-[#243247] line-clamp-2 max-w-md pt-1">
                              {s.application_description}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <p className="text-[#1F2937] font-medium">{s.business_type}</p>
                        <p className="text-[11px] text-[#64748B]">{s.country}</p>
                      </td>
                      <td className="py-3.5 px-4 font-mono">
                        {s.published_product_count} live / {s.product_count} total
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-block text-[10px] uppercase tracking-wider px-2.5 py-0.5 rounded-full border font-semibold ${
                            STATUS_STYLES[s.application_status] || ''
                          }`}
                        >
                          {s.application_status}
                        </span>
                        {s.rejection_reason && (
                          <p className="text-[10px] text-red-600 mt-1 max-w-44">
                            {s.rejection_reason}
                          </p>
                        )}
                        {s.suspension_reason && (
                          <p className="text-[10px] text-slate-600 mt-1 max-w-44">
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
                              className="px-2.5 py-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 font-semibold inline-flex items-center gap-1"
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
                              className="px-2.5 py-1.5 rounded-lg bg-white border border-red-300 text-red-700 hover:bg-red-50 font-semibold inline-flex items-center gap-1"
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
                              className="px-2.5 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 font-semibold inline-flex items-center gap-1"
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
                              className="px-2.5 py-1.5 rounded-lg bg-[#FF6B0A] text-white hover:bg-[#D94300] font-semibold inline-flex items-center gap-1"
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

          <div className="p-4 border-t border-[#E5E7EB] bg-[#FFF6ED] flex items-center justify-between text-xs text-[#64748B]">
            <span>
              Total: <strong className="text-[#1F2937]">{data.total}</strong> seller profiles
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white disabled:opacity-40"
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
                className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white disabled:opacity-40"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {modalAction && (
        <div className="fixed inset-0 z-50 bg-[#1F2937]/30 backdrop-blur-[2px] flex items-center justify-center p-4">
          <div className="bg-white border border-[#FFD4AE] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-lg">
            <h3 className="text-base font-bold text-[#1F2937] capitalize">
              {modalAction.action} "{modalAction.seller.store_name}"
            </h3>
            <p className="text-xs text-[#64748B]">
              Provide a clear administrative reason. This is logged in the audit trail and shown to the seller.
            </p>
            <textarea
              rows={3}
              required
              value={reasonInput}
              onChange={(e) => setReasonInput(e.target.value)}
              placeholder={`Enter ${modalAction.action} reason...`}
              className="dv-input text-sm"
            />
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setModalAction(null)}
                className="dv-btn-secondary px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy || !reasonInput.trim()}
                onClick={() => executeReview(modalAction.seller, modalAction.action, reasonInput.trim())}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-red-600 text-white hover:bg-red-700 disabled:opacity-40 capitalize"
              >
                Confirm {modalAction.action}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
};

export default AdminSellersPage;
