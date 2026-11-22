import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import { useDocumentMeta } from '../../components/common/StorefrontDesignSystem';
import { useAuth } from '../../context/AuthContext';

const E164_REGEX = /^\+[1-9][0-9]{7,14}$/;

const RegisterPage = () => {
  const navigate = useNavigate();
  const { registerCustomer } = useAuth();
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone_number: '+91',
    password: '',
    confirm_password: '',
    email_marketing_consent: false,
    whatsapp_marketing_consent: false,
  });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useDocumentMeta({
    title: 'Create Account',
    description: 'Create a DIGI-VERSE customer account for instant digital product downloads.',
    canonicalPath: '/register',
  });

  const validateForm = () => {
    if (formData.full_name.trim().length < 2) {
      return 'Full name must be at least 2 characters.';
    }
    if (!E164_REGEX.test(formData.phone_number.trim())) {
      return 'Phone number must be in E.164 format (e.g. +919876543210).';
    }
    if (formData.password.length < 8) {
      return 'Password must be at least 8 characters long.';
    }
    if (
      !/[A-Z]/.test(formData.password) ||
      !/[a-z]/.test(formData.password) ||
      !/\d/.test(formData.password) ||
      !/[^A-Za-z0-9]/.test(formData.password)
    ) {
      return 'Password must include uppercase, lowercase, number, and special character.';
    }
    if (formData.password !== formData.confirm_password) {
      return 'Passwords do not match.';
    }
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSubmitting(true);
    try {
      await registerCustomer({
        full_name: formData.full_name.trim(),
        email: formData.email.trim(),
        phone_number: formData.phone_number.trim(),
        password: formData.password,
        email_marketing_consent: formData.email_marketing_consent,
        whatsapp_marketing_consent: formData.whatsapp_marketing_consent,
      });
      navigate('/verify-phone', { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === 'string' ? detail : 'Registration failed. Please check your details.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <StorefrontLayout>
      <div className="w-full max-w-md mx-auto my-6 dv-card-warm p-6 sm:p-8">
        <p className="text-xs text-[#2563EB] font-semibold mb-1.5">
          Customer Account
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-[#263445] mb-6">
          Create your account
        </h1>

        {error && (
          <div
            role="alert"
            className="mb-6 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2.5"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="register-full-name"
              className="block text-xs font-medium text-[#263445] mb-1.5"
            >
              Full Name
            </label>
            <input
              id="register-full-name"
              type="text"
              required
              autoComplete="name"
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="Aarav Sharma"
            />
          </div>

          <div>
            <label
              htmlFor="register-email"
              className="block text-xs font-medium text-[#263445] mb-1.5"
            >
              Email Address
            </label>
            <input
              id="register-email"
              type="email"
              required
              autoComplete="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="name@example.com"
            />
          </div>

          <div>
            <label
              htmlFor="register-phone"
              className="block text-xs font-medium text-[#263445] mb-1.5"
            >
              Phone Number (E.164)
            </label>
            <input
              id="register-phone"
              type="tel"
              required
              autoComplete="tel"
              value={formData.phone_number}
              onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="+919876543210"
            />
          </div>

          <div>
            <label
              htmlFor="register-password"
              className="block text-xs font-medium text-[#263445] mb-1.5"
            >
              Password
            </label>
            <input
              id="register-password"
              type="password"
              required
              autoComplete="new-password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="8+ chars, upper, lower, digit & symbol"
            />
          </div>

          <div>
            <label
              htmlFor="register-confirm-password"
              className="block text-xs font-medium text-[#263445] mb-1.5"
            >
              Confirm Password
            </label>
            <input
              id="register-confirm-password"
              type="password"
              required
              autoComplete="new-password"
              value={formData.confirm_password}
              onChange={(e) => setFormData({ ...formData, confirm_password: e.target.value })}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="Re-enter password"
            />
          </div>

          <div className="pt-2 space-y-2 text-xs text-[#64748B]">
            <label className="flex items-center gap-2 cursor-pointer text-[#263445]">
              <input
                type="checkbox"
                checked={formData.email_marketing_consent}
                onChange={(e) =>
                  setFormData({ ...formData, email_marketing_consent: e.target.checked })
                }
                className="accent-[#2563EB]"
              />
              <span>Receive curated digital product releases via email</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-[#263445]">
              <input
                type="checkbox"
                checked={formData.whatsapp_marketing_consent}
                onChange={(e) =>
                  setFormData({ ...formData, whatsapp_marketing_consent: e.target.checked })
                }
                className="accent-[#2563EB]"
              />
              <span>Receive order and product updates via WhatsApp</span>
            </label>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary w-full mt-4 py-3 px-4 text-[13.5px] font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <span>{submitting ? 'Creating Account...' : 'Create Account'}</span>
            <ArrowRight className="w-4 h-4" aria-hidden="true" />
          </button>
        </form>

        <p className="mt-6 text-xs text-[#64748B] text-center">
          Already have an account?{' '}
          <Link to="/login" className="text-[#2563EB] font-semibold hover:text-[#1D4ED8] hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </StorefrontLayout>
  );
};

export default RegisterPage;
