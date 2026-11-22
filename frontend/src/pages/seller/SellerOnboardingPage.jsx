import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  Store,
  Upload,
} from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import {
  Button,
  LoadingState,
  ToastBanner,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { useAuth } from '../../context/AuthContext';
import { sellerApi } from '../../services/api';

const slugify = (val) =>
  val
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-|-$/g, '');

const SellerOnboardingPage = () => {
  const { customer, refreshCustomerProfile } = useAuth();

  useDocumentMeta({
    title: 'Become a Creator / Seller',
    description: 'Apply for a DIGI-VERSE creator storefront to publish and sell digital products.',
    canonicalPath: '/seller/apply',
  });

  const [loading, setLoading] = useState(true);
  const [application, setApplication] = useState(null);
  const [autoSlug, setAutoSlug] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [uploadingField, setUploadingField] = useState('');
  const [toast, setToast] = useState({ type: '', message: '' });

  const [form, setForm] = useState({
    store_name: '',
    store_slug: '',
    seller_display_name: customer?.full_name || '',
    store_description: '',
    application_description: '',
    logo_url: '',
    banner_url: '',
    contact_email: customer?.email || '',
    contact_info: customer?.phone_number || '',
    country: 'India',
    business_type: 'Independent Creator',
    product_categories_text: '',
  });

  const loadApplication = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sellerApi.getApplication();
      setApplication(data);
      setForm({
        store_name: data.store_name || '',
        store_slug: data.store_slug || '',
        seller_display_name: data.seller_display_name || '',
        store_description: data.store_description || '',
        application_description: data.application_description || '',
        logo_url: data.logo_url || '',
        banner_url: data.banner_url || '',
        contact_email: data.contact_email || '',
        contact_info: data.contact_info || '',
        country: data.country || 'India',
        business_type: data.business_type || 'Independent Creator',
        product_categories_text: (data.product_categories || []).join(', '),
      });
      setAutoSlug(false);
    } catch (err) {
      if (err.response?.status !== 404) {
        const detail = err.response?.data?.detail;
        setToast({
          type: 'error',
          message: typeof detail === 'string' ? detail : 'Could not load seller application status.',
        });
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadApplication();
  }, [loadApplication]);

  const handleImageUpload = async (field, e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingField(field);
    setToast({ type: '', message: '' });
    try {
      const res = await sellerApi.uploadBrandingImage(file);
      setForm((prev) => ({ ...prev, [field]: res.image_url }));
      setToast({ type: 'success', message: 'Image uploaded successfully.' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Image upload failed.',
      });
    } finally {
      setUploadingField('');
      e.target.value = '';
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setToast({ type: '', message: '' });
    try {
      const categories = form.product_categories_text
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      const created = await sellerApi.submitApplication({
        store_name: form.store_name.trim(),
        store_slug: form.store_slug.trim() || undefined,
        seller_display_name: form.seller_display_name.trim(),
        store_description: form.store_description.trim() || null,
        application_description: form.application_description.trim(),
        logo_url: form.logo_url.trim() || null,
        banner_url: form.banner_url.trim() || null,
        contact_email: form.contact_email.trim(),
        contact_info: form.contact_info.trim() || null,
        country: form.country.trim(),
        business_type: form.business_type.trim(),
        product_categories: categories,
      });
      setApplication(created);
      await refreshCustomerProfile();
      setToast({
        type: 'success',
        message: 'Seller application submitted! An administrator will review your store soon.',
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : 'Failed to submit seller application.',
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <StorefrontLayout>
        <LoadingState label="Checking seller application status..." />
      </StorefrontLayout>
    );
  }

  const status = application?.application_status;

  return (
    <StorefrontLayout>
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#FF6B0A]">
              Creator Marketplace
            </p>
            <h1 className="text-2xl sm:text-3xl font-bold text-[#1F2937] mt-1">
              DIGI-VERSE Seller Onboarding
            </h1>
            <p className="text-sm text-[#64748B] mt-1">
              Open your digital storefront, upload products securely, and reach verified marketplace buyers.
            </p>
          </div>
          <Link to="/profile" className="text-xs font-semibold text-[#FF6B0A] hover:underline">
            Back to Profile
          </Link>
        </div>

        <ToastBanner
          type={toast.type}
          message={toast.message}
          onDismiss={() => setToast({ type: '', message: '' })}
        />

        {status === 'approved' && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-6 h-6 text-emerald-700 shrink-0 mt-0.5" />
              <div>
                <h2 className="text-base font-bold text-emerald-900">
                  Your seller store "{application.store_name}" is Approved!
                </h2>
                <p className="text-xs text-emerald-800 mt-1">
                  You have full access to Seller Studio while keeping all of your customer purchasing privileges.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2.5 shrink-0">
              <Link
                to={`/store/${application.store_slug}`}
                className="dv-btn-secondary px-4 py-2 text-xs font-semibold"
              >
                View Storefront
              </Link>
              <Link to="/seller" className="dv-btn-primary px-5 py-2 text-xs font-semibold">
                Open Seller Studio
              </Link>
            </div>
          </div>
        )}

        {status === 'pending' && (
          <div className="bg-[#FFF2E6] border border-[#FFD4AE] rounded-2xl p-6 flex items-start gap-3.5">
            <Clock className="w-6 h-6 text-[#FF6B0A] shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h2 className="text-base font-bold text-[#1F2937]">
                Application Pending Administrator Review
              </h2>
              <p className="text-xs text-[#243247] leading-relaxed">
                Storefront <strong>{application.store_name}</strong> (<code>/store/{application.store_slug}</code>) was submitted and is awaiting administrator review. You cannot publish products until approval is granted.
              </p>
            </div>
          </div>
        )}

        {status === 'suspended' && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-6 flex items-start gap-3.5">
            <ShieldAlert className="w-6 h-6 text-red-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h2 className="text-base font-bold text-red-900">Seller Account Suspended</h2>
              <p className="text-xs text-red-800 leading-relaxed">
                {application.suspension_reason ||
                  'Your seller storefront has been suspended by marketplace administrators.'}
              </p>
              <p className="text-xs text-red-700">
                Creating, modifying, or publishing seller products is currently disabled. Existing buyer downloads remain unaffected unless explicitly revoked.
              </p>
            </div>
          </div>
        )}

        {status === 'rejected' && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-6 flex items-start gap-3.5">
            <AlertCircle className="w-6 h-6 text-red-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h2 className="text-base font-bold text-red-900">Previous Application Rejected</h2>
              <p className="text-xs text-red-800 leading-relaxed">
                <strong>Reason:</strong> {application.rejection_reason}
              </p>
              <p className="text-xs text-[#64748B]">
                Update your store profile details below and resubmit for administrator review.
              </p>
            </div>
          </div>
        )}

        {(!status || status === 'rejected') && (
          <form
            onSubmit={handleSubmit}
            className="bg-white border border-[#E5E7EB] rounded-2xl p-6 sm:p-8 shadow-xs space-y-5"
          >
            <div className="flex items-center gap-2.5 border-b border-[#E5E7EB] pb-4">
              <Store className="w-5 h-5 text-[#FF6B0A]" />
              <h2 className="text-base font-bold text-[#1F2937]">
                {status === 'rejected' ? 'Update & Resubmit Seller Application' : 'Seller Store Application'}
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                  Store Name *
                </label>
                <input
                  type="text"
                  required
                  value={form.store_name}
                  onChange={(e) => {
                    const val = e.target.value;
                    setForm((prev) => ({
                      ...prev,
                      store_name: val,
                      store_slug: autoSlug ? slugify(val) : prev.store_slug,
                    }));
                  }}
                  placeholder="e.g. Creative Studio"
                  className="dv-input text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                  Storefront URL Slug *
                </label>
                <input
                  type="text"
                  required
                  value={form.store_slug}
                  onChange={(e) => {
                    setAutoSlug(false);
                    setForm((prev) => ({ ...prev, store_slug: e.target.value.toLowerCase() }));
                  }}
                  placeholder="creative-studio"
                  className="dv-input text-sm font-mono"
                />
                <p className="text-[11px] text-[#64748B] mt-1">
                  Public URL: <code>/store/{form.store_slug || 'your-store'}</code>
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                  Seller Display Name *
                </label>
                <input
                  type="text"
                  required
                  value={form.seller_display_name}
                  onChange={(e) => setForm((prev) => ({ ...prev, seller_display_name: e.target.value }))}
                  className="dv-input text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                  Contact Email *
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
                  placeholder="+91... or support handle"
                  className="dv-input text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                  Country *
                </label>
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
                  Business / Creator Type *
                </label>
                <select
                  value={form.business_type}
                  onChange={(e) => setForm((prev) => ({ ...prev, business_type: e.target.value }))}
                  className="dv-input text-sm"
                >
                  <option value="Independent Creator">Independent Creator</option>
                  <option value="Design Studio">Design Studio</option>
                  <option value="Software Indie">Software Indie / Dev Tooling</option>
                  <option value="Digital Agency">Digital Agency</option>
                  <option value="Educator / Author">Educator / Author</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                  Intended Product Categories (comma separated)
                </label>
                <input
                  type="text"
                  value={form.product_categories_text}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, product_categories_text: e.target.value }))
                  }
                  placeholder="UI Kits, Notion Templates, React Starters"
                  className="dv-input text-sm"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                  Store Logo URL (or Upload)
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={form.logo_url}
                    onChange={(e) => setForm((prev) => ({ ...prev, logo_url: e.target.value }))}
                    placeholder="/api/uploads/images/..."
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
                <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                  Store Banner URL (or Upload)
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={form.banner_url}
                    onChange={(e) => setForm((prev) => ({ ...prev, banner_url: e.target.value }))}
                    placeholder="/api/uploads/images/..."
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
                Public Store Description
              </label>
              <textarea
                rows={3}
                value={form.store_description}
                onChange={(e) => setForm((prev) => ({ ...prev, store_description: e.target.value }))}
                placeholder="Tell buyers what your store specializes in..."
                className="dv-input text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#243247] mb-1.5">
                Application Review Notes (For Marketplace Admins) *
              </label>
              <textarea
                rows={3}
                required
                minLength={10}
                value={form.application_description}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, application_description: e.target.value }))
                }
                placeholder="Describe the digital products you plan to sell, your portfolio, or support standards..."
                className="dv-input text-sm"
              />
            </div>

            <div className="flex items-center justify-between gap-4 pt-2 border-t border-[#E5E7EB]">
              <p className="text-[11px] text-[#64748B]">
                No sensitive banking details are collected during onboarding.
              </p>
              <Button type="submit" disabled={submitting}>
                {submitting
                  ? 'Submitting...'
                  : status === 'rejected'
                    ? 'Resubmit Application'
                    : 'Submit Seller Application'}
              </Button>
            </div>
          </form>
        )}
      </div>
    </StorefrontLayout>
  );
};

export default SellerOnboardingPage;
