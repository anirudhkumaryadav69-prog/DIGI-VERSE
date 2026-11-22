import { useEffect, useState } from 'react';
import { CheckCircle2, Plus, Trash2, Video, XCircle } from 'lucide-react';
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
  const [toast, setToast] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

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
    setToast(null);
    try {
      await adminOperationsApi.createVideo({
        ...form,
        display_priority: Number(form.display_priority || 0),
      });
      setForm(INITIAL_FORM);
      setToast({ type: 'success', message: 'Promotional video added.' });
      loadVideos();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to create advertisement video.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (video) => {
    setToast(null);
    try {
      const updated = await adminOperationsApi.updateVideo(video.id, {
        is_active: !video.is_active,
      });
      setVideos((prev) => prev.map((v) => (v.id === video.id ? updated : v)));
      setToast({
        type: 'success',
        message: `Video "${video.title}" marked ${updated.is_active ? 'active' : 'inactive'}.`,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update video status.');
    }
  };

  const handleDelete = async (video) => {
    try {
      await adminOperationsApi.deleteVideo(video.id);
      setVideos((prev) => prev.filter((v) => v.id !== video.id));
      setToast({ type: 'success', message: `Video "${video.title}" deleted.` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to delete video.');
    } finally {
      setConfirmDelete(null);
    }
  };

  return (
    <AdminLayout
      title="Video Spotlights"
      subtitle="Manage storefront promotional videos, placements, and priorities"
    >
      {error && <ErrorAlert message={error} onRetry={loadVideos} className="mb-5" />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-5" />

      {/* Create Video Form */}
      <form
        onSubmit={handleCreate}
        className="bg-white border border-[#D5DEE8] rounded-xl p-6 mb-6 space-y-4 shadow-2xs"
      >
        <AdminSectionHeader
          icon={Video}
          title="Add Promotional Video"
          subtitle="Link storefront showcase videos to homepage or category placements"
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          <div>
            <label
              htmlFor="video-title"
              className="block text-[12px] font-medium text-[#263445] mb-1.5"
            >
              Video Title *
            </label>
            <input
              id="video-title"
              type="text"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g. DIGI-VERSE Creator Workflow Tour"
              className="dv-input px-3.5 py-2 text-[13px]"
            />
          </div>

          <div>
            <label
              htmlFor="video-url"
              className="block text-[12px] font-medium text-[#263445] mb-1.5"
            >
              Video URL *
            </label>
            <input
              id="video-url"
              type="text"
              required
              value={form.video_url}
              onChange={(e) => setForm({ ...form, video_url: e.target.value })}
              placeholder="https://..."
              className="dv-input px-3.5 py-2 text-[13px]"
            />
          </div>

          <div>
            <label
              htmlFor="video-description"
              className="block text-[12px] font-medium text-[#263445] mb-1.5"
            >
              Description
            </label>
            <input
              id="video-description"
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Brief overview of the featured digital collection"
              className="dv-input px-3.5 py-2 text-[13px]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="video-position"
                className="block text-[12px] font-medium text-[#263445] mb-1.5"
              >
                Display Position
              </label>
              <select
                id="video-position"
                value={form.display_position}
                onChange={(e) => setForm({ ...form, display_position: e.target.value })}
                className="dv-input px-3 py-2 text-[13px]"
              >
                <option value="home_hero">Home Hero</option>
                <option value="home_section">Home Section</option>
                <option value="category_page">Category Page</option>
                <option value="product_page">Product Page</option>
                <option value="sidebar">Sidebar</option>
              </select>
            </div>
            <div>
              <label
                htmlFor="video-priority"
                className="block text-[12px] font-medium text-[#263445] mb-1.5"
              >
                Priority
              </label>
              <input
                id="video-priority"
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
            <span>{submitting ? 'Adding...' : 'Add Video'}</span>
          </button>
        </div>
      </form>

      {/* Videos List */}
      <div className="bg-white border border-[#D5DEE8] rounded-xl divide-y divide-[#E5E7EB] shadow-2xs overflow-hidden">
        {loading ? (
          <LoadingState label="Loading advertisement videos..." />
        ) : videos.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={Video}
              title="No advertisement videos yet"
              description="Add a promotional video spotlight above to feature curated collections."
            />
          </div>
        ) : (
          videos.map((v) => (
            <div
              key={v.id}
              className="p-5 flex flex-wrap items-center justify-between gap-4 hover:bg-[#EDF5FC]/40 transition"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] font-semibold text-[#263445]">{v.title}</span>
                  <AdminStatusBadge status="processing" label={v.display_position} />
                  <AdminStatusBadge status="neutral" label={`Priority ${v.display_priority}`} />
                  <AdminStatusBadge status={v.is_active ? 'active' : 'inactive'} />
                </div>
                {v.description && <p className="text-[12.5px] text-[#64748B]">{v.description}</p>}
                <p className="text-[11.5px] font-mono text-[#64748B] truncate max-w-xl">
                  {v.video_url}
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => handleToggleActive(v)}
                  className="inline-flex items-center gap-1.5 rounded-lg text-[12px] font-medium px-3 py-1.5 border border-[#D5DEE8] bg-white text-[#263445] hover:border-[#93C5FD] hover:bg-[#EDF5FC] hover:text-[#2563EB] transition"
                >
                  {v.is_active ? (
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
                  onClick={() => setConfirmDelete(v)}
                  className="p-2 rounded-lg border border-red-200 bg-white text-[#DC2626] hover:bg-red-50 transition"
                  title="Delete Video"
                  aria-label={`Delete video ${v.title}`}
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
        title={`Delete video "${confirmDelete?.title}"?`}
        description="This video spotlight will be removed from all storefront placements."
        confirmLabel="Delete Video"
        variant="danger"
        onConfirm={() => confirmDelete && handleDelete(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />
    </AdminLayout>
  );
};

export default AdminVideosPage;
