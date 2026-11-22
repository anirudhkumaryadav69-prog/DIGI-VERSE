import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  Minus,
  Plus,
  RefreshCw,
  ShoppingBag,
  Trash2,
} from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  LoadingState,
  SectionHeading,
  ToastBanner,
  formatINR,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { commerceApi } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { resolveProductThumbnailUrl } from '../../utils/productThumbnails';

const CartPage = () => {
  const navigate = useNavigate();
  const { refreshCartAndWishlistCounts } = useAuth();
  const [cart, setCart] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const [toast, setToast] = useState({ type: '', message: '' });

  useDocumentMeta({
    title: 'Shopping Cart',
    description: 'Review your selected digital products and proceed to encrypted checkout.',
    canonicalPath: '/cart',
  });

  const fetchCart = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await commerceApi.getCart();
      setCart(res);
    } catch {
      setError('Unable to load your shopping cart.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCart();
  }, [fetchCart]);

  const handleQuantityChange = async (item, newQty) => {
    if (newQty < 1 || newQty > 100) return;
    try {
      const res = await commerceApi.updateCartItem(item.id, newQty);
      setCart(res);
      await refreshCartAndWishlistCounts();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not update quantity.',
      });
      await fetchCart();
    }
  };

  const handleRemoveItem = async (item) => {
    try {
      const res = await commerceApi.removeCartItem(item.id);
      setCart(res);
      await refreshCartAndWishlistCounts();
      setToast({ type: 'success', message: `"${item.product_name}" removed from cart.` });
    } catch {
      setToast({ type: 'error', message: 'Could not remove item.' });
    }
  };

  const handleConfirmClearCart = async () => {
    setConfirmClearOpen(false);
    try {
      const res = await commerceApi.clearCart();
      setCart(res);
      await refreshCartAndWishlistCounts();
      setToast({ type: 'success', message: 'Shopping cart cleared.' });
    } catch {
      setToast({ type: 'error', message: 'Failed to clear cart.' });
    }
  };

  const hasUnavailableItems = Boolean(
    cart?.items?.some((item) => item.is_available === false)
  );

  return (
    <StorefrontLayout>
      <SectionHeading
        eyebrow="Order Preparation"
        title={`Shopping Cart (${cart?.total_quantity || 0})`}
        subtitle="All unit prices, promotional discounts, and totals are calculated authoritatively on the server."
        action={
          cart?.items?.length > 0 && (
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={fetchCart}>
                <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Refresh Prices</span>
              </Button>
              <Button variant="danger" size="sm" onClick={() => setConfirmClearOpen(true)}>
                Clear Cart
              </Button>
            </div>
          )
        }
      />

      <ConfirmDialog
        open={confirmClearOpen}
        title="Clear Shopping Cart?"
        description="Are you sure you want to remove all items from your shopping cart?"
        confirmLabel="Clear Cart"
        onConfirm={handleConfirmClearCart}
        onCancel={() => setConfirmClearOpen(false)}
      />

      {toast.message && (
        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
          className="mb-6"
        />
      )}

      {error && <ErrorAlert message={error} onRetry={fetchCart} className="mb-6" />}

      {hasUnavailableItems && (
        <div
          role="alert"
          className="mb-6 p-4 rounded-xl bg-[#EAF4FC] border border-[#BFDBFE] text-[#1D4ED8] text-xs flex items-center gap-2.5"
        >
          <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>
            One or more items in your cart are no longer available. Please remove unavailable items
            before proceeding to checkout.
          </span>
        </div>
      )}

      {loading ? (
        <LoadingState label="Loading Shopping Cart..." />
      ) : !cart?.items?.length ? (
        <EmptyState
          icon={ShoppingBag}
          title="Your shopping cart is empty"
          description="Discover digital products in our catalog and add them to your cart to begin checkout."
          action={
            <Link
              to="/products"
              className="dv-btn-primary inline-flex items-center gap-2 text-[13px] font-semibold px-6 py-3"
            >
              <span>Continue Shopping</span>
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Cart Items List */}
          <div className="lg:col-span-8 dv-card divide-y divide-[#E5E7EB] overflow-hidden">
            {cart.items.map((item) => (
              <div
                key={item.id}
                className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-[#EDF5FC]/40 transition"
              >
                <div className="flex items-center gap-4">
                  <Link
                    to={`/products/${item.product_slug}`}
                    className="w-20 h-16 rounded-xl bg-[#F8FAFC] border border-[#E5E7EB] shrink-0 overflow-hidden flex items-center justify-center"
                  >
                    <img
                      src={resolveProductThumbnailUrl(
                        {
                          slug: item.product_slug,
                          name: item.product_name,
                          category: { name: item.category_name },
                        },
                        item.thumbnail_url,
                        0
                      )}
                      alt={item.product_name}
                      loading="lazy"
                      className="w-full h-full object-cover"
                    />
                  </Link>

                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-[11px] text-[#2563EB] font-semibold">
                        {item.category_name}
                      </p>
                      {item.is_available === false && (
                        <span className="text-[11px] font-medium rounded-full px-2 py-0.5 bg-red-50 text-red-700 border border-red-200">
                          Unavailable
                        </span>
                      )}
                    </div>
                    <Link
                      to={`/products/${item.product_slug}`}
                      className="text-sm font-semibold text-[#263445] hover:text-[#2563EB] transition"
                    >
                      {item.product_name}
                    </Link>
                    <div className="font-mono text-xs mt-1">
                      <span className="font-bold text-[#1D4ED8]">
                        {formatINR(item.effective_unit_price)}
                      </span>
                      {item.active_discount && (
                        <>
                          <span className="line-through text-[#64748B] ml-2">
                            {formatINR(item.unit_price)}
                          </span>
                          <span className="text-emerald-700 ml-2 font-medium">
                            (-{item.active_discount.discount_percentage}%)
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between sm:justify-end gap-5">
                  {/* Quantity Controls */}
                  <div className="inline-flex items-center rounded-xl border border-[#E5E7EB] bg-[#EAF4FC] overflow-hidden">
                    <button
                      type="button"
                      disabled={item.quantity <= 1 || item.is_available === false}
                      onClick={() => handleQuantityChange(item, item.quantity - 1)}
                      aria-label={`Decrease quantity for ${item.product_name}`}
                      className="p-2 text-[#263445] hover:bg-[#EDF5FC] hover:text-[#1D4ED8] disabled:opacity-40 transition"
                    >
                      <Minus className="w-3 h-3" aria-hidden="true" />
                    </button>
                    <span className="px-3 text-xs font-mono font-semibold text-[#263445]" aria-label="Quantity">
                      {item.quantity}
                    </span>
                    <button
                      type="button"
                      disabled={item.is_available === false}
                      onClick={() => handleQuantityChange(item, item.quantity + 1)}
                      aria-label={`Increase quantity for ${item.product_name}`}
                      className="p-2 text-[#263445] hover:bg-[#EDF5FC] hover:text-[#1D4ED8] disabled:opacity-40 transition"
                    >
                      <Plus className="w-3 h-3" aria-hidden="true" />
                    </button>
                  </div>

                  <div className="text-right font-mono min-w-[90px]">
                    <p className="text-sm font-bold text-[#263445]">
                      {formatINR(item.line_total)}
                    </p>
                    {Number(item.line_discount) > 0 && (
                      <p className="text-[11px] text-emerald-700">
                        Saved {formatINR(item.line_discount)}
                      </p>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => handleRemoveItem(item)}
                    aria-label={`Remove ${item.product_name} from cart`}
                    title="Remove item"
                    className="p-2 rounded-lg text-[#64748B] hover:text-red-600 hover:bg-red-50 transition"
                  >
                    <Trash2 className="w-4 h-4" aria-hidden="true" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Order Summary Sidebar */}
          <aside className="lg:col-span-4 dv-card-warm p-6 space-y-5">
            <h2 className="text-sm font-semibold text-[#263445] border-b border-[#E5E7EB] pb-3">
              Order Summary
            </h2>

            <div className="space-y-3 text-xs">
              <div className="flex justify-between text-[#64748B]">
                <span>Subtotal ({cart.total_quantity} items)</span>
                <span className="font-mono font-medium text-[#263445]">{formatINR(cart.subtotal)}</span>
              </div>

              <div className="flex justify-between text-emerald-700">
                <span>Promotional Discount</span>
                <span className="font-mono">-{formatINR(cart.total_discount)}</span>
              </div>

              <div className="pt-3 border-t border-[#E5E7EB] flex justify-between items-baseline text-sm font-semibold text-[#263445]">
                <span>Final Payable</span>
                <span className="font-mono text-xl font-bold text-[#1D4ED8]">
                  {formatINR(cart.final_payable_amount)}
                </span>
              </div>
            </div>

            <button
              type="button"
              disabled={hasUnavailableItems}
              onClick={() => navigate('/checkout')}
              className="dv-btn-primary w-full py-3.5 px-4 text-[13px] font-semibold flex items-center justify-center gap-2 disabled:opacity-40"
            >
              <span>Proceed to Checkout</span>
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </button>

            <Link
              to="/products"
              className="block text-center text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] hover:underline"
            >
              ← Continue Shopping
            </Link>
          </aside>
        </div>
      )}
    </StorefrontLayout>
  );
};

export default CartPage;
