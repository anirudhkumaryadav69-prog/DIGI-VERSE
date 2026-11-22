import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, FolderTree } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import ProductCard from '../../components/products/ProductCard';
import {
  EmptyState,
  ErrorAlert,
  ProductCardSkeleton,
  SectionHeading,
  ToastBanner,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { commerceApi, publicCatalogApi } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

const CategoryDetailPage = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, refreshCartAndWishlistCounts } = useAuth();

  const [category, setCategory] = useState(null);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState({ type: '', message: '' });

  useDocumentMeta({
    title: category ? `${category.name} Collection` : 'Category Collection',
    description:
      category?.description || 'Explore curated digital products in this DIGI-VERSE category.',
    canonicalPath: `/categories/${slug}`,
  });

  const loadCategoryAndProducts = useCallback(() => {
    setLoading(true);
    setError('');
    Promise.all([
      publicCatalogApi.getCategoryBySlug(slug),
      publicCatalogApi.listProducts({ category: slug, page: 1, page_size: 24 }),
    ])
      .then(([catData, prodData]) => {
        setCategory(catData);
        setProducts(prodData.items || []);
      })
      .catch(() => {
        setError('Category not found or currently inactive.');
      })
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    loadCategoryAndProducts();
  }, [loadCategoryAndProducts]);

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
      <div className="mb-6">
        <Link
          to="/categories"
          className="text-xs font-semibold text-[#FF6B0A] hover:text-[#D94300] hover:underline inline-flex items-center gap-1.5"
        >
          <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
          <span>All Categories</span>
        </Link>
      </div>

      {toast.message && (
        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
          className="mb-6"
        />
      )}

      {loading ? (
        <ProductCardSkeleton count={6} />
      ) : error || !category ? (
        <ErrorAlert message={error || 'Category not found.'} onRetry={loadCategoryAndProducts} />
      ) : (
        <>
          <SectionHeading
            eyebrow={`Category Collection (${category.product_count} Products)`}
            title={category.name}
            subtitle={category.description}
          />

          {products.length === 0 ? (
            <EmptyState
              icon={FolderTree}
              title="No active products in this category yet"
              description="Check back soon or browse our full digital product catalog."
              action={
                <Link
                  to="/products"
                  className="dv-btn-primary inline-block text-xs font-semibold uppercase tracking-wider px-5 py-2.5"
                >
                  Browse All Products
                </Link>
              }
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
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
        </>
      )}
    </StorefrontLayout>
  );
};

export default CategoryDetailPage;
