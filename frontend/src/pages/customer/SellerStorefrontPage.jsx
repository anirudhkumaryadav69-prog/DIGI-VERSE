import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Globe, MapPin, Package, Search, Store } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import ProductCard from '../../components/products/ProductCard';
import {
  Badge,
  EmptyState,
  LoadingState,
  Pagination,
  ToastBanner,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import {
  StorefrontAvatarLogo,
  StorefrontBannerVisual,
} from '../../components/products/StorefrontVisual';
import { resolveStorefrontTheme } from '../../utils/categoryTheme';
import { commerceApi, publicCatalogApi } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

const SellerStorefrontPage = () => {
  const { storeSlug } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, refreshCartAndWishlistCounts } = useAuth();

  const [storefront, setStorefront] = useState(null);
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState({ type: '', message: '' });

  useDocumentMeta({
    title: storefront?.seller?.store_name || 'Creator Storefront',
    description:
      storefront?.seller?.store_description ||
      'Discover curated digital downloads from a verified DIGI-VERSE seller.',
    canonicalPath: `/store/${storeSlug}`,
  });

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 250);
    return () => clearTimeout(t);
  }, [search]);

  const loadStorefront = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await publicCatalogApi.getStoreBySlug(storeSlug, {
        page,
        page_size: 12,
        search: debounced.trim() || undefined,
        category: selectedCategory || undefined,
        sort_by: sortBy,
      });
      setStorefront(res);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : 'This seller storefront is not available or is currently inactive.'
      );
      setStorefront(null);
    } finally {
      setLoading(false);
    }
  }, [storeSlug, page, debounced, selectedCategory, sortBy]);

  useEffect(() => {
    loadStorefront();
  }, [loadStorefront]);

  const handleAddToCart = async (e, product) => {
    e.preventDefault();
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    try {
      await commerceApi.addToCart(product.id, 1);
      await refreshCartAndWishlistCounts();
      setToast({ type: 'success', message: `"${product.name}" added to your cart.` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ type: 'error', message: typeof detail === 'string' ? detail : 'Could not add item.' });
    }
  };

  const handleAddToWishlist = async (e, product) => {
    e.preventDefault();
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    try {
      await commerceApi.addToWishlist(product.id);
      await refreshCartAndWishlistCounts();
      setToast({ type: 'success', message: `"${product.name}" saved to wishlist.` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ type: 'error', message: typeof detail === 'string' ? detail : 'Could not save item.' });
    }
  };

  if (loading && !storefront) {
    return (
      <StorefrontLayout>
        <LoadingState label="Loading creator storefront..." />
      </StorefrontLayout>
    );
  }

  if (error && !storefront) {
    return (
      <StorefrontLayout>
        <div className="max-w-4xl mx-auto px-4 py-16">
          <EmptyState
            icon={Store}
            title="Storefront Unavailable"
            description={error}
            action={
              <Link to="/stores" className="dv-btn-primary px-5 py-2.5 text-xs">
                Explore Creator Stores
              </Link>
            }
          />
        </div>
      </StorefrontLayout>
    );
  }

  const seller = storefront.seller;
  const products = storefront.products;
  const storeTheme = resolveStorefrontTheme(seller);

  return (
    <StorefrontLayout>
      <div className="space-y-8">
        {/* Storefront Banner & Header */}
        <section className="bg-[#111C30] border border-[#E5E7EB] rounded-3xl overflow-hidden shadow-xs">
          <div className="h-40 sm:h-52 border-b border-[#E5E7EB] relative overflow-hidden">
            <StorefrontBannerVisual store={seller} theme={storeTheme} showDomainPill={true} />
          </div>

          <div className="p-6 sm:p-8 pt-0 relative z-10">
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 -mt-10 mb-5">
              <div className="flex items-end gap-4">
                <StorefrontAvatarLogo
                  store={seller}
                  theme={storeTheme}
                  sizeClass="w-20 h-20 rounded-2xl shadow-md"
                  iconSizeClass="w-8 h-8"
                />
                <div className="pb-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="text-2xl sm:text-3xl font-bold text-[#F1F5F9]">
                      {seller.store_name}
                    </h1>
                    <Badge variant="accent">{seller.business_type}</Badge>
                  </div>
                  <p className="text-xs text-[#94A3B8] mt-1">
                    Curated by <strong className="text-[#F1F5F9]">{seller.seller_display_name}</strong>
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-xs text-[#94A3B8]">
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#18243A] border border-[#BFDBFE] text-[#93C5FD] font-semibold">
                  <Package className="w-3.5 h-3.5" />
                  {seller.published_product_count} Published Products
                </span>
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#111C30] border border-[#E5E7EB]">
                  <MapPin className="w-3.5 h-3.5 text-[#60A5FA]" />
                  {seller.country}
                </span>
              </div>
            </div>

            {seller.store_description && (
              <p className="text-sm text-[#F1F5F9] leading-relaxed max-w-3xl">
                {seller.store_description}
              </p>
            )}

            {storefront.categories?.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 mt-5 pt-4 border-t border-[#E5E7EB]">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedCategory('');
                    setPage(1);
                  }}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                    !selectedCategory
                      ? 'bg-[#2563EB] text-white border-[#2563EB]'
                      : 'bg-[#111C30] text-[#F1F5F9] border-[#E5E7EB] hover:border-[#93C5FD]'
                  }`}
                >
                  All Store Categories
                </button>
                {storefront.categories.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      setSelectedCategory(c.slug);
                      setPage(1);
                    }}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                      selectedCategory === c.slug
                        ? 'bg-[#2563EB] text-white border-[#2563EB]'
                        : 'bg-[#111C30] text-[#F1F5F9] border-[#E5E7EB] hover:border-[#93C5FD]'
                    }`}
                  >
                    {c.name} ({c.product_count})
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
        />

        {/* Store Catalog Filter Bar */}
        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-4">
          <div className="relative flex-1 max-w-md">
            <label htmlFor="store-catalog-search" className="sr-only">
              Search products in {seller.store_name}
            </label>
            <Search
              className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
              aria-hidden="true"
            />
            <input
              id="store-catalog-search"
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder={`Search products in ${seller.store_name}...`}
              className="dv-input pl-10 pr-3.5 py-2 text-[13px]"
            />
          </div>
          <div className="flex items-center gap-3">
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
              aria-label="Sort store products"
              className="dv-input px-3 py-2 text-[13px] sm:w-44"
            >
              <option value="newest">Newest Releases</option>
              <option value="popularity">Most Popular</option>
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
            </select>
            <Link to="/products" className="text-xs font-semibold text-[#60A5FA] hover:underline whitespace-nowrap inline-flex items-center gap-1">
              <Globe className="w-3.5 h-3.5" aria-hidden="true" /> Full Catalog
            </Link>
          </div>
        </div>

        {/* Store Products Grid */}
        {!products.items.length ? (
          <EmptyState
            icon={Package}
            title="No published products found"
            description="Try clearing your search or category filter, or explore other verified storefronts."
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 items-stretch">
            {products.items.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                onAddToCart={handleAddToCart}
                onAddToWishlist={handleAddToWishlist}
              />
            ))}
          </div>
        )}

        <Pagination page={page} totalPages={products.total_pages} onPageChange={setPage} />
      </div>
    </StorefrontLayout>
  );
};

export default SellerStorefrontPage;
