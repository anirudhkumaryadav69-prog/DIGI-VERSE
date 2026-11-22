import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, MapPin, Package, Search, Store } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import {
  Badge,
  EmptyState,
  ErrorAlert,
  LoadingState,
  Pagination,
  SectionHeading,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import {
  StorefrontAvatarLogo,
  StorefrontBannerVisual,
} from '../../components/products/StorefrontVisual';
import { resolveStorefrontTheme } from '../../utils/categoryTheme';
import { publicCatalogApi } from '../../services/api';

const StoresDirectoryPage = () => {
  const [data, setData] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useDocumentMeta({
    title: 'Creator Stores',
    description: 'Explore verified independent creators and studios selling digital products on DIGI-VERSE.',
    canonicalPath: '/stores',
  });

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 250);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    setLoading(true);
    setError('');
    publicCatalogApi
      .listStores({ page, page_size: 18, search: debounced.trim() || undefined })
      .then((res) => setData(res))
      .catch(() => setError('Unable to load creator stores right now.'))
      .finally(() => setLoading(false));
  }, [page, debounced]);

  return (
    <StorefrontLayout>
      <SectionHeading
        eyebrow="Verified Sellers"
        title="Creator Storefronts"
        subtitle="Discover independent studios and verified digital creators publishing on DIGI-VERSE."
        action={
          <div className="relative w-full sm:w-80">
            <label htmlFor="stores-search-input" className="sr-only">
              Search creator stores
            </label>
            <Search
              className="w-4 h-4 text-[#64748B] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
              aria-hidden="true"
            />
            <input
              id="stores-search-input"
              type="search"
              value={search}
              onChange={(e) => {
                setPage(1);
                setSearch(e.target.value);
              }}
              placeholder="Search stores or creators..."
              aria-label="Search creator stores"
              className="dv-input pl-10 pr-3.5 py-2.5 text-[13px]"
            />
          </div>
        }
      />

      <div className="space-y-8">
        {error && <ErrorAlert message={error} />}

        {loading ? (
          <LoadingState label="Loading creator storefronts..." />
        ) : !data.items.length ? (
          <EmptyState
            icon={Store}
            title="No creator storefronts match your search"
            description="Browse all digital products or become the first verified creator in this niche."
            action={
              <Link to="/products" className="dv-btn-primary px-5 py-2.5 text-xs font-semibold inline-block">
                Browse All Products
              </Link>
            }
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.items.map((store) => {
              const theme = resolveStorefrontTheme(store);
              return (
                <Link
                  key={store.id}
                  to={`/store/${store.store_slug}`}
                  className="group dv-card-interactive overflow-hidden flex flex-col justify-between"
                >
                  <div>
                    <div className="h-28 border-b border-[#E5E7EB] relative overflow-hidden">
                      <StorefrontBannerVisual store={store} theme={theme} />
                    </div>

                    <div className="p-5 pt-0 relative z-10">
                      <div className="flex items-end justify-between gap-2 -mt-7 mb-3">
                        <StorefrontAvatarLogo store={store} theme={theme} />
                        <Badge variant="accent">{store.business_type}</Badge>
                      </div>

                      <h2 className="text-lg font-bold text-[#263445] group-hover:text-[#2563EB] transition">
                        {store.store_name}
                      </h2>
                      <p className="text-xs text-[#64748B] mt-0.5">by {store.seller_display_name}</p>

                      {store.store_description && (
                        <p className="text-xs text-[#263445] line-clamp-2 mt-3 leading-relaxed">
                          {store.store_description}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="px-5 py-3.5 border-t border-[#E5E7EB] bg-[#F8FAFC] flex items-center justify-between text-xs text-[#64748B]">
                    <span className="inline-flex items-center gap-1.5">
                      <Package className="w-3.5 h-3.5 text-[#2563EB]" aria-hidden="true" />
                      <strong className="text-[#263445]">{store.published_product_count}</strong> products
                    </span>
                    <span className="inline-flex items-center gap-1 text-[#2563EB] font-semibold">
                      <MapPin className="w-3 h-3" aria-hidden="true" /> {store.country}
                      <ArrowRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}

        <Pagination page={page} totalPages={data.total_pages} onPageChange={setPage} />
      </div>
    </StorefrontLayout>
  );
};

export default StoresDirectoryPage;
