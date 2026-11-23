import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  FileArchive,
  Send,
  Star,
  Trash2,
  Upload,
} from 'lucide-react';
import SellerLayout from '../../layouts/SellerLayout';
import {
  Badge,
  Button,
  LoadingState,
  ToastBanner,
} from '../../components/common/StorefrontDesignSystem';
import { publicCatalogApi, sellerApi } from '../../services/api';

const slugify = (val) =>
  val
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-|-$/g, '');

const SellerProductFormPage = () => {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();

  const [categories, setCategories] = useState([]);
  const [product, setProduct] = useState(null);
  const [form, setForm] = useState({
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
  });
  const [autoSlug, setAutoSlug] = useState(!isEdit);
  const [pendingImages, setPendingImages] = useState([]);
  const [pendingAsset, setPendingAsset] = useState(null);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [uploadingAsset, setUploadingAsset] = useState(false);
  const [assetProgress, setAssetProgress] = useState(0);
  const [toast, setToast] = useState({ type: '', message: '' });

  useEffect(() => {
    publicCatalogApi
      .listCategories({ page: 1, page_size: 100 })
      .then((res) => setCategories(res.items || []))
      .catch(() => {});
  }, []);

  const loadProduct = useCallback(async () => {
    if (!isEdit) return;
    setLoading(true);
    try {
      const p = await sellerApi.getProduct(id);
      setProduct(p);
      setForm({
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
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to load seller product.',
      });
    } finally {
      setLoading(false);
    }
  }, [id, isEdit]);

  useEffect(() => {
    loadProduct();
  }, [loadProduct]);

  const handleSave = async (e, submitForReview = false) => {
    e.preventDefault();
    setToast({ type: '', message: '' });
    if (!form.category_id) {
      setToast({ type: 'error', message: 'Please select an active category.' });
      return;
    }
    const priceNum = Number(form.original_price);
    if (Number.isNaN(priceNum) || priceNum < 0) {
      setToast({ type: 'error', message: 'Enter a valid non-negative price.' });
      return;
    }

    const meta = {};
    if (form.metadata_format.trim()) meta.format = form.metadata_format.trim();
    if (form.metadata_version.trim()) meta.version = form.metadata_version.trim();

    const payload = {
      name: form.name.trim(),
      slug: form.slug.trim() || undefined,
      category_id: form.category_id,
      short_description: form.short_description.trim() || null,
      main_description: form.main_description.trim() || null,
      detailed_description: form.detailed_description.trim() || null,
      original_price: priceNum.toFixed(2),
      product_type: form.product_type.trim() || null,
      metadata: Object.keys(meta).length ? meta : null,
    };

    setSaving(true);
    try {
      if (isEdit) {
        let updated = await sellerApi.updateProduct(id, payload);
        if (submitForReview) {
          updated = await sellerApi.changeProductStatus(id, 'submit_for_review');
        }
        setProduct(updated);
        setToast({
          type: 'success',
          message: submitForReview
            ? 'Product updated and submitted for administrator approval.'
            : 'Product changes saved.',
        });
      } else {
        const created = await sellerApi.createProduct({
          ...payload,
          submit_for_review: submitForReview,
        });
        for (let i = 0; i < pendingImages.length; i += 1) {
          await sellerApi.uploadProductImage(created.id, pendingImages[i], {
            display_order: i,
            is_primary: i === 0,
          });
        }
        if (pendingAsset) {
          await sellerApi.uploadProductAsset(created.id, pendingAsset);
          setPendingAsset(null);
        }
        navigate(`/seller/products/${created.id}/edit`, { replace: true });
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ type: 'error', message: typeof detail === 'string' ? detail : 'Save failed.' });
    } finally {
      setSaving(false);
    }
  };

  const handleImageUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    if (!isEdit) {
      setPendingImages((prev) => [...prev, ...files]);
      return;
    }
    setUploadingImage(true);
    try {
      for (const f of files) {
        await sellerApi.uploadProductImage(id, f, { is_primary: !(product?.images?.length) });
      }
      await loadProduct();
      setToast({ type: 'success', message: 'Product image uploaded.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Image upload failed.',
      });
    } finally {
      setUploadingImage(false);
      e.target.value = '';
    }
  };

  const handleAssetUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!isEdit) {
      setPendingAsset(file);
      return;
    }
    setUploadingAsset(true);
    setAssetProgress(0);
    try {
      const updated = await sellerApi.uploadProductAsset(id, file, (evt) => {
        if (evt.total) setAssetProgress(Math.round((evt.loaded / evt.total) * 100));
      });
      setProduct(updated);
      setToast({ type: 'success', message: 'Private digital asset uploaded securely.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Asset upload failed.',
      });
    } finally {
      setUploadingAsset(false);
      e.target.value = '';
    }
  };

  const handleRemoveAsset = async () => {
    if (!isEdit) {
      setPendingAsset(null);
      return;
    }
    try {
      const updated = await sellerApi.deleteProductAsset(id);
      setProduct(updated);
      setToast({ type: 'success', message: 'Private digital asset removed.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not delete asset.',
      });
    }
  };

  const handleStatusTransition = async (action, label) => {
    if (!isEdit) return;
    setSaving(true);
    try {
      const updated = await sellerApi.changeProductStatus(id, action);
      setProduct(updated);
      setToast({ type: 'success', message: `Listing updated: ${label}.` });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Status change failed.',
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <SellerLayout title="Product Editor">
        <LoadingState label="Loading product details..." />
      </SellerLayout>
    );
  }

  return (
    <SellerLayout
      title={isEdit ? `Edit: ${product?.name || 'Product'}` : 'Add New Seller Product'}
      subtitle={
        isEdit
          ? `Approval Status: ${product?.approval_status || 'draft'}`
          : 'Create a digital product draft or submit directly for marketplace moderation'
      }
      actions={
        <Link to="/seller/products" className="dv-btn-secondary px-4 py-2 text-xs inline-flex items-center gap-1.5">
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>My Products</span>
        </Link>
      }
    >
      <div className="space-y-6">
        <ToastBanner
          toast={toast}
          onDismiss={() => setToast({ type: '', message: '' })}
        />

        {product?.approval_status === 'rejected' && product.rejection_reason && (
          <div className="bg-red-950/50 border border-red-200 rounded-2xl p-4 text-xs text-red-300">
            <strong>Moderation Rejection Reason:</strong> {product.rejection_reason}. Update your listing below and resubmit for review.
          </div>
        )}

        <form onSubmit={(e) => handleSave(e, false)} className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-5 bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-6 shadow-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">
                  Product Title *
                </label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={(e) => {
                    const v = e.target.value;
                    setForm((prev) => ({
                      ...prev,
                      name: v,
                      slug: autoSlug ? slugify(v) : prev.slug,
                    }));
                  }}
                  className="dv-input text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">
                  URL Slug *
                </label>
                <input
                  type="text"
                  required
                  value={form.slug}
                  onChange={(e) => {
                    setAutoSlug(false);
                    setForm((prev) => ({ ...prev, slug: e.target.value.toLowerCase() }));
                  }}
                  className="dv-input text-sm font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">
                  Category *
                </label>
                <select
                  required
                  value={form.category_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, category_id: e.target.value }))}
                  className="dv-input text-sm"
                >
                  <option value="">Select category...</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">
                  Price (INR) *
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  value={form.original_price}
                  onChange={(e) => setForm((prev) => ({ ...prev, original_price: e.target.value }))}
                  className="dv-input text-sm font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">
                  Product Type
                </label>
                <input
                  type="text"
                  value={form.product_type}
                  onChange={(e) => setForm((prev) => ({ ...prev, product_type: e.target.value }))}
                  placeholder="UI Kit, Notion Template, E-Book, Code"
                  className="dv-input text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">Format</label>
                  <input
                    type="text"
                    value={form.metadata_format}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, metadata_format: e.target.value }))
                    }
                    placeholder="ZIP / PDF"
                    className="dv-input text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">Version</label>
                  <input
                    type="text"
                    value={form.metadata_version}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, metadata_version: e.target.value }))
                    }
                    placeholder="1.0"
                    className="dv-input text-sm"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">
                Short Summary
              </label>
              <input
                type="text"
                maxLength={500}
                value={form.short_description}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, short_description: e.target.value }))
                }
                className="dv-input text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">
                Main Overview
              </label>
              <textarea
                rows={4}
                value={form.main_description}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, main_description: e.target.value }))
                }
                className="dv-input text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#F1F5F9] mb-1.5">
                Detailed Documentation / Whats Included
              </label>
              <textarea
                rows={4}
                value={form.detailed_description}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, detailed_description: e.target.value }))
                }
                className="dv-input text-sm"
              />
            </div>

            <div className="flex flex-wrap items-center justify-end gap-3 pt-4 border-t border-[#E5E7EB]">
              <Button type="submit" variant="secondary" disabled={saving}>
                {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Save Draft'}
              </Button>
              <Button type="button" disabled={saving} onClick={(e) => handleSave(e, true)}>
                <Send className="w-3.5 h-3.5" />
                <span>{isEdit ? 'Save & Submit for Review' : 'Create & Submit for Review'}</span>
              </Button>
            </div>
          </div>

          {/* Sidebar: Private Asset, Gallery & Workflow */}
          <div className="space-y-5">
            {isEdit && product && (
              <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-5 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-semibold text-[#94A3B8]">
                    Publication State
                  </h2>
                  <Badge
                    variant={
                      product.approval_status === 'published'
                        ? 'success'
                        : product.approval_status === 'rejected'
                          ? 'danger'
                          : product.approval_status === 'pending_review'
                            ? 'warning'
                            : 'neutral'
                    }
                  >
                    {product.approval_status}
                  </Badge>
                </div>
                <p className="text-[11px] text-[#94A3B8]">
                  First-time seller listings require admin review before appearing publicly.
                </p>
                <div className="flex flex-wrap gap-2">
                  {product.approval_status === 'published' && !product.is_active && (
                    <Button
                      size="sm"
                      disabled={saving}
                      onClick={() => handleStatusTransition('publish', 'Published')}
                    >
                      Re-publish Live
                    </Button>
                  )}
                  {product.approval_status === 'published' && product.is_active && (
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={saving}
                      onClick={() => handleStatusTransition('unpublish', 'Unpublished')}
                    >
                      Unpublish
                    </Button>
                  )}
                  {product.approval_status !== 'archived' && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={saving}
                      onClick={() => handleStatusTransition('archive', 'Archived')}
                    >
                      Archive
                    </Button>
                  )}
                </div>
              </div>
            )}

            {/* Private Digital Asset Box */}
            <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-5 shadow-xs space-y-3">
              <h2 className="text-xs font-semibold text-[#94A3B8] flex items-center gap-2">
                <FileArchive className="w-4 h-4 text-[#60A5FA]" aria-hidden="true" />
                Private Digital Asset
              </h2>
              {isEdit && product?.asset?.has_asset ? (
                <div className="p-3 rounded-xl bg-[#18243A] border border-[#BFDBFE] text-xs space-y-1">
                  <p className="font-semibold text-[#F1F5F9] flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300" />
                    {product.asset.filename}
                  </p>
                  <p className="text-[11px] text-[#94A3B8] font-mono">
                    {product.asset.size_bytes} bytes · {product.asset.content_type}
                  </p>
                </div>
              ) : pendingAsset ? (
                <div className="p-3 rounded-xl bg-[#18243A] border border-[#BFDBFE] text-xs">
                  Ready to upload on create: <strong>{pendingAsset.name}</strong>
                </div>
              ) : (
                <p className="text-[11px] text-[#94A3B8]">
                  No binary asset attached yet. Supported: ZIP, PDF, PNG/JPEG/WEBP, TXT/MD/JSON.
                </p>
              )}

              <div className="flex flex-wrap gap-2">
                <label className="dv-btn-secondary px-3.5 py-2 text-xs cursor-pointer inline-flex items-center gap-1.5">
                  <Upload className="w-3.5 h-3.5" />
                  <span>
                    {uploadingAsset
                      ? `Uploading ${assetProgress}%`
                      : product?.asset?.has_asset
                        ? 'Replace File'
                        : 'Upload Asset'}
                  </span>
                  <input type="file" onChange={handleAssetUpload} className="sr-only" />
                </label>
                {(product?.asset?.has_asset || pendingAsset) && (
                  <button
                    type="button"
                    onClick={handleRemoveAsset}
                    className="px-3 py-2 text-xs rounded-xl border border-red-200 text-red-300 hover:bg-red-950/60"
                  >
                    Remove
                  </button>
                )}
              </div>
            </div>

            {/* Product Gallery Images */}
            <div className="bg-[#111C30] border border-[#E5E7EB] rounded-2xl p-5 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold text-[#94A3B8]">
                  Storefront Images
                </h2>
                <label className="text-xs font-semibold text-[#60A5FA] hover:underline cursor-pointer">
                  {uploadingImage ? 'Uploading...' : '+ Upload Image'}
                  <input
                    type="file"
                    multiple
                    accept="image/png,image/jpeg,image/webp"
                    onChange={handleImageUpload}
                    className="sr-only"
                  />
                </label>
              </div>

              {isEdit && product?.images?.length > 0 && (
                <div className="grid grid-cols-2 gap-2">
                  {product.images.map((img) => (
                    <div
                      key={img.id}
                      className="relative border border-[#E5E7EB] rounded-xl overflow-hidden bg-[#18243A]"
                    >
                      <img src={img.image_url} alt="" className="w-full h-24 object-cover" />
                      <div className="p-2 flex items-center justify-between bg-[#111C30] text-[11px]">
                        <button
                          type="button"
                          onClick={async () => {
                            await sellerApi.updateProductImage(id, img.id, { is_primary: true });
                            await loadProduct();
                          }}
                          className={`inline-flex items-center gap-1 font-semibold ${
                            img.is_primary ? 'text-[#60A5FA]' : 'text-[#94A3B8]'
                          }`}
                        >
                          <Star className="w-3 h-3" aria-hidden="true" />
                          {img.is_primary ? 'Primary' : 'Make Primary'}
                        </button>
                        <button
                          type="button"
                          aria-label="Delete product image"
                          onClick={async () => {
                            await sellerApi.deleteProductImage(id, img.id);
                            await loadProduct();
                          }}
                          className="text-red-300 hover:text-red-300"
                        >
                          <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!isEdit && pendingImages.length > 0 && (
                <p className="text-[11px] text-[#94A3B8]">
                  {pendingImages.length} image(s) queued for upload when draft is created.
                </p>
              )}
            </div>
          </div>
        </form>
      </div>
    </SellerLayout>
  );
};

export default SellerProductFormPage;
