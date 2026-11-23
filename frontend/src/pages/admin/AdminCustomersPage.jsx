import { useEffect, useState } from 'react';
import { Search, ShieldAlert, UserCheck, Users } from 'lucide-react';
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
import { AdminStatusBadge } from '../../components/admin/AdminPrimitives';
import { adminOperationsApi } from '../../services/api';

const AdminCustomersPage = () => {
  const [customers, setCustomers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [actionBusy, setActionBusy] = useState(null);
  const [confirmSuspend, setConfirmSuspend] = useState(null);

  const loadCustomers = (targetPage = page) => {
    setLoading(true);
    const params = { page: targetPage, page_size: 20 };
    if (search.trim()) params.search = search.trim();
    if (statusFilter) params.account_status = statusFilter;

    adminOperationsApi
      .listCustomers(params)
      .then((res) => {
        setCustomers(res.items || []);
        setTotal(res.total || 0);
        setPage(res.page || 1);
        setTotalPages(res.total_pages || 1);
        setError('');
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load customer accounts.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadCustomers(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  const handleSearch = (e) => {
    e.preventDefault();
    loadCustomers(1);
  };

  const handleStatusChange = async (customer, newStatus) => {
    setActionBusy(customer.id);
    setToast(null);
    try {
      const updated = await adminOperationsApi.updateCustomerStatus(customer.id, newStatus);
      setCustomers((prev) => prev.map((c) => (c.id === customer.id ? updated : c)));
      setToast({
        type: 'success',
        message: `Account "${customer.full_name}" marked ${newStatus}.`,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update customer status.');
    } finally {
      setActionBusy(null);
      setConfirmSuspend(null);
    }
  };

  return (
    <AdminLayout
      title="Customer Accounts"
      subtitle={`Manage ${total} registered customer profiles, marketing consents, and account statuses`}
    >
      {error && <ErrorAlert message={error} onRetry={() => loadCustomers(page)} className="mb-5" />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-5" />

      {/* Search & Status Filter */}
      <form
        onSubmit={handleSearch}
        className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-4 mb-5 flex flex-wrap items-center gap-3 shadow-2xs"
      >
        <div className="relative flex-1 min-w-[220px]">
          <label htmlFor="admin-customers-search" className="sr-only">
            Search customers
          </label>
          <Search
            className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2"
            aria-hidden="true"
          />
          <input
            id="admin-customers-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by full name, email, or phone number..."
            className="dv-input pl-10 pr-4 py-2 text-[13px]"
          />
        </div>

        <select
          aria-label="Filter customers by status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="dv-input w-auto px-3.5 py-2 text-[13px]"
        >
          <option value="">All Account Statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="deactivated">Deactivated</option>
        </select>

        <button
          type="submit"
          className="dv-btn-primary text-[12px] font-semibold px-5 py-2"
        >
          Apply Filter
        </button>
      </form>

      {/* Customer Directory Table */}
      <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
        {loading ? (
          <LoadingState label="Loading customer accounts..." />
        ) : customers.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={Users}
              title="No matching customers"
              description="No registered customer profiles matched the current filter."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#D5DEE8] text-[#CBD5E1] bg-[#18243A] text-[11.5px] font-semibold">
                  <th className="py-3 px-4">Customer</th>
                  <th className="py-3 px-4">Verification</th>
                  <th className="py-3 px-4">Marketing Opt-In</th>
                  <th className="py-3 px-4">Orders &amp; Spend</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                {customers.map((c) => (
                  <tr key={c.id} className="hover:bg-[#18243A]/70 transition">
                    <td className="py-3.5 px-4">
                      <p className="font-semibold text-[#F1F5F9]">{c.full_name}</p>
                      <p className="text-[12px] text-[#94A3B8]">{c.email}</p>
                      {c.phone_number && (
                        <p className="text-[11.5px] font-mono text-[#94A3B8]">{c.phone_number}</p>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <AdminStatusBadge
                        status={c.is_phone_verified ? 'verified' : 'pending'}
                        label={c.is_phone_verified ? 'Phone Verified' : 'Unverified'}
                      />
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-wrap gap-1.5">
                        <AdminStatusBadge
                          status={c.email_marketing_consent ? 'processing' : 'neutral'}
                          label={`Email: ${c.email_marketing_consent ? 'Yes' : 'No'}`}
                        />
                        <AdminStatusBadge
                          status={c.whatsapp_marketing_consent ? 'verified' : 'neutral'}
                          label={`WhatsApp: ${c.whatsapp_marketing_consent ? 'Yes' : 'No'}`}
                        />
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <p className="text-[#F1F5F9] font-semibold font-mono tabular-nums">
                        {formatINR(c.total_spent)}
                      </p>
                      <p className="text-[11.5px] text-[#94A3B8] tabular-nums">
                        {c.order_count} orders
                      </p>
                    </td>
                    <td className="py-3.5 px-4">
                      <AdminStatusBadge status={c.account_status} />
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      {c.account_status === 'active' ? (
                        <button
                          type="button"
                          disabled={actionBusy === c.id}
                          onClick={() => setConfirmSuspend(c)}
                          className="inline-flex items-center gap-1.5 rounded-lg text-[12px] font-medium px-3 py-1.5 border border-red-200 bg-[#111C30] text-red-300 hover:bg-red-950/60 transition disabled:opacity-50"
                        >
                          <ShieldAlert className="w-3.5 h-3.5" />
                          <span>Suspend</span>
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={actionBusy === c.id}
                          onClick={() => handleStatusChange(c, 'active')}
                          className="inline-flex items-center gap-1.5 rounded-lg text-[12px] font-medium px-3 py-1.5 border border-emerald-200 bg-[#111C30] text-emerald-300 hover:bg-emerald-950/60 transition disabled:opacity-50"
                        >
                          <UserCheck className="w-3.5 h-3.5" />
                          <span>Reactivate</span>
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Pagination
        page={page}
        totalPages={totalPages}
        totalItems={total}
        itemLabel="customers"
        onPageChange={(nextPage) => loadCustomers(nextPage)}
      />

      <ConfirmDialog
        open={Boolean(confirmSuspend)}
        title={`Suspend account "${confirmSuspend?.full_name}"?`}
        description="Suspended customers cannot sign in, purchase digital assets, or generate download tokens until reactivated."
        confirmLabel="Suspend Account"
        variant="danger"
        onConfirm={() => confirmSuspend && handleStatusChange(confirmSuspend, 'suspended')}
        onCancel={() => setConfirmSuspend(null)}
      />
    </AdminLayout>
  );
};

export default AdminCustomersPage;
