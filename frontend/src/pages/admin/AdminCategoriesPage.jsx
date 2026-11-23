import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Edit3, FolderTree, Plus, Search, Trash2 } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  LoadingState,
  Pagination,
  ToastBanner,
} from '../../components/common/StorefrontDesignSystem';
import { AdminStatusBadge } from '../../components/admin/AdminPrimitives';
import { adminCatalogApi } from '../../services/api';

const AdminCategoriesPage = () => {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const fetchCategories = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = { page, page_size: 10 };
      if (search.trim()) params.search = search.trim();
      if (statusFilter === 'active') params.is_active = true;
      if (statusFilter === 'inactive') params.is_active = false;
      const res = await adminCatalogApi.listCategories(params);
      setData(res);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to load categories.');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  const handleDelete = async () => {
    if (!confirmDelete) return;
    setDeleting(true);
    setToast(null);
    try {
      await adminCatalogApi.deleteCategory(confirmDelete.id);
      setToast({ type: 'success', message: `Category "${confirmDelete.name}" deleted.` });
      setConfirmDelete(null);
      fetchCategories();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not delete category.',
      });
      setConfirmDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <AdminLayout
      title="Categories"
      subtitle="Organize digital product taxonomy, URL slugs, and storefront visibility"
      actions={
        <Link
          to="/admin/categories/new"
          className="dv-btn-primary text-[12px] font-semibold px-4 py-2 inline-flex items-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Category</span>
        </Link>
      }
    >
      {error && <ErrorAlert message={error} onRetry={fetchCategories} className="mb-5" />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-5" />

      {/* Search & Status Filters */}
      <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-4 mb-5 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shadow-2xs">
        <div className="relative flex-1">
          <label htmlFor="admin-categories-search" className="sr-only">
            Search categories
          </label>
          <Search
            className="w-4 h-4 text-[#94A3B8] absolute left-3.5 top-1/2 -translate-y-1/2"
            aria-hidden="true"
          />
          <input
            id="admin-categories-search"
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search categories by name, slug, or description..."
            className="dv-input pl-10 pr-4 py-2 text-[13px]"
          />
        </div>

        <select
          aria-label="Filter categories by status"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input sm:w-44 px-3.5 py-2 text-[13px]"
        >
          <option value="all">All Statuses</option>
          <option value="active">Active Only</option>
          <option value="inactive">Inactive Only</option>
        </select>
      </div>

      {/* Categories Table */}
      <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
        {loading ? (
          <LoadingState label="Loading categories..." />
        ) : data.items.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={FolderTree}
              title="No categories found"
              description="No categories matched your current filter."
              action={
                <Link
                  to="/admin/categories/new"
                  className="dv-btn-primary text-[12px] font-semibold px-4 py-2 inline-flex items-center gap-1.5"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Category</span>
                </Link>
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#D5DEE8] bg-[#18243A] text-[#CBD5E1] text-[11.5px] font-semibold">
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Slug</th>
                  <th className="py-3 px-4">Products</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                {data.items.map((cat) => (
                  <tr key={cat.id} className="hover:bg-[#18243A]/70 transition">
                    <td className="py-3.5 px-4">
                      <p className="font-semibold text-[#F1F5F9]">{cat.name}</p>
                      {cat.description && (
                        <p className="text-[12px] text-[#94A3B8] truncate max-w-md mt-0.5">
                          {cat.description}
                        </p>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-[12px] text-[#CBD5E1]">
                      {cat.slug}
                    </td>
                    <td className="py-3.5 px-4 font-mono tabular-nums text-[#F1F5F9]">
                      {cat.product_count}
                    </td>
                    <td className="py-3.5 px-4">
                      <AdminStatusBadge status={cat.is_active ? 'active' : 'inactive'} />
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <Link
                          to={`/admin/categories/${cat.id}/edit`}
                          className="p-1.5 rounded-lg border border-[#D5DEE8] bg-[#111C30] hover:border-[#93C5FD] hover:bg-[#18243A] hover:text-[#60A5FA] text-[#F1F5F9] transition"
                          title="Edit Category"
                          aria-label={`Edit ${cat.name}`}
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </Link>
                        <button
                          type="button"
                          onClick={() => setConfirmDelete(cat)}
                          className="p-1.5 rounded-lg border border-[#D5DEE8] bg-[#111C30] hover:border-red-300 hover:bg-red-950/60 text-red-300 transition"
                          title="Delete Category"
                          aria-label={`Delete ${cat.name}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Pagination
        page={data.page}
        totalPages={data.total_pages}
        totalItems={data.total}
        itemLabel="categories"
        onPageChange={(nextPage) => setPage(nextPage)}
      />

      <ConfirmDialog
        open={Boolean(confirmDelete)}
        title={`Delete category "${confirmDelete?.name}"?`}
        description="Categories containing active or historical products cannot be deleted."
        confirmLabel={deleting ? 'Deleting...' : 'Delete Category'}
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(null)}
      />
    </AdminLayout>
  );
};

export default AdminCategoriesPage;
