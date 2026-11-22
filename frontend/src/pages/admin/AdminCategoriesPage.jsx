import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Plus,
  Search,
  Edit3,
  Trash2,
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import { adminCatalogApi } from '../../services/api';

const AdminCategoriesPage = () => {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState({ type: '', message: '' });
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const fetchCategories = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 10 };
      if (search.trim()) params.search = search.trim();
      if (statusFilter === 'active') params.is_active = true;
      if (statusFilter === 'inactive') params.is_active = false;
      const res = await adminCatalogApi.listCategories(params);
      setData(res);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to load categories.',
      });
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
    setToast({ type: '', message: '' });
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
      subtitle="Organize digital product taxonomy, URL slugs, and visibility"
      actions={
        <Link
          to="/admin/categories/new"
          className="dv-btn-primary text-xs uppercase tracking-wider px-4 py-2.5 flex items-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Category</span>
        </Link>
      }
    >
      {toast.message && (
        <div
          className={`mb-6 p-4 rounded-xl border text-xs flex items-center gap-2.5 ${
            toast.type === 'error'
              ? 'bg-red-50 border-red-200 text-red-700'
              : 'bg-emerald-50 border-emerald-200 text-emerald-800'
          }`}
        >
          {toast.type === 'error' ? (
            <AlertCircle className="w-4 h-4 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Search & Status Filters */}
      <div className="dv-card p-4 mb-6 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-[#8490A0] absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search categories by name, slug, or description..."
            className="dv-input pl-10 pr-4 py-2 text-xs"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="dv-input w-auto px-3.5 py-2 text-xs"
        >
          <option value="all">All Statuses</option>
          <option value="active">Active Only</option>
          <option value="inactive">Inactive Only</option>
        </select>
      </div>

      {/* Categories Table */}
      <div className="dv-card overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-xs text-[#64748B] uppercase tracking-widest">
            Loading Categories...
          </div>
        ) : data.items.length === 0 ? (
          <div className="p-10 text-center space-y-3">
            <p className="text-xs text-[#64748B]">No categories match your current filter.</p>
            <Link
              to="/admin/categories/new"
              className="inline-block text-xs font-medium text-[#FF6B0A] hover:text-[#D94300] hover:underline"
            >
              + Create your first category
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#E5E7EB] bg-[#FFF6ED] text-[#64748B] uppercase">
                  <th className="py-3 px-4 font-semibold">Category</th>
                  <th className="py-3 px-4 font-semibold">Slug</th>
                  <th className="py-3 px-4 font-semibold">Products</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB]">
                {data.items.map((cat) => (
                  <tr key={cat.id} className="hover:bg-[#FFF0E2]/45 transition">
                    <td className="py-3.5 px-4">
                      <p className="font-semibold text-[#1F2937]">{cat.name}</p>
                      {cat.description && (
                        <p className="text-[11px] text-[#64748B] truncate max-w-md mt-0.5">
                          {cat.description}
                        </p>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-[#243247]">{cat.slug}</td>
                    <td className="py-3.5 px-4 text-[#243247]">{cat.product_count}</td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full border ${
                          cat.is_active
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-slate-100 text-[#64748B] border-[#E5E7EB]'
                        }`}
                      >
                        {cat.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="inline-flex items-center gap-2">
                        <Link
                          to={`/admin/categories/${cat.id}/edit`}
                          className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-[#FFD4AE] hover:text-[#FF6B0A] text-[#243247] transition"
                          title="Edit Category"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </Link>
                        <button
                          type="button"
                          onClick={() => setConfirmDelete(cat)}
                          className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-red-300 hover:bg-red-50 text-red-600 transition"
                          title="Delete Category"
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

        {/* Pagination Footer */}
        <div className="p-4 border-t border-[#E5E7EB] bg-[#FFF6ED] flex items-center justify-between text-xs text-[#64748B]">
          <span>
            Total: <strong className="text-[#1F2937]">{data.total}</strong> categories
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white text-[#243247] disabled:opacity-40 hover:border-[#FFD4AE] hover:text-[#FF6B0A] transition"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span>
              Page {data.page} of {data.total_pages}
            </span>
            <button
              type="button"
              disabled={page >= data.total_pages}
              onClick={() => setPage((p) => p + 1)}
              className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white text-[#243247] disabled:opacity-40 hover:border-[#FFD4AE] hover:text-[#FF6B0A] transition"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 bg-[#1F2937]/30 backdrop-blur-[2px] flex items-center justify-center p-4">
          <div className="bg-white border border-[#FFD4AE] rounded-2xl shadow-lg max-w-md w-full p-6 space-y-4">
            <h3 className="text-base font-semibold text-[#1F2937]">Delete Category</h3>
            <p className="text-xs text-[#64748B] leading-relaxed">
              Are you sure you want to delete <strong className="text-[#1F2937]">{confirmDelete.name}</strong>? Categories
              containing products cannot be deleted.
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                className="dv-btn-secondary px-4 py-2 text-xs uppercase tracking-wider"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={handleDelete}
                className="px-4 py-2 rounded-xl text-xs font-medium uppercase tracking-wider bg-red-600 text-white hover:bg-red-700 transition disabled:opacity-50"
              >
                {deleting ? 'Deleting...' : 'Delete Category'}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
};

export default AdminCategoriesPage;
