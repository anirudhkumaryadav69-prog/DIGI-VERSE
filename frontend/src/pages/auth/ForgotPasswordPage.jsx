import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Mail } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import { useDocumentMeta } from '../../components/common/StorefrontDesignSystem';
import { customerAuthApi } from '../../services/api';

const ForgotPasswordPage = () => {
  const [email, setEmail] = useState('');
  const [submittedMessage, setSubmittedMessage] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useDocumentMeta({
    title: 'Account Recovery',
    description: 'Request a single-use password reset token for your DIGI-VERSE account.',
    canonicalPath: '/forgot-password',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmittedMessage('');
    setSubmitting(true);
    try {
      const res = await customerAuthApi.forgotPassword({ email: email.trim() });
      setSubmittedMessage(
        res.message ||
          'If an account with that email exists, password reset instructions have been sent.'
      );
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Unable to process request right now.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <StorefrontLayout>
      <div className="w-full max-w-md mx-auto my-6 dv-card-warm p-6 sm:p-8">
        <div className="w-11 h-11 rounded-2xl bg-[#FFF2E6] border border-[#FFD4AE] text-[#FF6B0A] flex items-center justify-center mb-4">
          <Mail className="w-5 h-5" aria-hidden="true" />
        </div>
        <p className="text-xs uppercase tracking-[0.2em] text-[#FF6B0A] font-semibold mb-2">
          Account Recovery
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-[#1F2937] mb-2">
          Forgot your password?
        </h1>
        <p className="text-xs text-[#64748B] mb-6 leading-relaxed">
          Enter your registered email address and we will issue a single-use password reset token.
        </p>

        {error && (
          <div
            role="alert"
            className="mb-5 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2.5"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {submittedMessage && (
          <div
            role="status"
            className="mb-5 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs space-y-2"
          >
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
              <span>{submittedMessage}</span>
            </div>
            <div className="pt-1">
              <Link to="/reset-password" className="text-[#D94300] font-semibold underline">
                Have a reset token? Proceed to Reset Password →
              </Link>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="forgot-email"
              className="block text-xs font-medium text-[#243247] mb-1.5"
            >
              Email Address
            </label>
            <input
              id="forgot-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="name@example.com"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary w-full py-3 px-4 text-xs font-semibold uppercase tracking-wider disabled:opacity-50"
          >
            {submitting ? 'Sending...' : 'Send Reset Instructions'}
          </button>
        </form>
      </div>
    </StorefrontLayout>
  );
};

export default ForgotPasswordPage;
