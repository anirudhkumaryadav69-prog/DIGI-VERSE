import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import { useDocumentMeta } from '../../components/common/StorefrontDesignSystem';
import { useAuth } from '../../context/AuthContext';

const LoginPage = () => {
  const navigate = useNavigate();
  const { loginCustomer } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useDocumentMeta({
    title: 'Customer Sign In',
    description: 'Sign in to your DIGI-VERSE account to access your digital downloads and orders.',
    canonicalPath: '/login',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const data = await loginCustomer({ email: email.trim(), password });
      if (data.requires_phone_verification) {
        navigate('/verify-phone', { replace: true });
      } else {
        navigate('/profile', { replace: true });
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Invalid email or password.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <StorefrontLayout>
      <div className="w-full max-w-md mx-auto my-6 dv-card-warm p-6 sm:p-8">
        <p className="text-xs uppercase tracking-[0.2em] text-[#FF6B0A] font-semibold mb-2">
          Customer Sign In
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-[#1F2937] mb-6">Welcome back</h1>

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
              htmlFor="login-email"
              className="block text-xs font-medium text-[#243247] mb-1.5"
            >
              Email Address
            </label>
            <input
              id="login-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="name@example.com"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label
                htmlFor="login-password"
                className="block text-xs font-medium text-[#243247]"
              >
                Password
              </label>
              <Link
                to="/forgot-password"
                className="text-xs font-medium text-[#FF6B0A] hover:text-[#D94300] hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="Enter your password"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary w-full mt-4 py-3 px-4 text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <span>{submitting ? 'Signing In...' : 'Sign In'}</span>
            <ArrowRight className="w-4 h-4" aria-hidden="true" />
          </button>
        </form>

        <p className="mt-6 text-xs text-[#64748B] text-center">
          New to DIGI-VERSE?{' '}
          <Link to="/register" className="text-[#FF6B0A] font-semibold hover:text-[#D94300] hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </StorefrontLayout>
  );
};

export default LoginPage;
