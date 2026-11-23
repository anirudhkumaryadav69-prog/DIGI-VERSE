import { Link } from 'react-router-dom';
import { Heart, ShoppingBag, Star, Store } from 'lucide-react';
import { formatINR } from '../common/StorefrontDesignSystem';
import { getCategoryTheme } from '../../utils/categoryTheme';
import { resolveProductThumbnailUrl } from '../../utils/productThumbnails';

const ProductCard = ({ product, onAddToCart, onAddToWishlist }) => {
  if (!product) return null;

  const theme = getCategoryTheme(product.category?.slug || product.category?.name);
  const BadgeIcon = theme.badgeIcon || theme.icon;
  const thumbnailUrl = resolveProductThumbnailUrl(product, product.image_url, 0);

  const ratingValue = Number(product.average_rating ?? product.rating ?? 0);
  const reviewCount = Number(product.review_count ?? 0);
  const hasGenuineRating = ratingValue > 0 && reviewCount > 0;

  const formatLabel = product.product_metadata?.format
    ? String(product.product_metadata.format).toUpperCase()
    : null;
  const discountPercentage = product.active_discount
    ? Math.round(Number(product.active_discount.discount_percentage))
    : 0;
  const discountSavings =
    product.is_on_sale && Number(product.original_price) > Number(product.effective_price)
      ? Number(product.original_price) - Number(product.effective_price)
      : 0;

  return (
    <article className="group dv-card-interactive h-full flex flex-col justify-between overflow-hidden rounded-2xl bg-[#111C30] border border-[#D5DEE8]">
      <div className="flex-1 flex flex-col">
        {/* Consistent 16:10 Product Cover Thumbnail */}
        <Link
          to={`/products/${product.slug}`}
          className="block aspect-16/10 bg-[#18243A] relative overflow-hidden border-b border-[#E5E7EB]"
        >
          <img
            src={thumbnailUrl}
            alt={product.name}
            loading="lazy"
            width="640"
            height="400"
            className="w-full h-full object-cover group-hover:scale-[1.025] transition-transform duration-300 ease-out"
          />

          {formatLabel && (
            <span className="absolute bottom-2.5 left-3 rounded-md bg-[#111C30]/95 backdrop-blur-xs border border-[#D5DEE8] text-[#F1F5F9] text-[10px] font-mono font-semibold px-2 py-0.5 shadow-2xs">
              {formatLabel}
            </span>
          )}

          {product.is_on_sale && discountPercentage > 0 && (
            <span className="absolute top-2.5 right-3 rounded-full bg-[#16A34A] text-white text-[11px] font-semibold px-2.5 py-0.5 shadow-xs">
              -{discountPercentage}% OFF
            </span>
          )}
        </Link>

        {/* Card Metadata, Title, Seller & Description */}
        <div className="p-5 flex-1 flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1.5 mb-2.5">
            {product.category?.name && (
              <Link
                to={`/categories/${product.category.slug}`}
                title={product.category.name}
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold border transition hover:opacity-90 max-w-full ${theme.badgeClass}`}
              >
                {BadgeIcon && <BadgeIcon className="w-3 h-3 shrink-0" aria-hidden="true" />}
                <span className="truncate">{product.category.name}</span>
              </Link>
            )}
            {product.product_type && (
              <span className="text-[11px] font-medium text-[#94A3B8] whitespace-nowrap shrink-0">
                {product.product_type}
              </span>
            )}
          </div>

          <h3 className="text-[16.5px] leading-[1.35] font-semibold tracking-[-0.01em] text-[#F1F5F9] group-hover:text-[#60A5FA] transition-colors line-clamp-2 min-h-[2.7em] mb-2">
            <Link
              to={`/products/${product.slug}`}
              className="rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2563EB]"
            >
              {product.name}
            </Link>
          </h3>

          <div className="mb-2.5 flex items-center justify-between gap-2 text-[12.5px] font-medium text-[#94A3B8]">
            <div className="flex items-center gap-1.5 min-w-0">
              {product.seller?.logo_url ? (
                <img
                  src={product.seller.logo_url}
                  alt=""
                  loading="lazy"
                  className="w-4 h-4 rounded-full object-cover border border-[#D5DEE8] shrink-0"
                />
              ) : (
                <Store className="w-3.5 h-3.5 text-[#0EA5E9] shrink-0" aria-hidden="true" />
              )}
              {product.seller?.store_slug ? (
                <Link
                  to={`/store/${product.seller.store_slug}`}
                  className="text-[#F1F5F9] hover:text-[#60A5FA] hover:underline truncate"
                >
                  {product.seller.store_name}
                </Link>
              ) : (
                <span className="text-[#F1F5F9] truncate">DIGI-VERSE Official</span>
              )}
            </div>

            {hasGenuineRating && (
              <span
                className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#F1F5F9] shrink-0 tabular-nums"
                title={`${ratingValue.toFixed(1)} out of 5 (${reviewCount} reviews)`}
              >
                <Star className="w-3.5 h-3.5 fill-[#D97706] text-[#D97706]" aria-hidden="true" />
                <span>{ratingValue.toFixed(1)}</span>
                <span className="text-[#94A3B8] font-normal">({reviewCount})</span>
              </span>
            )}
          </div>

          {product.short_description && (
            <p className="text-[13px] leading-[1.5] text-[#94A3B8] line-clamp-2 mt-auto">
              {product.short_description}
            </p>
          )}
        </div>
      </div>

      {/* Pricing & Primary Actions Footer */}
      <div className="px-5 py-3.5 border-t border-[#E5E7EB] bg-[#18243A] flex items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5 min-w-0 tabular-nums">
          <span className="text-[19px] leading-none font-bold text-[#F1F5F9]">
            {formatINR(product.effective_price)}
          </span>
          {product.is_on_sale && (
            <div className="flex items-center gap-1.5 text-[11px] leading-none mt-1">
              <span className="font-medium text-[#94A3B8] line-through">
                {formatINR(product.original_price)}
              </span>
              {discountSavings > 0 && (
                <span className="font-semibold text-emerald-400">
                  Save {formatINR(discountSavings)}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {onAddToWishlist && (
            <button
              type="button"
              onClick={(e) => onAddToWishlist(e, product)}
              aria-label={`Save ${product.name} to wishlist`}
              title="Save to wishlist"
              className="h-9 w-9 inline-flex items-center justify-center rounded-xl border border-[#D5DEE8] bg-[#111C30] hover:bg-[#18243A] hover:border-[#93C5FD] text-[#94A3B8] hover:text-[#60A5FA] transition focus-visible:outline-2 focus-visible:outline-[#2563EB]"
            >
              <Heart className="w-4 h-4" aria-hidden="true" />
            </button>
          )}
          {onAddToCart && (
            <button
              type="button"
              disabled={product.is_available === false}
              onClick={(e) => onAddToCart(e, product)}
              aria-label={`Add ${product.name} to cart`}
              className="h-9 px-3.5 rounded-xl bg-[#2563EB] text-white text-[13px] font-semibold hover:bg-[#1D4ED8] shadow-xs transition inline-flex items-center gap-1.5 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-[#2563EB]"
            >
              <ShoppingBag className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{product.is_available === false ? 'Unavailable' : 'Add'}</span>
            </button>
          )}
        </div>
      </div>
    </article>
  );
};

export default ProductCard;
