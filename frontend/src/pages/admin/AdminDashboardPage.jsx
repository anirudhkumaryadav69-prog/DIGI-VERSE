import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  UserPlus,
  Package,
  FolderTree,
  CheckCircle2,
  ShoppingCart,
  IndianRupee,
  Clock,
  Download,
  Megaphone,
  TrendingUp,
  Plus,
  Activity,
  ArrowUpRight,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import { adminAuthApi, adminOperationsApi } from '../../services/api';

const STAT_CARDS = [
  { key: 'total_customers', label: 'Total Customers', icon: Users },
  { key: 'new_customers', label: 'New Customers (30d)', icon: UserPlus },
  { key: 'total_products', label: 'Total Products', icon: Package },
  { key: 'active_products', label: 'Active Products', icon: CheckCircle2 },
  { key: 'total_categories', label: 'Total Categories', icon: FolderTree },
  { key: 'total_orders', label: 'Total Orders', icon: ShoppingCart },
  { key: 'pending_orders', label: 'Pending Orders', icon: Clock },
  { key: 'total_sales_revenue', label: 'Total Order Revenue', icon: IndianRupee, isCurrency: true },
  { key: 'total_captured_revenue', label: 'Captured Payments', icon: IndianRupee, isCurrency: true },
  { key: 'average_order_value', label: 'Average Order Value', icon: TrendingUp, isCurrency: true },
  { key: 'total_downloads', label: 'Digital Downloads', icon: Download },
  { key: 'active_promotional_campaigns', label: 'Active Promotions', icon: Megaphone },
];

