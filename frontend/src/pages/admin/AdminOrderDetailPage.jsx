import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  IndianRupee,
  Package,
  ShieldCheck,
  User,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  ErrorAlert,
  LoadingState,
  ToastBanner,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import {
  AdminSectionHeader,
  AdminStatusBadge,
  formatAdminDateTime,
} from '../../components/admin/AdminPrimitives';
import { adminOrdersApi } from '../../services/api';

const AdminOrderDetailPage = () => {
  const { order_id } = useParams();
  const [order, setOrder] = useState(null);
  const [nextStatus, setNextStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [updating, setUpdating] = useState(false);
  const [toast, setToast] = useState(null);

  const loadOrder = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await adminOrdersApi.getOrder(order_id);
      setOrder(res);
      setNextStatus(res.status);
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

  const handleStatusUpdate = async (e) => {
    e.preventDefault();
    if (!nextStatus || nextStatus === order?.status) return;
    setUpdating(true);
    setToast(null);
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

  return (
    <AdminLayout
      title={order ? `Order ${order.order_number}` : 'Order Details'}
      subtitle="Customer breakdown, immutable price snapshots, payment references, and download audit logs"
      actions={
        <Link
          to="/admin/orders"
          className="dv-btn-secondary text-[12px] font-semibold px-4 py-2 inline-flex items-center gap-1.5"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Orders</span>
        </Link>
      }
    >
      {error && <ErrorAlert message={error} onRetry={loadOrder} className="mb-6" />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-6" />

      {loading ? (
        <LoadingState label="Loading order information..." />
      ) : !order ? null : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Customer Card */}
            <section className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-5 space-y-3 shadow-2xs">
              <div className="flex items-center gap-2 text-[#60A5FA]">
                <User className="w-4 h-4" />
                <h2 className="text-[13px] font-semibold text-[#F1F5F9]">Customer Account</h2>
              </div>
              <div className="space-y-1 text-[13px]">
                <p className="text-[16px] font-semibold text-[#F1F5F9]">
                  {order.customer.full_name}
                </p>
                <p className="text-[#CBD5E1]">{order.customer.email}</p>
                {order.customer.phone_number && (
                  <p className="font-mono text-[12px] text-[#94A3B8]">
                    {order.customer.phone_number}
                  </p>
                )}
              </div>
            </section>

            {/* Financial Summary */}
            <section className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-5 space-y-2.5 shadow-2xs">
              <div className="flex items-center gap-2 text-[#60A5FA] mb-1">
                <IndianRupee className="w-4 h-4" />
                <h2 className="text-[13px] font-semibold text-[#F1F5F9]">Financial Breakdown</h2>
              </div>
              <div className="flex justify-between text-[13px] text-[#94A3B8]">
                <span>Subtotal</span>
                <span className="font-mono text-[#F1F5F9] tabular-nums">
                  {formatINR(order.subtotal_amount)}
                </span>
              </div>
              <div className="flex justify-between text-[13px] text-emerald-300">
                <span>Discount</span>
                <span className="font-mono tabular-nums">
                  -{formatINR(order.discount_amount)}
                </span>
              </div>
              <div className="flex justify-between text-[15px] font-bold text-[#F1F5F9] pt-2.5 border-t border-[#E5E7EB]">
                <span>Total Amount</span>
                <span className="font-mono text-[#60A5FA] tabular-nums">
                  {formatINR(order.total_amount)}
                </span>
              </div>
            </section>

            {/* Controlled State Transition */}
            <section className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-5 space-y-3 shadow-2xs">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-[13px] font-semibold text-[#F1F5F9]">State Management</h2>
                <AdminStatusBadge status={order.payment_status} />
              </div>
              <p className="text-[12px] text-[#94A3B8]">
                Current Order State: <AdminStatusBadge status={order.status} className="ml-1" />
              </p>
              <form onSubmit={handleStatusUpdate} className="flex items-center gap-2 pt-1">
                <select
                  aria-label="Order status"
                  value={nextStatus}
                  onChange={(e) => setNextStatus(e.target.value)}
                  className="dv-input flex-1 px-3 py-2 text-[13px]"
                >
                  <option value="pending">Pending</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="fulfilled">Fulfilled</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="refunded">Refunded</option>
                  <option value="failed">Failed</option>
                </select>
                <button
                  type="submit"
                  disabled={updating || nextStatus === order.status}
                  className="dv-btn-primary px-4 py-2 text-[12px] font-semibold disabled:opacity-40"
                >
                  {updating ? 'Saving...' : 'Update'}
                </button>
              </form>
            </section>
          </div>

          {/* Order Items Table */}
          <section className="bg-[#111C30] border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
            <div className="p-5 border-b border-[#E5E7EB]">
              <AdminSectionHeader
                icon={Package}
                title="Purchased Line Items"
                subtitle="Immutable pricing snapshots recorded at checkout"
              />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#18243A] border-b border-[#D5DEE8] text-[11.5px] font-semibold text-[#CBD5E1]">
                    <th className="py-3 px-4">Product Snapshot</th>
                    <th className="py-3 px-4">Original Price</th>
                    <th className="py-3 px-4">Purchase Price</th>
                    <th className="py-3 px-4">Qty</th>
                    <th className="py-3 px-4">Line Total</th>
                    <th className="py-3 px-4">Downloads Used</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                  {order.items.map((item) => (
                    <tr key={item.id} className="hover:bg-[#18243A]/70 transition">
                      <td className="py-3.5 px-4 font-semibold text-[#F1F5F9]">
                        {item.product_name_snapshot}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[#94A3B8] tabular-nums">
                        {formatINR(item.original_price_snapshot)}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[#F1F5F9] tabular-nums">
                        {formatINR(item.purchase_price)}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[#F1F5F9] tabular-nums">
                        {item.quantity}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-semibold text-[#F1F5F9] tabular-nums">
                        {formatINR(item.line_total)}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[#CBD5E1] tabular-nums">
                        {item.downloads_used} / {item.max_downloads}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Payment References */}
          <section className="bg-[#111C30] border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
            <div className="p-5 border-b border-[#E5E7EB]">
              <AdminSectionHeader
                icon={ShieldCheck}
                title="Gateway Payment Records"
                subtitle="Cryptographic signature checks and payment gateway references"
              />
            </div>

            {order.payments.length === 0 ? (
              <p className="text-[13px] text-[#94A3B8] p-6">No payment attempts recorded.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#18243A] border-b border-[#D5DEE8] text-[11.5px] font-semibold text-[#CBD5E1]">
                      <th className="py-3 px-4">Gateway</th>
                      <th className="py-3 px-4">Gateway Order ID</th>
                      <th className="py-3 px-4">Gateway Payment ID</th>
                      <th className="py-3 px-4">Amount</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Signature</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                    {order.payments.map((p) => (
                      <tr key={p.id} className="hover:bg-[#18243A]/70 transition">
                        <td className="py-3.5 px-4 font-semibold text-[#F1F5F9]">
                          {String(p.gateway_name || '').toUpperCase()}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-[12px] text-[#F1F5F9]">
                          {p.gateway_order_id}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-[12px] text-[#94A3B8]">
                          {p.gateway_payment_id || '—'}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-[#F1F5F9] tabular-nums">
                          {formatINR(p.amount)}
                        </td>
                        <td className="py-3.5 px-4">
                          <AdminStatusBadge status={p.status} />
                        </td>
                        <td className="py-3.5 px-4">
                          <AdminStatusBadge
                            status={p.is_signature_verified ? 'verified' : 'pending'}
                            label={p.is_signature_verified ? 'Verified' : 'Unverified'}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Download Activity */}
          <section className="bg-[#111C30] border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
            <div className="p-5 border-b border-[#E5E7EB]">
              <AdminSectionHeader
                icon={Download}
                title={`Customer Download Activity (${order.downloads.length})`}
              />
            </div>

            {order.downloads.length === 0 ? (
              <p className="text-[13px] text-[#94A3B8] p-6">
                No downloads recorded for this order.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#18243A] border-b border-[#D5DEE8] text-[11.5px] font-semibold text-[#CBD5E1]">
                      <th className="py-3 px-4">Product</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Client IP</th>
                      <th className="py-3 px-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                    {order.downloads.map((d) => (
                      <tr key={d.id} className="hover:bg-[#18243A]/70 transition">
                        <td className="py-3 px-4 font-medium text-[#F1F5F9]">{d.product_name}</td>
                        <td className="py-3 px-4">
                          <AdminStatusBadge status={d.status} />
                        </td>
                        <td className="py-3 px-4 font-mono text-[12px] text-[#94A3B8]">
                          {d.ip_address || '—'}
                        </td>
                        <td className="py-3 px-4 text-[#94A3B8] tabular-nums whitespace-nowrap">
                          {formatAdminDateTime(d.downloaded_at)}
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
