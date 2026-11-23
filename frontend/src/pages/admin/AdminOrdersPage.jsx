import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Download,
  IndianRupee,
  RotateCcw,
  Search,
  ShoppingCart,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  EmptyState,
  ErrorAlert,
  LoadingState,
  Pagination,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import { AdminKpiCard, AdminStatusBadge } from '../../components/admin/AdminPrimitives';
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

  const hasFilters = Boolean(search.trim() || statusFilter || paymentFilter);

  return (
    <AdminLayout
      title="Order Management"
      subtitle="Inspect customer orders, payment verification references, and digital delivery activity"
    >
      {error && <ErrorAlert message={error} onRetry={fetchOrders} className="mb-6" />}

      {/* Order Statistics Cards */}
      {stats && (
        <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3.5 mb-6">
          <AdminKpiCard
            compact
            label="Total Orders"
            value={stats.total_orders ?? 0}
            icon={ShoppingCart}
            tone="neutral"
          />
          <AdminKpiCard
            compact
            label="Paid Orders"
            value={stats.paid_orders ?? 0}
            icon={CheckCircle2}
            tone="success"
          />
          <AdminKpiCard
            compact
            label="Pending Orders"
            value={stats.pending_orders ?? 0}
            icon={Clock}
            tone={Number(stats.pending_orders || 0) > 0 ? 'warning' : 'neutral'}
          />
          <AdminKpiCard
            compact
            label="Verified Revenue"
            value={formatINR(stats.total_revenue)}
            icon={IndianRupee}
            tone="blue"
          />
          <AdminKpiCard
            compact
            label="Refunded Amount"
            value={formatINR(stats.total_refunded_amount)}
            icon={RotateCcw}
            tone="neutral"
          />
          <AdminKpiCard
            compact
            label="Total Downloads"
            value={stats.total_downloads ?? 0}
            icon={Download}
            tone="blue"
          />
        </section>
      )}

      {/* Search & Filters */}
      <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-4 mb-5 grid grid-cols-1 md:grid-cols-4 gap-3 shadow-2xs">
        <div className="relative md:col-span-2">
          <label htmlFor="admin-orders-search" className="sr-only">
            Search orders
          </label>
          <Search
            className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2"
            aria-hidden="true"
          />
          <input
            id="admin-orders-search"
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search by order number, customer email, or name..."
            className="dv-input pl-10 pr-4 py-2 text-[13px]"
          />
        </div>

        <select
          aria-label="Filter by payment status"
          value={paymentFilter}
          onChange={(e) => {
            setPaymentFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input px-3.5 py-2 text-[13px]"
        >
          <option value="">All Payment Statuses</option>
          <option value="paid">Paid</option>
          <option value="pending">Pending</option>
          <option value="unpaid">Unpaid</option>
          <option value="failed">Failed</option>
          <option value="refunded">Refunded</option>
        </select>

        <select
          aria-label="Filter by order status"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input px-3.5 py-2 text-[13px]"
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
      <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
        {loading ? (
          <LoadingState label="Loading orders..." />
        ) : data.items.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={ShoppingCart}
              title="No matching orders"
              description={
                hasFilters
                  ? 'No orders matched your current search or status filters.'
                  : 'Customer orders will appear here once checkout is initiated.'
              }
              action={
                hasFilters && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearch('');
                      setStatusFilter('');
                      setPaymentFilter('');
                      setPage(1);
                    }}
                    className="dv-btn-secondary px-4 py-2 text-[12px] font-semibold"
                  >
                    Clear Filters
                  </button>
                )
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#18243A] border-b border-[#D5DEE8] text-[11.5px] font-semibold text-[#CBD5E1]">
                  <th className="py-3 px-4">Order</th>
                  <th className="py-3 px-4">Customer</th>
                  <th className="py-3 px-4">Total</th>
                  <th className="py-3 px-4">Payment</th>
                  <th className="py-3 px-4">Order Status</th>
                  <th className="py-3 px-4">Downloads</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                {data.items.map((ord) => (
                  <tr key={ord.id} className="hover:bg-[#18243A]/70 transition">
                    <td className="py-3.5 px-4 font-mono font-semibold text-[#F1F5F9] whitespace-nowrap">
                      {ord.order_number}
                    </td>
                    <td className="py-3.5 px-4">
                      <p className="font-semibold text-[#F1F5F9]">{ord.customer.full_name}</p>
                      <p className="text-[12px] text-[#94A3B8]">{ord.customer.email}</p>
                    </td>
                    <td className="py-3.5 px-4 font-mono font-semibold text-[#F1F5F9] tabular-nums whitespace-nowrap">
                      {formatINR(ord.total_amount)}
                    </td>
                    <td className="py-3.5 px-4">
                      <AdminStatusBadge status={ord.payment_status} />
                    </td>
                    <td className="py-3.5 px-4">
                      <AdminStatusBadge status={ord.status} />
                    </td>
                    <td className="py-3.5 px-4 font-mono text-[#CBD5E1] tabular-nums">
                      {ord.downloads?.length || 0}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        to={`/admin/orders/${ord.id}`}
                        className="px-3 py-1.5 rounded-lg border border-[#D5DEE8] bg-[#111C30] hover:border-[#93C5FD] hover:bg-[#18243A] hover:text-[#60A5FA] text-[12px] font-medium text-[#F1F5F9] inline-flex items-center gap-1 transition"
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
      </div>

      <Pagination
        page={data.page}
        totalPages={data.total_pages}
        totalItems={data.total}
        itemLabel="orders"
        onPageChange={(nextPage) => setPage(nextPage)}
      />
    </AdminLayout>
  );
};

export default AdminOrdersPage;
