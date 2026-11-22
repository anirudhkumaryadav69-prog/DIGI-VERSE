import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { PackageSearch, RotateCcw, Search } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import ProductCard from '../../components/products/ProductCard';
import {
  Button,
  EmptyState,
  ErrorAlert,
  Pagination,
  ProductCardSkeleton,
  SectionHeading,
  ToastBanner,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { commerceApi, publicCatalogApi } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

const ProductsCatalogPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated, refreshCartAndWishlistCounts } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [data, setData] = useState({
    items: [],
    total: 0,
    page: 1,
    page_size: 12,
    total_pages: 1,
  });
  const [categories, setCategories] = useState([]);
  const [stores, setStores] = useState([]);

  // Filter controls
  const [searchInput, setSearchInput] = useState(searchParams.get('search') || '');
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get('search') || '');
  const [selectedCategory, setSelectedCategory] = useState(searchParams.get('category') || '');
  const [selectedSeller, setSelectedSeller] = useState(searchParams.get('seller') || '');
  const [ownerType, setOwnerType] = useState(searchParams.get('owner_type') || '');
  const [minPrice, setMinPrice] = useState(searchParams.get('min_price') || '');
  const [maxPrice, setMaxPrice] = useState(searchParams.get('max_price') || '');
  const [onSaleOnly, setOnSaleOnly] = useState(searchParams.get('on_sale') === 'true');
  const [sortBy, setSortBy] = useState(searchParams.get('sort_by') || 'newest');
  const [page, setPage] = useState(Number(searchParams.get('page') || 1));

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState({ type: '', message: '' });

  // Request counter to prevent stale async responses from overwriting newer filters
  const latestRequestIdRef = useRef(0);

  useDocumentMeta({
    title: 'Digital Product Catalog',
    description:
      'Browse and filter curated digital products, UI systems, code templates, and discounted creator toolkits.',
    canonicalPath: '/products',
  });

  // Debounce search input (280ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput);
    }, 280);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    publicCatalogApi
      .listCategories({ page: 1, page_size: 50 })
      .then((res) => setCategories(res.items || []))
      .catch(() => {});
    publicCatalogApi
      .listStores({ page: 1, page_size: 60 })
      .then((res) => setStores(res.items || []))
      .catch(() => {});
  }, []);

  const fetchProducts = useCallback(async () => {
    const reqId = ++latestRequestIdRef.current;
    setLoading(true);
    setError('');

    const apiParams = { page, page_size: 12, sort_by: sortBy };
    const urlParams = {};

    if (page > 1) urlParams.page = String(page);
    if (sortBy && sortBy !== 'newest') urlParams.sort_by = sortBy;
    if (debouncedSearch.trim()) {
      apiParams.search = debouncedSearch.trim();
      urlParams.search = debouncedSearch.trim();
    }
    if (selectedCategory) {
      apiParams.category = selectedCategory;
      urlParams.category = selectedCategory;
    }
    if (selectedSeller) {
      apiParams.seller = selectedSeller;
      urlParams.seller = selectedSeller;
    }
    if (ownerType) {
      apiParams.owner_type = ownerType;
      urlParams.owner_type = ownerType;
    }
    if (minPrice !== '' && !Number.isNaN(Number(minPrice))) {
      apiParams.min_price = minPrice;
      urlParams.min_price = minPrice;
    }
    if (maxPrice !== '' && !Number.isNaN(Number(maxPrice))) {
      apiParams.max_price = maxPrice;
      urlParams.max_price = maxPrice;
    }
    if (onSaleOnly) {
      apiParams.on_sale = true;
      urlParams.on_sale = 'true';
    }

    setSearchParams(urlParams, { replace: true });

    try {
      const res = await publicCatalogApi.listProducts(apiParams);
      if (reqId !== latestRequestIdRef.current) return;
      setData(res);
    } catch (err) {
      if (reqId !== latestRequestIdRef.current) return;
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : 'Unable to load product catalog right now. Please try again.'
      );
    } finally {
      if (reqId === latestRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [
    page,
    debouncedSearch,
    selectedCategory,
    selectedSeller,
    ownerType,
    minPrice,
    maxPrice,
    onSaleOnly,
    sortBy,
    setSearchParams,
  ]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const hasActiveFilters = Boolean(
    searchInput.trim() ||
      selectedCategory ||
      selectedSeller ||
      ownerType ||
      minPrice !== '' ||
      maxPrice !== '' ||
      onSaleOnly ||
      sortBy !== 'newest'
  );

  const handleClearFilters = () => {
    setSearchInput('');
    setDebouncedSearch('');
    setSelectedCategory('');
    setSelectedSeller('');
    setOwnerType('');
    setMinPrice('');
    setMaxPrice('');
    setOnSaleOnly(false);
    setSortBy('newest');
    setPage(1);
  };

  const handleAddToCart = async (e, prod) => {
    e.preventDefault();
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    try {
      await commerceApi.addToCart(prod.id, 1);
      await refreshCartAndWishlistCounts();
      setToast({ type: 'success', message: `"${prod.name}" added to shopping cart.` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not add product to cart.',
      });
    }
  };

  const handleAddToWishlist = async (e, prod) => {
    e.preventDefault();
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    try {
      await commerceApi.addToWishlist(prod.id);
      await refreshCartAndWishlistCounts();
      setToast({ type: 'success', message: `"${prod.name}" saved to wishlist.` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not save to wishlist.',
      });
    }
  };

  return (
    <StorefrontLayout>
      <SectionHeading
        eyebrow="Digital Marketplace"
        title="Curated Digital Products"
        subtitle="Explore verified digital assets with instant download delivery."
        action={
          !loading && (
            <span className="text-xs font-mono font-medium px-3 py-1 rounded-full bg-[#FFF2E6] border border-[#FFD4AE] text-[#D94300]">
              {data.total} {data.total === 1 ? 'product' : 'products'} found
            </span>
          )
        }
      />

      {/* Filter & Search Bar */}
      <section
        aria-label="Catalog Filters"
        className="dv-card-warm p-4 sm:p-5 mb-6 space-y-3"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
          <div className="relative lg:col-span-2">
            <label htmlFor="catalog-search" className="sr-only">
              Search digital products
            </label>
            <Search
              className="w-4 h-4 text-[#8490A0] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
              aria-hidden="true"
            />
            <input
              id="catalog-search"
              type="search"
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value);
                setPage(1);
              }}
              placeholder="Search digital products..."
              className="dv-input pl-10 pr-3.5 py-2 text-xs"
            />
          </div>

          <div>
            <label htmlFor="catalog-category" className="sr-only">
              Filter by category
            </label>
            <select
              id="catalog-category"
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                setPage(1);
              }}
              className="dv-input px-3 py-2 text-xs"
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.slug}>
                  {c.name} ({c.product_count})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="catalog-min-price" className="sr-only">
              Minimum price
            </label>
            <input
              id="catalog-min-price"
              type="number"
              min="0"
              value={minPrice}
              onChange={(e) => {
                setMinPrice(e.target.value);
                setPage(1);
              }}
              placeholder="Min Price (₹)"
              className="dv-input px-3 py-2 text-xs"
            />
          </div>

          <div>
            <label htmlFor="catalog-max-price" className="sr-only">
              Maximum price
            </label>
            <input
              id="catalog-max-price"
              type="number"
              min="0"
              value={maxPrice}
              onChange={(e) => {
                setMaxPrice(e.target.value);
                setPage(1);
              }}
              placeholder="Max Price (₹)"
              className="dv-input px-3 py-2 text-xs"
            />
          </div>

          <div>
            <label htmlFor="catalog-sort" className="sr-only">
              Sort products
            </label>
            <select
              id="catalog-sort"
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
              className="dv-input px-3 py-2 text-xs"
            >
              <option value="newest">Sort: Newest</option>
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
              <option value="popularity">Sort: Popularity</option>
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-[#E5E7EB]">
          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex items-center gap-2 text-xs font-medium text-[#243247] cursor-pointer select-none">
              <input
                type="checkbox"
                checked={onSaleOnly}
                onChange={(e) => {
                  setOnSaleOnly(e.target.checked);
                  setPage(1);
                }}
                className="accent-[#FF6B0A]"
              />
              <span>Promotional Deals &amp; Active Discounts Only</span>
            </label>

            <select
              aria-label="Filter by creator store"
              value={selectedSeller}
              onChange={(e) => {
                setSelectedSeller(e.target.value);
                setPage(1);
              }}
              className="dv-input px-3 py-1.5 text-xs w-48"
            >
              <option value="">All Creators &amp; Stores</option>
              {stores.map((s) => (
                <option key={s.id} value={s.store_slug}>
                  {s.store_name} ({s.published_product_count})
                </option>
              ))}
            </select>

            <select
              aria-label="Filter by catalog source"
              value={ownerType}
              onChange={(e) => {
                setOwnerType(e.target.value);
                setPage(1);
              }}
              className="dv-input px-3 py-1.5 text-xs w-44"
            >
              <option value="">All Sources</option>
              <option value="platform">DIGI-VERSE Official</option>
              <option value="seller">Independent Sellers</option>
            </select>
          </div>

          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#FF6B0A] hover:text-[#D94300]"
            >
              <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Clear All Filters</span>
            </button>
          )}
        </div>
      </section>

      {toast.message && (
        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
          className="mb-6"
        />
      )}

      {error && <ErrorAlert message={error} onRetry={fetchProducts} className="mb-6" />}

      {/* Product Grid */}
      {loading ? (
        <ProductCardSkeleton count={6} />
      ) : data.items.length === 0 ? (
        <EmptyState
          icon={PackageSearch}
          title="No products match your search criteria"
          description="Try broadening your search keywords, adjusting the price range, or clearing active filters."
          action={
            hasActiveFilters && (
              <Button variant="secondary" size="sm" onClick={handleClearFilters}>
                Reset All Filters
              </Button>
            )
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {data.items.map((prod) => (
            <ProductCard
              key={prod.id}
              product={prod}
              onAddToCart={handleAddToCart}
              onAddToWishlist={handleAddToWishlist}
            />
          ))}
        </div>
      )}

      <Pagination
        page={data.page}
        totalPages={data.total_pages}
        totalItems={data.total}
        itemLabel="products"
        onPageChange={(newPage) => setPage(newPage)}
      />
    </StorefrontLayout>
  );
};

export default ProductsCatalogPage;
