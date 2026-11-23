import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Upload } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  ErrorAlert,
  LoadingState,
  ToastBanner,
} from '../../components/common/StorefrontDesignSystem';
import { adminCatalogApi } from '../../services/api';

const toKebabSlug = (val) =>
  val
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-|-$/g, '');

const AdminCategoryFormPage = () => {
  const { id } = useParams();
  const isEditing = Boolean(id);
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    description: '',
    image_url: '',
    is_active: true,
  });
  const [autoSlug, setAutoSlug] = useState(!isEditing);
  const [loading, setLoading] = useState(isEditing);
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!isEditing) return;
    setLoading(true);
    adminCatalogApi
      .getCategory(id)
      .then((cat) => {
        setFormData({
          name: cat.name || '',
          slug: cat.slug || '',
          description: cat.description || '',
          image_url: cat.image_url || '',
          is_active: Boolean(cat.is_active),
        });
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Unable to load category.');
      })
      .finally(() => setLoading(false));
  }, [id, isEditing]);

  const handleNameChange = (name) => {
    setFormData((prev) => ({
      ...prev,
      name,
      slug: autoSlug ? toKebabSlug(name) : prev.slug,
    }));
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    setUploadingImage(true);
    try {
      const res = await adminCatalogApi.uploadStandaloneImage(file);
      setFormData((prev) => ({ ...prev, image_url: res.image_url }));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Image upload failed.');
    } finally {
      setUploadingImage(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setToast(null);

    if (formData.name.trim().length < 2) {
      setError('Category name must be at least 2 characters.');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: formData.name.trim(),
        slug: formData.slug.trim() || undefined,
        description: formData.description.trim() || null,
        image_url: formData.image_url.trim() || null,
        is_active: formData.is_active,
      };
      if (isEditing) {
        await adminCatalogApi.updateCategory(id, payload);
        setToast({ type: 'success', message: 'Category updated successfully.' });
      } else {
        await adminCatalogApi.createCategory(payload);
        setToast({ type: 'success', message: 'Category created successfully.' });
      }
      setTimeout(() => navigate('/admin/categories'), 600);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to save category.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout
      title={isEditing ? 'Edit Category' : 'Create Category'}
      subtitle="Define category metadata, URL slug, and storefront visibility"
      actions={
        <Link
          to="/admin/categories"
          className="dv-btn-secondary text-[12px] font-semibold px-4 py-2 inline-flex items-center gap-1.5"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Categories</span>
        </Link>
      }
    >
      <div className="max-w-2xl bg-[#111C30] border border-[#D5DEE8] rounded-xl p-6 md:p-7 shadow-2xs">
        {error && <ErrorAlert message={error} className="mb-5" />}
        <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-5" />

        {loading ? (
          <LoadingState label="Loading category details..." />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="cat-name"
                className="block text-[12.5px] font-medium text-[#F1F5F9] mb-1.5"
              >
                Category Name *
              </label>
              <input
                id="cat-name"
                type="text"
                required
                value={formData.name}
                onChange={(e) => handleNameChange(e.target.value)}
                className="dv-input px-3.5 py-2.5 text-[13.5px]"
                placeholder="e.g. UI & UX Design Systems"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="cat-slug"
                  className="block text-[12.5px] font-medium text-[#F1F5F9]"
                >
                  URL Slug (kebab-case)
                </label>
                <label className="text-[12px] text-[#94A3B8] flex items-center gap-1.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={autoSlug}
                    onChange={(e) => setAutoSlug(e.target.checked)}
                    className="accent-[#2563EB]"
                  />
                  <span>Auto-generate from name</span>
                </label>
              </div>
              <input
                id="cat-slug"
                type="text"
                value={formData.slug}
                onChange={(e) => {
                  setAutoSlug(false);
                  setFormData({ ...formData, slug: e.target.value });
                }}
                className="dv-input px-3.5 py-2.5 text-[13px] font-mono"
                placeholder="ui-ux-design-systems"
              />
            </div>

            <div>
              <label
                htmlFor="cat-description"
                className="block text-[12.5px] font-medium text-[#F1F5F9] mb-1.5"
              >
                Description
              </label>
              <textarea
                id="cat-description"
                rows={4}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="dv-input px-3.5 py-2.5 text-[13.5px]"
                placeholder="Describe the digital products included in this category..."
              />
            </div>

            <div>
              <span className="block text-[12.5px] font-medium text-[#F1F5F9] mb-1.5">
                Category Cover Image (Optional)
              </span>
              <div className="flex flex-wrap items-center gap-4">
                <label className="dv-btn-secondary cursor-pointer px-4 py-2 text-[12px] font-medium inline-flex items-center gap-2">
                  <Upload className="w-3.5 h-3.5 text-[#60A5FA]" />
                  <span>{uploadingImage ? 'Uploading...' : 'Upload Image'}</span>
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg,.webp"
                    onChange={handleImageUpload}
                    className="hidden"
                  />
                </label>
                {formData.image_url && (
                  <div className="flex items-center gap-3">
                    <img
                      src={formData.image_url}
                      alt="Category preview"
                      className="w-12 h-12 object-cover rounded-lg border border-[#D5DEE8]"
                    />
                    <button
                      type="button"
                      onClick={() => setFormData({ ...formData, image_url: '' })}
                      className="text-[12px] font-medium text-red-300 hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div className="pt-1">
              <label className="flex items-center gap-2.5 cursor-pointer text-[13px] select-none">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="accent-[#2563EB]"
                />
                <span className="text-[#F1F5F9]">
                  Category is active and visible in the public storefront
                </span>
              </label>
            </div>

            <div className="pt-4 border-t border-[#E5E7EB] flex justify-end gap-2.5">
              <Link
                to="/admin/categories"
                className="dv-btn-secondary px-5 py-2 text-[12px] font-semibold"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={saving}
                className="dv-btn-primary px-6 py-2 text-[12px] font-semibold disabled:opacity-50"
              >
                {saving ? 'Saving...' : isEditing ? 'Update Category' : 'Create Category'}
              </button>
            </div>
          </form>
        )}
      </div>
    </AdminLayout>
  );
};

export default AdminCategoryFormPage;
