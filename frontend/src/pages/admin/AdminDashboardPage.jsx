import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Clock,
  Download,
  FolderTree,
  IndianRupee,
  Landmark,
  Megaphone,
  Package,
  Plus,
  ShoppingCart,
  Store,
  TrendingUp,
  UserPlus,
  Users,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  ErrorAlert,
  LoadingState,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import {
  AdminKpiCard,
  AdminSectionHeader,
  AdminStatusBadge,
  formatAdminDateTime,
} from '../../components/admin/AdminPrimitives';
import {
  adminAuthApi,
  adminCatalogApi,
  adminOperationsApi,
  adminPayoutApi,
  adminSellersApi,
} from '../../services/api';

const SECONDARY_STAT_CARDS = [
  { key: 'total_customers', label: 'Total Customers', icon: Users, tone: 'blue' },
  { key: 'new_customers', label: 'New Customers (30d)', icon: UserPlus, tone: 'blue' },
  { key: 'total_products', label: 'Total Products', icon: Package, tone: 'neutral' },
  { key: 'active_products', label: 'Active Products', icon: CheckCircle2, tone: 'success' },
  { key: 'total_categories', label: 'Total Categories', icon: FolderTree, tone: 'neutral' },
  { key: 'pending_orders', label: 'Pending Orders', icon: Clock, tone: 'warning' },
  { key: 'total_downloads', label: 'Digital Downloads', icon: Download, tone: 'blue' },
  { key: 'active_promotional_campaigns', label: 'Active Promotions', icon: Megaphone, tone: 'blue' },
];

