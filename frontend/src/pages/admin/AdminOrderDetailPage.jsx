import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  ShieldCheck,
  Download,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import { adminOrdersApi } from '../../services/api';

const AdminOrderDetailPage = () => {
  const { order_id } = useParams();
  const [order, setOrder] = useState(null);
  const [nextStatus, setNextStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [toast, setToast] = useState({ type: '', message: '' });

  const loadOrder = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminOrdersApi.getOrder(order_id);
      setOrder(res);
      setNextStatus(res.status);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Order not found.',
      });
    } finally {
      setLoading(false);
    }
  }, [order_id]);

  useEffect(() => {
    loadOrder();
  }, [loadOrder]);

  const handleStatusUpdate = async (e) => {
    e.preventDefault();
    if (!nextStatus || nextStatus === order?.status) return;
    setUpdating(true);
    setToast({ type: '', message: '' });
    try {
      const updated = await adminOrdersApi.updateOrderStatus(order_id, nextStatus);
      setOrder(updated);
      setToast({
        type: 'success',
        message: `Order status transitioned to "${updated.status}".`,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Invalid state transition.',
      });
    } finally {
      setUpdating(false);
    }
  };

  const formatINR = (v) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(v || 0));

  return (
    <AdminLayout
      title={order ? `Order ${order.order_number}` : 'Order Details'}
      subtitle="Customer breakdown, immutable price snapshots, payment references, and download audit logs"
      actions={
        <Link
          to="/admin/orders"
          className="dv-btn-secondary text-xs uppercase tracking-wider px-4 py-2 flex items-center gap-1.5"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Orders</span>
        </Link>
      }
    >
      {toast.message && (
        <div
          className={`mb-6 p-4 rounded-xl border text-xs flex items-center gap-2.5 ${
            toast.type === 'error'
              ? 'bg-red-50 border-red-200 text-red-700'
              : 'bg-emerald-50 border-emerald-200 text-emerald-800'
          }`}
        >
          {toast.type === 'error' ? (
            <AlertCircle className="w-4 h-4 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {loading || !order ? (
        <p className="text-xs text-[#64748B]">Loading order information...</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Customer Card */}
            <section className="dv-card p-6 space-y-2 text-xs">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-[#FF6B0A]">Customer</p>
              <p className="text-base font-semibold text-[#1F2937]">{order.customer.full_name}</p>
              <p className="text-[#243247]">{order.customer.email}</p>
              {order.customer.phone_number && (
                <p className="font-mono text-[#64748B]">{order.customer.phone_number}</p>
              )}
            </section>

            {/* Financial Summary */}
            <section className="dv-card p-6 space-y-2 text-xs">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-[#FF6B0A]">
                Financial Breakdown
              </p>
              <div className="flex justify-between text-[#64748B]">
                <span>Subtotal</span>
                <span className="font-mono text-[#1F2937]">{formatINR(order.subtotal_amount)}</span>
              </div>
              <div className="flex justify-between text-emerald-700">
                <span>Discount</span>
                <span className="font-mono">-{formatINR(order.discount_amount)}</span>
              </div>
              <div className="flex justify-between text-sm font-semibold text-[#1F2937] pt-2 border-t border-[#E5E7EB]">
                <span>Total Amount</span>
                <span className="font-mono text-[#FF6B0A]">{formatINR(order.total_amount)}</span>
              </div>
            </section>

            {/* Controlled State Transition */}
            <section className="dv-card p-6 space-y-3 text-xs">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-[#FF6B0A]">
                State Management
              </p>
              <p className="text-[11px] text-[#64748B]">
                Payment Status:{' '}
                <strong className="uppercase text-[#1F2937]">{order.payment_status}</strong>
              </p>
              <form onSubmit={handleStatusUpdate} className="flex items-center gap-2">
                <select
                  value={nextStatus}
                  onChange={(e) => setNextStatus(e.target.value)}
                  className="dv-input flex-1 px-3 py-2 text-xs"
                >
                  <option value="pending">pending</option>
                  <option value="confirmed">confirmed</option>
                  <option value="fulfilled">fulfilled</option>
                  <option value="cancelled">cancelled</option>
                  <option value="refunded">refunded</option>
                  <option value="failed">failed</option>
                </select>
                <button
                  type="submit"
                  disabled={updating || nextStatus === order.status}
                  className="dv-btn-primary px-4 py-2 uppercase tracking-wider text-[11px] disabled:opacity-40"
                >
                  {updating ? 'Saving...' : 'Update'}
                </button>
              </form>
            </section>
          </div>

          {/* Order Items Table */}
          <section className="dv-card p-6">
            <h2 className="text-xs font-semibold text-[#1F2937] uppercase tracking-widest mb-4">
              Purchased Line Items (Immutable Snapshots)
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#E5E7EB] text-[#64748B] uppercase">
                    <th className="py-2.5 pr-4 font-semibold">Product Snapshot</th>
                    <th className="py-2.5 pr-4 font-semibold">Original Price</th>
                    <th className="py-2.5 pr-4 font-semibold">Purchase Price</th>
                    <th className="py-2.5 pr-4 font-semibold">Qty</th>
                    <th className="py-2.5 pr-4 font-semibold">Line Total</th>
                    <th className="py-2.5 pr-4 font-semibold">Downloads Used</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB]">
                  {order.items.map((item) => (
                    <tr key={item.id}>
                      <td className="py-3 pr-4 font-semibold text-[#1F2937]">
                        {item.product_name_snapshot}
                      </td>
                      <td className="py-3 pr-4 font-mono text-[#64748B]">
                        {formatINR(item.original_price_snapshot)}
                      </td>
                      <td className="py-3 pr-4 font-mono text-[#1F2937]">
                        {formatINR(item.purchase_price)}
                      </td>
                      <td className="py-3 pr-4 font-mono text-[#243247]">{item.quantity}</td>
                      <td className="py-3 pr-4 font-mono font-semibold text-[#1F2937]">
                        {formatINR(item.line_total)}
                      </td>
                      <td className="py-3 pr-4 font-mono text-[#243247]">
                        {item.downloads_used} / {item.max_downloads}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Payment References */}
          <section className="dv-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="w-4 h-4 text-[#FF6B0A]" />
              <h2 className="text-xs font-semibold text-[#1F2937] uppercase tracking-widest">
                Gateway Payment Records
              </h2>
            </div>

            {order.payments.length === 0 ? (
              <p className="text-xs text-[#64748B]">No payment attempts recorded.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[#E5E7EB] text-[#64748B] uppercase">
                      <th className="py-2.5 pr-4 font-semibold">Gateway</th>
                      <th className="py-2.5 pr-4 font-semibold">Gateway Order ID</th>
                      <th className="py-2.5 pr-4 font-semibold">Gateway Payment ID</th>
                      <th className="py-2.5 pr-4 font-semibold">Amount</th>
                      <th className="py-2.5 pr-4 font-semibold">Status</th>
                      <th className="py-2.5 pr-4 font-semibold">Signature Verified</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB]">
                    {order.payments.map((p) => (
                      <tr key={p.id}>
                        <td className="py-3 pr-4 uppercase font-medium text-[#1F2937]">{p.gateway_name}</td>
                        <td className="py-3 pr-4 font-mono text-[#243247]">{p.gateway_order_id}</td>
                        <td className="py-3 pr-4 font-mono text-[#64748B]">{p.gateway_payment_id || '—'}</td>
                        <td className="py-3 pr-4 font-mono text-[#1F2937]">{formatINR(p.amount)}</td>
                        <td className="py-3 pr-4 uppercase text-[#243247]">{p.status}</td>
                        <td className="py-3 pr-4">
                          {p.is_signature_verified ? (
                            <span className="font-medium text-emerald-700">Verified</span>
                          ) : (
                            <span className="text-[#64748B]">Unverified</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Download Activity */}
          <section className="dv-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <Download className="w-4 h-4 text-[#FF6B0A]" />
              <h2 className="text-xs font-semibold text-[#1F2937] uppercase tracking-widest">
                Customer Download Activity ({order.downloads.length})
              </h2>
            </div>

            {order.downloads.length === 0 ? (
              <p className="text-xs text-[#64748B]">No downloads recorded for this order.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[#E5E7EB] text-[#64748B] uppercase">
                      <th className="py-2.5 pr-4 font-semibold">Product</th>
                      <th className="py-2.5 pr-4 font-semibold">Status</th>
                      <th className="py-2.5 pr-4 font-semibold">Client IP</th>
                      <th className="py-2.5 pr-4 font-semibold">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB]">
                    {order.downloads.map((d) => (
                      <tr key={d.id}>
                        <td className="py-2.5 pr-4 font-medium text-[#1F2937]">{d.product_name}</td>
                        <td className="py-2.5 pr-4 uppercase text-[#243247]">{d.status}</td>
                        <td className="py-2.5 pr-4 font-mono text-[#64748B]">
                          {d.ip_address || '—'}
                        </td>
                        <td className="py-2.5 pr-4 text-[#64748B]">
                          {new Date(d.downloaded_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </AdminLayout>
  );
};

export default AdminOrderDetailPage;
