import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  FileEdit,
  IndianRupee,
  Package,
  Plus,
  ShoppingBag,
  TrendingUp,
} from 'lucide-react';
import SellerLayout from '../../layouts/SellerLayout';
import {
  Badge,
  ErrorAlert,
  LoadingState,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import { sellerApi } from '../../services/api';

const STATUS_BADGE = {
  published: { label: 'Published', variant: 'success' },
  pending_review: { label: 'Pending Review', variant: 'orange' },
  draft: { label: 'Draft', variant: 'neutral' },
  rejected: { label: 'Rejected', variant: 'danger' },
  archived: { label: 'Archived', variant: 'neutral' },
};

const SellerOverviewPage = () => {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    sellerApi
      .getOverview()
      .then((res) => setOverview(res))
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load seller overview.');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <SellerLayout title="Seller Overview" subtitle="Store performance & product readiness">
        <LoadingState label="Loading your seller studio..." />
      </SellerLayout>
    );
  }

  return (
    <SellerLayout
      title={overview ? `${overview.store_name} Overview` : 'Seller Overview'}
      subtitle="Marketplace performance, product inventory, and recent seller order activity"
      actions={
        <Link to="/seller/products/new" className="dv-btn-primary px-4 py-2 text-xs inline-flex items-center gap-1.5">
          <Plus className="w-4 h-4" />
          <span>Add Product</span>
        </Link>
      }
    >
      {error && <ErrorAlert message={error} />}

      {overview && (
        <div className="space-y-6">
          {/* Gross Product Sales Disclaimer */}
          <div className="bg-[#FFF2E6] border border-[#FFD4AE] rounded-2xl px-5 py-3.5 text-xs text-[#D94300] flex flex-wrap items-center justify-between gap-2">
            <span>
              Revenue figures below reflect <strong>Gross Product Sales</strong> from your seller-owned items only. Commission splits and payouts will be introduced in Phase 10.
            </span>
            <Link to={`/store/${overview.store_slug}`} className="font-semibold underline">
              /store/{overview.store_slug}
            </Link>
          </div>

          {/* KPI Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 shadow-xs">
              <div className="flex items-center justify-between text-xs text-[#64748B]">
                <span>Total Products</span>
                <Package className="w-4 h-4 text-[#FF6B0A]" />
              </div>
              <p className="text-2xl font-bold text-[#1F2937] mt-2">{overview.total_products}</p>
              <p className="text-[11px] text-[#64748B] mt-1">
                {overview.published_products} published · {overview.draft_products} drafts
              </p>
            </div>

            <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 shadow-xs">
              <div className="flex items-center justify-between text-xs text-[#64748B]">
                <span>Review Pipeline</span>
                <Clock className="w-4 h-4 text-[#FF6B0A]" />
              </div>
              <p className="text-2xl font-bold text-[#1F2937] mt-2">
                {overview.pending_review_products}
              </p>
              <p className="text-[11px] text-[#64748B] mt-1">
                Pending admin approval · {overview.rejected_products} rejected
              </p>
            </div>

            <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 shadow-xs">
              <div className="flex items-center justify-between text-xs text-[#64748B]">
                <span>Orders & Units Sold</span>
                <ShoppingBag className="w-4 h-4 text-[#FF6B0A]" />
              </div>
              <p className="text-2xl font-bold text-[#1F2937] mt-2">{overview.total_orders}</p>
              <p className="text-[11px] text-[#64748B] mt-1">
                {overview.paid_orders} paid orders · {overview.total_units_sold} units sold
              </p>
            </div>

            <div className="bg-white border border-[#FFD4AE] rounded-2xl p-5 shadow-xs bg-linear-to-br from-white to-[#FFF6ED]">
              <div className="flex items-center justify-between text-xs font-semibold text-[#D94300]">
                <span>Gross Product Sales</span>
                <IndianRupee className="w-4 h-4 text-[#FF6B0A]" />
              </div>
              <p className="text-2xl font-bold text-[#F4510B] font-mono mt-2">
                {formatINR(overview.gross_product_sales)}
              </p>
              <p className="text-[11px] text-[#64748B] mt-1">
                Gross sales (not payout balance)
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Products */}
            <section className="bg-white border border-[#E5E7EB] rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-[#1F2937] flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-[#FF6B0A]" />
                  Best-Performing Products
                </h2>
                <Link to="/seller/analytics" className="text-xs font-semibold text-[#FF6B0A] hover:underline">
                  Full Analytics
                </Link>
              </div>
              {!overview.top_products?.length ? (
                <p className="text-xs text-[#64748B] py-6 text-center">
                  Create and publish your first digital product to see performance data.
                </p>
              ) : (
                <div className="space-y-3">
                  {overview.top_products.map((item) => {
                    const st = STATUS_BADGE[item.approval_status] || STATUS_BADGE.draft;
                    return (
                      <div
                        key={item.product_id}
                        className="flex items-center justify-between gap-3 p-3 rounded-xl border border-[#E5E7EB] bg-[#FFFAF5]"
                      >
                        <div className="min-w-0">
                          <Link
                            to={`/seller/products/${item.product_id}/edit`}
                            className="text-xs font-semibold text-[#1F2937] hover:text-[#FF6B0A] truncate block"
                          >
                            {item.name}
                          </Link>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant={st.variant}>{st.label}</Badge>
                            <span className="text-[11px] text-[#64748B]">
                              {item.units_sold} sold · {item.downloads_count} downloads
                            </span>
                          </div>
                        </div>
                        <span className="text-xs font-bold font-mono text-[#F4510B] shrink-0">
                          {formatINR(item.gross_sales)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* Recent Seller Orders */}
            <section className="bg-white border border-[#E5E7EB] rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-[#1F2937] flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-[#FF6B0A]" />
                  Recent Order Activity
                </h2>
                <Link to="/seller/orders" className="text-xs font-semibold text-[#FF6B0A] hover:underline inline-flex items-center gap-1">
                  All Orders <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
              {!overview.recent_orders?.length ? (
                <p className="text-xs text-[#64748B] py-6 text-center">
                  No customer orders contain your products yet.
                </p>
              ) : (
                <div className="space-y-3">
                  {overview.recent_orders.map((ord) => (
                    <div
                      key={ord.order_id}
                      className="flex items-center justify-between gap-3 p-3 rounded-xl border border-[#E5E7EB] bg-[#FFFAF5]"
                    >
                      <div className="min-w-0">
                        <p className="text-xs font-mono font-bold text-[#1F2937]">
                          {ord.order_number}
                        </p>
                        <p className="text-[11px] text-[#64748B] mt-0.5">
                          {ord.seller_units_count} unit(s) · Payment: {ord.payment_status} · Fulfilment: {ord.download_fulfilment_status}
                        </p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-xs font-bold font-mono text-[#1F2937]">
                          {formatINR(ord.seller_items_subtotal)}
                        </p>
                        <p className="text-[10px] text-[#64748B]">
                          {new Date(ord.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* Quick Actions Footer */}
          <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <FileEdit className="w-5 h-5 text-[#FF6B0A]" />
              <div>
                <p className="text-xs font-semibold text-[#1F2937]">Ready to launch a new digital release?</p>
                <p className="text-[11px] text-[#64748B]">
                  Upload your binary archive privately, add storefront images, and submit for marketplace review.
                </p>
              </div>
            </div>
            <Link to="/seller/products/new" className="dv-btn-secondary px-4 py-2 text-xs font-semibold">
              Create Listing
            </Link>
          </div>
        </div>
      )}
    </SellerLayout>
  );
};

export default SellerOverviewPage;
