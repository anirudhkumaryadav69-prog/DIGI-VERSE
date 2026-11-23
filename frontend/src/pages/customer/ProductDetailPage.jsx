import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Download,
  FileCheck2,
  Heart,
  PackageX,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Store,
  Tag,
} from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import ProductCard from '../../components/products/ProductCard';
import {
  Badge,
  EmptyState,
  LoadingState,
  SectionHeading,
  ToastBanner,
  formatINR,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { commerceApi, publicCatalogApi } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { getCategoryTheme } from '../../utils/categoryTheme';
import {
  resolveProductGalleryImages,
  resolveProductThumbnailUrl,
} from '../../utils/productThumbnails';

const ProductDetailPage = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, refreshCartAndWishlistCounts } = useAuth();

  const [product, setProduct] = useState(null);
  const [relatedProducts, setRelatedProducts] = useState([]);
  const [activeImage, setActiveImage] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState({ type: '', message: '' });

  useDocumentMeta({
    title: product ? product.name : 'Digital Product Details',
    description:
      product?.short_description ||
      'View specifications, pricing, and instant digital delivery details on DIGI-VERSE.',
    canonicalPath: `/products/${slug}`,
  });

  const loadProduct = useCallback(() => {
    setLoading(true);
    setError('');
    setRelatedProducts([]);
    publicCatalogApi
      .getProductBySlug(slug)
      .then((p) => {
        setProduct(p);
        const gallery = resolveProductGalleryImages(p);
        setActiveImage(gallery[0]?.image_url || resolveProductThumbnailUrl(p, p.image_url, 0));
        if (p.category?.slug) {
          publicCatalogApi
            .listProducts({ category: p.category.slug, page: 1, page_size: 4 })
            .then((rel) => {
              const filtered = (rel.items || []).filter((item) => item.id !== p.id).slice(0, 3);
              setRelatedProducts(filtered);
            })
            .catch(() => {});
        }
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(
          typeof detail === 'string'
            ? detail
            : 'This product is unavailable or has been removed from the catalog.'
        );
      })
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    loadProduct();
  }, [loadProduct]);

  const handleAddToCart = async (targetProd = product, qty = quantity) => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    setToast({ type: '', message: '' });
    try {
      await commerceApi.addToCart(targetProd.id, qty);
      await refreshCartAndWishlistCounts();
      setToast({
        type: 'success',
        message: `"${targetProd.name}" added to your shopping cart.`,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not add product to cart.',
      });
    }
  };

  const handleAddToWishlist = async (targetProd = product) => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    setToast({ type: '', message: '' });
    try {
      await commerceApi.addToWishlist(targetProd.id);
      await refreshCartAndWishlistCounts();
      setToast({
        type: 'success',
        message: `"${targetProd.name}" saved to your wishlist.`,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not save to wishlist.',
      });
    }
  };

  const metadataEntries =
    product?.metadata && typeof product.metadata === 'object'
      ? Object.entries(product.metadata).filter(
          ([k, v]) => v !== null && v !== undefined && String(v).trim() !== '' && k
        )
      : [];

  const categoryTheme = getCategoryTheme(product?.category?.slug || product?.category?.name);
  const CategoryBadgeIcon = categoryTheme.badgeIcon || Tag;
  const galleryImages = resolveProductGalleryImages(product);

  return (
    <StorefrontLayout>
      {/* Structured JSON-LD Product Metadata for Search Engines */}
      {product && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              '@context': 'https://schema.org',
              '@type': 'Product',
              name: product.name,
              description: product.short_description || product.main_description || product.name,
              image: activeImage ? [activeImage] : undefined,
              category: product.category?.name,
              offers: {
                '@type': 'Offer',
                priceCurrency: 'INR',
                price: String(product.effective_price),
                availability: product.is_available
                  ? 'https://schema.org/InStock'
                  : 'https://schema.org/OutOfStock',
              },
            })
              .replace(/</g, '\\u003c')
              .replace(/>/g, '\\u003e')
              .replace(/&/g, '\\u0026'),
          }}
        />
      )}

      <nav
        aria-label="Breadcrumb"
        className="mb-6 flex flex-wrap items-center gap-1.5 text-[13px] font-medium text-[#94A3B8]"
      >
        <Link to="/" className="hover:text-[#F1F5F9] transition-colors">
          Home
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-[#94A3B8]" aria-hidden="true" />
        {product?.category ? (
          <>
            <Link
              to={`/categories/${product.category.slug}`}
              className="hover:text-[#F1F5F9] transition-colors"
            >
              {product.category.name}
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-[#94A3B8]" aria-hidden="true" />
          </>
        ) : (
          <>
            <Link to="/products" className="hover:text-[#F1F5F9] transition-colors">
              Catalog
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-[#94A3B8]" aria-hidden="true" />
          </>
        )}
        <span className="text-[#F1F5F9] font-semibold truncate max-w-xs sm:max-w-md">
          {product ? product.name : 'Product details'}
        </span>
      </nav>

      {toast.message && (
        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
          className="mb-6"
        />
      )}

      {loading ? (
        <LoadingState label="Loading digital product..." />
      ) : error || !product ? (
        <EmptyState
          icon={PackageX}
          title="Digital product unavailable"
          description={
            error ||
            'This digital product is currently inactive, unavailable, or no longer in our catalog.'
          }
          action={
            <Link
              to="/products"
              className="dv-btn-primary inline-flex items-center gap-1.5 text-[13px] font-semibold px-5 py-2.5"
            >
              <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Browse active products</span>
            </Link>
          }
        />
      ) : (
        <div className="space-y-16">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
            {/* Gallery Column */}
            <div className="lg:col-span-7 space-y-4">
              <div className="aspect-16/10 bg-[#18243A] border border-[#E5E7EB] rounded-2xl overflow-hidden flex items-center justify-center shadow-xs">
                {activeImage ? (
                  <img
                    src={activeImage}
                    alt={product.name}
                    width="960"
                    height="600"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-xs font-medium text-[#94A3B8]">
                    {product.product_type || 'Digital product preview'}
                  </span>
                )}
              </div>

              {galleryImages.length > 1 && (
                <div
                  role="list"
                  aria-label="Product image thumbnails"
                  className="flex items-center gap-3 overflow-x-auto pb-2"
                >
                  {galleryImages.map((img, index) => (
                    <button
                      key={img.id}
                      type="button"
                      onClick={() => setActiveImage(img.image_url)}
                      aria-label={`View image ${index + 1}`}
                      className={`w-24 h-16 rounded-xl border overflow-hidden shrink-0 transition ${
                        activeImage === img.image_url
                          ? 'border-[#2563EB] ring-2 ring-[#EAF4FC]'
                          : 'border-[#E5E7EB] opacity-75 hover:opacity-100'
                      }`}
                    >
                      <img
                        src={img.image_url}
                        alt={`${product.name} preview ${index + 1}`}
                        loading="lazy"
                        className="w-full h-full object-cover"
                      />
                    </button>
                  ))}
                </div>
              )}

              {/* What the Customer Receives After Purchase */}
              <section className="dv-card p-6 space-y-4">
                <h2 className="text-[13px] font-semibold text-[#F1F5F9]">
                  What you receive after verified purchase
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs text-[#94A3B8]">
                  <div className="flex items-start gap-2.5">
                    <Download
                      className="w-4 h-4 text-[#60A5FA] shrink-0 mt-0.5"
                      aria-hidden="true"
                    />
                    <div>
                      <p className="font-semibold text-[#F1F5F9]">Instant Digital Access</p>
                      <p className="mt-0.5 leading-relaxed">
                        Unlocked immediately in your Downloads Library as soon as payment is
                        verified.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2.5">
                    <ShieldCheck
                      className="w-4 h-4 text-[#60A5FA] shrink-0 mt-0.5"
                      aria-hidden="true"
                    />
                    <div>
                      <p className="font-semibold text-[#F1F5F9]">Signed Delivery Links</p>
                      <p className="mt-0.5 leading-relaxed">
                        Generate fresh, authenticated short-lived download tokens from your account.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2.5">
                    <FileCheck2
                      className="w-4 h-4 text-[#60A5FA] shrink-0 mt-0.5"
                      aria-hidden="true"
                    />
                    <div>
                      <p className="font-semibold text-[#F1F5F9]">Official Tax/Purchase Invoice</p>
                      <p className="mt-0.5 leading-relaxed">
                        Permanent order snapshot and printable purchase invoice stored in your
                        profile.
                      </p>
                    </div>
                  </div>
                </div>
              </section>
            </div>

            {/* Product Details & Purchase Card Column */}
            <div className="lg:col-span-5 space-y-6">
              <div className="flex flex-wrap items-center gap-2">
                {product.category && (
                  <Link
                    to={`/categories/${product.category.slug}`}
                    className={`text-[12px] font-semibold px-3 py-1 rounded-full border inline-flex items-center gap-1.5 transition hover:opacity-90 ${categoryTheme.badgeClass}`}
                  >
                    <CategoryBadgeIcon className="w-3.5 h-3.5" aria-hidden="true" />
                    <span>{product.category.name}</span>
                  </Link>
                )}
                {product.product_type && (
                  <Badge variant="neutral">{product.product_type}</Badge>
                )}
              </div>

              <h1 className="text-[28px] sm:text-[34px] leading-[1.2] font-bold tracking-tight text-[#F1F5F9]">
                {product.name}
              </h1>

              {/* Seller Storefront Attribution */}
              <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 rounded-2xl bg-[#111C30] border border-[#E5E7EB]">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-[#18243A] border border-[#E5E7EB] text-[#60A5FA] flex items-center justify-center shrink-0 overflow-hidden">
                    {product.seller?.logo_url ? (
                      <img
                        src={product.seller.logo_url}
                        alt={product.seller.store_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <Store className="w-4 h-4" aria-hidden="true" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium text-[#94A3B8]">
                      {product.seller?.store_slug ? 'Verified creator storefront' : 'Platform catalog'}
                    </p>
                    {product.seller?.store_slug ? (
                      <Link
                        to={`/store/${product.seller.store_slug}`}
                        className="text-[14px] font-semibold text-[#F1F5F9] hover:text-[#93C5FD] hover:underline truncate block"
                      >
                        {product.seller.store_name}
                      </Link>
                    ) : (
                      <p className="text-[14px] font-semibold text-[#F1F5F9]">DIGI-VERSE Official</p>
                    )}
                  </div>
                </div>
                {product.seller?.store_slug && (
                  <Link
                    to={`/store/${product.seller.store_slug}`}
                    className="text-[13px] font-semibold text-[#60A5FA] hover:text-[#93C5FD] hover:underline shrink-0"
                  >
                    Visit store
                  </Link>
                )}
              </div>

              {/* Pricing & Purchase Actions Card */}
              <div className="dv-card p-6 space-y-4">
                <div className="flex items-baseline gap-3 tabular-nums">
                  <span className="text-[32px] leading-none font-bold text-[#F1F5F9]">
                    {formatINR(product.effective_price)}
                  </span>
                  {product.is_on_sale && (
                    <span className="text-[16px] font-medium text-[#94A3B8] line-through">
                      {formatINR(product.original_price)}
                    </span>
                  )}
                </div>

                {product.is_on_sale && product.active_discount && (
                  <div className="flex items-center gap-2 text-[13px] text-[#93C5FD] bg-[#18243A] border border-[#BFDBFE] rounded-xl px-3.5 py-2.5">
                    <Sparkles className="w-4 h-4 shrink-0 text-[#60A5FA]" aria-hidden="true" />
                    <span>
                      Limited-time deal: Save{' '}
                      <strong>{formatINR(product.active_discount.discount_amount)}</strong> (
                      {Math.round(Number(product.active_discount.discount_percentage))}% off)
                    </span>
                  </div>
                )}

                <div className="flex items-center gap-2 text-[13px] text-emerald-300 font-medium">
                  <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
                  <span>
                    {product.is_available
                      ? 'Instant verified digital download included'
                      : 'Currently unavailable'}
                  </span>
                </div>

                <div className="pt-2 flex flex-wrap sm:flex-nowrap items-center gap-3">
                  <div className="flex items-center gap-2 text-[13px]">
                    <label
                      htmlFor="product-quantity"
                      className="font-medium text-[#94A3B8]"
                    >
                      Qty
                    </label>
                    <input
                      id="product-quantity"
                      type="number"
                      min="1"
                      max="100"
                      value={quantity}
                      onChange={(e) =>
                        setQuantity(Math.max(1, Math.min(100, Number(e.target.value) || 1)))
                      }
                      className="dv-input w-16 px-2.5 py-2.5 text-center tabular-nums text-sm font-medium"
                    />
                  </div>

                  <button
                    type="button"
                    disabled={!product.is_available}
                    onClick={() => handleAddToCart(product, quantity)}
                    className="dv-btn-primary flex-1 h-11 px-5 text-[14px] font-semibold flex items-center justify-center gap-2 disabled:opacity-40"
                  >
                    <ShoppingBag className="w-4 h-4" aria-hidden="true" />
                    <span>Add to cart</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleAddToWishlist(product)}
                    aria-label="Save to Wishlist"
                    title="Save to wishlist"
                    className="h-11 w-11 inline-flex items-center justify-center rounded-xl border border-[#E5E7EB] bg-[#111C30] text-[#94A3B8] hover:bg-[#18243A] hover:text-[#93C5FD] hover:border-[#CBD5E1] transition"
                  >
                    <Heart className="w-4 h-4" aria-hidden="true" />
                  </button>
                </div>
              </div>

              {product.short_description && (
                <p className="text-[15px] text-[#CBD5E1] font-medium leading-relaxed">
                  {product.short_description}
                </p>
              )}

              {product.main_description && (
                <div className="space-y-2">
                  <h2 className="text-[13px] font-semibold text-[#F1F5F9]">
                    Overview
                  </h2>
                  <p className="text-[14px] text-[#CBD5E1] leading-relaxed whitespace-pre-line">
                    {product.main_description}
                  </p>
                </div>
              )}

              {/* Product Metadata Attributes (Sanitized on Backend) */}
              {metadataEntries.length > 0 && (
                <div className="space-y-2.5 pt-4 border-t border-[#E5E7EB]">
                  <h2 className="text-[13px] font-semibold text-[#F1F5F9]">
                    Specifications
                  </h2>
                  <dl className="dv-card divide-y divide-[#F1F5F9] text-[13px] overflow-hidden">
                    {metadataEntries.map(([key, value]) => (
                      <div key={key} className="px-4 py-2.5 flex justify-between gap-4">
                        <dt className="capitalize font-medium text-[#94A3B8]">
                          {key.replace(/_/g, ' ')}
                        </dt>
                        <dd className="font-medium text-[#F1F5F9] text-right">
                          {Array.isArray(value)
                            ? value.join(', ')
                            : typeof value === 'object'
                              ? JSON.stringify(value)
                              : String(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}

              {product.detailed_description && (
                <div className="space-y-2 pt-4 border-t border-[#E5E7EB]">
                  <h2 className="text-[13px] font-semibold text-[#F1F5F9]">
                    What&apos;s included &amp; details
                  </h2>
                  <p className="text-[13px] text-[#CBD5E1] leading-relaxed whitespace-pre-line">
                    {product.detailed_description}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Related Products Section (Only when actual related products exist) */}
          {relatedProducts.length > 0 && (
            <section className="pt-8 border-t border-[#E5E7EB]">
              <SectionHeading
                eyebrow="More in this Category"
                title={`Related in ${product.category?.name || 'Catalog'}`}
                subtitle="Explore additional digital assets from the same category."
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {relatedProducts.map((rel) => (
                  <ProductCard
                    key={rel.id}
                    product={rel}
                    onAddToCart={(e, p) => {
                      e.preventDefault();
                      handleAddToCart(p, 1);
                    }}
                    onAddToWishlist={(e, p) => {
                      e.preventDefault();
                      handleAddToWishlist(p);
                    }}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </StorefrontLayout>
  );
};

export default ProductDetailPage;
