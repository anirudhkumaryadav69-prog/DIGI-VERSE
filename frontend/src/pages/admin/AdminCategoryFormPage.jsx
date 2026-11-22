import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Upload, AlertCircle, CheckCircle2 } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
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
  const [success, setSuccess] = useState('');

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
    setSuccess('');

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
        setSuccess('Category updated successfully.');
      } else {
        await adminCatalogApi.createCategory(payload);
        setSuccess('Category created successfully.');
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
      subtitle="Define category metadata, URL slug, and storefront status"
      actions={
        <Link
          to="/admin/categories"
          className="dv-btn-secondary text-xs uppercase tracking-wider px-4 py-2 flex items-center gap-1.5"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Categories</span>
        </Link>
      }
    >
      <div className="max-w-2xl dv-card p-6 md:p-8">
        {error && (
          <div className="mb-6 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {success && (
          <div className="mb-6 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {loading ? (
          <p className="text-xs text-[#64748B]">Loading category details...</p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                Category Name *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => handleNameChange(e.target.value)}
                className="dv-input px-3.5 py-2.5 text-sm"
                placeholder="e.g. UI & UX Design Systems"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B]">
                  URL Slug (Kebab-Case)
                </label>
                <label className="text-[11px] text-[#64748B] flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoSlug}
                    onChange={(e) => setAutoSlug(e.target.checked)}
                  />
                  <span>Auto-generate from name</span>
                </label>
              </div>
              <input
                type="text"
                value={formData.slug}
                onChange={(e) => {
                  setAutoSlug(false);
                  setFormData({ ...formData, slug: e.target.value });
                }}
                className="dv-input px-3.5 py-2.5 text-sm font-mono"
                placeholder="ui-ux-design-systems"
              />
            </div>

            <div>
              <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                Description
              </label>
              <textarea
                rows={4}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="dv-input px-3.5 py-2.5 text-sm"
                placeholder="Describe the digital products included in this category..."
              />
            </div>

            <div>
              <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                Category Cover Image (Optional)
              </label>
              <div className="flex flex-wrap items-center gap-4">
                <label className="dv-btn-secondary cursor-pointer px-4 py-2 text-xs uppercase tracking-wider inline-flex items-center gap-2">
                  <Upload className="w-3.5 h-3.5 text-[#FF6B0A]" />
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
                      className="w-12 h-12 object-cover rounded-lg border border-[#E5E7EB]"
                    />
                    <button
                      type="button"
                      onClick={() => setFormData({ ...formData, image_url: '' })}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div className="pt-2">
              <label className="flex items-center gap-2.5 cursor-pointer text-xs">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
                <span className="text-[#243247]">
                  Category is active and visible in the public storefront
                </span>
              </label>
            </div>

            <div className="pt-4 border-t border-[#E5E7EB] flex justify-end gap-3">
              <Link
                to="/admin/categories"
                className="dv-btn-secondary px-5 py-2.5 text-xs uppercase tracking-wider"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={saving}
                className="dv-btn-primary px-6 py-2.5 text-xs uppercase tracking-widest disabled:opacity-50"
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
