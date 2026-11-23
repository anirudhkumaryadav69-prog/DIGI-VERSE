import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Heart, ShoppingBag, Trash2, XCircle } from 'lucide-react';
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

const WishlistPage = () => {
  const { refreshCartAndWishlistCounts } = useAuth();
  const [wishlist, setWishlist] = useState({ items: [], total_items: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const [toast, setToast] = useState({ type: '', message: '' });

  useDocumentMeta({
    title: 'Saved Wishlist',
    description: 'Manage your saved digital products and move items to your shopping cart.',
    canonicalPath: '/wishlist',
  });

  const fetchWishlist = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await commerceApi.getWishlist();
      setWishlist(res);
    } catch {
      setError('Unable to load your saved wishlist.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWishlist();
  }, [fetchWishlist]);

  const handleRemove = async (productId, name) => {
    try {
      const res = await commerceApi.removeFromWishlist(productId);
      setWishlist(res);
      await refreshCartAndWishlistCounts();
      setToast({ type: 'success', message: `"${name}" removed from wishlist.` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not remove item.',
      });
    }
  };

  const handleMoveToCart = async (item) => {
    setToast({ type: '', message: '' });
    try {
      try {
        await commerceApi.addToCart(item.product_id, 1);
      } catch (addErr) {
        // If already in cart (409), still allow removing from wishlist
        if (addErr.response?.status !== 409) {
          throw addErr;
        }
      }
      const res = await commerceApi.removeFromWishlist(item.product_id);
      setWishlist(res);
      await refreshCartAndWishlistCounts();
      setToast({ type: 'success', message: `"${item.product_name}" moved to shopping cart.` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not move product to cart.',
      });
    }
  };

  const handleConfirmClear = async () => {
    setConfirmClearOpen(false);
    try {
      const res = await commerceApi.clearWishlist();
      setWishlist(res);
      await refreshCartAndWishlistCounts();
      setToast({ type: 'success', message: 'Wishlist cleared.' });
    } catch {
      setToast({ type: 'error', message: 'Failed to clear wishlist.' });
    }
  };

  return (
    <StorefrontLayout>
      <SectionHeading
        eyebrow="Saved Collection"
        title={`Your Wishlist (${wishlist.total_items})`}
        subtitle="Save digital products for later and move available items directly into your cart."
        action={
          wishlist.items.length > 0 && (
            <Button variant="danger" size="sm" onClick={() => setConfirmClearOpen(true)}>
              Clear Wishlist
            </Button>
          )
        }
      />

      <ConfirmDialog
        open={confirmClearOpen}
        title="Clear Saved Wishlist?"
        description="This will remove all saved products from your wishlist. You can re-add them from the catalog anytime."
        confirmLabel="Clear Wishlist"
        onConfirm={handleConfirmClear}
        onCancel={() => setConfirmClearOpen(false)}
      />

      {toast.message && (
        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
          className="mb-6"
        />
      )}

      {error && <ErrorAlert message={error} onRetry={fetchWishlist} className="mb-6" />}

      {loading ? (
        <LoadingState label="Loading Saved Wishlist..." />
      ) : wishlist.items.length === 0 ? (
        <EmptyState
          icon={Heart}
          title="Your wishlist is currently empty"
          description="Explore our catalog and click the heart icon on any digital product to save it here."
          action={
            <Link
              to="/products"
              className="dv-btn-primary inline-flex items-center gap-2 text-[13px] font-semibold px-6 py-3"
            >
              <span>Browse Digital Catalog</span>
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {wishlist.items.map((item) => (
            <article
              key={item.id}
              className="dv-card-interactive flex flex-col justify-between overflow-hidden"
            >
              <div>
                <Link
                  to={`/products/${item.product_slug}`}
                  className="block aspect-16/10 bg-[#18243A] relative border-b border-[#E5E7EB]"
                >
                  <img
                    src={resolveProductThumbnailUrl(
                      {
                        slug: item.product_slug,
                        name: item.product_name,
                        category: { name: item.category_name },
                      },
                      item.image_url,
                      0
                    )}
                    alt={item.product_name}
                    loading="lazy"
                    className="w-full h-full object-cover"
                  />
                  {item.is_on_sale && item.active_discount && (
                    <span className="absolute top-2.5 right-3 rounded-full bg-[#16A34A] text-white text-[11px] font-semibold px-2.5 py-0.5 shadow-xs">
                      -{item.active_discount.discount_percentage}% OFF
                    </span>
                  )}
                </Link>

                <div className="p-5 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] text-[#60A5FA] font-semibold">
                      {item.category_name}
                    </p>
                    <span
                      className={`inline-flex items-center gap-1 text-[11px] font-medium ${
                        item.is_available ? 'text-emerald-300' : 'text-red-300'
                      }`}
                    >
                      {item.is_available ? (
                        <>
                          <CheckCircle2 className="w-3 h-3" aria-hidden="true" />
                          <span>Available</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3 h-3" aria-hidden="true" />
                          <span>Unavailable</span>
                        </>
                      )}
                    </span>
                  </div>

                  <Link
                    to={`/products/${item.product_slug}`}
                    className="text-lg font-semibold text-[#F1F5F9] hover:text-[#60A5FA] transition block"
                  >
                    {item.product_name}
                  </Link>

                  <div className="font-mono pt-1">
                    <span className="text-base font-bold text-[#93C5FD]">
                      {formatINR(item.effective_price)}
                    </span>
                    {item.is_on_sale && (
                      <span className="text-xs text-[#94A3B8] line-through ml-2">
                        {formatINR(item.original_price)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="p-4 border-t border-[#E5E7EB] bg-[#18243A] flex items-center justify-between gap-2">
                <button
                  type="button"
                  disabled={!item.is_available}
                  onClick={() => handleMoveToCart(item)}
                  className="dv-btn-primary flex-1 py-2.5 px-4 text-[13px] font-semibold flex items-center justify-center gap-1.5 disabled:opacity-40"
                >
                  <ShoppingBag className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>{item.is_available ? 'Move to Cart' : 'Unavailable'}</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleRemove(item.product_id, item.product_name)}
                  aria-label={`Remove ${item.product_name} from wishlist`}
                  title="Remove from Wishlist"
                  className="p-2.5 rounded-xl border border-[#E5E7EB] bg-[#111C30] hover:border-red-500 hover:bg-red-950/60 text-red-300 transition"
                >
                  <Trash2 className="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </StorefrontLayout>
  );
};

export default WishlistPage;