const AdminDashboardPage = () => {
  const [overview, setOverview] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [queues, setQueues] = useState({
    pendingSellers: 0,
    submittedProducts: 0,
    requestedPayouts: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadDashboard = () => {
    setLoading(true);
    Promise.all([
      adminAuthApi.getDashboardOverview(),
      adminOperationsApi.getAnalytics(),
      adminSellersApi.listSellers({ status: 'pending', page_size: 1 }).catch(() => null),
      adminCatalogApi.listProducts({ approval_status: 'submitted', page_size: 1 }).catch(() => null),
      adminPayoutApi.listRequests({ status: 'requested', page_size: 1 }).catch(() => null),
    ])
      .then(([overviewData, analyticsData, sellerQueue, productQueue, payoutQueue]) => {
        setOverview(overviewData);
        setAnalytics(analyticsData);
        setQueues({
          pendingSellers: sellerQueue?.total ?? 0,
          submittedProducts: productQueue?.total ?? 0,
          requestedPayouts: payoutQueue?.total ?? 0,
        });
        setError('');
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Unable to load dashboard statistics.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const metrics = overview?.metrics || {};
  const pendingOrders = Number(metrics.pending_orders ?? 0);
  const totalAlerts =
    pendingOrders + queues.pendingSellers + queues.submittedProducts + queues.requestedPayouts;

  const maxProductRev = Math.max(
    1,
    ...(analytics?.best_selling_products || []).map((p) => Number(p.total_revenue || 0))
  );
  const maxCategoryRev = Math.max(
    1,
    ...(analytics?.top_categories || []).map((c) => Number(c.total_revenue || 0))
  );
  const maxDownloads = Math.max(
    1,
    ...(analytics?.most_downloaded_products || []).map((d) => Number(d.download_count || 0))
  );

  return (
    <AdminLayout
      title="Dashboard & Analytics"
      subtitle="Live PostgreSQL telemetry, revenue breakdown, approval queues, and recent audit activity"
      actions={
        <>
          <Link
            to="/admin/categories/new"
            className="dv-btn-secondary text-[12px] font-semibold px-4 py-2 inline-flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Category</span>
          </Link>
          <Link
            to="/admin/products/new"
            className="dv-btn-primary text-[12px] font-semibold px-4 py-2 inline-flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Product</span>
          </Link>
        </>
      }
    >
      {error && <ErrorAlert message={error} onRetry={loadDashboard} className="mb-6" />}

      {loading && !overview ? (
        <LoadingState label="Loading live dashboard telemetry..." />
      ) : (
        <div className="space-y-6">
          {/* Operational Alerts & Pending Approvals */}
          <section className="bg-white border border-[#D5DEE8] rounded-xl p-5 shadow-2xs">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2.5">
                <div
                  className={`w-8 h-8 rounded-lg border flex items-center justify-center ${
                    totalAlerts > 0
                      ? 'bg-amber-50 border-amber-200 text-[#D97706]'
                      : 'bg-emerald-50 border-emerald-200 text-[#16A34A]'
                  }`}
                >
                  {totalAlerts > 0 ? (
                    <AlertTriangle className="w-4 h-4" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4" />
                  )}
                </div>
                <div>
                  <h2 className="text-[14px] font-semibold text-[#263445]">
                    Pending Approvals & Operational Queues
                  </h2>
                  <p className="text-[12px] text-[#64748B]">
                    {totalAlerts > 0
                      ? `${totalAlerts} item(s) awaiting administrative review across orders, sellers, catalog, or payouts.`
                      : 'All administrative approval queues are clear.'}
                  </p>
                </div>
              </div>
              <Link
                to="/admin/payouts"
                className="text-[12px] font-semibold text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1"
              >
                <span>Open Payout Operations</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
              <AdminKpiCard
                compact
                label="Seller Applications"
                value={queues.pendingSellers}
                icon={Store}
                tone={queues.pendingSellers > 0 ? 'warning' : 'neutral'}
                hint="Pending onboarding review"
                to="/admin/sellers"
              />
              <AdminKpiCard
                compact
                label="Submitted Products"
                value={queues.submittedProducts}
                icon={Package}
                tone={queues.submittedProducts > 0 ? 'warning' : 'neutral'}
                hint="Awaiting catalog publication"
                to="/admin/products"
              />
              <AdminKpiCard
                compact
                label="Pending Orders"
                value={pendingOrders}
                icon={Clock}
                tone={pendingOrders > 0 ? 'warning' : 'neutral'}
                hint="Orders awaiting fulfillment"
                to="/admin/orders"
              />
              <AdminKpiCard
                compact
                label="Payout Requests"
                value={queues.requestedPayouts}
                icon={Landmark}
                tone={queues.requestedPayouts > 0 ? 'warning' : 'neutral'}
                hint="Seller settlement requests"
                to="/admin/payouts"
              />
            </div>
          </section>

          {/* Primary Financial & Order KPIs */}
          <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <AdminKpiCard
              label="Total Order Revenue"
              value={formatINR(metrics.total_sales_revenue)}
              icon={IndianRupee}
              tone="blue"
            />
            <AdminKpiCard
              label="Captured Payments"
              value={formatINR(metrics.total_captured_revenue)}
              icon={CheckCircle2}
              tone="success"
            />
            <AdminKpiCard
              label="Average Order Value"
              value={formatINR(metrics.average_order_value)}
              icon={TrendingUp}
              tone="blue"
            />
            <AdminKpiCard
              label="Total Orders"
              value={metrics.total_orders ?? 0}
              icon={ShoppingCart}
              tone="neutral"
            />
          </section>

          {/* Marketplace & Operations Metrics */}
          <section className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-3.5">
            {SECONDARY_STAT_CARDS.map((card) => (
              <AdminKpiCard
                key={card.key}
                compact
                label={card.label}
                value={metrics[card.key] ?? 0}
                icon={card.icon}
                tone={card.tone}
              />
            ))}
          </section>

          {/* Visual Revenue & Engagement Summaries */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
            <section className="bg-white border border-[#D5DEE8] rounded-xl p-5 shadow-2xs">
              <AdminSectionHeader
                icon={TrendingUp}
                title="Best-Selling Products"
                badge={<AdminStatusBadge status="processing" label="90d Paid" />}
              />

              {!analytics?.best_selling_products?.length ? (
                <p className="text-[12.5px] text-[#64748B] py-8 text-center">
                  No paid product sales recorded in this period.
                </p>
              ) : (
                <div className="mt-4 space-y-3.5">
                  {analytics.best_selling_products.map((item, idx) => {
                    const rev = Number(item.total_revenue || 0);
                    const pct = Math.max(4, Math.round((rev / maxProductRev) * 100));
                    return (
                      <div key={item.product_id || idx} className="space-y-1.5">
                        <div className="flex items-center justify-between gap-3 text-[12.5px]">
                          <span className="font-medium text-[#263445] truncate">
                            {item.product_name}
                          </span>
                          <span className="font-mono font-semibold text-[#1D4ED8] shrink-0 tabular-nums">
                            {formatINR(rev)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 rounded-full bg-[#EDF5FC] overflow-hidden">
                            <div
                              className="h-full rounded-full bg-[#2563EB]"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-[11px] text-[#64748B] tabular-nums shrink-0">
                            {item.units_sold} sold
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="bg-white border border-[#D5DEE8] rounded-xl p-5 shadow-2xs">
              <AdminSectionHeader
                icon={BarChart3}
                title="Top Categories"
                badge={<AdminStatusBadge status="processing" label="By Revenue" />}
              />

              {!analytics?.top_categories?.length ? (
                <p className="text-[12.5px] text-[#64748B] py-8 text-center">
                  No category revenue recorded yet.
                </p>
              ) : (
                <div className="mt-4 space-y-3.5">
                  {analytics.top_categories.map((cat) => {
                    const rev = Number(cat.total_revenue || 0);
                    const pct = Math.max(4, Math.round((rev / maxCategoryRev) * 100));
                    return (
                      <div key={cat.category_id} className="space-y-1.5">
                        <div className="flex items-center justify-between gap-3 text-[12.5px]">
                          <span className="font-medium text-[#263445] truncate">
                            {cat.category_name}
                          </span>
                          <span className="font-mono font-semibold text-[#15803D] shrink-0 tabular-nums">
                            {formatINR(rev)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 rounded-full bg-[#F8FAFC] overflow-hidden">
                            <div
                              className="h-full rounded-full bg-[#16A34A]"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-[11px] text-[#64748B] tabular-nums shrink-0">
                            {cat.units_sold} units
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="bg-white border border-[#D5DEE8] rounded-xl p-5 shadow-2xs">
              <AdminSectionHeader
                icon={Download}
                title="Most Downloaded Assets"
                badge={<AdminStatusBadge status="processing" label="Deliveries" />}
              />

              {!analytics?.most_downloaded_products?.length ? (
                <p className="text-[12.5px] text-[#64748B] py-8 text-center">
                  No digital product downloads recorded yet.
                </p>
              ) : (
                <div className="mt-4 space-y-3.5">
                  {analytics.most_downloaded_products.map((dl, idx) => {
                    const count = Number(dl.download_count || 0);
                    const pct = Math.max(4, Math.round((count / maxDownloads) * 100));
                    return (
                      <div key={dl.product_id || idx} className="space-y-1.5">
                        <div className="flex items-center justify-between gap-3 text-[12.5px]">
                          <span className="font-medium text-[#263445] truncate">
                            {dl.product_name}
                          </span>
                          <span className="font-mono font-semibold text-[#0284C7] shrink-0 tabular-nums">
                            {count}
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-[#EDF5FC] overflow-hidden">
                          <div
                            className="h-full rounded-full bg-[#0EA5E9]"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>

          {/* Recent Catalog & Registrations */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <section className="bg-white border border-[#D5DEE8] rounded-xl p-5 shadow-2xs">
              <AdminSectionHeader
                icon={Package}
                title="Recently Added Products"
                action={
                  <Link
                    to="/admin/products"
                    className="text-[12px] font-semibold text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1"
                  >
                    <span>Manage All</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                }
              />

              {!overview?.recent_products?.length ? (
                <p className="text-[12.5px] text-[#64748B] py-6">No products created yet.</p>
              ) : (
                <div className="divide-y divide-[#E5E7EB] mt-4">
                  {overview.recent_products.map((p) => (
                    <div key={p.id} className="py-3 flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <Link
                          to={`/admin/products/${p.id}/edit`}
                          className="text-[13px] font-semibold text-[#263445] hover:text-[#2563EB] truncate block"
                        >
                          {p.name}
                        </Link>
                        <span className="text-[12px] text-[#64748B]">{p.category_name}</span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="font-mono text-[13px] font-semibold text-[#263445] tabular-nums">
                          {formatINR(p.effective_price)}
                        </span>
                        <AdminStatusBadge status={p.is_active ? 'active' : 'inactive'} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="bg-white border border-[#D5DEE8] rounded-xl p-5 shadow-2xs">
              <AdminSectionHeader
                icon={Users}
                title="Recent Customer Registrations"
                action={
                  <Link
                    to="/admin/customers"
                    className="text-[12px] font-semibold text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1"
                  >
                    <span>All Customers</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                }
              />

              {!overview?.recent_registrations?.length ? (
                <p className="text-[12.5px] text-[#64748B] py-6">
                  No customer registrations yet.
                </p>
              ) : (
                <div className="divide-y divide-[#E5E7EB] mt-4">
                  {overview.recent_registrations.map((c) => (
                    <div key={c.id} className="py-3 flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-[13px] font-semibold text-[#263445] truncate">
                          {c.full_name}
                        </p>
                        <p className="text-[12px] text-[#64748B] truncate">{c.email}</p>
                      </div>
                      <AdminStatusBadge
                        status={c.is_phone_verified ? 'verified' : 'pending'}
                        label={c.is_phone_verified ? 'Phone Verified' : 'Unverified'}
                      />
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* Recent Orders Table */}
          <section className="bg-white border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
            <div className="p-5 border-b border-[#E5E7EB]">
              <AdminSectionHeader
                icon={ShoppingCart}
                title="Recent Orders"
                action={
                  <Link
                    to="/admin/orders"
                    className="text-[12px] font-semibold text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1"
                  >
                    <span>Order Ledger</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                }
              />
            </div>

            {!overview?.recent_orders?.length ? (
              <p className="text-[12.5px] text-[#64748B] p-6">No orders placed yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#F8FAFC] border-b border-[#D5DEE8] text-[11.5px] font-semibold text-[#475569]">
                      <th className="py-3 px-4">Order</th>
                      <th className="py-3 px-4">Customer</th>
                      <th className="py-3 px-4">Amount</th>
                      <th className="py-3 px-4">Order Status</th>
                      <th className="py-3 px-4">Payment</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                    {overview.recent_orders.map((o) => (
                      <tr key={o.id} className="hover:bg-[#EDF5FC]/45 transition">
                        <td className="py-3 px-4 font-mono font-semibold text-[#263445]">
                          <Link
                            to={`/admin/orders/${o.id}`}
                            className="hover:text-[#2563EB] hover:underline"
                          >
                            {o.order_number}
                          </Link>
                        </td>
                        <td className="py-3 px-4">
                          <span className="block font-medium text-[#263445]">
                            {o.customer_name}
                          </span>
                          <span className="text-[11.5px] text-[#64748B]">
                            {o.customer_email}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono font-semibold text-[#1D4ED8] tabular-nums">
                          {formatINR(o.total_amount)}
                        </td>
                        <td className="py-3 px-4">
                          <AdminStatusBadge status={o.status} />
                        </td>
                        <td className="py-3 px-4">
                          <AdminStatusBadge status={o.payment_status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Recent Administrative Audit Logs */}
          <section className="bg-white border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
            <div className="p-5 border-b border-[#E5E7EB]">
              <AdminSectionHeader
                icon={Activity}
                title="Recent Administrative Audit Logs"
                action={
                  <Link
                    to="/admin/settings"
                    className="text-[12px] font-semibold text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1"
                  >
                    <span>Full Audit Log</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                }
              />
            </div>

            {!overview?.recent_audit_logs?.length ? (
              <p className="text-[12.5px] text-[#64748B] p-6">No audit records yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#F8FAFC] border-b border-[#D5DEE8] text-[11.5px] font-semibold text-[#475569]">
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4">Target Resource</th>
                      <th className="py-3 px-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                    {overview.recent_audit_logs.map((log) => (
                      <tr key={log.id} className="hover:bg-[#EDF5FC]/45 transition">
                        <td className="py-3 px-4 font-mono text-[12px] font-medium text-[#1D4ED8]">
                          {log.action}
                        </td>
                        <td className="py-3 px-4 text-[#475569]">
                          {log.entity_type} {log.entity_id ? `(${log.entity_id})` : ''}
                        </td>
                        <td className="py-3 px-4 text-[#64748B] tabular-nums whitespace-nowrap">
                          {formatAdminDateTime(log.created_at)}
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

export default AdminDashboardPage;
