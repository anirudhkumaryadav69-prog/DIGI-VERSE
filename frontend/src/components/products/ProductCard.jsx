import { Link } from 'react-router-dom';
import { Heart, ShoppingBag, Store, Tag } from 'lucide-react';
import { Badge, formatINR } from '../common/StorefrontDesignSystem';

const ProductCard = ({ product, onAddToCart, onAddToWishlist }) => {
  if (!product) return null;

  return (
    <article className="group dv-card-interactive flex flex-col justify-between overflow-hidden">
      <div>
        <Link
          to={`/products/${product.slug}`}
          className="block aspect-16/10 bg-[#FFF6ED] relative overflow-hidden border-b border-[#E5E7EB]"
        >
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.name}
              loading="lazy"
              width="640"
              height="400"
              className="w-full h-full object-cover group-hover:scale-103 transition duration-300"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-xs uppercase tracking-widest text-[#8490A0] font-medium">
              {product.product_type || 'Digital Asset'}
            </div>
          )}

          {product.is_on_sale && product.active_discount && (
            <span className="absolute top-3 right-3 rounded-full bg-[#FF6B0A] text-white text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 shadow-xs">
              -{product.active_discount.discount_percentage}% OFF
            </span>
          )}
        </Link>

        <div className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] uppercase tracking-wider text-[#FF6B0A] mb-2">
            {product.category?.name && (
              <span className="inline-flex items-center gap-1 font-semibold">
                <Tag className="w-3 h-3" aria-hidden="true" />
                <span>{product.category.name}</span>
              </span>
            )}
            {product.product_type && (
              <Badge variant="neutral">{product.product_type}</Badge>
            )}
          </div>

          <h3 className="text-base md:text-lg font-semibold text-[#1F2937] group-hover:text-[#FF6B0A] transition mb-1.5">
            <Link to={`/products/${product.slug}`} className="focus:outline-none">
              {product.name}
            </Link>
          </h3>

          <div className="mb-2 flex items-center gap-1.5 text-[11px] text-[#64748B]">
            <Store className="w-3 h-3 text-[#FF6B0A] shrink-0" aria-hidden="true" />
            {product.seller?.store_slug ? (
              <Link
                to={`/store/${product.seller.store_slug}`}
                className="font-medium text-[#243247] hover:text-[#FF6B0A] hover:underline truncate"
              >
                {product.seller.store_name}
              </Link>
            ) : (
              <span className="font-medium text-[#243247]">DIGI-VERSE Official</span>
            )}
          </div>

          {product.short_description && (
            <p className="text-xs text-[#64748B] line-clamp-2 leading-relaxed">
              {product.short_description}
            </p>
          )}
        </div>
      </div>

      <div className="px-5 py-4 border-t border-[#E5E7EB] bg-[#FFFAF5]/50 flex items-center justify-between gap-2">
        <div className="font-mono">
          <span className="text-base font-bold text-[#F4510B]">
            {formatINR(product.effective_price)}
          </span>
          {product.is_on_sale && (
            <span className="text-xs text-[#8490A0] line-through ml-2">
              {formatINR(product.original_price)}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {onAddToWishlist && (
            <button
              type="button"
              onClick={(e) => onAddToWishlist(e, product)}
              aria-label={`Save ${product.name} to wishlist`}
              title="Save to Wishlist"
              className="p-2 rounded-xl border border-[#FFD4AE] bg-white hover:bg-[#FFF0E2] hover:border-[#FF6B0A] text-[#D94300] transition focus-visible:outline-2 focus-visible:outline-[#FF6B0A]"
            >
              <Heart className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          )}
          {onAddToCart && (
            <button
              type="button"
              disabled={product.is_available === false}
              onClick={(e) => onAddToCart(e, product)}
              aria-label={`Add ${product.name} to cart`}
              className="px-3.5 py-2 rounded-xl bg-[#FF6B0A] text-white text-xs font-semibold hover:bg-[#D94300] shadow-[0_3px_10px_-2px_rgba(255,107,10,0.28)] transition inline-flex items-center gap-1.5 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-[#FF6B0A]"
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