const AdminDashboardPage = () => {
  const [overview, setOverview] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([adminAuthApi.getDashboardOverview(), adminOperationsApi.getAnalytics()])
      .then(([overviewData, analyticsData]) => {
        setOverview(overviewData);
        setAnalytics(analyticsData);
        setError('');
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Unable to load dashboard statistics.');
      })
      .finally(() => setLoading(false));
  }, []);

  const formatCurrency = (val) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(val || 0));

  return (
    <AdminLayout
      title="Dashboard & SQL Analytics"
      subtitle="Live PostgreSQL marketplace telemetry, revenue trends, and catalog operations"
      actions={
        <>
          <Link
            to="/admin/categories/new"
            className="dv-btn-secondary text-xs font-semibold uppercase tracking-wider px-4 py-2.5 flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Category</span>
          </Link>
          <Link
            to="/admin/products/new"
            className="dv-btn-primary text-xs font-semibold uppercase tracking-wider px-4 py-2.5 flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Product</span>
          </Link>
        </>
      }
    >
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
          {error}
        </div>
      )}

      {/* 12 Live PostgreSQL Statistics Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {STAT_CARDS.map((card) => {
          const Icon = card.icon;
          const rawVal = overview?.metrics?.[card.key];
          const displayVal = loading
            ? '...'
            : card.isCurrency
            ? formatCurrency(rawVal)
            : (rawVal ?? 0);

          return (
            <div
              key={card.key}
              className="dv-card p-5 flex items-start justify-between hover:border-[#FFD4AE] transition"
            >
              <div>
                <p className="text-[11px] uppercase tracking-wider text-[#64748B] font-medium mb-2">
                  {card.label}
                </p>
                <p className="text-2xl font-bold text-[#1F2937]">{displayVal}</p>
              </div>
              <div className="w-10 h-10 rounded-xl bg-[#FFF2E6] border border-[#FFD4AE] flex items-center justify-center text-[#FF6B0A]">
                <Icon className="w-4 h-4" />
              </div>
            </div>
          );
        })}
      </section>

      {/* SQL Analytics: Best-Selling Products & Top Categories */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-8">
        {/* Best-Selling Products */}
        <section className="dv-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937]">
              Best-Selling Products
            </h2>
            <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#FFF2E6] text-[#D94300] font-semibold">
              90d Paid
            </span>
          </div>

          {!analytics?.best_selling_products?.length ? (
            <p className="text-xs text-[#64748B] py-6">No paid product sales in period.</p>
          ) : (
            <div className="divide-y divide-[#E5E7EB] text-xs">
              {analytics.best_selling_products.map((item, idx) => (
                <div
                  key={item.product_id || idx}
                  className="py-2.5 flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <p className="text-[#1F2937] font-semibold truncate">{item.product_name}</p>
                    <p className="text-[11px] text-[#64748B]">{item.units_sold} units sold</p>
                  </div>
                  <span className="font-mono font-bold text-[#F4510B] shrink-0">
                    {formatCurrency(item.total_revenue)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Top-Performing Categories */}
        <section className="dv-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937]">
              Top-Performing Categories
            </h2>
            <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#FFF2E6] text-[#D94300] font-semibold">
              By Revenue
            </span>
          </div>

          {!analytics?.top_categories?.length ? (
            <p className="text-xs text-[#64748B] py-6">No category revenue recorded yet.</p>
          ) : (
            <div className="divide-y divide-[#E5E7EB] text-xs">
              {analytics.top_categories.map((cat) => (
                <div
                  key={cat.category_id}
                  className="py-2.5 flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <p className="text-[#1F2937] font-semibold truncate">{cat.category_name}</p>
                    <p className="text-[11px] text-[#64748B]">{cat.units_sold} units sold</p>
                  </div>
                  <span className="font-mono font-bold text-[#F4510B] shrink-0">
                    {formatCurrency(cat.total_revenue)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Most Downloaded Digital Products */}
        <section className="dv-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937]">
              Most Downloaded Products
            </h2>
            <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#FFF2E6] text-[#D94300] font-semibold">
              Deliveries
            </span>
          </div>

          {!analytics?.most_downloaded_products?.length ? (
            <p className="text-xs text-[#64748B] py-6">No digital product downloads yet.</p>
          ) : (
            <div className="divide-y divide-[#E5E7EB] text-xs">
              {analytics.most_downloaded_products.map((dl, idx) => (
                <div
                  key={dl.product_id || idx}
                  className="py-2.5 flex items-center justify-between gap-3"
                >
                  <p className="text-[#1F2937] font-semibold truncate">{dl.product_name}</p>
                  <span className="font-mono font-semibold text-[#FF6B0A] shrink-0">
                    {dl.download_count} downloads
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-8">
        {/* Recently Added Products */}
        <section className="dv-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937]">
              Recently Added Products
            </h2>
            <Link
              to="/admin/products"
              className="text-xs font-semibold text-[#FF6B0A] hover:underline flex items-center gap-1"
            >
              <span>Manage All</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {!overview?.recent_products?.length ? (
            <p className="text-xs text-[#64748B] py-6">No products created yet.</p>
          ) : (
            <div className="divide-y divide-[#E5E7EB] text-xs">
              {overview.recent_products.map((p) => (
                <div key={p.id} className="py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <Link
                      to={`/admin/products/${p.id}/edit`}
                      className="font-semibold text-[#1F2937] hover:text-[#FF6B0A] truncate block"
                    >
                      {p.name}
                    </Link>
                    <span className="text-[11px] text-[#64748B]">{p.category_name}</span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="font-mono font-semibold text-[#F4510B]">
                      {formatCurrency(p.effective_price)}
                    </span>
                    <span
                      className={`text-[10px] uppercase tracking-wider rounded-full px-2.5 py-0.5 border font-medium ${
                        p.is_active
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-slate-100 text-[#64748B] border-[#E5E7EB]'
                      }`}
                    >
                      {p.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Recent Customer Registrations */}
        <section className="dv-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937]">
              Recent Customer Registrations
            </h2>
            <Link
              to="/admin/customers"
              className="text-xs font-semibold text-[#FF6B0A] hover:underline flex items-center gap-1"
            >
              <span>All Customers</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {!overview?.recent_registrations?.length ? (
            <p className="text-xs text-[#64748B] py-6">No customer registrations yet.</p>
          ) : (
            <div className="divide-y divide-[#E5E7EB] text-xs">
              {overview.recent_registrations.map((c) => (
                <div key={c.id} className="py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="font-semibold text-[#1F2937] truncate">{c.full_name}</p>
                    <p className="text-[11px] text-[#64748B] truncate">{c.email}</p>
                  </div>
                  <span
                    className={`text-[10px] uppercase tracking-wider rounded-full px-2.5 py-0.5 border font-medium shrink-0 ${
                      c.is_phone_verified
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-[#FFF2E6] text-[#D94300] border-[#FFD4AE]'
                    }`}
                  >
                    {c.is_phone_verified ? 'Verified' : 'Unverified'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Recent Orders Table */}
      <section className="dv-card p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937]">
            Recent Orders
          </h2>
          <Link
            to="/admin/orders"
            className="text-xs font-semibold text-[#FF6B0A] hover:underline flex items-center gap-1"
          >
            <span>Order Ledger</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {!overview?.recent_orders?.length ? (
          <p className="text-xs text-[#64748B] py-4">No orders placed yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#E5E7EB] text-[#64748B] uppercase">
                  <th className="py-2.5 pr-4">Order #</th>
                  <th className="py-2.5 pr-4">Customer</th>
                  <th className="py-2.5 pr-4">Amount</th>
                  <th className="py-2.5 pr-4">Order Status</th>
                  <th className="py-2.5 pr-4">Payment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB]">
                {overview.recent_orders.map((o) => (
                  <tr key={o.id}>
                    <td className="py-2.5 pr-4 font-mono font-semibold text-[#1F2937]">
                      {o.order_number}
                    </td>
                    <td className="py-2.5 pr-4">
                      <span className="block font-medium text-[#1F2937]">{o.customer_name}</span>
                      <span className="text-[11px] text-[#64748B]">{o.customer_email}</span>
                    </td>
                    <td className="py-2.5 pr-4 font-mono font-semibold text-[#F4510B]">
                      {formatCurrency(o.total_amount)}
                    </td>
                    <td className="py-2.5 pr-4 uppercase text-[11px] text-[#243247]">{o.status}</td>
                    <td className="py-2.5 pr-4 uppercase text-[11px] text-[#243247]">
                      {o.payment_status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Recent Audit Logs */}
      <section className="dv-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-[#FF6B0A]" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937]">
              Recent Administrative Audit Logs
            </h2>
          </div>
          <Link
            to="/admin/settings"
            className="text-xs font-semibold text-[#FF6B0A] hover:underline flex items-center gap-1"
          >
            <span>Full Audit Log</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {!overview?.recent_audit_logs?.length ? (
          <p className="text-xs text-[#64748B] py-4">No audit records yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#E5E7EB] text-[#64748B] uppercase">
                  <th className="py-2.5 pr-4">Action</th>
                  <th className="py-2.5 pr-4">Target Resource</th>
                  <th className="py-2.5 pr-4">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB]">
                {overview.recent_audit_logs.map((log) => (
                  <tr key={log.id}>
                    <td className="py-2.5 pr-4 font-mono font-medium text-[#D94300]">
                      {log.action}
                    </td>
                    <td className="py-2.5 pr-4 text-[#64748B]">
                      {log.entity_type} ({log.entity_id})
                    </td>
                    <td className="py-2.5 pr-4 text-[#64748B]">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AdminLayout>
  );
};

export default AdminDashboardPage;
