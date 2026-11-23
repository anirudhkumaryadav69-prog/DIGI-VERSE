import { useCallback, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, Search, ShoppingBag } from 'lucide-react';
import SellerLayout from '../../layouts/SellerLayout';
import {
  Badge,
  LoadingState,
  ToastBanner,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import { sellerApi } from '../../services/api';

const FULFILMENT_BADGE = {
  ready: { label: 'Download Ready', variant: 'success' },
  downloaded: { label: 'Downloaded', variant: 'accent' },
  pending_payment: { label: 'Pending Payment', variant: 'neutral' },
  revoked: { label: 'Refunded / Revoked', variant: 'danger' },
};

const SellerOrdersPage = () => {
  const [data, setData] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [search, setSearch] = useState('');
  const [paymentStatus, setPaymentStatus] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState({ type: '', message: '' });

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 10 };
      if (search.trim()) params.search = search.trim();
      if (paymentStatus) params.payment_status = paymentStatus;
      const res = await sellerApi.listOrders(params);
      setData(res);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to load seller orders.',
      });
    } finally {
      setLoading(false);
    }
  }, [page, search, paymentStatus]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  return (
    <SellerLayout
      title="Seller Orders"
      subtitle="Orders containing your products (isolated to your items; customer PII and other sellers' items are excluded)"
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
              aria-label="Search orders by reference"
              placeholder="Search by order reference (DV-...)..."
              className="dv-input pl-10 pr-3.5 py-2 text-[13px]"
            />
          </div>

          <select
            value={paymentStatus}
            onChange={(e) => {
              setPaymentStatus(e.target.value);
              setPage(1);
            }}
            aria-label="Filter orders by payment status"
            className="dv-input text-xs sm:w-48"
          >
            <option value="">All Payment States</option>
            <option value="paid">Paid</option>
            <option value="pending">Pending</option>
            <option value="refunded">Refunded</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        <div className="space-y-4">
          {loading ? (
            <LoadingState label="Loading seller order attributions..." />
          ) : !data.items.length ? (
            <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-10 text-center">
              <ShoppingBag className="w-8 h-8 text-[#60A5FA] mx-auto mb-2" />
              <p className="text-sm font-semibold text-[#F1F5F9]">No matching orders found</p>
              <p className="text-xs text-[#94A3B8] mt-1">
                Only orders containing at least one item you own appear here.
              </p>
            </div>
          ) : (
            data.items.map((ord) => {
              const dlBadge = FULFILMENT_BADGE[ord.download_fulfilment_status] || {
                label: ord.download_fulfilment_status,
                variant: 'neutral',
              };
              return (
                <div
                  key={ord.order_id}
                  className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl overflow-hidden shadow-xs"
                >
                  <div className="px-5 py-3.5 bg-[#18243A] border-b border-[#E5E7EB] flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="font-mono text-xs font-bold text-[#F1F5F9]">
                        {ord.order_number}
                      </span>
                      <span className="text-[11px] text-[#94A3B8]">
                        {new Date(ord.created_at).toLocaleString()}
                      </span>
                      <Badge variant={ord.payment_status === 'paid' ? 'success' : ord.payment_status === 'refunded' ? 'danger' : 'neutral'}>
                        Payment: {ord.payment_status}
                      </Badge>
                      <Badge variant={dlBadge.variant}>{dlBadge.label}</Badge>
                    </div>
                    <div className="text-right">
                      <span className="text-[11px] text-[#94A3B8] mr-2">
                        Your Items Total ({ord.seller_units_count} qty):
                      </span>
                      <span className="font-mono text-sm font-bold text-[#93C5FD]">
                        {formatINR(ord.seller_items_subtotal)}
                      </span>
                    </div>
                  </div>

                  <div className="divide-y divide-[#E5E7EB]">
                    {ord.items.map((item) => (
                      <div
                        key={item.id}
                        className="px-5 py-3 flex flex-wrap items-center justify-between gap-3 text-xs"
                      >
                        <div>
                          <p className="font-semibold text-[#F1F5F9]">{item.product_name_snapshot}</p>
                          <p className="text-[11px] text-[#94A3B8]">
                            Qty: {item.quantity} × {formatINR(item.purchase_price)} · Snapshot: {item.seller_store_name_snapshot}
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="inline-flex items-center gap-1 text-[11px] text-[#94A3B8]">
                            <Download className="w-3.5 h-3.5 text-[#60A5FA]" />
                            {item.downloads_used}/{item.max_downloads} downloads
                          </span>
                          <span className="font-mono font-bold text-[#F1F5F9]">
                            {formatINR(item.line_total)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-4 flex items-center justify-between text-xs text-[#94A3B8]">
          <span>
            Total: <strong className="text-[#F1F5F9]">{data.total}</strong> seller orders
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Previous page"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-[#111C30] disabled:opacity-40"
            >
              <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
            <span>
              Page {data.page} of {data.total_pages}
            </span>
            <button
              type="button"
              aria-label="Next page"
              disabled={page >= data.total_pages}
              onClick={() => setPage((p) => p + 1)}
              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-[#111C30] disabled:opacity-40"
            >
              <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </SellerLayout>
  );
};

export default SellerOrdersPage;
