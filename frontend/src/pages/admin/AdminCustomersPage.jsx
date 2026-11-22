import { useEffect, useState } from 'react';
import { Search, UserCheck, UserX, ShieldAlert } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
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
  const [actionBusy, setActionBusy] = useState(null);

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

  const handleStatusChange = async (customerId, newStatus) => {
    setActionBusy(customerId);
    try {
      const updated = await adminOperationsApi.updateCustomerStatus(customerId, newStatus);
      setCustomers((prev) => prev.map((c) => (c.id === customerId ? updated : c)));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update customer status.');
    } finally {
      setActionBusy(null);
    }
  };

  const formatCurrency = (val) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(val || 0));

  return (
    <AdminLayout
      title="Customer Accounts"
      subtitle={`Manage ${total} registered customer profiles, marketing consents, and account statuses`}
    >
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
          {error}
        </div>
      )}

      {/* Search & Status Filter */}
      <form
        onSubmit={handleSearch}
        className="dv-card p-4 mb-6 flex flex-wrap items-center gap-4"
      >
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-[#8490A0] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by full name, email, or phone number..."
            className="dv-input pl-9 pr-4 py-2 text-xs"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="dv-input w-auto px-3 py-2 text-xs"
        >
          <option value="">All Account Statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="deactivated">Deactivated</option>
        </select>

        <button
          type="submit"
          className="dv-btn-primary text-xs uppercase tracking-wider px-5 py-2"
        >
          Filter
        </button>
      </form>

      {/* Customer Directory Table */}
      <div className="dv-card overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-[#E5E7EB] text-[#64748B] uppercase bg-[#FFF6ED]">
              <th className="p-4 font-semibold">Customer</th>
              <th className="p-4 font-semibold">Verification</th>
              <th className="p-4 font-semibold">Marketing Opt-In</th>
              <th className="p-4 font-semibold">Orders & Spend</th>
              <th className="p-4 font-semibold">Status</th>
              <th className="p-4 text-right font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB]">
            {loading ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-[#64748B]">
                  Loading customers...
                </td>
              </tr>
            ) : customers.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-[#64748B]">
                  No customers match the current filter.
                </td>
              </tr>
            ) : (
              customers.map((c) => (
                <tr key={c.id} className="hover:bg-[#FFF0E2]/45 transition">
                  <td className="p-4">
                    <p className="font-semibold text-[#1F2937]">{c.full_name}</p>
                    <p className="text-[11px] text-[#64748B]">{c.email}</p>
                    {c.phone_number && (
                      <p className="text-[11px] font-mono text-[#8490A0]">{c.phone_number}</p>
                    )}
                  </td>
                  <td className="p-4">
                    <span
                      className={`text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full border ${
                        c.is_phone_verified
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-[#FFE9D6] text-[#D94300] border-[#FFD4AE]'
                      }`}
                    >
                      {c.is_phone_verified ? 'Phone Verified' : 'Phone Unverified'}
                    </span>
                  </td>
                  <td className="p-4 space-x-1.5">
                    <span
                      className={`text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full border ${
                        c.email_marketing_consent
                          ? 'bg-sky-50 text-sky-700 border-sky-200'
                          : 'bg-slate-100 text-[#64748B] border-[#E5E7EB]'
                      }`}
                    >
                      Email: {c.email_marketing_consent ? 'Yes' : 'No'}
                    </span>
                    <span
                      className={`text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full border ${
                        c.whatsapp_marketing_consent
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-slate-100 text-[#64748B] border-[#E5E7EB]'
                      }`}
                    >
                      WA: {c.whatsapp_marketing_consent ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td className="p-4">
                    <p className="text-[#1F2937] font-semibold font-mono">{formatCurrency(c.total_spent)}</p>
                    <p className="text-[11px] text-[#64748B]">{c.order_count} orders</p>
                  </td>
                  <td className="p-4">
                    <span
                      className={`text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full border ${
                        c.account_status === 'active'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-red-50 text-red-700 border-red-200'
                      }`}
                    >
                      {c.account_status}
                    </span>
                  </td>
                  <td className="p-4 text-right">
                    {c.account_status === 'active' ? (
                      <button
                        type="button"
                        disabled={actionBusy === c.id}
                        onClick={() => handleStatusChange(c.id, 'suspended')}
                        className="inline-flex items-center gap-1 rounded-lg text-[11px] font-medium uppercase tracking-wider px-3 py-1.5 border border-red-200 bg-white text-red-600 hover:bg-red-50 transition disabled:opacity-50"
                      >
                        <ShieldAlert className="w-3.5 h-3.5" />
                        <span>Suspend</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={actionBusy === c.id}
                        onClick={() => handleStatusChange(c.id, 'active')}
                        className="inline-flex items-center gap-1 rounded-lg text-[11px] font-medium uppercase tracking-wider px-3 py-1.5 border border-emerald-200 bg-white text-emerald-700 hover:bg-emerald-50 transition disabled:opacity-50"
                      >
                        <UserCheck className="w-3.5 h-3.5" />
                        <span>Reactivate</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-xs text-[#64748B]">
          <span>
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => loadCustomers(page - 1)}
              className="dv-btn-secondary px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => loadCustomers(page + 1)}
              className="dv-btn-secondary px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </AdminLayout>
  );
};

export default AdminCustomersPage;
