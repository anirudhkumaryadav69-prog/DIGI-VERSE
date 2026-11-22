import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, CheckCircle2, KeyRound, LogOut, Shield } from 'lucide-react';
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
    <div className="min-h-screen bg-[#EAF4FC] text-[#263445] flex flex-col justify-between p-6 md:p-10">
      <header className="max-w-5xl w-full mx-auto flex items-center justify-between border-b border-[#D5DEE8] pb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-[#2563EB] text-white flex items-center justify-center shadow-xs">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-[14px] text-[#263445] block leading-tight">
              DIGI-VERSE Admin
            </span>
            <span className="text-[11.5px] text-[#64748B]">{admin?.username}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="text-[12.5px] font-semibold text-[#64748B] hover:text-[#2563EB] inline-flex items-center gap-1.5"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </header>

      <main className="w-full max-w-md mx-auto my-10 bg-white border border-[#D5DEE8] rounded-xl p-7 sm:p-8 shadow-sm">
        <div className="w-10 h-10 rounded-lg bg-[#EAF4FC] border border-[#BFDBFE] text-[#2563EB] flex items-center justify-center mb-4">
          <KeyRound className="w-5 h-5" />
        </div>
        <p className="text-[12px] font-semibold text-[#2563EB] mb-1">
          {adminMustChangePassword ? 'Mandatory Security Action' : 'Administrator Security'}
        </p>
        <h1 className="text-[22px] font-semibold tracking-tight text-[#263445] mb-3">
          {adminMustChangePassword ? 'Change Initial Password' : 'Change Administrator Password'}
        </h1>
        {adminMustChangePassword && (
          <p className="text-[12.5px] text-[#1D4ED8] bg-[#EAF4FC] border border-[#BFDBFE] rounded-lg p-3 mb-5 leading-relaxed">
            For security, all administrative operations remain locked until the one-time provisioned
            password is changed.
          </p>
        )}

        {error && (
          <div
            role="alert"
            className="mb-5 p-3.5 rounded-lg bg-red-50 border border-red-200 text-[#DC2626] text-[12.5px] flex items-start gap-2.5"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div
            role="status"
            className="mb-5 p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-[#15803D] text-[12.5px] flex items-start gap-2.5"
          >
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="admin-current-pw"
              className="block text-[12.5px] font-medium text-[#263445] mb-1.5"
            >
              Current Password
            </label>
            <input
              id="admin-current-pw"
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-[14px]"
            />
          </div>

          <div>
            <label
              htmlFor="admin-new-pw"
              className="block text-[12.5px] font-medium text-[#263445] mb-1.5"
            >
              New Strong Password
            </label>
            <input
              id="admin-new-pw"
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="8+ chars, upper, lower, digit & symbol"
              className="dv-input px-3.5 py-2.5 text-[14px]"
            />
          </div>

          <div>
            <label
              htmlFor="admin-confirm-pw"
              className="block text-[12.5px] font-medium text-[#263445] mb-1.5"
            >
              Confirm New Password
            </label>
            <input
              id="admin-confirm-pw"
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="dv-input px-3.5 py-2.5 text-[14px]"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary w-full mt-2 py-2.5 px-4 text-[13px] font-semibold disabled:opacity-50"
          >
            {submitting ? 'Updating...' : 'Update Password & Continue'}
          </button>
        </form>
      </main>

      <footer className="max-w-5xl w-full mx-auto border-t border-[#D5DEE8] pt-4 text-[12px] text-[#64748B]">
        <span>Password rotation revokes all prior administrator sessions.</span>
      </footer>
    </div>
  );
};

export default AdminChangePasswordPage;
