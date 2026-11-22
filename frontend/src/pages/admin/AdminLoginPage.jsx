import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Shield, Lock, AlertCircle, ArrowRight } from 'lucide-react';
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
    <div className="min-h-screen bg-[#FFFAF5] text-[#243247] flex flex-col justify-between p-6 md:p-12">
      <header className="max-w-6xl w-full mx-auto flex items-center justify-between border-b border-[#E5E7EB] pb-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#FF6B0A] text-white flex items-center justify-center shadow-[0_4px_12px_-2px_rgba(255,107,10,0.3)]">
            <Shield className="w-4 h-4" />
          </div>
          <span className="font-bold tracking-tight text-sm text-[#1F2937] uppercase">
            DIGI-VERSE <span className="text-[#FF6B0A]">ADMIN</span>
          </span>
        </div>
        <Link
          to="/"
          className="text-xs font-semibold text-[#FF6B0A] hover:text-[#D94300] hover:underline"
        >
          Storefront →
        </Link>
      </header>

      <main className="w-full max-w-md mx-auto my-12 dv-card-warm p-8">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-[#FF6B0A] font-semibold mb-2">
          <Lock className="w-3.5 h-3.5" />
          <span>Restricted Access</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-[#1F2937] mb-6">
          Administrator Sign In
        </h1>

        {error && (
          <div className="mb-6 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[#243247] mb-1.5">
              Administrator Username
            </label>
            <input
              type="text"
              required
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="Enter administrator username"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[#243247] mb-1.5">
              Password
            </label>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm"
              placeholder="Enter administrator password"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary w-full mt-4 py-3 px-4 text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <span>{submitting ? 'Authenticating...' : 'Authenticate'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
      </main>

      <footer className="max-w-6xl w-full mx-auto border-t border-[#E5E7EB] pt-5 text-xs text-[#64748B] flex justify-between">
        <span>Isolated Administrator Session Authority</span>
        <span>All login attempts are audited</span>
      </footer>
    </div>
  );
};

export default AdminLoginPage;
