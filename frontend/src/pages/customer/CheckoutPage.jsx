import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Download,
  FileText,
  Lock,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
  XCircle,
} from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import {
  Button,
  EmptyState,
  LoadingState,
  SectionHeading,
  formatINR,
  useDocumentMeta,
} from '../../components/common/StorefrontDesignSystem';
import { commerceApi } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

const CHECKOUT_STAGES = [
  { id: 1, label: '1. Review Order' },
  { id: 2, label: '2. Billing Details' },
  { id: 3, label: '3. Initialize Payment' },
  { id: 4, label: '4. Complete Payment' },
  { id: 5, label: '5. Server Verification' },
  { id: 6, label: '6. Final Result' },
];

const CheckoutPage = () => {
  const { customer, refreshCartAndWishlistCounts } = useAuth();
  const [searchParams] = useSearchParams();
  const existingOrderIdParam = searchParams.get('order_id');

  const [cart, setCart] = useState(null);
  const [checkoutSession, setCheckoutSession] = useState(null);
  const [verifiedOrder, setVerifiedOrder] = useState(null);
  const [stage, setStage] = useState(1);
  const [outcome, setOutcome] = useState('idle'); // 'idle' | 'awaiting_gateway' | 'verifying' | 'success' | 'failed' | 'cancelled'
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [billingConfirmed, setBillingConfirmed] = useState(true);
  const [idempotencyKey] = useState(
    () => `chk-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  );

  useDocumentMeta({
    title: 'Secure Checkout',
    description:
      'Complete your digital product purchase with cryptographic backend payment verification.',
    canonicalPath: '/checkout',
  });

  const loadInitialState = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      if (existingOrderIdParam) {
        const ord = await commerceApi.getOrder(existingOrderIdParam);
        if (ord.payment_status === 'paid') {
          setVerifiedOrder(ord);
          setStage(6);
          setOutcome('success');
        } else {
          // Prepare retry session for existing order
          const session = await commerceApi.retryOrderPayment(existingOrderIdParam);
          setCheckoutSession(session);
          setStage(3);
          setOutcome('awaiting_gateway');
        }
      } else {
        const res = await commerceApi.getCart();
        setCart(res);
        setStage(1);
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Unable to load checkout details.');
    } finally {
      setLoading(false);
    }
  }, [existingOrderIdParam]);

  useEffect(() => {
    loadInitialState();
  }, [loadInitialState]);

  const handleVerifyGatewayCallback = async (orderId, paymentPayload) => {
    setStage(5);
    setOutcome('verifying');
    setProcessing(true);
    setError('');
    try {
      const confirmedOrder = await commerceApi.verifyPayment({
        order_id: orderId,
        gateway_order_id: paymentPayload.gateway_order_id,
        gateway_payment_id: paymentPayload.gateway_payment_id,
        gateway_signature: paymentPayload.gateway_signature,
        payment_method: paymentPayload.payment_method || 'upi',
      });
      await refreshCartAndWishlistCounts();
      setVerifiedOrder(confirmedOrder);
      setStage(6);
      setOutcome('success');
    } catch (verifyErr) {
      const detail = verifyErr.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : 'Backend payment signature verification failed. Order remains unpaid.'
      );
      setStage(6);
      setOutcome('failed');
    } finally {
      setProcessing(false);
    }
  };

  const launchGatewayFlow = (session) => {
    setStage(4);
    setOutcome('awaiting_gateway');

    if (session.payment.gateway_name === 'razorpay' && typeof window.Razorpay === 'function') {
      const rzp = new window.Razorpay({
        key: session.payment.public_key_id,
        amount: session.payment.amount_subunits,
        currency: session.payment.currency,
        name: 'DIGI-VERSE',
        description: `Order ${session.order_number}`,
        order_id: session.payment.gateway_order_id,
        prefill: {
          name: customer?.full_name || '',
          email: customer?.email || '',
          contact: customer?.phone_number || '',
        },
        modal: {
          ondismiss: () => {
            setOutcome('cancelled');
            setStage(6);
            setError(
              'Payment window was closed before completion. Your order reference is saved and you can retry payment anytime.'
            );
          },
        },
        handler: async (response) => {
          await handleVerifyGatewayCallback(session.order_id, {
            gateway_order_id: response.razorpay_order_id,
            gateway_payment_id: response.razorpay_payment_id,
            gateway_signature: response.razorpay_signature,
            payment_method: 'upi',
          });
        },
      });
      rzp.open();
    }
  };

  const handleInitializeCheckout = async () => {
    if (processing) return;
    setError('');
    setProcessing(true);
    setStage(3);
    try {
      const session = checkoutSession
        ? await commerceApi.retryOrderPayment(checkoutSession.order_id)
        : await commerceApi.checkout(idempotencyKey);
      setCheckoutSession(session);
      launchGatewayFlow(session);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : 'Checkout initialization failed. Please check payment gateway configuration.'
      );
      setOutcome('failed');
      setStage(6);
    } finally {
      setProcessing(false);
    }
  };

  const handleRetryPayment = async () => {
    if (!checkoutSession?.order_id || processing) return;
    setError('');
    setProcessing(true);
    setStage(3);
    try {
      const session = await commerceApi.retryOrderPayment(checkoutSession.order_id);
      setCheckoutSession(session);
      launchGatewayFlow(session);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Could not re-initialize payment.');
      setOutcome('failed');
      setStage(6);
    } finally {
      setProcessing(false);
    }
  };

  const handleRefreshOrderStatus = async () => {
    if (!checkoutSession?.order_id || processing) return;
    setProcessing(true);
    try {
      const ord = await commerceApi.getOrder(checkoutSession.order_id);
      if (ord.payment_status === 'paid') {
        await refreshCartAndWishlistCounts();
        setVerifiedOrder(ord);
        setStage(6);
        setOutcome('success');
      } else {
        setError(
          `Order ${ord.order_number} is currently in status "${ord.status}" (payment: "${ord.payment_status}").`
        );
      }
    } catch {
      setError('Unable to check order payment status.');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <StorefrontLayout>
      <SectionHeading
        eyebrow="Idempotent Encrypted Checkout"
        title="Review & Complete Order"
        subtitle="Orders are fulfilled only after cryptographic backend payment verification."
      />

      {/* 6-Stage Checkout Progress Bar */}
      <nav aria-label="Checkout progress" className="mb-8">
        <ol className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-[11px] font-medium">
          {CHECKOUT_STAGES.map((s) => {
            const isActive = stage === s.id;
            const isCompleted = stage > s.id || outcome === 'success';
            return (
              <li
                key={s.id}
                className={`px-3 py-2.5 rounded-xl border text-center transition ${
                  isActive
                    ? 'bg-[#FF6B0A] text-white border-[#FF6B0A] font-semibold shadow-xs'
                    : isCompleted
                    ? 'bg-[#FFF2E6] text-[#D94300] border-[#FFD4AE]'
                    : 'bg-white text-[#64748B] border-[#E5E7EB]'
                }`}
              >
                {s.label}
              </li>
            );
          })}
        </ol>
      </nav>

      {error && (
        <div
          role="alert"
          className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-start gap-2.5"
        >
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <LoadingState label="Preparing Checkout..." />
      ) : outcome === 'success' && verifiedOrder ? (
        /* STAGE 6A: VERIFIED PAYMENT SUCCESS VIEW */
        <section
          aria-label="Payment Verified"
          className="dv-card-warm p-8 md:p-10 space-y-6 max-w-3xl mx-auto"
        >
          <div className="flex items-center gap-3 text-emerald-700">
            <CheckCircle2 className="w-7 h-7 shrink-0" aria-hidden="true" />
            <div>
              <p className="text-xs uppercase tracking-wider text-[#FF6B0A] font-semibold">
                Backend Signature Verified
              </p>
              <h2 className="text-2xl font-bold text-[#1F2937]">
                Payment Confirmed &amp; Digital Downloads Unlocked
              </h2>
            </div>
          </div>

          <div className="bg-[#FFF6ED] border border-[#FFD4AE] rounded-2xl p-5 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <p className="text-[#64748B] uppercase tracking-wider text-[10px]">Order Number</p>
              <p className="font-mono font-bold text-[#1F2937] text-sm mt-1">
                {verifiedOrder.order_number}
              </p>
            </div>
            <div>
              <p className="text-[#64748B] uppercase tracking-wider text-[10px]">Payment Status</p>
              <p className="uppercase font-semibold text-emerald-700 mt-1">
                {verifiedOrder.payment_status} ({verifiedOrder.status})
              </p>
            </div>
            <div>
              <p className="text-[#64748B] uppercase tracking-wider text-[10px]">Amount Paid</p>
              <p className="font-mono font-bold text-[#F4510B] text-sm mt-1">
                {formatINR(verifiedOrder.total_amount)}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link
              to="/downloads"
              className="dv-btn-primary px-6 py-3 text-xs font-semibold uppercase tracking-wider inline-flex items-center gap-2"
            >
              <Download className="w-4 h-4" aria-hidden="true" />
              <span>Access Digital Downloads</span>
            </Link>
            <Link
              to={`/orders/${verifiedOrder.id}`}
              className="dv-btn-secondary px-6 py-3 text-xs font-semibold uppercase tracking-wider inline-flex items-center gap-2"
            >
              <FileText className="w-4 h-4" aria-hidden="true" />
              <span>View Order &amp; Invoice</span>
            </Link>
          </div>
        </section>
      ) : (outcome === 'failed' || outcome === 'cancelled') && checkoutSession ? (
        /* STAGE 6B: PAYMENT FAILURE / CANCELLATION VIEW WITH RETRY */
        <section
          aria-label="Payment Incomplete"
          className="bg-white border border-red-200 rounded-2xl p-8 md:p-10 space-y-6 max-w-3xl mx-auto shadow-xs"
        >
          <div className="flex items-center gap-3 text-red-700">
            <XCircle className="w-7 h-7 shrink-0" aria-hidden="true" />
            <div>
              <p className="text-xs uppercase tracking-wider font-semibold">
                {outcome === 'cancelled' ? 'Payment Cancelled' : 'Payment Verification Failed'}
              </p>
              <h2 className="text-2xl font-bold text-[#1F2937]">
                Your order is saved and awaiting verified payment
              </h2>
            </div>
          </div>

          <div className="bg-[#FFF6ED] border border-[#E5E7EB] rounded-2xl p-5 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <p className="text-[#64748B] uppercase tracking-wider text-[10px]">Order Reference</p>
              <p className="font-mono font-semibold text-sm text-[#1F2937] mt-1">
                {checkoutSession.order_number}
              </p>
            </div>
            <div>
              <p className="text-[#64748B] uppercase tracking-wider text-[10px]">Gateway Order ID</p>
              <p className="font-mono text-xs text-[#243247] mt-1">
                {checkoutSession.payment.gateway_order_id}
              </p>
            </div>
            <div>
              <p className="text-[#64748B] uppercase tracking-wider text-[10px]">Total Payable</p>
              <p className="font-mono font-bold text-[#F4510B] text-sm mt-1">
                {formatINR(checkoutSession.total_amount)}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" disabled={processing} onClick={handleRetryPayment}>
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              <span>{processing ? 'Re-initializing...' : 'Retry Payment Now'}</span>
            </Button>
            <Button variant="secondary" disabled={processing} onClick={handleRefreshOrderStatus}>
              Check Webhook Status
            </Button>
            <Link
              to={`/orders/${checkoutSession.order_id}`}
              className="text-xs font-semibold text-[#FF6B0A] hover:text-[#D94300] underline px-3 py-2"
            >
              View Pending Order →
            </Link>
          </div>
        </section>
      ) : !cart?.items?.length && !checkoutSession ? (
        <EmptyState
          icon={ShoppingBag}
          title="Your cart is empty"
          description="Add digital products to your shopping cart before proceeding to checkout."
          action={
            <Link
              to="/products"
              className="dv-btn-primary inline-block text-xs font-semibold uppercase tracking-wider px-5 py-2.5"
            >
              Browse Products
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Stage 1 (Order Review) & Stage 2 (Billing Details) */}
          <div className="lg:col-span-7 space-y-6">
            {/* Stage 1: Order Items Review */}
            <section className="dv-card p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937]">
                  1. Review Digital Order Items
                </h2>
                <Link to="/cart" className="text-xs font-semibold text-[#FF6B0A] hover:underline">
                  Edit Cart
                </Link>
              </div>

              {cart?.items?.length ? (
                <div className="divide-y divide-[#E5E7EB] text-xs">
                  {cart.items.map((item) => (
                    <div key={item.id} className="py-3 flex items-center justify-between gap-4">
                      <div>
                        <p className="font-semibold text-[#1F2937]">{item.product_name}</p>
                        <p className="text-[#64748B]">
                          Qty: {item.quantity} × {formatINR(item.effective_unit_price)}
                        </p>
                      </div>
                      <span className="font-mono font-bold text-[#1F2937]">
                        {formatINR(item.line_total)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                checkoutSession && (
                  <p className="text-xs text-[#64748B]">
                    Resuming payment for pending order{' '}
                    <strong className="font-mono text-[#1F2937]">
                      {checkoutSession.order_number}
                    </strong>
                    .
                  </p>
                )
              )}
            </section>

            {/* Stage 2: Billing & Delivery Recipient Details */}
            <section className="dv-card p-6 space-y-4">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-[#1F2937] border-b border-[#E5E7EB] pb-3">
                2. Confirm Customer &amp; Delivery Details
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[#64748B]">
                    Customer Name
                  </p>
                  <p className="font-semibold text-[#1F2937] mt-0.5">{customer?.full_name}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[#64748B]">
                    Receipt &amp; Delivery Email
                  </p>
                  <p className="font-semibold text-[#1F2937] mt-0.5">{customer?.email}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[#64748B]">
                    Phone Number
                  </p>
                  <p className="font-mono text-[#1F2937] mt-0.5">
                    {customer?.phone_number || 'Not provided'}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[#64748B]">
                    Fulfillment Method
                  </p>
                  <p className="text-emerald-700 font-semibold mt-0.5">
                    Instant Signed Digital Download
                  </p>
                </div>
              </div>

              <label className="pt-2 flex items-center gap-2 text-xs text-[#243247] cursor-pointer">
                <input
                  type="checkbox"
                  checked={billingConfirmed}
                  onChange={(e) => {
                    setBillingConfirmed(e.target.checked);
                    if (e.target.checked && stage < 2) setStage(2);
                  }}
                  className="accent-[#FF6B0A]"
                />
                <span>
                  I confirm my account billing details for invoice generation and digital delivery.
                </span>
              </label>
            </section>

            {/* Active Checkout Session Status Card */}
            {checkoutSession && (
              <section className="dv-card-warm p-6 space-y-4 bg-[#FFF6ED]/50">
                <div className="flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wider text-[#D94300] font-semibold">
                    Payment Session Initialized
                  </span>
                  <span className="font-mono text-xs rounded-lg bg-[#FFE9D6] text-[#D94300] px-2.5 py-1 font-semibold">
                    {checkoutSession.order_number}
                  </span>
                </div>
                <p className="text-xs text-[#64748B] leading-relaxed">
                  Gateway Reference:{' '}
                  <strong className="font-mono text-[#1F2937]">
                    {checkoutSession.payment.gateway_order_id}
                  </strong>{' '}
                  ({checkoutSession.payment.gateway_name.toUpperCase()}). Your shopping cart remains
                  intact until payment is cryptographically verified by the backend.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={processing}
                    onClick={handleRefreshOrderStatus}
                  >
                    <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
                    <span>Check Payment / Webhook Status</span>
                  </Button>
                  <Link
                    to={`/orders/${checkoutSession.order_id}`}
                    className="text-xs font-semibold text-[#FF6B0A] hover:text-[#D94300] underline"
                  >
                    View Pending Order Details →
                  </Link>
                </div>
              </section>
            )}
          </div>

          {/* Right Column: Payment Summary & Initialization */}
          <aside className="lg:col-span-5 dv-card-warm p-6 space-y-5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#1F2937] border-b border-[#E5E7EB] pb-3">
              <Lock className="w-3.5 h-3.5 text-[#FF6B0A]" aria-hidden="true" />
              <span>Payment Summary</span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between text-[#64748B]">
                <span>Subtotal</span>
                <span className="font-mono font-medium text-[#1F2937]">
                  {formatINR(checkoutSession?.subtotal_amount ?? cart?.subtotal)}
                </span>
              </div>
              <div className="flex justify-between text-emerald-700">
                <span>Promotional Discount</span>
                <span className="font-mono">
                  -{formatINR(checkoutSession?.discount_amount ?? cart?.total_discount)}
                </span>
              </div>
              <div className="pt-3 border-t border-[#E5E7EB] flex justify-between items-baseline text-sm font-semibold text-[#1F2937]">
                <span>Total Payable</span>
                <span className="font-mono text-xl font-bold text-[#F4510B]">
                  {formatINR(checkoutSession?.total_amount ?? cart?.final_payable_amount)}
                </span>
              </div>
            </div>

            <button
              type="button"
              disabled={processing || !billingConfirmed}
              onClick={handleInitializeCheckout}
              className="dv-btn-primary w-full py-3.5 px-4 text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-2 disabled:opacity-45"
            >
              <span>
                {processing
                  ? 'Processing Payment Gateway...'
                  : checkoutSession
                  ? 'Retry Secure Payment'
                  : 'Initialize Secure Payment'}
              </span>
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </button>

            <div className="flex items-start gap-2 text-[11px] text-[#64748B] leading-relaxed">
              <ShieldCheck
                className="w-4 h-4 text-[#FF6B0A] shrink-0 mt-0.5"
                aria-hidden="true"
              />
              <span>
                Idempotency protection prevents duplicate orders during retries. Digital downloads
                unlock only after server-side signature verification.
              </span>
            </div>
          </aside>
        </div>
      )}
    </StorefrontLayout>
  );
};

export default CheckoutPage;
