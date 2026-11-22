import { useEffect, useState } from 'react';
import { Plus, Trash2, CheckCircle2, XCircle } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
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
    try {
      await adminOperationsApi.createBanner({
        ...form,
        display_priority: Number(form.display_priority || 0),
      });
      setForm(INITIAL_FORM);
      loadBanners();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to create banner.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (banner) => {
    try {
      const updated = await adminOperationsApi.updateBanner(banner.id, {
        is_active: !banner.is_active,
      });
      setBanners((prev) => prev.map((b) => (b.id === banner.id ? updated : b)));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update banner status.');
    }
  };

  const handleDelete = async (bannerId) => {
    try {
      await adminOperationsApi.deleteBanner(bannerId);
      setBanners((prev) => prev.filter((b) => b.id !== bannerId));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to delete banner.');
    }
  };

  return (
    <AdminLayout
      title="Promotional Banners"
      subtitle="Manage hero and storefront promotional banners with priority ordering"
    >
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
          {error}
        </div>
      )}

      {/* Create Banner Form */}
      <form
        onSubmit={handleCreate}
        className="dv-card p-6 mb-8 space-y-4"
      >
        <h2 className="text-xs font-semibold uppercase tracking-widest text-[#1F2937]">
          Create Promotional Banner
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
              Banner Heading *
            </label>
            <input
              type="text"
              required
              value={form.heading}
              onChange={(e) => setForm({ ...form, heading: e.target.value })}
              placeholder="e.g. Creators Week — Up to 50% Off"
              className="dv-input px-3 py-2 text-xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
              Subtitle
            </label>
            <input
              type="text"
              value={form.subtitle}
              onChange={(e) => setForm({ ...form, subtitle: e.target.value })}
              placeholder="e.g. Curated UI Kits, 3D Assets & Code Templates"
              className="dv-input px-3 py-2 text-xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
              Banner Image URL *
            </label>
            <input
              type="text"
              required
              value={form.image_url}
              onChange={(e) => setForm({ ...form, image_url: e.target.value })}
              placeholder="https://..."
              className="dv-input px-3 py-2 text-xs"
            />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                CTA Text
              </label>
              <input
                type="text"
                value={form.cta_text}
                onChange={(e) => setForm({ ...form, cta_text: e.target.value })}
                className="dv-input px-3 py-2 text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                CTA Link
              </label>
              <input
                type="text"
                value={form.cta_destination}
                onChange={(e) => setForm({ ...form, cta_destination: e.target.value })}
                className="dv-input px-3 py-2 text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                Priority
              </label>
              <input
                type="number"
                min={0}
                max={1000}
                value={form.display_priority}
                onChange={(e) => setForm({ ...form, display_priority: e.target.value })}
                className="dv-input px-3 py-2 text-xs"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary text-xs uppercase tracking-wider px-5 py-2.5 inline-flex items-center gap-1.5 disabled:opacity-50"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{submitting ? 'Creating...' : 'Create Banner'}</span>
          </button>
        </div>
      </form>

      {/* Banners List */}
      <div className="dv-card divide-y divide-[#E5E7EB]">
        {loading ? (
          <p className="p-6 text-xs text-[#64748B]">Loading banners...</p>
        ) : banners.length === 0 ? (
          <p className="p-6 text-xs text-[#64748B]">No promotional banners created yet.</p>
        ) : (
          banners.map((b) => (
            <div key={b.id} className="p-5 flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-[#1F2937]">{b.heading}</span>
                  <span className="text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full bg-[#FFF6ED] border border-[#FFD4AE] text-[#D94300]">
                    Priority {b.display_priority}
                  </span>
                </div>
                {b.subtitle && <p className="text-xs text-[#64748B]">{b.subtitle}</p>}
                <p className="text-[11px] font-mono text-[#8490A0] truncate max-w-xl">
                  {b.image_url}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleToggleActive(b)}
                  className={`inline-flex items-center gap-1 rounded-full text-[11px] font-medium uppercase tracking-wider px-3 py-1.5 border transition ${
                    b.is_active
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-[#E5E7EB] bg-slate-100 text-[#64748B]'
                  }`}
                >
                  {b.is_active ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Active</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Inactive</span>
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(b.id)}
                  className="p-2 rounded-lg border border-red-200 bg-white text-red-600 hover:bg-red-50 transition"
                  title="Delete Banner"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </AdminLayout>
  );
};

export default AdminBannersPage;
