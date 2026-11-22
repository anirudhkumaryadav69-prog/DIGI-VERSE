import { useCallback, useEffect, useState } from 'react';
import { FolderTree, Search } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import CategoryCard from '../../components/products/CategoryCard';
import {
  EmptyState,
  ErrorAlert,
  LoadingState,
  SectionHeading,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { publicCatalogApi } from '../../services/api';

const CategoriesPage = () => {
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useDocumentMeta({
    title: 'Product Categories',
    description: 'Explore DIGI-VERSE digital product categories and curated asset collections.',
    canonicalPath: '/categories',
  });

  const fetchCategories = useCallback(() => {
    setLoading(true);
    setError('');
    publicCatalogApi
      .listCategories({ page: 1, page_size: 50, search: search.trim() || undefined })
      .then((res) => setCategories(res.items || []))
      .catch(() => setError('Unable to load categories right now.'))
      .finally(() => setLoading(false));
  }, [search]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  return (
    <StorefrontLayout>
      <SectionHeading
        eyebrow="Browse Collections"
        title="Digital Product Categories"
        subtitle="Explore curated toolkits, UI kits, study guides, templates, and creator assets across eight marketplace categories."
        action={
          <div className="relative w-full sm:w-72">
            <label htmlFor="category-search" className="sr-only">
              Search categories
            </label>
            <Search
              className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2"
              aria-hidden="true"
            />
            <input
              id="category-search"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search categories..."
              className="dv-input pl-10 pr-4 py-2 text-[13px]"
            />
          </div>
        }
      />

      {error && <ErrorAlert message={error} onRetry={fetchCategories} className="mb-6" />}

      {loading ? (
        <LoadingState label="Loading categories..." />
      ) : categories.length === 0 ? (
        <EmptyState
          icon={FolderTree}
          title="No categories found"
          description="No active product categories matched your search."
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 items-stretch">
          {categories.map((cat) => (
            <CategoryCard key={cat.id} category={cat} />
          ))}
        </div>
      )}
    </StorefrontLayout>
  );
};

export default CategoriesPage;
