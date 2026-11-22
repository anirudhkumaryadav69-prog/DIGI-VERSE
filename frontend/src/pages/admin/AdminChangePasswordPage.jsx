import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, KeyRound, AlertCircle, CheckCircle2, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { adminAuthApi } from '../../services/api';

const AdminChangePasswordPage = () => {
  const navigate = useNavigate();
  const { admin, setAdmin, adminMustChangePassword, logoutAdmin } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await adminAuthApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setAdmin(res.admin);
      setSuccess(res.message || 'Administrator password updated.');
      setTimeout(() => navigate('/admin', { replace: true }), 900);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update password.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await logoutAdmin();
    navigate('/admin/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#FFFAF5] text-[#243247] flex flex-col justify-between p-6 md:p-12">
      <header className="max-w-6xl w-full mx-auto flex items-center justify-between border-b border-[#E5E7EB] pb-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#FF6B0A] text-white flex items-center justify-center shadow-xs">
            <Shield className="w-4 h-4" />
          </div>
          <span className="font-bold tracking-tight text-sm text-[#1F2937] uppercase">
            DIGI-VERSE ADMIN ({admin?.username})
          </span>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="text-xs font-semibold text-[#64748B] hover:text-[#FF6B0A] flex items-center gap-1.5"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </header>

      <main className="w-full max-w-md mx-auto my-12 dv-card-warm p-8">
        <div className="w-11 h-11 rounded-2xl bg-[#FFF2E6] border border-[#FFD4AE] text-[#FF6B0A] flex items-center justify-center mb-4">
          <KeyRound className="w-5 h-5" />
        </div>
        <p className="text-xs uppercase tracking-[0.2em] text-[#FF6B0A] font-semibold mb-2">
          {adminMustChangePassword ? 'Mandatory Security Action' : 'Administrator Security'}
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-[#1F2937] mb-2">
          {adminMustChangePassword ? 'Change Initial Password' : 'Change Administrator Password'}
        </h1>
        {adminMustChangePassword && (
          <p className="text-xs text-[#D94300] bg-[#FFF2E6] border border-[#FFD4AE] rounded-xl p-3 mb-6 leading-relaxed">
            For security, all administrative operations remain locked until the one-time provisioned
            password is changed.
          </p>
        )}

        {error && (
          <div className="mb-5 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-5 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2.5">
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[#243247] mb-1.5">
              Current Password
            </label>
            <input
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[#243247] mb-1.5">
              New Strong Password
            </label>
            <input
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="8+ chars, upper, lower, digit & symbol"
              className="dv-input px-3.5 py-2.5 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[#243247] mb-1.5">
              Confirm New Password
            </label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-sm"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary w-full mt-2 py-3 px-4 text-xs font-semibold uppercase tracking-wider disabled:opacity-50"
          >
            {submitting ? 'Updating...' : 'Update Password & Continue'}
          </button>
        </form>
      </main>

      <footer className="max-w-6xl w-full mx-auto border-t border-[#E5E7EB] pt-5 text-xs text-[#64748B]">
        <span>Password rotation revokes all prior administrator sessions.</span>
      </footer>
    </div>
  );
};

export default AdminChangePasswordPage;
