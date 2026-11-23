import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, CheckCircle2, ShieldCheck } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import { useDocumentMeta } from '../../components/common/StorefrontDesignSystem';
import { useAuth } from '../../context/AuthContext';
import { customerAuthApi } from '../../services/api';

const VerifyPhonePage = () => {
  const navigate = useNavigate();
  const { customer, setCustomer, otpDeliveryStatus, setOtpDeliveryStatus } = useAuth();
  const [otpCode, setOtpCode] = useState('');
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);

  useDocumentMeta({
    title: 'Verify Phone Number',
    description: 'Verify your phone number with a 6-digit one-time code.',
    canonicalPath: '/verify-phone',
  });

  const targetPhone = customer?.pending_phone_number || customer?.phone_number || 'your phone';

  useEffect(() => {
    if (otpDeliveryStatus?.status === 'development_only') {
      setStatusMessage('Development mode: check the backend terminal for the local OTP. No WhatsApp message was sent.');
    } else if (otpDeliveryStatus?.status === 'accepted') {
      setStatusMessage('WhatsApp accepted the authentication message request.');
    } else if (otpDeliveryStatus?.status === 'failed' || otpDeliveryStatus?.status === 'disabled') {
      setError(otpDeliveryStatus.detail || 'OTP delivery is unavailable.');
    }
  }, [otpDeliveryStatus]);

  const handleVerify = async (e) => {
    e.preventDefault();
    setError('');
    setStatusMessage('');
    if (!/^\d{6}$/.test(otpCode.trim())) {
      setError('Please enter a valid 6-digit numeric verification code.');
      return;
    }

    setSubmitting(true);
    try {
      const updatedCustomer = await customerAuthApi.verifyOtp({ otp_code: otpCode.trim() });
      setCustomer(updatedCustomer);
      setStatusMessage('Phone number verified successfully.');
      setTimeout(() => navigate('/profile', { replace: true }), 800);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'OTP verification failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleResend = async () => {
    setError('');
    setStatusMessage('');
    setResending(true);
    try {
      const res = await customerAuthApi.sendOtp();
      setOtpDeliveryStatus({
        status: res.delivery_status,
        detail: res.delivery_detail,
      });
      if (res.delivery_status === 'development_only') {
        setStatusMessage('Development mode: check the backend terminal for the local OTP. No WhatsApp message was sent.');
      } else if (res.delivery_status === 'accepted') {
        setStatusMessage('WhatsApp accepted the new authentication message request.');
      } else {
        setStatusMessage(res.message || 'OTP delivery status unavailable.');
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Unable to send OTP right now.');
    } finally {
      setResending(false);
    }
  };

  return (
    <StorefrontLayout>
      <div className="w-full max-w-md mx-auto my-6 dv-card-warm p-6 sm:p-8">
        <div className="w-11 h-11 rounded-2xl bg-[#18243A] border border-[#BFDBFE] text-[#60A5FA] flex items-center justify-center mb-4">
          <ShieldCheck className="w-5 h-5" aria-hidden="true" />
        </div>
        <p className="text-xs text-[#60A5FA] font-semibold mb-1.5">
          Security Verification
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-[#F1F5F9] mb-2">
          Verify your phone number
        </h1>
        <p className="text-xs text-[#94A3B8] mb-6 leading-relaxed">
          Enter the 6-digit one-time verification code sent to{' '}
          <strong className="text-[#F1F5F9]">{targetPhone}</strong>. Codes expire after 5 minutes.
        </p>

        {error && (
          <div
            role="alert"
            className="mb-5 p-3.5 rounded-xl bg-red-950/50 border border-red-200 text-red-300 text-xs flex items-start gap-2.5"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {statusMessage && (
          <div
            role="status"
            className="mb-5 p-3.5 rounded-xl bg-emerald-950/50 border border-emerald-200 text-emerald-300 text-xs flex items-start gap-2.5"
          >
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{statusMessage}</span>
          </div>
        )}

        <form onSubmit={handleVerify} className="space-y-4">
          <div>
            <label
              htmlFor="otp-code-input"
              className="block text-xs font-medium text-[#F1F5F9] mb-1.5"
            >
              6-Digit Verification Code
            </label>
            <input
              id="otp-code-input"
              type="text"
              inputMode="numeric"
              maxLength={6}
              required
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
              className="dv-input px-4 py-3 text-center tracking-[0.5em] text-lg font-mono"
              placeholder="000000"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="dv-btn-primary w-full py-3 px-4 text-[13.5px] font-semibold disabled:opacity-50"
          >
            {submitting ? 'Verifying...' : 'Verify Phone Number'}
          </button>
        </form>

        <div className="mt-6 pt-5 border-t border-[#E5E7EB] flex items-center justify-between text-xs">
          <span className="text-[#94A3B8]">Didn&apos;t receive a code?</span>
          <button
            type="button"
            disabled={resending}
            onClick={handleResend}
            className="text-[#60A5FA] font-semibold hover:text-[#93C5FD] hover:underline disabled:opacity-50"
          >
            {resending ? 'Sending...' : 'Resend Code'}
          </button>
        </div>
      </div>
    </StorefrontLayout>
  );
};

export default VerifyPhonePage;
