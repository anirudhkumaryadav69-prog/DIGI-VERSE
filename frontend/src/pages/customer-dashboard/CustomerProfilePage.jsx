import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Heart,
  KeyRound,
  LogOut,
  Package,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Store,
  UserCheck,
} from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import { useDocumentMeta } from '../../components/common/StorefrontDesignSystem';
import { useAuth } from '../../context/AuthContext';
import { customerAuthApi } from '../../services/api';

const CustomerProfilePage = () => {
  const navigate = useNavigate();
  const {
    customer,
    setCustomer,
    logoutCustomer,
    logoutAllCustomerDevices,
    wishlistCount,
  } = useAuth();

  useDocumentMeta({
    title: 'Account & Preferences',
    description:
      'Manage your DIGI-VERSE profile, phone verification, communication preferences, orders, and downloads.',
    canonicalPath: '/profile',
  });

  const [fullName, setFullName] = useState(customer?.full_name || '');
  const [emailConsent, setEmailConsent] = useState(Boolean(customer?.email_marketing_consent));
  const [whatsappConsent, setWhatsappConsent] = useState(
    Boolean(customer?.whatsapp_marketing_consent)
  );
  const [profileStatus, setProfileStatus] = useState({ error: '', success: '', loading: false });

  const [newPhone, setNewPhone] = useState(customer?.pending_phone_number || '');
  const [phoneStatus, setPhoneStatus] = useState({ error: '', success: '', loading: false });

  const [passwords, setPasswords] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [pwStatus, setPwStatus] = useState({ error: '', success: '', loading: false });

  const handleProfileSave = async (e) => {
    e.preventDefault();
    setProfileStatus({ error: '', success: '', loading: true });
    try {
      const updated = await customerAuthApi.updateProfile({
        full_name: fullName.trim(),
        email_marketing_consent: emailConsent,
        whatsapp_marketing_consent: whatsappConsent,
      });
      setCustomer(updated);
      setProfileStatus({ error: '', success: 'Profile updated successfully.', loading: false });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setProfileStatus({
        error: typeof detail === 'string' ? detail : 'Failed to update profile.',
        success: '',
        loading: false,
      });
    }
  };

  const handlePhoneChangeRequest = async (e) => {
    e.preventDefault();
    setPhoneStatus({ error: '', success: '', loading: true });
    try {
      const updated = await customerAuthApi.requestPhoneChange({
        phone_number: newPhone.trim(),
      });
      setCustomer(updated);
      setPhoneStatus({
        error: '',
        success: 'OTP sent to your new phone number. Redirecting to verification...',
        loading: false,
      });
      setTimeout(() => navigate('/verify-phone'), 700);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setPhoneStatus({
        error: typeof detail === 'string' ? detail : 'Unable to update phone number.',
        success: '',
        loading: false,
      });
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (passwords.new_password !== passwords.confirm_password) {
      setPwStatus({ error: 'New passwords do not match.', success: '', loading: false });
      return;
    }
    setPwStatus({ error: '', success: '', loading: true });
    try {
      const res = await customerAuthApi.changePassword({
        current_password: passwords.current_password,
        new_password: passwords.new_password,
      });
      setCustomer(res.customer);
      setPasswords({ current_password: '', new_password: '', confirm_password: '' });
      setPwStatus({
        error: '',
        success: res.message || 'Password updated and previous sessions revoked.',
        loading: false,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setPwStatus({
        error: typeof detail === 'string' ? detail : 'Password change failed.',
        success: '',
        loading: false,
      });
    }
  };

  const handleLogout = async () => {
    await logoutCustomer();
    navigate('/login', { replace: true });
  };

  const handleLogoutAll = async () => {
    await logoutAllCustomerDevices();
    navigate('/login', { replace: true });
  };

  return (
    <StorefrontLayout>
      <div className="space-y-8">
        {/* Account Overview Banner */}
        <section className="dv-card-warm p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-[#FF6B0A] font-semibold mb-1">
              Customer Account
            </p>
            <h1 className="text-2xl font-bold tracking-tight text-[#1F2937]">
              {customer?.full_name}
            </h1>
            <p className="text-xs text-[#64748B] mt-1">{customer?.email}</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {customer?.is_phone_verified ? (
              <div className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs">
                <ShieldCheck className="w-4 h-4" aria-hidden="true" />
                <span>Phone Verified ({customer.phone_number})</span>
              </div>
            ) : (
              <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-[#FFF2E6] border border-[#FFD4AE] text-[#D94300] text-xs">
                <ShieldAlert className="w-4 h-4 shrink-0 text-[#FF6B0A]" aria-hidden="true" />
                <span>Phone verification required for sensitive operations.</span>
                <Link
                  to="/verify-phone"
                  className="font-semibold underline text-[#1F2937] ml-1"
                >
                  Verify Now
                </Link>
              </div>
            )}

            <button
              type="button"
              onClick={handleLogoutAll}
              className="dv-btn-secondary text-xs font-semibold uppercase tracking-wider px-3.5 py-2"
            >
              Sign Out All Devices
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="dv-btn-primary text-xs font-semibold uppercase tracking-wider px-3.5 py-2 inline-flex items-center gap-1.5"
            >
              <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Sign Out</span>
            </button>
          </div>
        </section>

        {/* Quick Navigation Hub: Orders, Downloads, Wishlist */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Link
            to="/orders"
            className="dv-card-interactive p-5 flex items-center justify-between"
          >
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[#FF6B0A] font-semibold">
                Purchase History
              </p>
              <p className="text-base font-semibold text-[#1F2937] mt-1">Orders &amp; Invoices</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-[#FFF2E6] border border-[#FFD4AE] flex items-center justify-center text-[#FF6B0A]">
              <Package className="w-5 h-5" aria-hidden="true" />
            </div>
          </Link>

          <Link
            to="/downloads"
            className="dv-card-interactive p-5 flex items-center justify-between"
          >
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[#FF6B0A] font-semibold">
                Digital Library
              </p>
              <p className="text-base font-semibold text-[#1F2937] mt-1">Purchased Downloads</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-[#FFF2E6] border border-[#FFD4AE] flex items-center justify-center text-[#FF6B0A]">
              <Download className="w-5 h-5" aria-hidden="true" />
            </div>
          </Link>

          <Link
            to="/wishlist"
            className="dv-card-interactive p-5 flex items-center justify-between"
          >
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[#FF6B0A] font-semibold">
                Saved Items ({wishlistCount})
              </p>
              <p className="text-base font-semibold text-[#1F2937] mt-1">Your Wishlist</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-[#FFF2E6] border border-[#FFD4AE] flex items-center justify-center text-[#FF6B0A]">
              <Heart className="w-5 h-5" aria-hidden="true" />
            </div>
          </Link>

          <Link
            to={customer?.is_seller ? '/seller' : '/seller/apply'}
            className="dv-card-interactive p-5 flex items-center justify-between sm:col-span-3 bg-linear-to-r from-white to-[#FFF6ED]"
          >
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[#FF6B0A] font-semibold">
                {customer?.is_seller
                  ? 'Approved Creator Store'
                  : customer?.seller_status === 'pending'
                    ? 'Application Under Review'
                    : customer?.seller_status === 'rejected'
                      ? 'Application Update Required'
                      : customer?.seller_status === 'suspended'
                        ? 'Seller Account Suspended'
                        : 'Creator Marketplace'}
              </p>
              <p className="text-base font-semibold text-[#1F2937] mt-1">
                {customer?.is_seller
                  ? 'Open Seller Studio & Manage Your Storefront'
                  : customer?.seller_status
                    ? 'View Your Seller Application Status'
                    : 'Apply to Sell Digital Products on DIGI-VERSE'}
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-[#FF6B0A] text-white flex items-center justify-center shrink-0">
              <Store className="w-5 h-5" aria-hidden="true" />
            </div>
          </Link>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Permitted Profile Update */}
          <section className="dv-card p-6 md:p-8">
            <div className="flex items-center gap-2.5 mb-5">
              <UserCheck className="w-4 h-4 text-[#FF6B0A]" aria-hidden="true" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-[#1F2937]">
                Profile &amp; Communication Preferences
              </h2>
            </div>

            {profileStatus.error && (
              <div
                role="alert"
                className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2"
              >
                <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
                <span>{profileStatus.error}</span>
              </div>
            )}
            {profileStatus.success && (
              <div
                role="status"
                className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2"
              >
                <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
                <span>{profileStatus.success}</span>
              </div>
            )}

            <form onSubmit={handleProfileSave} className="space-y-4">
              <div>
                <label
                  htmlFor="profile-full-name"
                  className="block text-xs font-medium text-[#243247] mb-1.5"
                >
                  Full Name
                </label>
                <input
                  id="profile-full-name"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="dv-input px-3.5 py-2.5 text-sm"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-email-readonly"
                  className="block text-xs font-medium text-[#243247] mb-1.5"
                >
                  Registered Email (Read-Only)
                </label>
                <input
                  id="profile-email-readonly"
                  type="email"
                  disabled
                  value={customer?.email || ''}
                  className="dv-input bg-[#FFF6ED] px-3.5 py-2.5 text-sm text-[#64748B] cursor-not-allowed"
                />
              </div>

              <div className="pt-2 space-y-2 text-xs text-[#64748B]">
                <label className="flex items-center gap-2 cursor-pointer text-[#243247]">
                  <input
                    type="checkbox"
                    checked={emailConsent}
                    onChange={(e) => setEmailConsent(e.target.checked)}
                    className="accent-[#FF6B0A]"
                  />
                  <span>Email marketing notifications</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-[#243247]">
                  <input
                    type="checkbox"
                    checked={whatsappConsent}
                    onChange={(e) => setWhatsappConsent(e.target.checked)}
                    className="accent-[#FF6B0A]"
                  />
                  <span>WhatsApp marketing notifications</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={profileStatus.loading}
                className="dv-btn-primary py-2.5 px-5 text-xs font-semibold uppercase tracking-wider disabled:opacity-50"
              >
                {profileStatus.loading ? 'Saving...' : 'Save Profile'}
              </button>
            </form>
          </section>

          {/* Phone Number Update with OTP Re-verification */}
          <section className="dv-card p-6 md:p-8">
            <div className="flex items-center gap-2.5 mb-5">
              <Smartphone className="w-4 h-4 text-[#FF6B0A]" aria-hidden="true" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-[#1F2937]">
                Phone Number &amp; OTP Re-Verification
              </h2>
            </div>

            <p className="text-xs text-[#64748B] mb-4 leading-relaxed">
              Current phone: <strong className="text-[#1F2937]">{customer?.phone_number}</strong>.
              Updating your phone number sends a new 6-digit OTP before activating the change.
            </p>

            {phoneStatus.error && (
              <div
                role="alert"
                className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2"
              >
                <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
                <span>{phoneStatus.error}</span>
              </div>
            )}
            {phoneStatus.success && (
              <div
                role="status"
                className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2"
              >
                <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
                <span>{phoneStatus.success}</span>
              </div>
            )}

            <form onSubmit={handlePhoneChangeRequest} className="space-y-4">
              <div>
                <label
                  htmlFor="profile-new-phone"
                  className="block text-xs font-medium text-[#243247] mb-1.5"
                >
                  New Phone Number (E.164)
                </label>
                <input
                  id="profile-new-phone"
                  type="tel"
                  required
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  placeholder="+919876543210"
                  className="dv-input px-3.5 py-2.5 text-sm"
                />
              </div>

              <button
                type="submit"
                disabled={phoneStatus.loading}
                className="dv-btn-secondary py-2.5 px-5 text-xs font-semibold uppercase tracking-wider disabled:opacity-50"
              >
                {phoneStatus.loading ? 'Sending OTP...' : 'Send Verification OTP'}
              </button>
            </form>
          </section>
        </div>

        {/* Change Password Section */}
        <section className="dv-card p-6 md:p-8">
          <div className="flex items-center gap-2.5 mb-5">
            <KeyRound className="w-4 h-4 text-[#FF6B0A]" aria-hidden="true" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[#1F2937]">
              Change Password
            </h2>
          </div>

          {pwStatus.error && (
            <div
              role="alert"
              className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2"
            >
              <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>{pwStatus.error}</span>
            </div>
          )}
          {pwStatus.success && (
            <div
              role="status"
              className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>{pwStatus.success}</span>
            </div>
          )}

          <form
            onSubmit={handleChangePassword}
            className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end"
          >
            <div>
              <label
                htmlFor="profile-current-password"
                className="block text-xs font-medium text-[#243247] mb-1.5"
              >
                Current Password
              </label>
              <input
                id="profile-current-password"
                type="password"
                required
                value={passwords.current_password}
                onChange={(e) =>
                  setPasswords({ ...passwords, current_password: e.target.value })
                }
                className="dv-input px-3.5 py-2.5 text-sm"
              />
            </div>

            <div>
              <label
                htmlFor="profile-new-password"
                className="block text-xs font-medium text-[#243247] mb-1.5"
              >
                New Password
              </label>
              <input
                id="profile-new-password"
                type="password"
                required
                value={passwords.new_password}
                onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })}
                className="dv-input px-3.5 py-2.5 text-sm"
              />
            </div>

            <div>
              <label
                htmlFor="profile-confirm-password"
                className="block text-xs font-medium text-[#243247] mb-1.5"
              >
                Confirm New Password
              </label>
              <input
                id="profile-confirm-password"
                type="password"
                required
                value={passwords.confirm_password}
                onChange={(e) =>
                  setPasswords({ ...passwords, confirm_password: e.target.value })
                }
                className="dv-input px-3.5 py-2.5 text-sm"
              />
            </div>

            <div className="md:col-span-3 pt-2">
              <button
                type="submit"
                disabled={pwStatus.loading}
                className="dv-btn-primary py-2.5 px-6 text-xs font-semibold uppercase tracking-wider disabled:opacity-50"
              >
                {pwStatus.loading ? 'Updating Password...' : 'Update Password'}
              </button>
            </div>
          </form>
        </section>
      </div>
    </StorefrontLayout>
  );
};

export default CustomerProfilePage;
