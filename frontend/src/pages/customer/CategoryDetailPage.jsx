import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ChevronRight, FolderTree, RotateCcw, Search } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import ProductCard from '../../components/products/ProductCard';
import {
  Button,
  EmptyState,
  ErrorAlert,
  ProductCardSkeleton,
  ToastBanner,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { commerceApi, publicCatalogApi } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { getCategoryTheme } from '../../utils/categoryTheme';
import {
  CategoryDisciplineStrip,
  CategoryVisualIcon,
} from '../../components/products/CategoryVisual';

const CategoryDetailPage = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, refreshCartAndWishlistCounts } = useAuth();

  const [category, setCategory] = useState(null);
  const [products, setProducts] = useState([]);
  const [totalMatching, setTotalMatching] = useState(0);
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const [onSaleOnly, setOnSaleOnly] = useState(false);

  const [categoryLoading, setCategoryLoading] = useState(true);
  const [productsLoading, setProductsLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState({ type: '', message: '' });

  const latestReqRef = useRef(0);
  const theme = getCategoryTheme(category?.slug || slug || category?.name);

  useDocumentMeta({
    title: category ? `${category.name} Collection` : 'Category Collection',
    description:
      category?.description || 'Explore curated digital products in this DIGI-VERSE category.',
    canonicalPath: `/categories/${slug}`,
  });

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
    }, 250);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setSearchInput('');
    setDebouncedSearch('');
    setSortBy('newest');
    setOnSaleOnly(false);
    setCategoryLoading(true);
    setError('');
    publicCatalogApi
      .getCategoryBySlug(slug)
      .then((catData) => {
        setCategory(catData);
      })
      .catch(() => {
        setError('Category not found or currently inactive.');
      })
      .finally(() => setCategoryLoading(false));
  }, [slug]);

  const loadProducts = useCallback(() => {
    const reqId = ++latestReqRef.current;
    setProductsLoading(true);
    const params = {
      category: slug,
      page: 1,
      page_size: 24,
      sort_by: sortBy,
    };
    if (debouncedSearch) params.search = debouncedSearch;
    if (onSaleOnly) params.on_sale = true;

    publicCatalogApi
      .listProducts(params)
      .then((prodData) => {
        if (reqId !== latestReqRef.current) return;
        setProducts(prodData.items || []);
        setTotalMatching(prodData.total ?? (prodData.items?.length || 0));
      })
      .catch(() => {
        if (reqId !== latestReqRef.current) return;
        setError('Unable to load products for this category right now.');
      })
      .finally(() => {
        if (reqId === latestReqRef.current) {
          setProductsLoading(false);
        }
      });
  }, [slug, debouncedSearch, sortBy, onSaleOnly]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  const hasFilters = Boolean(debouncedSearch || sortBy !== 'newest' || onSaleOnly);

  const resetFilters = () => {
    setSearchInput('');
    setDebouncedSearch('');
    setSortBy('newest');
    setOnSaleOnly(false);
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
      {/* Breadcrumb Navigation */}
      <nav
        aria-label="Breadcrumb"
        className="mb-6 flex flex-wrap items-center gap-1.5 text-[13px] font-medium text-[#94A3B8]"
      >
        <Link to="/" className="hover:text-[#F1F5F9] transition-colors">
          Home
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-[#94A3B8]" aria-hidden="true" />
        <Link to="/categories" className="hover:text-[#F1F5F9] transition-colors">
          Categories
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-[#94A3B8]" aria-hidden="true" />
        <span className="text-[#F1F5F9] font-semibold">
          {category ? category.name : 'Collection'}
        </span>
      </nav>

      {toast.message && (
        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
          className="mb-6"
        />
      )}

      {categoryLoading ? (
        <ProductCardSkeleton
          count={4}
          gridClassName="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
        />
      ) : error || !category ? (
        <ErrorAlert
          message={error || 'Category not found.'}
          onRetry={loadProducts}
        />
      ) : (
        <div className="space-y-8">
          {/* Category Hero Header */}
          <section className="relative overflow-hidden rounded-2xl bg-[#111C30] border border-[#E5E7EB] p-6 sm:p-8 shadow-xs">
            <div
              className={`absolute inset-x-0 top-0 h-1 ${theme.accentLineClass}`}
              aria-hidden="true"
            />

            <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6">
              <div className="space-y-3 max-w-2xl">
                <div className="flex flex-wrap items-center gap-2.5">
                  <div
                    className={`w-12 h-12 rounded-xl border flex items-center justify-center shrink-0 ${theme.iconBoxClass}`}
                  >
                    <CategoryVisualIcon theme={theme} className="w-6 h-6" />
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full border px-3 py-1 text-[12px] font-semibold tabular-nums ${theme.badgeClass}`}
                  >
                    {category.product_count}{' '}
                    {category.product_count === 1 ? 'product available' : 'products available'}
                  </span>
                  {theme.disciplineIcons?.length > 0 && (
                    <span className="inline-flex items-center gap-2 rounded-full border border-[#D5DEE8] bg-[#18243A] px-3 py-1 text-[12px] font-medium text-[#94A3B8]">
                      <CategoryDisciplineStrip icons={theme.disciplineIcons} className="w-3.5 h-3.5" />
                      <span>{theme.disciplineLabel}</span>
                    </span>
                  )}
                </div>

                <h1 className="text-[32px] sm:text-[38px] leading-[1.15] font-bold tracking-tight text-[#F1F5F9]">
                  {category.name}
                </h1>

                {category.description && (
                  <p className="text-[15px] sm:text-[16px] leading-relaxed font-normal text-[#CBD5E1]">
                    {category.description}
                  </p>
                )}
              </div>

              {/* Category Filter & Sort Toolbar */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full lg:w-auto">
                <div className="relative flex-1 sm:w-60">
                  <label htmlFor="category-product-search" className="sr-only">
                    Search in {category.name}
                  </label>
                  <Search
                    className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
                    aria-hidden="true"
                  />
                  <input
                    id="category-product-search"
                    type="search"
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    placeholder={`Search ${category.name}...`}
                    className="dv-input pl-10 pr-3.5 py-2 text-[13px]"
                  />
                </div>

                <div className="flex items-center gap-2.5">
                  <label htmlFor="category-sort" className="sr-only">
                    Sort products
                  </label>
                  <select
                    id="category-sort"
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="dv-input px-3 py-2 text-[13px] font-medium sm:w-44"
                  >
                    <option value="newest">Sort: Newest</option>
                    <option value="price_asc">Price: Low to High</option>
                    <option value="price_desc">Price: High to Low</option>
                    <option value="popularity">Most Popular</option>
                  </select>

                  <label className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-[#E5E7EB] bg-[#18243A] text-[13px] font-medium text-[#F1F5F9] cursor-pointer select-none whitespace-nowrap hover:bg-[#111C30] transition">
                    <input
                      type="checkbox"
                      checked={onSaleOnly}
                      onChange={(e) => setOnSaleOnly(e.target.checked)}
                      className="accent-[#2563EB]"
                    />
                    <span>On sale</span>
                  </label>
                </div>
              </div>
            </div>

            {hasFilters && !productsLoading && (
              <div className="mt-4 pt-3.5 border-t border-[#F1F5F9] flex flex-wrap items-center justify-between gap-2 text-[13px] text-[#94A3B8]">
                <span>
                  Showing <strong className="text-[#F1F5F9]">{totalMatching}</strong> matching{' '}
                  {totalMatching === 1 ? 'result' : 'results'} in {category.name}
                </span>
                <button
                  type="button"
                  onClick={resetFilters}
                  className="inline-flex items-center gap-1.5 font-semibold text-[#60A5FA] hover:text-[#93C5FD]"
                >
                  <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>Reset filters</span>
                </button>
              </div>
            )}
          </section>

          {/* Product Grid */}
          {productsLoading ? (
            <ProductCardSkeleton
              count={4}
              gridClassName="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
            />
          ) : products.length === 0 ? (
            <EmptyState
              icon={FolderTree}
              title={
                hasFilters
                  ? 'No matching products in this category'
                  : 'No active products in this category yet'
              }
              description={
                hasFilters
                  ? 'Try clearing your search terms or toggling the active deals filter.'
                  : 'Check back soon or browse our full digital product catalog.'
              }
              action={
                hasFilters ? (
                  <Button variant="secondary" size="sm" onClick={resetFilters}>
                    Reset category filters
                  </Button>
                ) : (
                  <Link
                    to="/products"
                    className="dv-btn-primary inline-block text-xs font-semibold px-5 py-2.5"
                  >
                    Browse all products
                  </Link>
                )
              }
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 items-stretch">
              {products.map((prod) => (
                <ProductCard
                  key={prod.id}
                  product={prod}
                  onAddToCart={handleAddToCart}
                  onAddToWishlist={handleAddToWishlist}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </StorefrontLayout>
  );
};

export default CategoryDetailPage;
