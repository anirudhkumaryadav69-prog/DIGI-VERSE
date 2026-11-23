import { useEffect, useState } from 'react';
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
  SectionHeading,
  ToastBanner,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { checkBackendHealth, commerceApi, publicCatalogApi } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

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
  const [toast, setToast] = useState({ type: '', message: '' });

  useDocumentMeta({
    title: 'Curated Digital Marketplace',
    description:
      'Discover curated digital products, UI systems, code templates, and creator toolkits with cryptographic payment verification and instant signed digital downloads.',
    canonicalPath: '/',
  });

  useEffect(() => {
    checkBackendHealth()
      .then((data) => setHealthStatus(data?.status === 'healthy' ? 'online' : 'degraded'))
      .catch(() => setHealthStatus('offline'));

    publicCatalogApi
      .listBanners()
      .then((data) => setBanners(data || []))
      .catch(() => {});

    publicCatalogApi
      .listVideos()
      .then((data) => setVideos(data || []))
      .catch(() => {});

    publicCatalogApi
      .getPublicSettings()
      .then((data) => setStoreSettings(data || {}))
      .catch(() => {});

    publicCatalogApi
      .listCategories({ page: 1, page_size: 8 })
      .then((res) => setCategories(res.items || []))
      .catch(() => {});

    publicCatalogApi
      .listProducts({ page: 1, page_size: 4, sort_by: 'popularity' })
      .then((res) => setBestSellers(res.items || []))
      .catch(() => {});

    publicCatalogApi
      .listProducts({ page: 1, page_size: 8, sort_by: 'newest' })
      .then((res) => setRecentProducts(res.items || []))
      .catch(() => {});

    publicCatalogApi
      .listProducts({ page: 1, page_size: 4, on_sale: true })
      .then((res) => setDiscountedProducts(res.items || []))
      .catch(() => {});
  }, []);

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
    <div className="min-h-screen bg-[#080D19] text-[#F1F5F9] flex flex-col justify-between px-4 py-6 sm:px-6 md:px-10 overflow-x-hidden">
      <StorefrontHeader
        announcementText={storeSettings['store.announcement_text']}
        storeName={storeName}
      />

      <main className="max-w-7xl w-full mx-auto py-8 md:py-12 flex-1 space-y-16">
        {toast.message && (
          <ToastBanner toast={toast} onDismiss={() => setToast({ type: '', message: '' })} />
        )}

<<<<<<< Updated upstream
        {/* 1. Hero Section (Soft White Elevated Surface) */}
        <section className="relative overflow-hidden rounded-3xl bg-[#F8FAFC] border border-[#D5DEE8] p-6 sm:p-10 md:p-12 shadow-[0_8px_28px_-8px_rgba(38,52,69,0.08)]">
=======
        {catalogError && <ErrorAlert message={catalogError} onRetry={loadHomeData} />}

        {/* 1. Hero Section (Dark Secondary Elevated Surface) */}
        <section className="relative overflow-hidden rounded-3xl bg-[#0D1424] border border-[#D5DEE8] p-6 sm:p-10 md:p-12 shadow-[0_8px_28px_-8px_rgba(38,52,69,0.08)]">
