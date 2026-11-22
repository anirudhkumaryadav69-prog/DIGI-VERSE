import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Store, Upload } from 'lucide-react';
import SellerLayout from '../../layouts/SellerLayout';
import {
  Button,
  LoadingState,
  ToastBanner,
} from '../../components/common/StorefrontDesignSystem';
import { sellerApi } from '../../services/api';

const SellerProfilePage = () => {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingField, setUploadingField] = useState('');
  const [toast, setToast] = useState({ type: '', message: '' });

  const [form, setForm] = useState({
    store_name: '',
    seller_display_name: '',
    store_description: '',
    logo_url: '',
    banner_url: '',
    contact_email: '',
    contact_info: '',
    country: '',
    business_type: '',
    product_categories_text: '',
  });

  useEffect(() => {
    sellerApi
      .getProfile()
      .then((res) => {
        setProfile(res);
        setForm({
          store_name: res.store_name || '',
          seller_display_name: res.seller_display_name || '',
          store_description: res.store_description || '',
          logo_url: res.logo_url || '',
          banner_url: res.banner_url || '',
          contact_email: res.contact_email || '',
          contact_info: res.contact_info || '',
          country: res.country || '',
          business_type: res.business_type || '',
          product_categories_text: (res.product_categories || []).join(', '),
        });
      })
      .catch(() => setToast({ type: 'error', message: 'Failed to load store profile.' }))
      .finally(() => setLoading(false));
  }, []);

  const handleImageUpload = async (field, e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingField(field);
    try {
      const res = await sellerApi.uploadBrandingImage(file);
      setForm((prev) => ({ ...prev, [field]: res.image_url }));
      setToast({ type: 'success', message: 'Branding image uploaded.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({ type: 'error', message: typeof detail === 'string' ? detail : 'Upload failed.' });
    } finally {
      setUploadingField('');
      e.target.value = '';
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setToast({ type: '', message: '' });
    try {
      const updated = await sellerApi.updateProfile({
        store_name: form.store_name.trim(),
        seller_display_name: form.seller_display_name.trim(),
        store_description: form.store_description.trim() || null,
        logo_url: form.logo_url.trim() || null,
        banner_url: form.banner_url.trim() || null,
        contact_email: form.contact_email.trim(),
        contact_info: form.contact_info.trim() || null,
        country: form.country.trim(),
        business_type: form.business_type.trim(),
        product_categories: form.product_categories_text
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      });
      setProfile(updated);
      setToast({ type: 'success', message: 'Storefront profile saved.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Could not update store profile.',
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <SellerLayout title="Store Profile">
        <LoadingState label="Loading storefront settings..." />
      </SellerLayout>
    );
  }

  return (
    <SellerLayout
      title="Store Profile"
      subtitle="Customize your public creator storefront identity"
      actions={
        profile?.store_slug && (
          <Link
            to={`/store/${profile.store_slug}`}
            className="dv-btn-secondary px-4 py-2 text-xs inline-flex items-center gap-1.5"
          >
            <span>Open Public Storefront</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        )
      }
    >
      <div className="max-w-3xl space-y-5">
        <ToastBanner
          type={toast.type}
          message={toast.message}
          onDismiss={() => setToast({ type: '', message: '' })}
        />

        <form onSubmit={handleSubmit} className="bg-white border border-[#E5E7EB] rounded-2xl p-6 space-y-5 shadow-xs">
          <div className="flex items-center gap-2 border-b border-[#E5E7EB] pb-3">
            <Store className="w-5 h-5 text-[#FF6B0A]" />
            <h2 className="text-sm font-bold text-[#1F2937]">
              Storefront URL: <code className="text-[#FF6B0A]">/store/{profile?.store_slug}</code>
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#243247] mb-1.5">Store Name</label>
              <input
                type="text"
                required
                value={form.store_name}
                onChange={(e) => setForm((prev) => ({ ...prev, store_name: e.target.value }))}
                className="dv-input text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                Seller Display Name
              </label>
              <input
                type="text"
                required
                value={form.seller_display_name}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, seller_display_name: e.target.value }))
                }
                className="dv-input text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                Contact Email
              </label>
              <input
                type="email"
                required
                value={form.contact_email}
                onChange={(e) => setForm((prev) => ({ ...prev, contact_email: e.target.value }))}
                className="dv-input text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                Contact Phone / Handle
              </label>
              <input
                type="text"
                value={form.contact_info}
                onChange={(e) => setForm((prev) => ({ ...prev, contact_info: e.target.value }))}
                className="dv-input text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#243247] mb-1.5">Country</label>
              <input
                type="text"
                required
                value={form.country}
                onChange={(e) => setForm((prev) => ({ ...prev, country: e.target.value }))}
                className="dv-input text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                Business Type
              </label>
              <input
                type="text"
                required
                value={form.business_type}
                onChange={(e) => setForm((prev) => ({ ...prev, business_type: e.target.value }))}
                className="dv-input text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#243247] mb-1.5">Logo URL</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={form.logo_url}
                  onChange={(e) => setForm((prev) => ({ ...prev, logo_url: e.target.value }))}
                  className="dv-input text-xs flex-1"
                />
                <label className="dv-btn-secondary px-3 py-2 text-xs cursor-pointer inline-flex items-center gap-1 shrink-0">
                  <Upload className="w-3.5 h-3.5" />
                  <span>{uploadingField === 'logo_url' ? '...' : 'Upload'}</span>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={(e) => handleImageUpload('logo_url', e)}
                    className="sr-only"
                  />
                </label>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#243247] mb-1.5">Banner URL</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={form.banner_url}
                  onChange={(e) => setForm((prev) => ({ ...prev, banner_url: e.target.value }))}
                  className="dv-input text-xs flex-1"
                />
                <label className="dv-btn-secondary px-3 py-2 text-xs cursor-pointer inline-flex items-center gap-1 shrink-0">
                  <Upload className="w-3.5 h-3.5" />
                  <span>{uploadingField === 'banner_url' ? '...' : 'Upload'}</span>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={(e) => handleImageUpload('banner_url', e)}
                    className="sr-only"
                  />
                </label>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#243247] mb-1.5">
              Categories Focus (comma separated)
            </label>
            <input
              type="text"
              value={form.product_categories_text}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, product_categories_text: e.target.value }))
              }
              className="dv-input text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#243247] mb-1.5">
              Store Description
            </label>
            <textarea
              rows={4}
              value={form.store_description}
              onChange={(e) => setForm((prev) => ({ ...prev, store_description: e.target.value }))}
              className="dv-input text-sm"
            />
          </div>

          <div className="flex justify-end pt-2 border-t border-[#E5E7EB]">
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving...' : 'Save Store Profile'}
            </Button>
          </div>
        </form>
      </div>
    </SellerLayout>
  );
};

export default SellerProfilePage;
