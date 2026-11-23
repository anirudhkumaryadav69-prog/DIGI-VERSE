import { useEffect, useState } from 'react';
import { BarChart3, Download, IndianRupee, Package, ShoppingBag } from 'lucide-react';
import SellerLayout from '../../layouts/SellerLayout';
import {
  Badge,
  ErrorAlert,
  LoadingState,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import { sellerApi } from '../../services/api';

const SellerAnalyticsPage = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    sellerApi
      .getAnalytics()
      .then((res) => setAnalytics(res))
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load seller analytics.');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <SellerLayout title="Sales Analytics">
        <LoadingState label="Computing product performance..." />
      </SellerLayout>
    );
  }

  return (
    <SellerLayout
      title="Sales Analytics"
      subtitle="Product-level gross sales, unit volume, and digital asset delivery metrics"
    >
      {error && <ErrorAlert message={error} />}

      {analytics && (
        <div className="space-y-6">
          <div className="bg-[#18243A] border border-[#BFDBFE] rounded-2xl px-5 py-3 text-xs text-[#93C5FD]">
            Metrics below show <strong>Gross Product Sales</strong> across your paid orders. Platform fee splits and payout ledgers are scheduled for Phase 10.
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-5 shadow-xs">
              <p className="text-xs text-[#94A3B8] flex items-center justify-between">
                <span>Gross Product Sales</span>
                <IndianRupee className="w-4 h-4 text-[#60A5FA]" />
              </p>
              <p className="text-2xl font-bold font-mono text-[#93C5FD] mt-2">
                {formatINR(analytics.gross_product_sales)}
              </p>
            </div>

            <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-5 shadow-xs">
              <p className="text-xs text-[#94A3B8] flex items-center justify-between">
                <span>Units Sold / Orders</span>
                <ShoppingBag className="w-4 h-4 text-[#60A5FA]" />
              </p>
              <p className="text-2xl font-bold text-[#F1F5F9] mt-2">
                {analytics.total_units_sold}{' '}
                <span className="text-xs font-normal text-[#94A3B8]">
                  across {analytics.total_orders} orders
                </span>
              </p>
            </div>

            <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-5 shadow-xs">
              <p className="text-xs text-[#94A3B8] flex items-center justify-between">
                <span>Verified Downloads</span>
                <Download className="w-4 h-4 text-[#60A5FA]" />
              </p>
              <p className="text-2xl font-bold text-[#F1F5F9] mt-2">{analytics.total_downloads}</p>
            </div>
          </div>

          <section className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl overflow-hidden shadow-xs">
            <div className="px-6 py-4 border-b border-[#E5E7EB] flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-[#60A5FA]" />
              <h2 className="text-sm font-bold text-[#F1F5F9]">Product Performance Breakdown</h2>
            </div>

            {!analytics.product_breakdown?.length ? (
              <div className="p-8 text-center text-xs text-[#94A3B8]">
                <Package className="w-6 h-6 text-[#60A5FA] mx-auto mb-2" />
                No seller products recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-[#18243A] border-b border-[#E5E7EB] text-[12px] font-semibold text-[#94A3B8]">
                      <th className="py-3 px-4">Product</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Units Sold</th>
                      <th className="py-3 px-4 text-right">Downloads</th>
                      <th className="py-3 px-4 text-right">Gross Product Sales</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB]">
                    {analytics.product_breakdown.map((row) => (
                      <tr key={row.product_id} className="hover:bg-[#18243A]">
                        <td className="py-3 px-4 font-semibold text-[#F1F5F9]">{row.name}</td>
                        <td className="py-3 px-4">
                          <Badge variant={row.approval_status === 'published' ? 'success' : 'neutral'}>
                            {row.approval_status}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-right font-mono">{row.units_sold}</td>
                        <td className="py-3 px-4 text-right font-mono">{row.downloads_count}</td>
                        <td className="py-3 px-4 text-right font-mono font-bold text-[#93C5FD]">
                          {formatINR(row.gross_sales)}
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
    </SellerLayout>
  );
};

export default SellerAnalyticsPage;
