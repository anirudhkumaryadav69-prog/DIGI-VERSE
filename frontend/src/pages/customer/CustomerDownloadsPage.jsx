import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Clock, Download, FileArchive, Lock, ShieldCheck } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import {
  Badge,
  EmptyState,
  ErrorAlert,
  LoadingState,
  SectionHeading,
  ToastBanner,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { commerceApi } from '../../services/api';

const formatFileBytes = (bytes) => {
  if (!bytes && bytes !== 0) return null;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const CustomerDownloadsPage = () => {
  const [overview, setOverview] = useState({ eligible_items: [], history: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeId, setActiveId] = useState(null);
  const [downloadProgress, setDownloadProgress] = useState(null);
  const [toast, setToast] = useState({ type: '', message: '' });

  useDocumentMeta({
    title: 'Digital Downloads Library',
    description:
      'Access your purchased digital products, check download quotas, and download verified files securely.',
    canonicalPath: '/downloads',
  });

  const loadDownloads = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await commerceApi.listDownloads();
      setOverview(res);
    } catch {
      setError('Unable to load your digital downloads library.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDownloads();
  }, [loadDownloads]);

  const handleDownload = async (item) => {
    setActiveId(item.order_item_id);
    setDownloadProgress({ orderItemId: item.order_item_id, percent: 0 });
    setToast({ type: '', message: '' });
    try {
      // Never store signed download URLs in browser storage
      const grant = await commerceApi.requestDownload(item.order_item_id);
      const result = await commerceApi.downloadAssetFile(grant.download_url, {
        fallbackFilename: grant.filename || item.asset_filename || item.product_name,
        onProgress: ({ percent, loaded, total }) => {
          setDownloadProgress({
            orderItemId: item.order_item_id,
            percent: percent ?? null,
            loaded,
            total,
          });
        },
      });
      setToast({
        type: 'success',
        message: `Downloaded "${result.filename}" (${grant.remaining_downloads} remaining).`,
      });
      await loadDownloads();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Download could not be completed.',
      });
    } finally {
      setActiveId(null);
      setDownloadProgress(null);
    }
  };

  return (
    <StorefrontLayout>
      <SectionHeading
        eyebrow="Verified Digital Library"
        title="Your Digital Downloads"
        subtitle="Generate short-lived, cryptographically signed download links for your verified purchases."
      />

      {toast.message && (
        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
          className="mb-6"
        />
      )}

      {error && <ErrorAlert message={error} onRetry={loadDownloads} className="mb-6" />}

      {loading ? (
        <LoadingState label="Loading Digital Library..." />
      ) : (
        <div className="space-y-10">
          {/* Purchased Items Eligible for Download */}
          <section className="dv-card-warm p-6 md:p-8 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E7EB] pb-3">
              <h2 className="text-sm font-semibold text-[#263445]">
                Purchased Digital Products ({overview.eligible_items.length})
              </h2>
              <span className="text-[11px] text-[#64748B] inline-flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-[#2563EB]" aria-hidden="true" />
                <span>Signed URLs expire automatically and are never cached in browser storage</span>
              </span>
            </div>

            {overview.eligible_items.length === 0 ? (
              <EmptyState
                icon={Download}
                title="No purchased digital products yet"
                description="Once you complete a verified purchase, your digital assets will appear here for immediate download."
                action={
                  <Link
                    to="/products"
                    className="dv-btn-primary inline-block text-[13px] font-semibold px-5 py-2.5"
                  >
                    Browse Catalog
                  </Link>
                }
              />
            ) : (
              <div className="divide-y divide-[#E5E7EB]">
                {overview.eligible_items.map((item) => {
                  const limitReached = item.remaining_downloads <= 0;
                  return (
                    <div
                      key={item.order_item_id}
                      className="py-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                    >
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          {item.product_slug ? (
                            <Link
                              to={`/products/${item.product_slug}`}
                              className="text-base font-semibold text-[#263445] hover:text-[#2563EB] transition"
                            >
                              {item.product_name}
                            </Link>
                          ) : (
                            <p className="text-base font-semibold text-[#263445]">
                              {item.product_name}
                            </p>
                          )}

                          <Badge variant={item.download_eligible ? 'success' : 'warning'}>
                            {item.download_eligible
                              ? 'Available'
                              : limitReached
                              ? 'Quota Exhausted'
                              : 'Unavailable'}
                          </Badge>
                        </div>

                        <p className="text-xs text-[#64748B]">
                          Order{' '}
                          <Link
                            to={`/orders/${item.order_id}`}
                            className="font-mono text-[#1D4ED8] underline hover:text-[#2563EB]"
                          >
                            {item.order_number}
                          </Link>{' '}
                          · Purchased on {new Date(item.purchased_at).toLocaleDateString()}
                        </p>

                        <div className="flex flex-wrap items-center gap-4 text-[11px] pt-1">
                          <span className="font-mono text-[#263445]">
                            Downloads Used: <strong>{item.downloads_used}</strong> /{' '}
                            {item.max_downloads}
                          </span>
                          <span className="font-mono text-[#2563EB]">
                            Remaining: <strong>{item.remaining_downloads}</strong>
                          </span>
                          {item.asset_filename && (
                            <span className="inline-flex items-center gap-1 font-mono text-[#64748B]">
                              <FileArchive className="w-3 h-3 text-[#2563EB]" aria-hidden="true" />
                              <span>{item.asset_filename}</span>
                              {formatFileBytes(item.asset_size_bytes) && (
                                <span>({formatFileBytes(item.asset_size_bytes)})</span>
                              )}
                            </span>
                          )}
                        </div>
                        {activeId === item.order_item_id &&
                          downloadProgress?.orderItemId === item.order_item_id && (
                            <div className="pt-1 max-w-xs space-y-1">
                              <div className="w-full h-1.5 rounded-full bg-[#EAF4FC] overflow-hidden">
                                <div
                                  className="h-full bg-[#2563EB] transition-all"
                                  style={{
                                    width: `${
                                      downloadProgress.percent !== null
                                        ? downloadProgress.percent
                                        : 60
                                    }%`,
                                  }}
                                />
                              </div>
                            </div>
                          )}
                      </div>

                      <button
                        type="button"
                        disabled={!item.download_eligible || activeId === item.order_item_id}
                        onClick={() => handleDownload(item)}
                        className="dv-btn-primary px-5 py-2.5 text-xs font-semibold inline-flex items-center justify-center gap-2 disabled:opacity-40"
                      >
                        {item.download_eligible ? (
                          <Download className="w-3.5 h-3.5" aria-hidden="true" />
                        ) : (
                          <Lock className="w-3.5 h-3.5" aria-hidden="true" />
                        )}
                        <span>
                          {activeId === item.order_item_id
                            ? downloadProgress?.percent !== null &&
                              downloadProgress?.percent !== undefined
                              ? `Downloading (${downloadProgress.percent}%)...`
                              : 'Downloading...'
                            : item.download_eligible
                            ? 'Download Now'
                            : limitReached
                            ? 'Download Limit Reached'
                            : 'Unavailable'}
                        </span>
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* Download History Audit Log */}
          <section className="dv-card p-6 md:p-8 space-y-4">
            <div className="flex items-center gap-2 border-b border-[#E5E7EB] pb-3">
              <Clock className="w-4 h-4 text-[#2563EB]" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-[#263445]">
                Download Activity History ({overview.history.length})
              </h2>
            </div>

            {overview.history.length === 0 ? (
              <p className="text-xs text-[#64748B] py-4">No download events recorded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[#E5E7EB] text-[#64748B] font-semibold">
                      <th className="py-2.5 pr-4">Product</th>
                      <th className="py-2.5 pr-4">Status</th>
                      <th className="py-2.5 pr-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB]">
                    {overview.history.map((h) => (
                      <tr key={h.id}>
                        <td className="py-2.5 pr-4 font-semibold text-[#263445]">{h.product_name}</td>
                        <td className="py-2.5 pr-4">
                          <Badge variant={h.status === 'completed' ? 'success' : 'neutral'}>
                            {h.status}
                          </Badge>
                        </td>
                        <td className="py-2.5 pr-4 text-[#64748B]">
                          {new Date(h.downloaded_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </StorefrontLayout>
  );
};

export default CustomerDownloadsPage;
