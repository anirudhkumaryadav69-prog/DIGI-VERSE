import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, Lock, Shield } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const AdminLoginPage = () => {
  const navigate = useNavigate();
  const { loginAdmin } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const data = await loginAdmin({ username: username.trim(), password });
      if (data.must_change_password) {
        navigate('/admin/change-password', { replace: true });
      } else {
        navigate('/admin', { replace: true });
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Invalid administrator credentials.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#EAF4FC] text-[#263445] flex flex-col justify-between p-6 md:p-10">
      <header className="max-w-5xl w-full mx-auto flex items-center justify-between border-b border-[#D5DEE8] pb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-[#2563EB] text-white flex items-center justify-center shadow-xs">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-[15px] text-[#263445] block leading-tight">
              DIGI-VERSE<span className="text-[#2563EB]">.</span>
            </span>
            <span className="text-[11px] font-medium text-[#64748B]">Admin Console</span>
          </div>
        </div>
        <Link
          to="/"
          className="text-[13px] font-semibold text-[#2563EB] hover:text-[#1D4ED8] hover:underline"
        >
          Back to Storefront →
        </Link>
      </header>

      <main className="w-full max-w-md mx-auto my-10 bg-white border border-[#D5DEE8] rounded-xl p-7 sm:p-8 shadow-sm">
        <div className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-[#1D4ED8] bg-[#EAF4FC] border border-[#BFDBFE] px-2.5 py-1 rounded-full mb-3">
          <Lock className="w-3.5 h-3.5" />
          <span>Restricted Administrator Access</span>
        </div>
        <h1 className="text-[22px] font-semibold tracking-tight text-[#263445] mb-1.5">
          Administrator Sign In
        </h1>
        <p className="text-[13px] text-[#64748B] mb-6">
          Authenticate with your provisioned administrator credentials.
        </p>

        {error && (
          <div
            role="alert"
            className="mb-5 p-3.5 rounded-lg bg-red-50 border border-red-200 text-[#DC2626] text-[12.5px] flex items-start gap-2.5"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="admin-login-username"
              className="block text-[12.5px] font-medium text-[#263445] mb-1.5"
            >
              Administrator Username
            </label>
            <input
              id="admin-login-username"
              type="text"
              required
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-[14px]"
              placeholder="Enter administrator username"
            />
          </div>

          <div>
            <label
              htmlFor="admin-login-password"
              className="block text-[12.5px] font-medium text-[#263445] mb-1.5"
            >
              Password
            </label>
            <input
              id="admin-login-password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-[14px]"
              placeholder="Enter administrator password"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary w-full mt-2 py-2.5 px-4 text-[13px] font-semibold inline-flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <span>{submitting ? 'Authenticating...' : 'Sign In to Console'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
      </main>

      <footer className="max-w-5xl w-full mx-auto border-t border-[#D5DEE8] pt-4 text-[12px] text-[#64748B] flex flex-wrap justify-between gap-2">
        <span>Isolated Administrator Session Authority</span>
        <span>All authentication events are logged in the audit trail</span>
      </footer>
    </div>
  );
};

export default AdminLoginPage;
