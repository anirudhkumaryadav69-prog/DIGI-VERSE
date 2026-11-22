import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Upload,
  Trash2,
  Star,
  Percent,
  Lock,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  FileArchive,
  ShieldCheck,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import { adminCatalogApi } from '../../services/api';

const formatFileBytes = (bytes) => {
  if (!bytes && bytes !== 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const toKebabSlug = (val) =>
  val
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-|-$/g, '');

const AdminProductFormPage = () => {
  const { id } = useParams();
  const isEditing = Boolean(id);
  const navigate = useNavigate();

  const [categories, setCategories] = useState([]);
  const [product, setProduct] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    category_id: '',
    short_description: '',
    main_description: '',
    detailed_description: '',
    original_price: '',
    product_type: '',
    metadata_format: '',
    metadata_version: '',
    private_download_url: '',
    is_active: true,
  });
  const [autoSlug, setAutoSlug] = useState(!isEditing);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [pendingAssetFile, setPendingAssetFile] = useState(null);
  const [loading, setLoading] = useState(isEditing);
  const [saving, setSaving] = useState(false);
  const [uploadingImg, setUploadingImg] = useState(false);
  const [uploadingAsset, setUploadingAsset] = useState(false);
  const [assetProgress, setAssetProgress] = useState(0);
  const [assetStatus, setAssetStatus] = useState({ type: '', message: '' });
  const [deletingAsset, setDeletingAsset] = useState(false);
  const [toast, setToast] = useState({ type: '', message: '' });

  // Discount / Sale Form State
  const defaultStart = new Date().toISOString().slice(0, 16);
  const defaultExpiry = new Date(Date.now() + 7 * 86400 * 1000).toISOString().slice(0, 16);
  const [saleForm, setSaleForm] = useState({
    discounted_price: '',
    starts_at: defaultStart,
    expires_at: defaultExpiry,
    is_active: true,
  });
  const [savingSale, setSavingSale] = useState(false);

  useEffect(() => {
    adminCatalogApi
      .listCategories({ page: 1, page_size: 100 })
      .then((res) => setCategories(res.items || []))
      .catch(() => {});
  }, []);

  const loadProduct = useCallback(async () => {
    if (!isEditing) return;
    setLoading(true);
    try {
      const p = await adminCatalogApi.getProduct(id);
      setProduct(p);
      setFormData({
        name: p.name || '',
        slug: p.slug || '',
        category_id: p.category_id || '',
        short_description: p.short_description || '',
        main_description: p.main_description || '',
        detailed_description: p.detailed_description || '',
        original_price: String(p.original_price ?? ''),
        product_type: p.product_type || '',
        metadata_format: p.metadata?.format || '',
        metadata_version: p.metadata?.version || '',
        private_download_url: p.private_download_url || '',
        is_active: Boolean(p.is_active),
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to load product details.',
      });
    } finally {
      setLoading(false);
    }
  }, [id, isEditing]);

  useEffect(() => {
    loadProduct();
  }, [loadProduct]);

  const handleNameChange = (name) => {
    setFormData((prev) => ({
      ...prev,
      name,
      slug: autoSlug ? toKebabSlug(name) : prev.slug,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setToast({ type: '', message: '' });

    if (!formData.category_id) {
      setToast({ type: 'error', message: 'Please select a category.' });
      return;
    }

    const priceNum = Number(formData.original_price);
    if (Number.isNaN(priceNum) || priceNum < 0) {
      setToast({ type: 'error', message: 'Please enter a valid non-negative price.' });
      return;
    }

    const metadataObj = {};
    if (formData.metadata_format.trim()) metadataObj.format = formData.metadata_format.trim();
    if (formData.metadata_version.trim()) metadataObj.version = formData.metadata_version.trim();

    const payload = {
      name: formData.name.trim(),
      slug: formData.slug.trim() || undefined,
      category_id: formData.category_id,
      short_description: formData.short_description.trim() || null,
      main_description: formData.main_description.trim() || null,
      detailed_description: formData.detailed_description.trim() || null,
      original_price: priceNum.toFixed(2),
      product_type: formData.product_type.trim() || null,
      metadata: Object.keys(metadataObj).length ? metadataObj : null,
      is_active: formData.is_active,
    };
    if (!product?.asset?.has_asset) {
      payload.private_download_url = formData.private_download_url.trim() || null;
    }

    setSaving(true);
    try {
      if (isEditing) {
        const updated = await adminCatalogApi.updateProduct(id, payload);
        setProduct(updated);
        setToast({ type: 'success', message: 'Product updated successfully.' });
      } else {
        const created = await adminCatalogApi.createProduct(payload);
        // Upload any staged image files in order
        for (let idx = 0; idx < pendingFiles.length; idx += 1) {
          await adminCatalogApi.uploadProductImage(created.id, pendingFiles[idx], {
            display_order: idx,
            is_primary: idx === 0,
          });
        }
        if (pendingAssetFile) {
          await adminCatalogApi.uploadProductAsset(created.id, pendingAssetFile);
          setPendingAssetFile(null);
        }
        setToast({ type: 'success', message: 'Product created successfully.' });
        navigate(`/admin/products/${created.id}/edit`, { replace: true });
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to save product.',
      });
    } finally {
      setSaving(false);
    }
  };

  // Multi-image operations for existing product
  const handleDirectImageUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    if (!isEditing) {
      setPendingFiles((prev) => [...prev, ...files]);
      return;
    }

    setUploadingImg(true);
    setToast({ type: '', message: '' });
    try {
      for (const file of files) {
        await adminCatalogApi.uploadProductImage(id, file, {
          is_primary: !product?.images?.length,
        });
      }
      await loadProduct();
      setToast({ type: 'success', message: 'Product image(s) uploaded.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Image upload failed.',
      });
    } finally {
      setUploadingImg(false);
    }
  };

  const handleSetPrimaryImage = async (img) => {
    try {
      await adminCatalogApi.updateProductImage(id, img.id, { is_primary: true });
      await loadProduct();
      setToast({ type: 'success', message: 'Primary product image updated.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not update primary image.',
      });
    }
  };

  const handleReorderImage = async (img, newOrder) => {
    try {
      await adminCatalogApi.updateProductImage(id, img.id, {
        display_order: Math.max(0, Number(newOrder)),
      });
      await loadProduct();
    } catch {
      // Ignore transient reorder error
    }
  };

  const handleReplaceImage = async (img, e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await adminCatalogApi.replaceProductImage(id, img.id, file);
      await loadProduct();
      setToast({ type: 'success', message: 'Image replaced.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Image replacement failed.',
      });
    }
  };

  const handleDeleteImage = async (img) => {
    try {
      await adminCatalogApi.deleteProductImage(id, img.id);
      await loadProduct();
      setToast({ type: 'success', message: 'Product image deleted.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to delete image.',
      });
    }
  };

  const handleDigitalAssetUpload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    if (!isEditing) {
      setPendingAssetFile(file);
      setAssetStatus({
        type: 'success',
        message: `Staged "${file.name}" (${formatFileBytes(file.size)}) for upload on product creation.`,
      });
      return;
    }

    setUploadingAsset(true);
    setAssetProgress(0);
    setAssetStatus({ type: '', message: '' });
    try {
      const updated = await adminCatalogApi.uploadProductAsset(id, file, (evt) => {
        if (evt.total) {
          setAssetProgress(Math.min(100, Math.round((evt.loaded / evt.total) * 100)));
        }
      });
      setProduct(updated);
      setFormData((prev) => ({
        ...prev,
        private_download_url: updated.private_download_url || '',
      }));
      setAssetProgress(100);
      setAssetStatus({
        type: 'success',
        message: `Private digital asset "${updated.asset?.filename || file.name}" uploaded and verified.`,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setAssetStatus({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Digital asset upload failed.',
      });
    } finally {
      setUploadingAsset(false);
    }
  };

  const handleDeleteDigitalAsset = async () => {
    if (!isEditing || !product?.asset?.has_asset) return;
    setDeletingAsset(true);
    setAssetStatus({ type: '', message: '' });
    try {
      const updated = await adminCatalogApi.deleteProductAsset(id);
      setProduct(updated);
      setFormData((prev) => ({
        ...prev,
        private_download_url: updated.private_download_url || '',
      }));
      setAssetStatus({
        type: 'success',
        message: 'Private digital asset removed from storage.',
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setAssetStatus({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Unable to remove digital asset.',
      });
    } finally {
      setDeletingAsset(false);
    }
  };

  // Discount / Sale handlers
  const handleCreateSale = async (e) => {
    e.preventDefault();
    setSavingSale(true);
    setToast({ type: '', message: '' });
    try {
      await adminCatalogApi.createProductSale(id, {
        discounted_price: Number(saleForm.discounted_price).toFixed(2),
        starts_at: new Date(saleForm.starts_at).toISOString(),
        expires_at: new Date(saleForm.expires_at).toISOString(),
        is_active: saleForm.is_active,
      });
      setSaleForm((prev) => ({ ...prev, discounted_price: '' }));
      await loadProduct();
      setToast({ type: 'success', message: 'Product discount created.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to create discount.',
      });
    } finally {
      setSavingSale(false);
    }
  };

  const handleToggleSaleActive = async (sale) => {
    setToast({ type: '', message: '' });
    try {
      await adminCatalogApi.updateProductSale(id, sale.id, { is_active: !sale.is_active });
      await loadProduct();
      setToast({
        type: 'success',
        message: `Discount ${!sale.is_active ? 'activated' : 'deactivated'}.`,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not update discount.',
      });
    }
  };

  const formatINR = (v) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(v || 0));

  return (
    <AdminLayout
      title={isEditing ? `Edit Product: ${product?.name || ''}` : 'Create Digital Product'}
      subtitle="Configure product details, gallery images, confidential delivery link, and promotional pricing"
      actions={
        <Link
          to="/admin/products"
          className="dv-btn-secondary text-xs uppercase tracking-wider px-4 py-2 flex items-center gap-1.5"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Products</span>
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

      {loading ? (
        <p className="text-xs text-[#64748B]">Loading product configuration...</p>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Core Product Form (2 cols) */}
          <form
            onSubmit={handleSubmit}
            className="xl:col-span-2 dv-card p-6 md:p-8 space-y-5"
          >
            <h2 className="text-xs font-semibold uppercase tracking-widest text-[#FF6B0A] border-b border-[#E5E7EB] pb-3">
              1. Core Product Information
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                  Product Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  className="dv-input px-3.5 py-2.5 text-sm"
                  placeholder="e.g. Minimal SaaS UI Kit"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B]">
                    URL Slug
                  </label>
                  <label className="text-[11px] text-[#64748B] flex items-center gap-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoSlug}
                      onChange={(e) => setAutoSlug(e.target.checked)}
                    />
                    <span>Auto</span>
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
                  placeholder="minimal-saas-ui-kit"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                  Category *
                </label>
                <select
                  required
                  value={formData.category_id}
                  onChange={(e) => setFormData({ ...formData, category_id: e.target.value })}
                  className="dv-input px-3.5 py-2.5 text-sm"
                >
                  <option value="">Select Category</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                  Original Price (INR) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={formData.original_price}
                  onChange={(e) => setFormData({ ...formData, original_price: e.target.value })}
                  className="dv-input px-3.5 py-2.5 text-sm font-mono"
                  placeholder="1499.00"
                />
              </div>

              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                  Product Type
                </label>
                <input
                  type="text"
                  value={formData.product_type}
                  onChange={(e) => setFormData({ ...formData, product_type: e.target.value })}
                  className="dv-input px-3.5 py-2.5 text-sm"
                  placeholder="e.g. Figma Kit / Notion / Code"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                Short Summary Description
              </label>
              <input
                type="text"
                maxLength={500}
                value={formData.short_description}
                onChange={(e) => setFormData({ ...formData, short_description: e.target.value })}
                className="dv-input px-3.5 py-2.5 text-sm"
                placeholder="Concise one-line value proposition for product cards..."
              />
            </div>

            <div>
              <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                Main Description
              </label>
              <textarea
                rows={3}
                value={formData.main_description}
                onChange={(e) => setFormData({ ...formData, main_description: e.target.value })}
                className="dv-input px-3.5 py-2.5 text-sm"
                placeholder="Core overview of the digital product..."
              />
            </div>

            <div>
              <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                Detailed Technical Specifications & Included Contents
              </label>
              <textarea
                rows={4}
                value={formData.detailed_description}
                onChange={(e) =>
                  setFormData({ ...formData, detailed_description: e.target.value })
                }
                className="dv-input px-3.5 py-2.5 text-sm"
                placeholder="Detailed breakdown of deliverables, licenses, and requirements..."
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                  Deliverable Format (Metadata)
                </label>
                <input
                  type="text"
                  value={formData.metadata_format}
                  onChange={(e) => setFormData({ ...formData, metadata_format: e.target.value })}
                  className="dv-input px-3.5 py-2 text-xs"
                  placeholder="e.g. ZIP Archive (.fig, .pdf)"
                />
              </div>
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-[#64748B] mb-1.5">
                  Version (Metadata)
                </label>
                <input
                  type="text"
                  value={formData.metadata_version}
                  onChange={(e) => setFormData({ ...formData, metadata_version: e.target.value })}
                  className="dv-input px-3.5 py-2 text-xs"
                  placeholder="e.g. v1.4.0"
                />
              </div>
            </div>

            {/* Private Asset Delivery Info */}
            <div className="p-4 rounded-xl bg-[#FFF6ED] border border-[#FFD4AE] space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs text-[#D94300] uppercase tracking-wider font-semibold">
                  <Lock className="w-3.5 h-3.5" />
                  <span>Private Digital Delivery Asset</span>
                </div>
                {product?.asset?.has_asset && (
                  <span className="text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                    Managed Private File Active
                  </span>
                )}
              </div>
              <p className="text-[11px] text-[#64748B]">
                Upload the actual downloadable digital product in the Private Digital Asset panel.
                Never exposed in public catalog responses or audit logs; streamed only via single-use
                signed tokens after payment verification.
              </p>
              {!product?.asset?.has_asset && (
                <p className="text-[11px] font-mono text-[#243247]">
                  {pendingAssetFile
                    ? `Staged file: ${pendingAssetFile.name} (${formatFileBytes(pendingAssetFile.size)})`
                    : 'No private binary asset attached yet. Upload one in the Digital Asset panel on the right.'}
                </p>
              )}
            </div>

            <div className="pt-2">
              <label className="flex items-center gap-2.5 cursor-pointer text-xs">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
                <span className="text-[#243247]">
                  Product is active and available in the public catalog
                </span>
              </label>
            </div>

            <div className="pt-4 border-t border-[#E5E7EB] flex justify-end gap-3">
              <Link
                to="/admin/products"
                className="dv-btn-secondary px-5 py-2.5 text-xs uppercase tracking-wider"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={saving}
                className="dv-btn-primary px-6 py-2.5 text-xs uppercase tracking-widest disabled:opacity-50"
              >
                {saving ? 'Saving...' : isEditing ? 'Save Product Changes' : 'Create Product'}
              </button>
            </div>
          </form>

          {/* Right Column: Private Digital Asset, Product Images & Discounts */}
          <div className="space-y-8">
            {/* Private Digital Product Asset Upload & Management */}
            <section className="dv-card p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                <div className="flex items-center gap-2">
                  <FileArchive className="w-4 h-4 text-[#FF6B0A]" />
                  <h2 className="text-xs font-semibold uppercase tracking-widest text-[#FF6B0A]">
                    2. Digital Asset File
                  </h2>
                </div>
                <label className="dv-btn-primary cursor-pointer px-3 py-1.5 text-[11px] uppercase tracking-wider inline-flex items-center gap-1.5">
                  <Upload className="w-3 h-3" />
                  <span>
                    {uploadingAsset
                      ? 'Uploading...'
                      : product?.asset?.has_asset
                      ? 'Replace File'
                      : 'Upload File'}
                  </span>
                  <input
                    type="file"
                    data-testid="admin-asset-file-input"
                    accept=".zip,.fig,.pdf,.epub,.7z,.gz,.png,.jpg,.jpeg,.webp,.mp3,.wav,.mp4,.woff2,.ttf,.otf,.json,.txt,.md,.csv"
                    onChange={handleDigitalAssetUpload}
                    disabled={uploadingAsset}
                    className="hidden"
                  />
                </label>
              </div>

              <p className="text-[11px] text-[#64748B]">
                Stored privately outside public web directories. Validated by extension, MIME type,
                and binary file signature up to 100 MB (ZIP, FIG, PDF, EPUB, 7Z, PNG/JPG/WEBP, MP3/WAV/MP4, WOFF2/TTF/OTF, JSON/TXT/MD/CSV).
              </p>

              {uploadingAsset && (
                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] font-mono text-[#243247]">
                    <span>Uploading &amp; verifying signature...</span>
                    <span>{assetProgress}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-[#FFE9D6] border border-[#FFD4AE] overflow-hidden">
                    <div
                      className="h-full bg-[#FF6B0A] transition-all"
                      style={{ width: `${assetProgress}%` }}
                    />
                  </div>
                </div>
              )}

              {assetStatus.message && (
                <div
                  className={`p-3 rounded-xl border text-xs flex items-start gap-2 ${
                    assetStatus.type === 'error'
                      ? 'bg-red-50 border-red-200 text-red-700'
                      : 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  }`}
                >
                  {assetStatus.type === 'error' ? (
                    <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  )}
                  <span>{assetStatus.message}</span>
                </div>
              )}

              {!isEditing ? (
                pendingAssetFile ? (
                  <div className="p-3 rounded-xl bg-[#FFF6ED] border border-[#FFD4AE] flex items-center justify-between gap-2 text-xs">
                    <div className="min-w-0">
                      <p className="font-mono text-[#1F2937] truncate">{pendingAssetFile.name}</p>
                      <p className="text-[11px] text-[#64748B]">
                        {formatFileBytes(pendingAssetFile.size)} · Will upload on Create Product
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setPendingAssetFile(null);
                        setAssetStatus({ type: '', message: '' });
                      }}
                      className="text-red-600 font-medium text-[11px] shrink-0 hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <p className="text-xs text-[#64748B] py-2">
                    Optionally select a digital asset file now, or upload it after creating the product.
                  </p>
                )
              ) : product?.asset?.has_asset ? (
                <div className="p-3.5 rounded-xl bg-[#FFF6ED] border border-[#FFD4AE] space-y-2 text-xs">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 space-y-0.5">
                      <p className="font-mono font-medium text-[#1F2937] truncate" title={product.asset.filename}>
                        {product.asset.filename}
                      </p>
                      <p className="text-[11px] text-[#64748B]">
                        {formatFileBytes(product.asset.size_bytes)} · {product.asset.content_type}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={handleDeleteDigitalAsset}
                      disabled={deletingAsset}
                      className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-red-300 hover:bg-red-50 text-red-600 shrink-0 disabled:opacity-50 transition"
                      title="Remove Digital Asset"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="pt-2 border-t border-[#FFD4AE]/70 flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-[#64748B]">
                    <span className="inline-flex items-center gap-1 text-emerald-700 font-medium">
                      <ShieldCheck className="w-3 h-3" />
                      Backend: {(product.asset.storage_backend || 'local').toUpperCase()}
                    </span>
                    {product.asset.sha256 && (
                      <span title={product.asset.sha256}>
                        SHA-256: {product.asset.sha256.slice(0, 16)}…
                      </span>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[#64748B] py-2">
                  No digital asset file uploaded yet. Purchasers cannot download until a verified file
                  is attached.
                </p>
              )}
            </section>

            {/* Multi-Image Gallery Management */}
            <section className="dv-card p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                <h2 className="text-xs font-semibold uppercase tracking-widest text-[#FF6B0A]">
                  3. Product Images
                </h2>
                <label className="dv-btn-primary cursor-pointer px-3 py-1.5 text-[11px] uppercase tracking-wider inline-flex items-center gap-1.5">
                  <Upload className="w-3 h-3" />
                  <span>{uploadingImg ? 'Uploading...' : 'Add Images'}</span>
                  <input
                    type="file"
                    multiple
                    accept=".png,.jpg,.jpeg,.webp"
                    onChange={handleDirectImageUpload}
                    className="hidden"
                  />
                </label>
              </div>

              <p className="text-[11px] text-[#64748B]">
                Allowed: PNG, JPG, WEBP up to 5 MB. Validated by extension and binary signature.
              </p>

              {!isEditing ? (
                <div className="space-y-2 text-xs">
                  {pendingFiles.length === 0 ? (
                    <p className="text-[#64748B] py-3">
                      Select image files above to upload automatically when the product is created.
                    </p>
                  ) : (
                    pendingFiles.map((f, idx) => (
                      <div
                        key={`${f.name}-${idx}`}
                        className="flex items-center justify-between p-2.5 rounded-xl bg-[#FFF6ED] border border-[#E5E7EB]"
                      >
                        <span className="truncate max-w-[180px] text-[#1F2937]">{f.name}</span>
                        <button
                          type="button"
                          onClick={() =>
                            setPendingFiles((prev) => prev.filter((_, i) => i !== idx))
                          }
                          className="text-red-600 font-medium text-[11px] hover:underline"
                        >
                          Remove
                        </button>
                      </div>
                    ))
                  )}
                </div>
              ) : !product?.images?.length ? (
                <p className="text-xs text-[#64748B] py-4">No images uploaded for this product.</p>
              ) : (
                <div className="space-y-3">
                  {product.images.map((img) => (
                    <div
                      key={img.id}
                      className="p-3 rounded-xl bg-[#FFF6ED] border border-[#E5E7EB] flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-3">
                        <img
                          src={img.image_url}
                          alt="Product gallery"
                          className="w-14 h-14 object-cover rounded-lg border border-[#E5E7EB] bg-white"
                        />
                        <div className="space-y-1 text-xs">
                          <div className="flex items-center gap-2">
                            {img.is_primary ? (
                              <span className="text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                                Primary
                              </span>
                            ) : (
                              <button
                                type="button"
                                onClick={() => handleSetPrimaryImage(img)}
                                className="text-[11px] font-medium text-[#FF6B0A] hover:text-[#D94300] hover:underline flex items-center gap-1"
                              >
                                <Star className="w-3 h-3" />
                                <span>Set Primary</span>
                              </button>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 text-[11px] text-[#64748B]">
                            <span>Order:</span>
                            <input
                              type="number"
                              min="0"
                              value={img.display_order}
                              onChange={(e) => handleReorderImage(img, e.target.value)}
                              className="w-12 rounded-md bg-white border border-[#E5E7EB] px-1.5 py-0.5 text-center text-[#1F2937]"
                            />
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <label
                          className="cursor-pointer p-1.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-[#FFD4AE] hover:text-[#FF6B0A] text-[#243247] transition"
                          title="Replace Image File"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                          <input
                            type="file"
                            accept=".png,.jpg,.jpeg,.webp"
                            onChange={(e) => handleReplaceImage(img, e)}
                            className="hidden"
                          />
                        </label>
                        <button
                          type="button"
                          onClick={() => handleDeleteImage(img)}
                          className="p-1.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-red-300 hover:bg-red-50 text-red-600 transition"
                          title="Delete Image"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Sales & Discount Integration Panel */}
            {isEditing && (
              <section className="dv-card p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                  <div className="flex items-center gap-2">
                    <Percent className="w-4 h-4 text-[#FF6B0A]" />
                    <h2 className="text-xs font-semibold uppercase tracking-widest text-[#FF6B0A]">
                      4. Sales &amp; Discounts
                    </h2>
                  </div>
                  <span className="text-xs font-semibold font-mono text-[#D94300]">
                    Effective: {formatINR(product?.effective_price)}
                  </span>
                </div>

                {/* Create New Discount Form */}
                <form onSubmit={handleCreateSale} className="space-y-3 text-xs">
                  <div>
                    <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                      Discounted Price (must be &lt; {formatINR(product?.original_price)})
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      required
                      value={saleForm.discounted_price}
                      onChange={(e) =>
                        setSaleForm({ ...saleForm, discounted_price: e.target.value })
                      }
                      className="dv-input px-3 py-2 font-mono"
                      placeholder="999.00"
                    />
                  </div>

                  <div className="grid grid-cols-1 gap-2">
                    <div>
                      <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                        Starts At (UTC/Local)
                      </label>
                      <input
                        type="datetime-local"
                        required
                        value={saleForm.starts_at}
                        onChange={(e) => setSaleForm({ ...saleForm, starts_at: e.target.value })}
                        className="dv-input px-3 py-1.5"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                        Expires At
                      </label>
                      <input
                        type="datetime-local"
                        required
                        value={saleForm.expires_at}
                        onChange={(e) => setSaleForm({ ...saleForm, expires_at: e.target.value })}
                        className="dv-input px-3 py-1.5"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={savingSale}
                    className="dv-btn-primary w-full py-2 uppercase tracking-widest text-[11px] disabled:opacity-50"
                  >
                    {savingSale ? 'Scheduling...' : 'Create / Schedule Discount'}
                  </button>
                </form>

                {/* Existing Sales History */}
                {product?.sales?.length > 0 && (
                  <div className="pt-3 border-t border-[#E5E7EB] space-y-2">
                    <p className="text-[11px] font-medium uppercase tracking-wider text-[#64748B]">
                      Discount History
                    </p>
                    {product.sales.map((s) => (
                      <div
                        key={s.id}
                        className="p-3 rounded-xl bg-[#FFF6ED] border border-[#E5E7EB] text-xs flex items-center justify-between gap-2"
                      >
                        <div>
                          <p className="font-mono font-semibold text-[#1F2937]">
                            {formatINR(s.discounted_price)}{' '}
                            <span className="text-emerald-700">(-{s.discount_percentage}%)</span>
                          </p>
                          <p className="text-[10px] text-[#64748B]">
                            {new Date(s.starts_at).toLocaleDateString()} →{' '}
                            {new Date(s.expires_at).toLocaleDateString()}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleToggleSaleActive(s)}
                          className={`text-[10px] uppercase tracking-wider font-medium px-2.5 py-1 rounded-full border ${
                            s.is_active
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : 'bg-slate-100 text-[#64748B] border-[#E5E7EB]'
                          }`}
                        >
                          {s.is_currently_live
                            ? 'Live (Deactivate)'
                            : s.is_active
                            ? 'Scheduled (Cancel)'
                            : 'Inactive (Activate)'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}
          </div>
        </div>
      )}
    </AdminLayout>
  );
};

export default AdminProductFormPage;
