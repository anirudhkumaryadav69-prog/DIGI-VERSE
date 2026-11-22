import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowUpRight,
  AlertCircle,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import { adminOrdersApi } from '../../services/api';

const AdminOrdersPage = () => {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 15, total_pages: 1 });
  const [stats, setStats] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [paymentFilter, setPaymentFilter] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    adminOrdersApi
      .getStatistics()
      .then((res) => setStats(res))
      .catch(() => {});
  }, []);

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = { page, page_size: 15 };
      if (search.trim()) params.search = search.trim();
      if (statusFilter) params.status = statusFilter;
      if (paymentFilter) params.payment_status = paymentFilter;
      const res = await adminOrdersApi.listOrders(params);
      setData(res);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to load orders.');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, paymentFilter]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const formatINR = (v) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(v || 0));

  return (
    <AdminLayout
      title="Order Management"
      subtitle="Inspect customer orders, payment verification references, and digital delivery activity"
    >
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Order Statistics Cards */}
      {stats && (
        <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
          <div className="dv-card p-4">
            <p className="text-[10px] uppercase tracking-widest text-[#64748B]">Total Orders</p>
            <p className="text-xl font-semibold text-[#1F2937] mt-1">{stats.total_orders}</p>
          </div>
          <div className="dv-card p-4">
            <p className="text-[10px] uppercase tracking-widest text-[#64748B]">Paid Orders</p>
            <p className="text-xl font-semibold text-emerald-700 mt-1">{stats.paid_orders}</p>
          </div>
          <div className="dv-card p-4">
            <p className="text-[10px] uppercase tracking-widest text-[#64748B]">Pending Orders</p>
            <p className="text-xl font-semibold text-[#D94300] mt-1">{stats.pending_orders}</p>
          </div>
          <div className="dv-card p-4">
            <p className="text-[10px] uppercase tracking-widest text-[#64748B]">Verified Revenue</p>
            <p className="text-xl font-semibold font-mono text-[#FF6B0A] mt-1">{formatINR(stats.total_revenue)}</p>
          </div>
          <div className="dv-card p-4">
            <p className="text-[10px] uppercase tracking-widest text-[#64748B]">Refunded</p>
            <p className="text-xl font-semibold font-mono text-[#1F2937] mt-1">
              {formatINR(stats.total_refunded_amount)}
            </p>
          </div>
          <div className="dv-card p-4">
            <p className="text-[10px] uppercase tracking-widest text-[#64748B]">Total Downloads</p>
            <p className="text-xl font-semibold text-[#1F2937] mt-1">{stats.total_downloads}</p>
          </div>
        </section>
      )}

      {/* Search & Filters */}
      <div className="dv-card p-4 mb-6 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="relative md:col-span-2">
          <Search className="w-4 h-4 text-[#8490A0] absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search by order number, customer email, or name..."
            className="dv-input pl-10 pr-4 py-2 text-xs"
          />
        </div>

        <select
          value={paymentFilter}
          onChange={(e) => {
            setPaymentFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input px-3.5 py-2 text-xs"
        >
          <option value="">All Payment Statuses</option>
          <option value="paid">Paid</option>
          <option value="pending">Pending</option>
          <option value="unpaid">Unpaid</option>
          <option value="failed">Failed</option>
          <option value="refunded">Refunded</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input px-3.5 py-2 text-xs"
        >
          <option value="">All Order Statuses</option>
          <option value="pending">Pending</option>
          <option value="confirmed">Confirmed</option>
          <option value="fulfilled">Fulfilled</option>
          <option value="refunded">Refunded</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Orders Table */}
      <div className="dv-card overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-xs text-[#64748B] uppercase tracking-widest">
            Loading Orders...
          </div>
        ) : data.items.length === 0 ? (
          <div className="p-10 text-center text-xs text-[#64748B]">
            No orders match your current filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#E5E7EB] bg-[#FFF6ED] text-[#64748B] uppercase">
                  <th className="py-3 px-4 font-semibold">Order #</th>
                  <th className="py-3 px-4 font-semibold">Customer</th>
                  <th className="py-3 px-4 font-semibold">Total</th>
                  <th className="py-3 px-4 font-semibold">Payment</th>
                  <th className="py-3 px-4 font-semibold">Order Status</th>
                  <th className="py-3 px-4 font-semibold">Downloads</th>
                  <th className="py-3 px-4 text-right font-semibold">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB]">
                {data.items.map((ord) => (
                  <tr key={ord.id} className="hover:bg-[#FFF0E2]/45 transition">
                    <td className="py-3.5 px-4 font-mono font-semibold text-[#1F2937]">{ord.order_number}</td>
                    <td className="py-3.5 px-4">
                      <p className="font-semibold text-[#1F2937]">{ord.customer.full_name}</p>
                      <p className="text-[11px] text-[#64748B]">{ord.customer.email}</p>
                    </td>
                    <td className="py-3.5 px-4 font-mono font-medium text-[#1F2937]">{formatINR(ord.total_amount)}</td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full border ${
                          ord.payment_status === 'paid'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : ord.payment_status === 'refunded'
                            ? 'bg-amber-50 text-amber-800 border-amber-200'
                            : 'bg-slate-100 text-[#64748B] border-[#E5E7EB]'
                        }`}
                      >
                        {ord.payment_status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 uppercase text-[11px] font-medium text-[#243247]">
                      {ord.status}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-[#243247]">
                      {ord.downloads?.length || 0}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        to={`/admin/orders/${ord.id}`}
                        className="px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-[#FFD4AE] hover:text-[#FF6B0A] text-[#243247] inline-flex items-center gap-1 transition"
                      >
                        <span>Inspect</span>
                        <ArrowUpRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="p-4 border-t border-[#E5E7EB] bg-[#FFF6ED] flex items-center justify-between text-xs text-[#64748B]">
          <span>
            Total: <strong className="text-[#1F2937]">{data.total}</strong> orders
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white text-[#243247] disabled:opacity-40 hover:border-[#FFD4AE] hover:text-[#FF6B0A] transition"
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
              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white text-[#243247] disabled:opacity-40 hover:border-[#FFD4AE] hover:text-[#FF6B0A] transition"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};

export default AdminOrdersPage;
