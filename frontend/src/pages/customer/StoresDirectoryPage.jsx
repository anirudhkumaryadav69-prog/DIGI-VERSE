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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <SectionHeading
            eyebrow="Verified Sellers"
            title="Creator Storefronts"
            subtitle="Discover independent studios and verified digital creators publishing on DIGI-VERSE."
          />

          <div className="relative w-full md:w-80">
            <Search className="w-4 h-4 text-[#8490A0] absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setPage(1);
                setSearch(e.target.value);
              }}
              placeholder="Search stores or creators..."
              aria-label="Search creator stores"
              className="dv-input pl-10 text-sm"
            />
          </div>
        </div>

        {error && <ErrorAlert message={error} />}

        {loading ? (
          <LoadingState label="Loading creator storefronts..." />
        ) : !data.items.length ? (
          <EmptyState
            icon={Store}
            title="No creator storefronts match your search"
            description="Browse all digital products or become the first verified creator in this niche."
            action={
              <Link to="/products" className="dv-btn-primary px-5 py-2.5 text-xs">
                Browse All Products
              </Link>
            }
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.items.map((store) => (
              <Link
                key={store.id}
                to={`/store/${store.store_slug}`}
                className="group dv-card-interactive overflow-hidden flex flex-col justify-between"
              >
                <div>
                  <div className="h-28 bg-[#FFF6ED] border-b border-[#E5E7EB] relative overflow-hidden">
                    {store.banner_url ? (
                      <img
                        src={store.banner_url}
                        alt={`${store.store_name} banner`}
                        loading="lazy"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full bg-linear-to-r from-[#FFF2E6] via-[#FFE9D6] to-[#FFF6ED]" />
                    )}
                  </div>

                  <div className="p-5 pt-0">
                    <div className="flex items-end justify-between -mt-7 mb-3">
                      <div className="w-14 h-14 rounded-2xl bg-white border-2 border-[#FFD4AE] shadow-xs overflow-hidden flex items-center justify-center">
                        {store.logo_url ? (
                          <img
                            src={store.logo_url}
                            alt={store.store_name}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <Store className="w-6 h-6 text-[#FF6B0A]" />
                        )}
                      </div>
                      <Badge variant="orange">{store.business_type}</Badge>
                    </div>

                    <h2 className="text-lg font-bold text-[#1F2937] group-hover:text-[#FF6B0A] transition">
                      {store.store_name}
                    </h2>
                    <p className="text-xs text-[#64748B] mt-0.5">by {store.seller_display_name}</p>

                    {store.store_description && (
                      <p className="text-xs text-[#243247] line-clamp-2 mt-3 leading-relaxed">
                        {store.store_description}
                      </p>
                    )}
                  </div>
                </div>

                <div className="px-5 py-3.5 border-t border-[#E5E7EB] bg-[#FFFAF5] flex items-center justify-between text-xs text-[#64748B]">
                  <span className="inline-flex items-center gap-1.5">
                    <Package className="w-3.5 h-3.5 text-[#FF6B0A]" />
                    <strong className="text-[#1F2937]">{store.published_product_count}</strong> products
                  </span>
                  <span className="inline-flex items-center gap-1 text-[#FF6B0A] font-semibold">
                    <MapPin className="w-3 h-3" /> {store.country}
                    <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}

        <Pagination page={page} totalPages={data.total_pages} onPageChange={setPage} />
      </div>
    </StorefrontLayout>
  );
};

export default StoresDirectoryPage;
