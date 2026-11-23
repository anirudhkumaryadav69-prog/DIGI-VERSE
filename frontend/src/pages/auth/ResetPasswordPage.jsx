import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, KeyRound } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import { useDocumentMeta } from '../../components/common/StorefrontDesignSystem';
import { customerAuthApi } from '../../services/api';

const ResetPasswordPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [token, setToken] = useState(searchParams.get('token') || '');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useDocumentMeta({
    title: 'Reset Password',
    description: 'Set a new password for your DIGI-VERSE customer account.',
    canonicalPath: '/reset-password',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await customerAuthApi.resetPassword({
        token: token.trim(),
        new_password: newPassword,
      });
      setSuccess(res.message || 'Password reset successful.');
      setTimeout(() => navigate('/login', { replace: true }), 1200);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Invalid or expired reset token.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <StorefrontLayout>
      <div className="w-full max-w-md mx-auto my-6 dv-card-warm p-6 sm:p-8">
        <div className="w-11 h-11 rounded-2xl bg-[#18243A] border border-[#BFDBFE] text-[#60A5FA] flex items-center justify-center mb-4">
          <KeyRound className="w-5 h-5" aria-hidden="true" />
        </div>
        <p className="text-xs text-[#60A5FA] font-semibold mb-1.5">
          Password Reset
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-[#F1F5F9] mb-6">
          Set a new password
        </h1>

        {error && (
          <div
            role="alert"
            className="mb-5 p-3.5 rounded-xl bg-red-950/50 border border-red-200 text-red-300 text-xs flex items-start gap-2.5"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div
            role="status"
            className="mb-5 p-3.5 rounded-xl bg-emerald-950/50 border border-emerald-200 text-emerald-300 text-xs flex items-start gap-2.5"
          >
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="reset-token"
              className="block text-xs font-medium text-[#F1F5F9] mb-1.5"
            >
              Reset Token
            </label>
            <input
              id="reset-token"
              type="text"
              required
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm font-mono"
              placeholder="Paste single-use reset token"
            />
          </div>

          <div>
            <label
              htmlFor="reset-new-password"
              className="block text-xs font-medium text-[#F1F5F9] mb-1.5"
            >
              New Password
            </label>
            <input
              id="reset-new-password"
              type="password"
              required
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="8+ chars, upper, lower, digit & symbol"
            />
          </div>

          <div>
            <label
              htmlFor="reset-confirm-password"
              className="block text-xs font-medium text-[#F1F5F9] mb-1.5"
            >
              Confirm New Password
            </label>
            <input
              id="reset-confirm-password"
              type="password"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="Re-enter new password"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary w-full py-3 px-4 text-[13.5px] font-semibold disabled:opacity-50"
          >
            {submitting ? 'Resetting...' : 'Reset Password'}
          </button>
        </form>
      </div>
    </StorefrontLayout>
  );
};

export default ResetPasswordPage;
