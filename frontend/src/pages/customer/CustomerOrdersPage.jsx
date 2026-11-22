import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, CheckCircle2, Clock, Package } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import {
  Badge,
  EmptyState,
  ErrorAlert,
  LoadingState,
  Pagination,
  SectionHeading,
  formatINR,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { commerceApi } from '../../services/api';

const CustomerOrdersPage = () => {
  const [data, setData] = useState({
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
    total_pages: 1,
  });
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useDocumentMeta({
    title: 'Your Orders',
    description: 'View your DIGI-VERSE purchase history, order statuses, and official invoices.',
    canonicalPath: '/orders',
  });

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = { page, page_size: 10 };
      if (statusFilter) params.status = statusFilter;
      const res = await commerceApi.listOrders(params);
      setData(res);
    } catch {
      setError('Unable to load your order history.');
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  return (
    <StorefrontLayout>
      <SectionHeading
        eyebrow="Purchase Ledger"
        title={`Your Orders (${data.total})`}
        subtitle="Inspect order snapshots, payment verification status, and official purchase invoices."
        action={
          <div>
            <label htmlFor="order-status-filter" className="sr-only">
              Filter orders by status
            </label>
            <select
              id="order-status-filter"
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
        }
      />

      {error && <ErrorAlert message={error} onRetry={fetchOrders} className="mb-6" />}

      {loading ? (
        <LoadingState label="Loading Order History..." />
      ) : data.items.length === 0 ? (
        <EmptyState
          icon={Package}
          title="No orders found"
          description="You haven't placed any orders matching the current filter yet."
          action={
            <Link
              to="/products"
              className="dv-btn-primary inline-block text-[13px] font-semibold px-6 py-3"
            >
              Explore Products
            </Link>
          }
        />
      ) : (
        <div className="dv-card divide-y divide-[#E5E7EB] overflow-hidden">
          {data.items.map((ord) => (
            <div
              key={ord.id}
              className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-[#EDF5FC]/45 transition"
            >
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="font-mono text-sm font-bold text-[#263445]">
                    {ord.order_number}
                  </span>
                  <Badge
                    variant={
                      ord.payment_status === 'paid'
                        ? 'success'
                        : ord.payment_status === 'failed'
                        ? 'danger'
                        : ord.payment_status === 'refunded'
                        ? 'warning'
                        : 'neutral'
                    }
                  >
                    Payment: {ord.payment_status}
                  </Badge>
                  <Badge variant="accent">Order: {ord.status}</Badge>
                </div>
                <p className="text-xs text-[#64748B]">
                  Placed on {new Date(ord.created_at).toLocaleString()} · {ord.items.length}{' '}
                  {ord.items.length === 1 ? 'item' : 'items'}
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-between md:justify-end gap-4">
                <div className="text-left md:text-right">
                  <p className="font-mono text-base font-bold text-[#1D4ED8]">
                    {formatINR(ord.total_amount)}
                  </p>
                  <p className="text-[11px] flex items-center md:justify-end gap-1 mt-0.5">
                    {ord.download_eligible ? (
                      <span className="text-emerald-700 font-medium inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" aria-hidden="true" />
                        <span>Downloads Ready</span>
                      </span>
                    ) : (
                      <span className="text-[#64748B] inline-flex items-center gap-1">
                        <Clock className="w-3 h-3" aria-hidden="true" />
                        <span>Awaiting Verified Payment</span>
                      </span>
                    )}
                  </p>
                </div>

                {ord.payment_status !== 'paid' &&
                  !['fulfilled', 'refunded', 'cancelled'].includes(ord.status) && (
                    <Link
                      to={`/checkout?order_id=${ord.id}`}
                      className="dv-btn-primary px-4 py-2 text-xs font-semibold"
                    >
                      Retry Payment
                    </Link>
                  )}

                <Link
                  to={`/orders/${ord.id}`}
                  className="dv-btn-secondary px-4 py-2 text-xs font-semibold inline-flex items-center gap-1.5"
                >
                  <span>View Order</span>
                  <ArrowUpRight className="w-3.5 h-3.5" aria-hidden="true" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      <Pagination
        page={data.page}
        totalPages={data.total_pages}
        totalItems={data.total}
        itemLabel="orders"
        onPageChange={(newPage) => setPage(newPage)}
      />
    </StorefrontLayout>
  );
};

export default CustomerOrdersPage;
