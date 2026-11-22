import { useEffect, useState } from 'react';
import { Plus, Trash2, CheckCircle2, XCircle } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import { adminOperationsApi } from '../../services/api';

const INITIAL_FORM = {
  title: '',
  description: '',
  video_url: '',
  thumbnail_url: '',
  destination_url: '/products',
  display_position: 'home_section',
  display_priority: 10,
  is_active: true,
};

const AdminVideosPage = () => {
  const [videos, setVideos] = useState([]);
  const [form, setForm] = useState(INITIAL_FORM);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const loadVideos = () => {
    setLoading(true);
    adminOperationsApi
      .listVideos()
      .then((data) => {
        setVideos(data || []);
        setError('');
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load advertisement videos.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadVideos();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await adminOperationsApi.createVideo({
        ...form,
        display_priority: Number(form.display_priority || 0),
      });
      setForm(INITIAL_FORM);
      loadVideos();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to create advertisement video.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (video) => {
    try {
      const updated = await adminOperationsApi.updateVideo(video.id, {
        is_active: !video.is_active,
      });
      setVideos((prev) => prev.map((v) => (v.id === video.id ? updated : v)));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update video status.');
    }
  };

  const handleDelete = async (videoId) => {
    try {
      await adminOperationsApi.deleteVideo(videoId);
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to delete video.');
    }
  };

  return (
    <AdminLayout
      title="Advertisement Videos"
      subtitle="Manage storefront promotional videos, placements, and priorities"
    >
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
          {error}
        </div>
      )}

      {/* Create Video Form */}
      <form
        onSubmit={handleCreate}
        className="dv-card p-6 mb-8 space-y-4"
      >
        <h2 className="text-xs font-semibold uppercase tracking-widest text-[#1F2937]">
          Add Promotional Video
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
              Video Title *
            </label>
            <input
              type="text"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g. DIGI-VERSE Creator Workflow Tour"
              className="dv-input px-3 py-2 text-xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
              Video URL *
            </label>
            <input
              type="text"
              required
              value={form.video_url}
              onChange={(e) => setForm({ ...form, video_url: e.target.value })}
              placeholder="https://..."
              className="dv-input px-3 py-2 text-xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
              Description
            </label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Brief overview of the featured digital collection"
              className="dv-input px-3 py-2 text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                Display Position
              </label>
              <select
                value={form.display_position}
                onChange={(e) => setForm({ ...form, display_position: e.target.value })}
                className="dv-input px-3 py-2 text-xs"
              >
                <option value="home_hero">Home Hero</option>
                <option value="home_section">Home Section</option>
                <option value="category_page">Category Page</option>
                <option value="product_page">Product Page</option>
                <option value="sidebar">Sidebar</option>
              </select>
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
            <span>{submitting ? 'Adding...' : 'Add Video'}</span>
          </button>
        </div>
      </form>

      {/* Videos List */}
      <div className="dv-card divide-y divide-[#E5E7EB]">
        {loading ? (
          <p className="p-6 text-xs text-[#64748B]">Loading advertisement videos...</p>
        ) : videos.length === 0 ? (
          <p className="p-6 text-xs text-[#64748B]">No advertisement videos added yet.</p>
        ) : (
          videos.map((v) => (
            <div key={v.id} className="p-5 flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-[#1F2937]">{v.title}</span>
                  <span className="text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full bg-[#FFE9D6] border border-[#FFD4AE] text-[#D94300]">
                    {v.display_position}
                  </span>
                  <span className="text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full bg-[#FFF6ED] border border-[#E5E7EB] text-[#64748B]">
                    Priority {v.display_priority}
                  </span>
                </div>
                {v.description && <p className="text-xs text-[#64748B]">{v.description}</p>}
                <p className="text-[11px] font-mono text-[#8490A0] truncate max-w-xl">
                  {v.video_url}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleToggleActive(v)}
                  className={`inline-flex items-center gap-1 rounded-full text-[11px] font-medium uppercase tracking-wider px-3 py-1.5 border transition ${
                    v.is_active
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-[#E5E7EB] bg-slate-100 text-[#64748B]'
                  }`}
                >
                  {v.is_active ? (
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
                  onClick={() => handleDelete(v.id)}
                  className="p-2 rounded-lg border border-red-200 bg-white text-red-600 hover:bg-red-50 transition"
                  title="Delete Video"
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

export default AdminVideosPage;
