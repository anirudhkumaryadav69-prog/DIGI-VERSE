import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Lock,
  PlayCircle,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react';
import StorefrontHeader from '../../components/common/StorefrontHeader';
import StorefrontFooter from '../../components/common/StorefrontFooter';
import ProductCard from '../../components/products/ProductCard';
import CategoryCard from '../../components/products/CategoryCard';
import {
  ErrorAlert,
  SectionHeading,
  ToastBanner,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { checkBackendHealth, commerceApi, publicCatalogApi } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import {
  assertArrayResponse,
  assertObjectResponse,
  assertPaginatedResponse,
} from '../../utils/apiValidation';

const HomePage = () => {
  const navigate = useNavigate();
  const { isAuthenticated, refreshCartAndWishlistCounts } = useAuth();

  const [healthStatus, setHealthStatus] = useState('checking');
  const [banners, setBanners] = useState([]);
  const [videos, setVideos] = useState([]);
  const [categories, setCategories] = useState([]);
  const [bestSellers, setBestSellers] = useState([]);
  const [recentProducts, setRecentProducts] = useState([]);
  const [discountedProducts, setDiscountedProducts] = useState([]);
  const [storeSettings, setStoreSettings] = useState({});
  const [catalogError, setCatalogError] = useState('');
  const [toast, setToast] = useState({ type: '', message: '' });

  useDocumentMeta({
    title: 'Curated Digital Marketplace',
    description:
      'Discover curated digital products, UI systems, code templates, and creator toolkits with cryptographic payment verification and instant signed digital downloads.',
    canonicalPath: '/',
  });

  const loadHomeData = useCallback(async () => {
    setCatalogError('');

    const [
      healthRes,
      bannersRes,
      videosRes,
      settingsRes,
      categoriesRes,
      bestRes,
      recentRes,
      dealsRes,
    ] = await Promise.allSettled([
      checkBackendHealth(),
      publicCatalogApi.listBanners(),
      publicCatalogApi.listVideos(),
      publicCatalogApi.getPublicSettings(),
      publicCatalogApi.listCategories({ page: 1, page_size: 8 }),
      publicCatalogApi.listProducts({ page: 1, page_size: 4, sort_by: 'popularity' }),
      publicCatalogApi.listProducts({ page: 1, page_size: 8, sort_by: 'newest' }),
      publicCatalogApi.listProducts({ page: 1, page_size: 4, on_sale: true }),
    ]);

    if (healthRes.status === 'fulfilled') {
      const healthData = healthRes.value;
      setHealthStatus(healthData?.status === 'healthy' ? 'online' : 'degraded');
    } else {
      setHealthStatus('offline');
    }

    if (bannersRes.status === 'fulfilled') {
      try {
        setBanners(assertArrayResponse(bannersRes.value, 'banners'));
      } catch {
        setBanners([]);
      }
    } else {
      setBanners([]);
    }

    if (videosRes.status === 'fulfilled') {
      try {
        setVideos(assertArrayResponse(videosRes.value, 'videos'));
      } catch {
        setVideos([]);
      }
    } else {
      setVideos([]);
    }

    if (settingsRes.status === 'fulfilled') {
      try {
        setStoreSettings(assertObjectResponse(settingsRes.value, 'public settings'));
      } catch {
        setStoreSettings({});
      }
    }

    let coreFailureCount = 0;

    if (categoriesRes.status === 'fulfilled') {
      try {
        setCategories(assertPaginatedResponse(categoriesRes.value, 'categories').items);
      } catch {
        setCategories([]);
        coreFailureCount += 1;
      }
    } else {
      setCategories([]);
      coreFailureCount += 1;
    }

    if (bestRes.status === 'fulfilled') {
      try {
        setBestSellers(assertPaginatedResponse(bestRes.value, 'best sellers').items);
      } catch {
        setBestSellers([]);
        coreFailureCount += 1;
      }
    } else {
      setBestSellers([]);
      coreFailureCount += 1;
    }

    if (recentRes.status === 'fulfilled') {
      try {
        setRecentProducts(assertPaginatedResponse(recentRes.value, 'recent products').items);
      } catch {
        setRecentProducts([]);
        coreFailureCount += 1;
      }
    } else {
      setRecentProducts([]);
      coreFailureCount += 1;
    }

    if (dealsRes.status === 'fulfilled') {
      try {
        setDiscountedProducts(assertPaginatedResponse(dealsRes.value, 'discounted products').items);
      } catch {
        setDiscountedProducts([]);
      }
    } else {
      setDiscountedProducts([]);
    }

    if (coreFailureCount >= 3) {
      setCatalogError(
        'Marketplace catalog services are currently unavailable. Check backend connectivity or API configuration and try again.'
      );
    }
  }, []);

  useEffect(() => {
    loadHomeData();
  }, [loadHomeData]);

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
        message: typeof detail === 'string' ? detail : 'Could not save product to wishlist.',
      });
    }
  };

  const storeName = storeSettings['store.name'] || 'DIGI-VERSE';

  return (
    <div className="min-h-screen bg-[#EAF4FC] text-[#263445] flex flex-col justify-between px-4 py-6 sm:px-6 md:px-10 overflow-x-hidden">
      <StorefrontHeader
        announcementText={storeSettings['store.announcement_text']}
        storeName={storeName}
      />

      <main className="max-w-7xl w-full mx-auto py-8 md:py-12 flex-1 space-y-16">
        {toast.message && (
          <ToastBanner toast={toast} onDismiss={() => setToast({ type: '', message: '' })} />
        )}

        {catalogError && <ErrorAlert message={catalogError} onRetry={loadHomeData} />}

        {/* 1. Hero Section (Soft White Elevated Surface) */}
        <section className="relative overflow-hidden rounded-3xl bg-[#F8FAFC] border border-[#D5DEE8] p-6 sm:p-10 md:p-12 shadow-[0_8px_28px_-8px_rgba(38,52,69,0.08)]">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -top-24 -right-24 w-72 h-72 rounded-full bg-[#DCE6EF]/70 blur-2xl"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -bottom-20 -left-20 w-56 h-56 rounded-full bg-[#EAF4FC] blur-2xl"
          />

          <div className="relative grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 text-xs font-medium px-3.5 py-1.5 rounded-full border border-[#D5DEE8] bg-white shadow-2xs">
                <Activity className="w-3.5 h-3.5 text-[#0EA5E9]" aria-hidden="true" />
                <span className="text-[#64748B]">System Status:</span>
                <span
                  className={
                    healthStatus === 'online'
                      ? 'text-[#16A34A] font-semibold'
                      : healthStatus === 'checking'
                      ? 'text-[#64748B]'
                      : 'text-[#DC2626] font-semibold'
                  }
                >
                  {healthStatus}
                </span>
              </div>

              <div>
                <p className="text-xs tracking-[0.02em] text-[#2563EB] font-semibold mb-2.5">
                  {storeName} — Digital Commerce Platform
                </p>
                <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-[#263445] leading-[1.15]">
                  Curated digital products for{' '}
                  <span className="text-[#2563EB]">modern creators</span>.
                </h1>
              </div>

              <p className="text-[#64748B] text-sm md:text-base leading-relaxed max-w-2xl">
                Discover professional UI kits, code architectures, and design systems. Save assets
                to your wishlist, build your cart, checkout with server-verified cryptographic
                payment signatures, and unlock instant signed digital downloads.
              </p>

              <div className="flex flex-wrap gap-3 pt-2">
                <Link
                  to="/products"
                  className="dv-btn-primary px-6 py-3 text-[13px] font-semibold inline-flex items-center gap-2"
                >
                  <span>Browse Products</span>
                  <ArrowRight className="w-4 h-4" aria-hidden="true" />
                </Link>
                <Link
                  to="/categories"
                  className="dv-btn-secondary px-6 py-3 text-[13px] font-semibold inline-flex items-center gap-2"
                >
                  <span>Explore Categories</span>
                </Link>
              </div>
            </div>

            <div className="lg:col-span-5 bg-white border border-[#D5DEE8] rounded-2xl p-6 md:p-8 space-y-5 shadow-[0_8px_24px_-6px_rgba(38,52,69,0.07)]">
              <p className="text-xs text-[#2563EB] font-semibold">
                Verified Digital Delivery Standard
              </p>
              <div className="space-y-4 text-xs text-[#64748B]">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-[#EAF4FC] border border-[#D5DEE8] flex items-center justify-center text-[#2563EB] shrink-0">
                    <Lock className="w-4 h-4" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="font-semibold text-[#263445]">Authoritative Backend Pricing</p>
                    <p className="mt-0.5 leading-relaxed">
                      Every price, active discount, and line total is computed and snapshotted on
                      the server at checkout.
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-[#EAF4FC] border border-[#D5DEE8] flex items-center justify-center text-[#0EA5E9] shrink-0">
                    <Zap className="w-4 h-4" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="font-semibold text-[#263445]">Short-Lived Signed Download Grants</p>
                    <p className="mt-0.5 leading-relaxed">
                      Private storage paths are never exposed. Downloads use authenticated,
                      time-limited cryptographic tokens.
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-[#EAF4FC] border border-[#D5DEE8] flex items-center justify-center text-[#16A34A] shrink-0">
                    <ShieldCheck className="w-4 h-4" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="font-semibold text-[#263445]">Complete Order &amp; Invoice History</p>
                    <p className="mt-0.5 leading-relaxed">
                      Download official purchase receipts and manage your digital library from your
                      account dashboard.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 2. Active Promotional Banners (Shown only when active & scheduled) */}
        {banners.length > 0 && (
          <section aria-label="Promotional Banners" className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {banners.map((b) => (
              <div
                key={b.id}
                className="bg-white border border-[#D5DEE8] rounded-2xl p-6 md:p-8 flex flex-col justify-between gap-4 shadow-xs"
              >
                <div>
                  <span className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full bg-[#EAF4FC] border border-[#BFDBFE] text-[#1D4ED8] font-semibold">
                    <Sparkles className="w-3.5 h-3.5 text-[#2563EB]" aria-hidden="true" />
                    <span>Featured Promotion</span>
                  </span>
                  <h2 className="text-xl md:text-2xl font-bold text-[#263445] mt-3">
                    {b.heading}
                  </h2>
                  {b.subtitle && <p className="text-xs text-[#64748B] mt-1.5">{b.subtitle}</p>}
                  {b.promotional_text && (
                    <p className="text-xs text-[#64748B] mt-2 leading-relaxed">
                      {b.promotional_text}
                    </p>
                  )}
                </div>
                {b.cta_destination && (
                  <Link
                    to={b.cta_destination}
                    className="text-xs font-semibold text-[#2563EB] inline-flex items-center gap-1.5 hover:text-[#1D4ED8] transition"
                  >
                    <span>{b.cta_text || 'Explore Promotion'}</span>
                    <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
                  </Link>
                )}
              </div>
            ))}
          </section>
        )}

        {/* 3. Featured Categories */}
        {categories.length > 0 && (
          <section>
            <SectionHeading
              eyebrow="Taxonomy"
              title="Featured Categories"
              subtitle="Browse curated collections organized by discipline and format."
              action={
                <Link
                  to="/categories"
                  className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1 transition"
                >
                  <span>View All Categories</span>
                  <ArrowUpRight className="w-3.5 h-3.5" aria-hidden="true" />
                </Link>
              }
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 items-stretch">
              {categories.map((cat) => (
                <CategoryCard key={cat.id} category={cat} />
              ))}
            </div>
          </section>
        )}

        {/* 4. Promotional Offers & Active Discounts (Secondary Blue-Grey Band) */}
        {discountedProducts.length > 0 && (
          <section className="rounded-3xl bg-[#DCE6EF]/75 border border-[#D5DEE8] p-6 sm:p-8">
            <SectionHeading
              eyebrow="Limited-Time Savings"
              title="Promotional Offers & Discounts"
              subtitle="Verified active discounts calculated directly from the live catalog."
              action={
                <Link
                  to="/products?on_sale=true"
                  className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1 transition"
                >
                  <span>All Discounted Products</span>
                  <ArrowUpRight className="w-3.5 h-3.5" aria-hidden="true" />
                </Link>
              }
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 items-stretch">
              {discountedProducts.map((prod) => (
                <ProductCard
                  key={prod.id}
                  product={prod}
                  onAddToCart={handleAddToCart}
                  onAddToWishlist={handleAddToWishlist}
                />
              ))}
            </div>
          </section>
        )}

        {/* 5. Best-Selling & Featured Products (Soft White Band) */}
        {bestSellers.length > 0 && (
          <section className="rounded-3xl bg-[#F8FAFC] border border-[#D5DEE8] p-6 sm:p-8">
            <SectionHeading
              eyebrow="Popular Selection"
              title="Featured & Best-Selling Products"
              subtitle="Digital products ordered by verified customer purchases."
              action={
                <Link
                  to="/products?sort_by=popularity"
                  className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1 transition"
                >
                  <span>Explore Popular</span>
                  <ArrowUpRight className="w-3.5 h-3.5" aria-hidden="true" />
                </Link>
              }
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 items-stretch">
              {bestSellers.map((prod) => (
                <ProductCard
                  key={prod.id}
                  product={prod}
                  onAddToCart={handleAddToCart}
                  onAddToWishlist={handleAddToWishlist}
                />
              ))}
            </div>
          </section>
        )}

        {/* 6. Recently Added Products */}
        {recentProducts.length > 0 && (
          <section>
            <SectionHeading
              eyebrow="Latest Releases"
              title="Recently Added Products"
              subtitle="Fresh additions to the DIGI-VERSE digital product catalog."
              action={
                <Link
                  to="/products?sort_by=newest"
                  className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] inline-flex items-center gap-1 transition"
                >
                  <span>Browse Full Catalog</span>
                  <ArrowUpRight className="w-3.5 h-3.5" aria-hidden="true" />
                </Link>
              }
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 items-stretch">
              {recentProducts.map((prod) => (
                <ProductCard
                  key={prod.id}
                  product={prod}
                  onAddToCart={handleAddToCart}
                  onAddToWishlist={handleAddToWishlist}
                />
              ))}
            </div>
          </section>
        )}

        {/* 7. Advertisement Video Section */}
        {videos.length > 0 && (
          <section>
            <SectionHeading
              eyebrow="Creator Showcases"
              title="Featured Product Spotlights"
              subtitle="Tour featured digital toolkits and creator workflows."
            />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {videos.slice(0, 4).map((v) => (
                <div
                  key={v.id}
                  className="bg-white border border-[#D5DEE8] rounded-2xl p-6 md:p-8 flex flex-col justify-between gap-4 shadow-xs"
                >
                  <div>
                    <div className="inline-flex items-center gap-2 text-xs px-3 py-1 rounded-full bg-[#EAF4FC] border border-[#BFDBFE] text-[#1D4ED8] font-semibold mb-3">
                      <PlayCircle className="w-3.5 h-3.5 text-[#2563EB]" aria-hidden="true" />
                      <span>Video Spotlight</span>
                    </div>
                    <h3 className="text-lg font-bold text-[#263445]">{v.title}</h3>
                    {v.description && (
                      <p className="text-xs text-[#64748B] mt-2 leading-relaxed">{v.description}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 pt-2">
                    {v.destination_url && (
                      <Link
                        to={v.destination_url}
                        className="dv-btn-primary text-xs font-semibold px-4 py-2.5 inline-flex items-center gap-1.5"
                      >
                        <span>Explore Featured Collection</span>
                        <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>

      <StorefrontFooter storeSettings={storeSettings} />
    </div>
  );
};

export default HomePage;