>>>>>>> Stashed changes
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -top-24 -right-24 w-72 h-72 rounded-full bg-[#18243A]/70 blur-2xl"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -bottom-20 -left-20 w-56 h-56 rounded-full bg-[#080D19]/70 blur-2xl"
          />

          <div className="relative grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 text-xs font-medium px-3.5 py-1.5 rounded-full border border-[#D5DEE8] bg-[#111C30] shadow-2xs">
                <Activity className="w-3.5 h-3.5 text-[#0EA5E9]" aria-hidden="true" />
                <span className="text-[#94A3B8]">System Status:</span>
                <span
                  className={
                    healthStatus === 'online'
                      ? 'text-emerald-400 font-semibold'
                      : healthStatus === 'checking'
                      ? 'text-[#94A3B8]'
                      : 'text-red-400 font-semibold'
                  }
                >
                  {healthStatus}
                </span>
              </div>

              <div>
                <p className="text-xs tracking-[0.02em] text-[#60A5FA] font-semibold mb-2.5">
                  {storeName} — Digital Commerce Platform
                </p>
                <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-[#F1F5F9] leading-[1.15]">
                  Curated digital products for{' '}
                  <span className="text-[#60A5FA]">modern creators</span>.
                </h1>
              </div>

              <p className="text-[#94A3B8] text-sm md:text-base leading-relaxed max-w-2xl">
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

            <div className="lg:col-span-5 bg-[#111C30] border border-[#D5DEE8] rounded-2xl p-6 md:p-8 space-y-5 shadow-[0_8px_24px_-6px_rgba(38,52,69,0.07)]">
              <p className="text-xs text-[#60A5FA] font-semibold">
                Verified Digital Delivery Standard
              </p>
              <div className="space-y-4 text-xs text-[#94A3B8]">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-[#18243A] border border-[#D5DEE8] flex items-center justify-center text-[#60A5FA] shrink-0">
                    <Lock className="w-4 h-4" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="font-semibold text-[#F1F5F9]">Authoritative Backend Pricing</p>
                    <p className="mt-0.5 leading-relaxed">
                      Every price, active discount, and line total is computed and snapshotted on
                      the server at checkout.
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-[#18243A] border border-[#D5DEE8] flex items-center justify-center text-[#0EA5E9] shrink-0">
                    <Zap className="w-4 h-4" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="font-semibold text-[#F1F5F9]">Short-Lived Signed Download Grants</p>
                    <p className="mt-0.5 leading-relaxed">
                      Private storage paths are never exposed. Downloads use authenticated,
                      time-limited cryptographic tokens.
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-xl bg-[#18243A] border border-[#D5DEE8] flex items-center justify-center text-emerald-400 shrink-0">
                    <ShieldCheck className="w-4 h-4" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="font-semibold text-[#F1F5F9]">Complete Order &amp; Invoice History</p>
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
                className="bg-[#111C30] border border-[#D5DEE8] rounded-2xl p-6 md:p-8 flex flex-col justify-between gap-4 shadow-xs"
              >
                <div>
                  <span className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full bg-[#18243A] border border-[#BFDBFE] text-[#93C5FD] font-semibold">
                    <Sparkles className="w-3.5 h-3.5 text-[#60A5FA]" aria-hidden="true" />
                    <span>Featured Promotion</span>
                  </span>
                  <h2 className="text-xl md:text-2xl font-bold text-[#F1F5F9] mt-3">
                    {b.heading}
                  </h2>
                  {b.subtitle && <p className="text-xs text-[#94A3B8] mt-1.5">{b.subtitle}</p>}
                  {b.promotional_text && (
                    <p className="text-xs text-[#94A3B8] mt-2 leading-relaxed">
                      {b.promotional_text}
                    </p>
                  )}
                </div>
                {b.cta_destination && (
                  <Link
                    to={b.cta_destination}
                    className="text-xs font-semibold text-[#60A5FA] inline-flex items-center gap-1.5 hover:text-[#93C5FD] transition"
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
                  className="text-xs font-semibold text-[#60A5FA] hover:text-[#93C5FD] inline-flex items-center gap-1 transition"
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

        {/* 4. Promotional Offers & Active Discounts (Secondary Dark Navy Band) */}
        {discountedProducts.length > 0 && (
          <section className="rounded-3xl bg-[#0D1424] border border-[#D5DEE8] p-6 sm:p-8">
            <SectionHeading
              eyebrow="Limited-Time Savings"
              title="Promotional Offers & Discounts"
              subtitle="Verified active discounts calculated directly from the live catalog."
              action={
                <Link
                  to="/products?on_sale=true"
                  className="text-xs font-semibold text-[#60A5FA] hover:text-[#93C5FD] inline-flex items-center gap-1 transition"
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

        {/* 5. Best-Selling & Featured Products (Secondary Dark Navy Band) */}
        {bestSellers.length > 0 && (
          <section className="rounded-3xl bg-[#0D1424] border border-[#D5DEE8] p-6 sm:p-8">
            <SectionHeading
              eyebrow="Popular Selection"
              title="Featured & Best-Selling Products"
              subtitle="Digital products ordered by verified customer purchases."
              action={
                <Link
                  to="/products?sort_by=popularity"
                  className="text-xs font-semibold text-[#60A5FA] hover:text-[#93C5FD] inline-flex items-center gap-1 transition"
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
                  className="text-xs font-semibold text-[#60A5FA] hover:text-[#93C5FD] inline-flex items-center gap-1 transition"
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
                  className="bg-[#111C30] border border-[#D5DEE8] rounded-2xl p-6 md:p-8 flex flex-col justify-between gap-4 shadow-xs"
                >
                  <div>
                    <div className="inline-flex items-center gap-2 text-xs px-3 py-1 rounded-full bg-[#18243A] border border-[#BFDBFE] text-[#93C5FD] font-semibold mb-3">
                      <PlayCircle className="w-3.5 h-3.5 text-[#60A5FA]" aria-hidden="true" />
                      <span>Video Spotlight</span>
                    </div>
                    <h3 className="text-lg font-bold text-[#F1F5F9]">{v.title}</h3>
                    {v.description && (
                      <p className="text-xs text-[#94A3B8] mt-2 leading-relaxed">{v.description}</p>
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
