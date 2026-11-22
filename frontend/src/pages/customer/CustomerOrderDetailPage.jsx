import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Download, FileText, RefreshCw } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import {
  Badge,
  ErrorAlert,
  LoadingState,
  ToastBanner,
  formatINR,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { commerceApi, resolveApiAssetUrl } from '../../services/api';

const CustomerOrderDetailPage = () => {
  const { order_id } = useParams();
  const [order, setOrder] = useState(null);
  const [invoice, setInvoice] = useState(null);
  const [showInvoice, setShowInvoice] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [downloadingItem, setDownloadingItem] = useState(null);
  const [toast, setToast] = useState({ type: '', message: '' });

  useDocumentMeta({
    title: order ? `Order ${order.order_number}` : 'Order Details',
    description: 'View order details, official purchase invoice, and digital product downloads.',
    canonicalPath: `/orders/${order_id}`,
  });

  const loadOrder = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const ord = await commerceApi.getOrder(order_id);
      setOrder(ord);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Order not found.');
    } finally {
      setLoading(false);
    }
  }, [order_id]);

  useEffect(() => {
    loadOrder();
  }, [loadOrder]);

  const handleToggleInvoice = async () => {
    if (!invoice) {
      try {
        const inv = await commerceApi.getOrderInvoice(order_id);
        setInvoice(inv);
      } catch {
        setToast({ type: 'error', message: 'Unable to load purchase invoice.' });
        return;
      }
    }
    setShowInvoice((prev) => !prev);
  };

  const handleDownloadItem = async (item) => {
    setDownloadingItem(item.id);
    setToast({ type: '', message: '' });
    try {
      const grant = await commerceApi.requestDownload(item.id);
      setToast({
        type: 'success',
        message: `Secure download link generated (${grant.remaining_downloads} downloads remaining).`,
      });
      window.open(resolveApiAssetUrl(grant.download_url), '_blank', 'noopener,noreferrer');
      await loadOrder();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Download request failed.',
      });
    } finally {
      setDownloadingItem(null);
    }
  };

  return (
    <StorefrontLayout>
      <div className="space-y-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link
            to="/orders"
            className="text-xs font-semibold text-[#FF6B0A] hover:text-[#D94300] hover:underline inline-flex items-center gap-1.5"
          >
            <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Back to Orders</span>
          </Link>

          {order && (
            <div className="flex flex-wrap items-center gap-3">
              {order.payment_status !== 'paid' &&
                !['fulfilled', 'refunded', 'cancelled'].includes(order.status) && (
                  <Link
                    to={`/checkout?order_id=${order.id}`}
                    className="dv-btn-primary text-xs font-semibold uppercase tracking-wider px-4 py-2 inline-flex items-center gap-1.5"
                  >
                    <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
                    <span>Retry Payment</span>
                  </Link>
                )}

              <button
                type="button"
                onClick={handleToggleInvoice}
                className="dv-btn-secondary text-xs font-semibold uppercase tracking-wider px-4 py-2 inline-flex items-center gap-1.5"
              >
                <FileText className="w-3.5 h-3.5" aria-hidden="true" />
                <span>{showInvoice ? 'Hide Invoice' : 'View Purchase Invoice'}</span>
              </button>
            </div>
          )}
        </div>

        {toast.message && (
          <ToastBanner toast={toast} onDismiss={() => setToast({ type: '', message: '' })} />
        )}

        {error && <ErrorAlert message={error} onRetry={loadOrder} />}

        {loading ? (
          <LoadingState label="Loading Order Details..." />
        ) : (
          order && (
            <>
              {/* Order Header Summary */}
              <section className="dv-card p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-[#FF6B0A] font-semibold mb-1">
                    Order Reference
                  </p>
                  <h1 className="text-2xl font-mono font-bold text-[#1F2937]">
                    {order.order_number}
                  </h1>
                  <p className="text-xs text-[#64748B] mt-1">
                    Placed on {new Date(order.created_at).toLocaleString()}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <Badge
                    variant={
                      order.payment_status === 'paid'
                        ? 'success'
                        : order.payment_status === 'failed'
                        ? 'danger'
                        : 'warning'
                    }
                  >
                    Payment: {order.payment_status}
                  </Badge>
                  <Badge variant="dark">Status: {order.status}</Badge>
                </div>
              </section>

              {/* Invoice Panel */}
              {showInvoice && invoice && (
                <section
                  aria-label="Official Purchase Invoice"
                  className="dv-card-warm p-6 md:p-8 space-y-6 bg-[#FFF6ED]/40"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#FFD4AE] pb-4">
                    <div>
                      <p className="text-xs uppercase tracking-wider text-[#FF6B0A] font-semibold">
                        Official Purchase Invoice
                      </p>
                      <h2 className="text-xl font-mono font-bold text-[#1F2937] mt-1">
                        {invoice.invoice_number}
                      </h2>
                    </div>
                    <div className="text-right text-xs text-[#64748B]">
                      <p>Issued: {new Date(invoice.issued_at).toLocaleString()}</p>
                      <p>
                        Billed To: {invoice.customer_name} ({invoice.customer_email})
                      </p>
                      {invoice.gateway_payment_id && (
                        <p className="font-mono">Gateway Ref: {invoice.gateway_payment_id}</p>
                      )}
                    </div>
                  </div>

                  <div className="space-y-2 text-xs text-[#243247]">
                    <div className="flex justify-between">
                      <span>Subtotal</span>
                      <span className="font-mono">{formatINR(invoice.subtotal_amount)}</span>
                    </div>
                    <div className="flex justify-between text-emerald-700">
                      <span>Discount</span>
                      <span className="font-mono">-{formatINR(invoice.discount_amount)}</span>
                    </div>
                    <div className="flex justify-between font-bold text-sm pt-2 border-t border-[#FFD4AE]">
                      <span>Total Paid</span>
                      <span className="font-mono text-[#F4510B]">
                        {formatINR(invoice.total_amount)}
                      </span>
                    </div>
                  </div>
                </section>
              )}

              {/* Purchased Items & Digital Downloads */}
              <section className="dv-card p-6 md:p-8 space-y-4">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937] border-b border-[#E5E7EB] pb-3">
                  Purchased Products &amp; Digital Delivery
                </h2>

                <div className="divide-y divide-[#E5E7EB]">
                  {order.items.map((item) => {
                    const remaining = Math.max(0, (item.max_downloads || 0) - (item.downloads_used || 0));
                    return (
                      <div
                        key={item.id}
                        className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                      >
                        <div>
                          <p className="text-base font-semibold text-[#1F2937]">
                            {item.product_name_snapshot}
                          </p>
                          <p className="text-xs text-[#64748B] font-mono mt-0.5">
                            Qty: {item.quantity} × {formatINR(item.purchase_price)} (Original:{' '}
                            {formatINR(item.original_price_snapshot)})
                          </p>
                          <p className="text-[11px] font-medium text-[#D94300] mt-1">
                            Downloads used: {item.downloads_used} / {item.max_downloads} ({remaining}{' '}
                            remaining)
                          </p>
                        </div>

                        <div className="flex items-center justify-between sm:justify-end gap-4">
                          <span className="font-mono text-sm font-bold text-[#F4510B]">
                            {formatINR(item.line_total)}
                          </span>

                          <button
                            type="button"
                            disabled={!item.download_eligible || downloadingItem === item.id}
                            onClick={() => handleDownloadItem(item)}
                            className="dv-btn-primary px-4 py-2.5 text-xs font-semibold uppercase tracking-wider inline-flex items-center gap-1.5 disabled:opacity-40"
                          >
                            <Download className="w-3.5 h-3.5" aria-hidden="true" />
                            <span>
                              {downloadingItem === item.id
                                ? 'Generating Link...'
                                : item.download_eligible
                                ? 'Download Asset'
                                : remaining === 0 && order.payment_status === 'paid'
                                ? 'Quota Exhausted'
                                : 'Locked'}
                            </span>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            </>
          )
        )}
      </div>
    </StorefrontLayout>
  );
};

export default CustomerOrderDetailPage;
