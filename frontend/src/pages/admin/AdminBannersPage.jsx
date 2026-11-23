import { useEffect, useState } from 'react';
import { CheckCircle2, Image as ImageIcon, Plus, Trash2, XCircle } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  LoadingState,
  ToastBanner,
} from '../../components/common/StorefrontDesignSystem';
import { AdminSectionHeader, AdminStatusBadge } from '../../components/admin/AdminPrimitives';
import { adminOperationsApi } from '../../services/api';

const INITIAL_FORM = {
  heading: '',
  subtitle: '',
  promotional_text: '',
  image_url: '',
  cta_text: 'Explore Catalog',
  cta_destination: '/products',
  display_priority: 10,
  is_active: true,
};

const AdminBannersPage = () => {
  const [banners, setBanners] = useState([]);
  const [form, setForm] = useState(INITIAL_FORM);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const loadBanners = () => {
    setLoading(true);
    adminOperationsApi
      .listBanners()
      .then((data) => {
        setBanners(data || []);
        setError('');
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load promotional banners.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadBanners();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    setToast(null);
    try {
      await adminOperationsApi.createBanner({
        ...form,
        display_priority: Number(form.display_priority || 0),
      });
      setForm(INITIAL_FORM);
      setToast({ type: 'success', message: 'Promotional banner created.' });
      loadBanners();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to create banner.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (banner) => {
    setToast(null);
    try {
      const updated = await adminOperationsApi.updateBanner(banner.id, {
        is_active: !banner.is_active,
      });
      setBanners((prev) => prev.map((b) => (b.id === banner.id ? updated : b)));
      setToast({
        type: 'success',
        message: `Banner "${banner.heading}" marked ${updated.is_active ? 'active' : 'inactive'}.`,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update banner status.');
    }
  };

  const handleDelete = async (banner) => {
    try {
      await adminOperationsApi.deleteBanner(banner.id);
      setBanners((prev) => prev.filter((b) => b.id !== banner.id));
      setToast({ type: 'success', message: `Banner "${banner.heading}" deleted.` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to delete banner.');
    } finally {
      setConfirmDelete(null);
    }
  };

  return (
    <AdminLayout
      title="Promotional Banners"
      subtitle="Manage storefront promotional banners with priority ordering"
    >
      {error && <ErrorAlert message={error} onRetry={loadBanners} className="mb-5" />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-5" />

      {/* Create Banner Form */}
      <form
        onSubmit={handleCreate}
        className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-6 mb-6 space-y-4 shadow-2xs"
      >
        <AdminSectionHeader
          icon={ImageIcon}
          title="Create Promotional Banner"
          subtitle="Configure hero callout messaging and storefront destination links"
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          <div>
            <label
              htmlFor="banner-heading"
              className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5"
            >
              Banner Heading *
            </label>
            <input
              id="banner-heading"
              type="text"
              required
              value={form.heading}
              onChange={(e) => setForm({ ...form, heading: e.target.value })}
              placeholder="e.g. Creators Week — Up to 50% Off"
              className="dv-input px-3.5 py-2 text-[13px]"
            />
          </div>

          <div>
            <label
              htmlFor="banner-subtitle"
              className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5"
            >
              Subtitle
            </label>
            <input
              id="banner-subtitle"
              type="text"
              value={form.subtitle}
              onChange={(e) => setForm({ ...form, subtitle: e.target.value })}
              placeholder="e.g. Curated UI Kits, 3D Assets & Code Templates"
              className="dv-input px-3.5 py-2 text-[13px]"
            />
          </div>

          <div>
            <label
              htmlFor="banner-image-url"
              className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5"
            >
              Banner Image URL *
            </label>
            <input
              id="banner-image-url"
              type="text"
              required
              value={form.image_url}
              onChange={(e) => setForm({ ...form, image_url: e.target.value })}
              placeholder="https://..."
              className="dv-input px-3.5 py-2 text-[13px]"
            />
          </div>

          <div className="grid grid-cols-3 gap-2.5">
            <div>
              <label
                htmlFor="banner-cta-text"
                className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5"
              >
                CTA Text
              </label>
              <input
                id="banner-cta-text"
                type="text"
                value={form.cta_text}
                onChange={(e) => setForm({ ...form, cta_text: e.target.value })}
                className="dv-input px-3 py-2 text-[13px]"
              />
            </div>
            <div>
              <label
                htmlFor="banner-cta-link"
                className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5"
              >
                CTA Link
              </label>
              <input
                id="banner-cta-link"
                type="text"
                value={form.cta_destination}
                onChange={(e) => setForm({ ...form, cta_destination: e.target.value })}
                className="dv-input px-3 py-2 text-[13px]"
              />
            </div>
            <div>
              <label
                htmlFor="banner-priority"
                className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5"
              >
                Priority
              </label>
              <input
                id="banner-priority"
                type="number"
                min={0}
                max={1000}
                value={form.display_priority}
                onChange={(e) => setForm({ ...form, display_priority: e.target.value })}
                className="dv-input px-3 py-2 text-[13px]"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-1">
          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary text-[12px] font-semibold px-5 py-2 inline-flex items-center gap-1.5 disabled:opacity-50"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{submitting ? 'Creating...' : 'Create Banner'}</span>
          </button>
        </div>
      </form>

      {/* Banners List */}
      <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl divide-y divide-[#E5E7EB] shadow-2xs overflow-hidden">
        {loading ? (
          <LoadingState label="Loading banners..." />
        ) : banners.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={ImageIcon}
              title="No promotional banners yet"
              description="Create your first storefront banner above to highlight seasonal offers."
            />
          </div>
        ) : (
          banners.map((b) => (
            <div
              key={b.id}
              className="p-5 flex flex-wrap items-center justify-between gap-4 hover:bg-[#18243A]/60 transition"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-semibold text-[#F1F5F9]">{b.heading}</span>
                  <AdminStatusBadge status="processing" label={`Priority ${b.display_priority}`} />
                  <AdminStatusBadge status={b.is_active ? 'active' : 'inactive'} />
                </div>
                {b.subtitle && <p className="text-[12.5px] text-[#94A3B8]">{b.subtitle}</p>}
                <p className="text-[11.5px] font-mono text-[#94A3B8] truncate max-w-xl">
                  {b.image_url}
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => handleToggleActive(b)}
                  className="inline-flex items-center gap-1.5 rounded-lg text-[12px] font-medium px-3 py-1.5 border border-[#D5DEE8] bg-[#111C30] text-[#F1F5F9] hover:border-[#93C5FD] hover:bg-[#18243A] hover:text-[#60A5FA] transition"
                >
                  {b.is_active ? (
                    <>
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Deactivate</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A]" />
                      <span>Activate</span>
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(b)}
                  className="p-2 rounded-lg border border-red-200 bg-[#111C30] text-red-300 hover:bg-red-950/60 transition"
                  title="Delete Banner"
                  aria-label={`Delete banner ${b.heading}`}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <ConfirmDialog
        open={Boolean(confirmDelete)}
        title={`Delete banner "${confirmDelete?.heading}"?`}
        description="This banner will be permanently removed from storefront rotations."
        confirmLabel="Delete Banner"
        variant="danger"
        onConfirm={() => confirmDelete && handleDelete(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />
    </AdminLayout>
  );
};

export default AdminBannersPage;
