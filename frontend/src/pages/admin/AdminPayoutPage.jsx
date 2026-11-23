import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Landmark,
  ReceiptText,
  RefreshCw,
  Search,
  ShieldCheck,
  WalletCards,
  XCircle,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  Badge,
  ConfirmDialog,
  ErrorAlert,
  LoadingState,
  Pagination,
  ToastBanner,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import {
  adminPayoutAccountApi,
  adminPayoutApi,
} from '../../services/api';

const PAGE_SIZE = 20;

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'requests', label: 'Payout Requests' },
  { id: 'reconciliation', label: 'Reconciliation' },
  { id: 'verification', label: 'Account Verification' },
  { id: 'reports', label: 'Financial Reports' },
];

const statusVariant = {
  requested: 'warning',
  under_review: 'warning',
  approved: 'accent',
  processing: 'accent',
  completed: 'success',
  rejected: 'danger',
  failed: 'danger',
  cancelled: 'neutral',
  uncertain: 'danger',
  pending: 'warning',
  verified: 'success',
};

const classificationVariant = {
  consistent: 'success',
  pending: 'warning',
  uncertain: 'danger',
  failed: 'danger',
  settlement_missing: 'danger',
  unexpected_settlement: 'danger',
  duplicate_settlement: 'danger',
  ledger_mismatch: 'danger',
  status_mismatch: 'danger',
  requires_manual_review: 'warning',
};

const AdminPayoutPage = () => {
  const [tab, setTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);

  const [payouts, setPayouts] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [report, setReport] = useState(null);
  const [reconciliationSummary, setReconciliationSummary] = useState(null);
  const [reconciliation, setReconciliation] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [accounts, setAccounts] = useState({ items: [], total: 0, page: 1, total_pages: 1 });

  const [statusFilter, setStatusFilter] = useState('');
  const [sellerFilter, setSellerFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [classificationFilter, setClassificationFilter] = useState('');
  const [unresolvedOnly, setUnresolvedOnly] = useState(false);
  const [accountStatusFilter, setAccountStatusFilter] = useState('');
  const [accountTypeFilter, setAccountTypeFilter] = useState('');

  const [selectedPayout, setSelectedPayout] = useState(null);
  const [payoutDetail, setPayoutDetail] = useState(null);
  const [reconciliationDetail, setReconciliationDetail] = useState(null);
  const [attempts, setAttempts] = useState([]);
  const [resolutionTarget, setResolutionTarget] = useState(null);
  const [resolutionAction, setResolutionAction] = useState('investigate');
  const [resolutionReason, setResolutionReason] = useState('');
  const [evidenceReference, setEvidenceReference] = useState('');
  const [rejectTarget, setRejectTarget] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [approveTarget, setApproveTarget] = useState(null);
  const [accountRejectTarget, setAccountRejectTarget] = useState(null);
  const [accountRejectReason, setAccountRejectReason] = useState('');

  const loadOverview = async () => {
    setLoading(true);
    setError('');
    try {
      const [payoutReport, reconciliationReport] = await Promise.all([
        adminPayoutApi.getReport(),
        adminPayoutApi.getReconciliationSummary(),
      ]);
      setReport(payoutReport);
      setReconciliationSummary(reconciliationReport);
    } catch (err) {
      setError(errorDetail(err, 'Failed to load payout operations overview.'));
    } finally {
      setLoading(false);
    }
  };

  const loadRequests = async (params = {}) => {
    setLoading(true);
    setError('');
    try {
      const data = await adminPayoutApi.listRequests({
        page: params.page || payouts.page,
        page_size: PAGE_SIZE,
        status: statusFilter || undefined,
        seller_id: sellerFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setPayouts(data);
    } catch (err) {
      setError(errorDetail(err, 'Failed to load payout requests.'));
    } finally {
      setLoading(false);
    }
  };

  const loadReconciliation = async (params = {}) => {
    setLoading(true);
    setError('');
    try {
      const data = await adminPayoutApi.listReconciliation({
        page: params.page || reconciliation.page,
        page_size: PAGE_SIZE,
        classification: classificationFilter || undefined,
        seller_id: sellerFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        unresolved_only: unresolvedOnly,
      });
      setReconciliation(data);
    } catch (err) {
      setError(errorDetail(err, 'Failed to load reconciliation records.'));
    } finally {
      setLoading(false);
    }
  };

  const loadAccounts = async (params = {}) => {
    setLoading(true);
    setError('');
    try {
      const data = await adminPayoutAccountApi.listVerification({
        page: params.page || accounts.page,
        page_size: PAGE_SIZE,
        status: accountStatusFilter || undefined,
        account_type: accountTypeFilter || undefined,
      });
      setAccounts(data);
    } catch (err) {
      setError(errorDetail(err, 'Failed to load payout account verification.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === 'overview') loadOverview();
    if (tab === 'requests') loadRequests();
    if (tab === 'reconciliation') loadReconciliation();
    if (tab === 'verification') loadAccounts();
    if (tab === 'reports') loadOverview();
  }, [tab]);

  const refreshTab = () => {
    if (tab === 'overview' || tab === 'reports') loadOverview();
    if (tab === 'requests') loadRequests();
    if (tab === 'reconciliation') loadReconciliation();
    if (tab === 'verification') loadAccounts();
  };

  const openPayoutDetail = async (payout) => {
    setSelectedPayout(payout);
    setLoading(true);
    setError('');
    try {
      const [detail, reconciliationDetail, attemptData] = await Promise.all([
        adminPayoutApi.getDetail(payout.id),
        adminPayoutApi.getReconciliationDetail(payout.id),
        adminPayoutApi.listAttempts(payout.id),
      ]);
      setPayoutDetail(detail);
      setReconciliationDetail(reconciliationDetail);
      setAttempts(attemptData);
    } catch (err) {
      setError(errorDetail(err, 'Failed to load payout detail.'));
    } finally {
      setLoading(false);
    }
  };

  const reviewRequest = async (payoutId) => {
    setSaving(true);
    try {
      await adminPayoutApi.reviewRequest(payoutId, { action: 'under_review' });
      setToast({ type: 'success', message: 'Payout moved under review.' });
      await loadRequests();
    } catch (err) {
      setError(errorDetail(err, 'Failed to move payout under review.'));
    } finally {
      setSaving(false);
    }
  };

  const approveRequest = async () => {
    if (!approveTarget) return;
    setSaving(true);
    try {
      await adminPayoutApi.approveRequest(approveTarget.id, { reason: 'Approved by administrator' });
      setApproveTarget(null);
      setToast({ type: 'success', message: 'Payout approved. Funds have not been transferred.' });
      await loadRequests();
    } catch (err) {
      setError(errorDetail(err, 'Failed to approve payout.'));
    } finally {
      setSaving(false);
    }
  };

  const rejectRequest = async () => {
    if (!rejectTarget || rejectReason.trim().length < 3) return;
    setSaving(true);
    try {
      await adminPayoutApi.rejectRequest(rejectTarget.id, { reason: rejectReason.trim() });
      setRejectTarget(null);
      setRejectReason('');
      setToast({ type: 'success', message: 'Payout rejected and reservation released.' });
      await loadRequests();
    } catch (err) {
      setError(errorDetail(err, 'Failed to reject payout.'));
    } finally {
      setSaving(false);
    }
  };

  const executeRequest = async (payoutId, scenario = 'success') => {
    setSaving(true);
    try {
      await adminPayoutApi.executeRequest(payoutId, { scenario });
      setToast({ type: 'success', message: 'Simulated execution result recorded. No real money was transferred.' });
      await openPayoutDetail({ id: payoutId });
      await loadReconciliation();
    } catch (err) {
      setError(errorDetail(err, 'Failed to execute simulated payout action.'));
    } finally {
      setSaving(false);
    }
  };

  const retryRequest = async (payoutId) => {
    setSaving(true);
    try {
      await adminPayoutApi.retryRequest(payoutId, { scenario: 'success' });
      setToast({ type: 'success', message: 'Retry attempt recorded as simulated. No real money was transferred.' });
      await openPayoutDetail({ id: payoutId });
    } catch (err) {
      setError(errorDetail(err, 'Failed to retry payout.'));
    } finally {
      setSaving(false);
    }
  };

  const resolveReconciliation = async () => {
    if (!resolutionTarget || resolutionReason.trim().length < 3) return;
    setSaving(true);
    try {
      await adminPayoutApi.resolveReconciliation(resolutionTarget.payout_id, {
        resolution_action: resolutionAction,
        resolution_reason: resolutionReason.trim(),
        evidence_reference: evidenceReference.trim() || undefined,
        expected_classification: resolutionTarget.classification,
      });
      setResolutionTarget(null);
      setResolutionReason('');
      setEvidenceReference('');
      setToast({ type: 'success', message: 'Reconciliation resolution recorded.' });
      await loadReconciliation();
      if (selectedPayout) await openPayoutDetail(selectedPayout);
    } catch (err) {
      setError(errorDetail(err, 'Failed to record reconciliation resolution.'));
    } finally {
      setSaving(false);
    }
  };

  const approveAccount = async (accountId) => {
    setSaving(true);
    try {
      await adminPayoutAccountApi.approveAccount(accountId, {});
      setToast({ type: 'success', message: 'Payout account approved for manual administrator review.' });
      await loadAccounts();
    } catch (err) {
      setError(errorDetail(err, 'Failed to approve payout account.'));
    } finally {
      setSaving(false);
    }
  };

  const rejectAccount = async () => {
    if (!accountRejectTarget || accountRejectReason.trim().length < 3) return;
    setSaving(true);
    try {
      await adminPayoutAccountApi.rejectAccount(accountRejectTarget.id, {
        reason: accountRejectReason.trim(),
      });
      setAccountRejectTarget(null);
      setAccountRejectReason('');
      setToast({ type: 'success', message: 'Payout account rejected.' });
      await loadAccounts();
    } catch (err) {
      setError(errorDetail(err, 'Failed to reject payout account.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout
      title="Payout Management"
      subtitle="Requests, simulated execution, reconciliation and payout account verification"
      actions={
        <button type="button" onClick={refreshTab} className="dv-btn-secondary text-xs px-3.5 py-2.5 inline-flex items-center gap-2">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      }
    >
      {error && <ErrorAlert message={error} onRetry={refreshTab} />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-6" />

      <nav aria-label="Payout operations sections" className="flex gap-2 overflow-x-auto mb-6">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`shrink-0 px-4 py-2.5 rounded-xl border text-xs font-semibold transition ${
              tab === item.id
                ? 'bg-[#18243A] border-[#BFDBFE] text-[#93C5FD]'
                : 'bg-[#111C30] border-[#E5E7EB] text-[#94A3B8] hover:border-[#93C5FD]'
            }`}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {tab === 'overview' && (
        <OverviewTab report={report} reconciliationSummary={reconciliationSummary} loading={loading} />
      )}

      {tab === 'requests' && (
        <RequestsTab
          payouts={payouts}
          loading={loading}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          sellerFilter={sellerFilter}
          setSellerFilter={setSellerFilter}
          dateFrom={dateFrom}
          setDateFrom={setDateFrom}
          dateTo={dateTo}
          setDateTo={setDateTo}
          applyFilters={() => loadRequests({ page: 1 })}
          changePage={(page) => loadRequests({ page })}
          openDetail={openPayoutDetail}
          reviewRequest={reviewRequest}
          setApproveTarget={setApproveTarget}
          setRejectTarget={(p) => { setRejectTarget(p); setRejectReason(''); }}
          saving={saving}
        />
      )}

      {tab === 'reconciliation' && (
        <ReconciliationTab
          reconciliation={reconciliation}
          loading={loading}
          classificationFilter={classificationFilter}
          setClassificationFilter={setClassificationFilter}
          unresolvedOnly={unresolvedOnly}
          setUnresolvedOnly={setUnresolvedOnly}
          sellerFilter={sellerFilter}
          setSellerFilter={setSellerFilter}
          applyFilters={() => loadReconciliation({ page: 1 })}
          changePage={(page) => loadReconciliation({ page })}
          openPayout={openPayoutDetail}
        />
      )}

      {tab === 'verification' && (
        <VerificationTab
          accounts={accounts}
          loading={loading}
          statusFilter={accountStatusFilter}
          setStatusFilter={setAccountStatusFilter}
          accountTypeFilter={accountTypeFilter}
          setAccountTypeFilter={setAccountTypeFilter}
          applyFilters={() => loadAccounts({ page: 1 })}
          changePage={(page) => loadAccounts({ page })}
          approveAccount={approveAccount}
          setRejectTarget={(account) => { setAccountRejectTarget(account); setAccountRejectReason(''); }}
          saving={saving}
          adminPayoutAccountApi={adminPayoutAccountApi}
        />
      )}

      {tab === 'reports' && (
        <ReportsTab
          report={report}
          reconciliationSummary={reconciliationSummary}
        />
      )}

      {selectedPayout && (
        <PayoutDetailDrawer
          payoutDetail={payoutDetail}
          reconciliationDetail={reconciliationDetail}
          attempts={attempts}
          selectedPayout={selectedPayout}
          saving={saving}
          onClose={() => { setSelectedPayout(null); setPayoutDetail(null); setReconciliationDetail(null); }}
          onResolve={(detail) => {
            setResolutionTarget({
              payout_id: selectedPayout.id,
              classification: detail?.classification,
            });
            setResolutionAction('investigate');
            setResolutionReason('');
            setEvidenceReference('');
          }}
          onExecute={executeRequest}
          onRetry={retryRequest}
        />
      )}

      <ConfirmDialog
        open={Boolean(approveTarget)}
        title="Approve payout request?"
        description="Approval does not execute or confirm a money transfer."
        confirmLabel="Approve"
        cancelLabel="Cancel"
        variant="primary"
        onConfirm={approveRequest}
        onCancel={() => setApproveTarget(null)}
      />

      {rejectTarget && (
        <div role="dialog" aria-modal="true" aria-labelledby="reject-payout-title" className="fixed inset-0 z-50 bg-[#080D19]/70 backdrop-blur-[2px] flex items-center justify-center p-4">
          <div className="bg-[#111C30] border border-red-200 rounded-2xl max-w-md w-full p-6 space-y-4">
            <h3 id="reject-payout-title" className="text-base font-semibold">Reject payout request</h3>
            <label htmlFor="payout-reject-reason" className="block text-xs font-medium text-[#94A3B8]">Mandatory rejection reason</label>
            <textarea id="payout-reject-reason" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} maxLength={2000} rows={4} className="dv-input px-3 py-2.5 text-sm w-full" />
            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setRejectTarget(null)} className="dv-btn-secondary text-xs px-4 py-2.5">Cancel</button>
              <button type="button" disabled={saving || rejectReason.trim().length < 3} onClick={rejectRequest} className="text-xs px-4 py-2.5 rounded-xl border border-red-200 bg-red-950/50 text-red-300 disabled:opacity-50">Reject payout</button>
            </div>
          </div>
        </div>
      )}

      {accountRejectTarget && (
        <div role="dialog" aria-modal="true" aria-labelledby="reject-account-title" className="fixed inset-0 z-50 bg-[#080D19]/70 backdrop-blur-[2px] flex items-center justify-center p-4">
          <div className="bg-[#111C30] border border-red-200 rounded-2xl max-w-md w-full p-6 space-y-4">
            <h3 id="reject-account-title" className="text-base font-semibold">Reject payout account</h3>
            <label htmlFor="account-reject-reason" className="block text-xs font-medium text-[#94A3B8]">Mandatory rejection reason</label>
            <textarea id="account-reject-reason" value={accountRejectReason} onChange={(e) => setAccountRejectReason(e.target.value)} maxLength={2000} rows={4} className="dv-input px-3 py-2.5 text-sm w-full" />
            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setAccountRejectTarget(null)} className="dv-btn-secondary text-xs px-4 py-2.5">Cancel</button>
              <button type="button" disabled={saving || accountRejectReason.trim().length < 3} onClick={rejectAccount} className="text-xs px-4 py-2.5 rounded-xl border border-red-200 bg-red-950/50 text-red-300 disabled:opacity-50">Reject account</button>
            </div>
          </div>
        </div>
      )}

      {resolutionTarget && (
        <div role="dialog" aria-modal="true" aria-labelledby="resolution-title" className="fixed inset-0 z-50 bg-[#080D19]/70 backdrop-blur-[2px] flex items-center justify-center p-4">
          <div className="bg-[#111C30] border border-[#BFDBFE] rounded-2xl max-w-lg w-full p-6 space-y-4">
            <h3 id="resolution-title" className="text-base font-semibold">Record reconciliation resolution</h3>
            <p className="text-xs text-[#94A3B8]">Current classification: <strong>{resolutionTarget.classification}</strong>. This records an administrative action only; it does not post or repair accounting entries.</p>
            <div>
              <label htmlFor="resolution-action" className="block text-xs font-medium text-[#94A3B8] mb-1.5">Resolution action</label>
              <select id="resolution-action" value={resolutionAction} onChange={(e) => setResolutionAction(e.target.value)} className="dv-input px-3 py-2.5 text-sm w-full">
                <option value="investigate">Investigate</option>
                <option value="confirm_evidence">Confirm evidence</option>
                <option value="keep_pending">Keep pending</option>
                <option value="mark_resolved">Mark resolved</option>
              </select>
            </div>
            <div>
              <label htmlFor="resolution-reason" className="block text-xs font-medium text-[#94A3B8] mb-1.5">Mandatory reason</label>
              <textarea id="resolution-reason" value={resolutionReason} onChange={(e) => setResolutionReason(e.target.value)} maxLength={5000} rows={4} className="dv-input px-3 py-2.5 text-sm w-full" />
            </div>
            <div>
              <label htmlFor="resolution-evidence" className="block text-xs font-medium text-[#94A3B8] mb-1.5">Evidence reference (optional)</label>
              <input id="resolution-evidence" value={evidenceReference} onChange={(e) => setEvidenceReference(e.target.value)} maxLength={255} className="dv-input px-3 py-2.5 text-sm w-full" />
            </div>
            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setResolutionTarget(null)} className="dv-btn-secondary text-xs px-4 py-2.5">Cancel</button>
              <button type="button" disabled={saving || resolutionReason.trim().length < 3} onClick={resolveReconciliation} className="dv-btn-primary text-xs px-4 py-2.5">{saving ? 'Saving...' : 'Record resolution'}</button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
};

function errorDetail(err, fallback) {
  const detail = err.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

const OverviewTab = ({ report, reconciliationSummary, loading }) => {
  if (loading && !report && !reconciliationSummary) return <LoadingState label="Loading financial operations..." />;
  const cards = [
    ['Total requests', reconciliationSummary?.total_payout_requests ?? report?.total_requests ?? 0, WalletCards],
    ['Requested amount', reconciliationSummary?.total_requested_amount ?? report?.total_requested_amount ?? 0, Landmark],
    ['Approved amount', reconciliationSummary?.approved_amount ?? report?.approved_amount ?? 0, CheckCircle2],
    ['Processing amount', reconciliationSummary?.processing_amount ?? report?.processing_amount ?? 0, Clock3],
    ['Completed payout', reconciliationSummary?.completed_amount ?? report?.settled_amount ?? 0, ReceiptText],
    ['Failed payout', reconciliationSummary?.failed_amount ?? report?.failed_amount ?? 0, XCircle],
    ['Settled ledger amount', reconciliationSummary?.settled_amount ?? 0, ShieldCheck],
    ['Reserved amount', reconciliationSummary?.reserved_amount ?? 0, WalletCards],
    ['Outstanding debt', reconciliationSummary?.outstanding_seller_debt ?? 0, AlertTriangle],
    ['Unresolved exceptions', reconciliationSummary?.unresolved_discrepancy_count ?? 0, AlertTriangle],
  ];
  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
      {cards.map(([label, value, Icon]) => (
        <div key={label} className="dv-card p-5">
          <p className="text-[12px] font-medium text-[#94A3B8] flex justify-between gap-2">
            {label}<Icon className="w-4 h-4 text-[#60A5FA]" />
          </p>
          {typeof value === 'number' && label === 'Unresolved exceptions'
            ? <p className="text-2xl font-bold text-[#F1F5F9] mt-2">{value}</p>
            : typeof value === 'number' && label === 'Total requests'
              ? <p className="text-2xl font-bold text-[#F1F5F9] mt-2">{value}</p>
              : <p className="text-xl font-bold font-mono text-[#93C5FD] mt-2">{formatINR(value)}</p>}
        </div>
      ))}
    </section>
  );
};

const RequestsTab = ({
  payouts,
  loading,
  statusFilter,
  setStatusFilter,
  sellerFilter,
  setSellerFilter,
  dateFrom,
  setDateFrom,
  dateTo,
  setDateTo,
  applyFilters,
  changePage,
  openDetail,
  reviewRequest,
  setApproveTarget,
  setRejectTarget,
  saving,
}) => (
  <>
    <section className="dv-card p-5 mb-6">
      <h2 className="text-sm font-bold mb-4 flex items-center gap-2"><Search className="w-4 h-4 text-[#60A5FA]" />Payout filters</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <select aria-label="Payout status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="dv-input px-3 py-2.5 text-xs">
          <option value="">All statuses</option>
          {['requested','under_review','approved','processing','completed','rejected','failed','cancelled','uncertain'].map((status) => <option key={status} value={status}>{status}</option>)}
        </select>
        <input aria-label="Seller filter" value={sellerFilter} onChange={(e) => setSellerFilter(e.target.value)} placeholder="Seller UUID" className="dv-input px-3 py-2.5 text-xs" />
        <input aria-label="Payout date from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="dv-input px-3 py-2.5 text-xs" />
        <input aria-label="Payout date to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="dv-input px-3 py-2.5 text-xs" />
      </div>
      <button type="button" onClick={applyFilters} className="dv-btn-primary text-xs px-4 py-2.5 mt-3">Apply filters</button>
    </section>
    <section className="dv-card overflow-hidden">
      {loading ? <LoadingState label="Loading payout requests..." /> : !payouts.items.length ? (
        <p className="p-8 text-center text-xs text-[#94A3B8]">No payout requests match the filters.</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead><tr className="bg-[#18243A] text-[#94A3B8] border-b border-[#E5E7EB]">
                <th className="px-4 py-3">Reference</th><th className="px-4 py-3">Seller</th><th className="px-4 py-3">Destination</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Actions</th>
              </tr></thead>
              <tbody className="divide-y divide-[#E5E7EB]">{payouts.items.map((payout) => (
                <tr key={payout.id} className="hover:bg-[#18243A]">
                  <td className="px-4 py-3"><button type="button" onClick={() => openDetail(payout)} className="font-mono text-[#93C5FD] hover:underline">{payout.id}</button></td>
                  <td className="px-4 py-3 font-mono">{payout.seller_id}</td>
                  <td className="px-4 py-3">{payout.destination_masked_snapshot}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold">{formatINR(payout.amount)}</td>
                  <td className="px-4 py-3"><Badge variant={statusVariant[payout.status] || 'neutral'}>{payout.status}</Badge></td>
                  <td className="px-4 py-3"><div className="flex justify-end gap-2">
                    {payout.status === 'requested' && <button type="button" disabled={saving} onClick={() => reviewRequest(payout.id)} className="dv-btn-secondary text-[11px] px-3 py-1.5">Review</button>}
                    {['requested','under_review'].includes(payout.status) && <>
                      <button type="button" disabled={saving} onClick={() => setApproveTarget(payout)} className="dv-btn-primary text-[11px] px-3 py-1.5">Approve</button>
                      <button type="button" disabled={saving} onClick={() => setRejectTarget(payout)} className="text-[11px] px-3 py-1.5 rounded-xl border border-red-200 text-red-300">Reject</button>
                    </>}
                  </div></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="px-5"><Pagination page={payouts.page} totalPages={payouts.total_pages} totalItems={payouts.total} itemLabel="payout requests" onPageChange={changePage} /></div>
        </>
      )}
    </section>
  </>
);

const ReconciliationTab = ({
  reconciliation,
  loading,
  classificationFilter,
  setClassificationFilter,
  unresolvedOnly,
  setUnresolvedOnly,
  sellerFilter,
  setSellerFilter,
  applyFilters,
  changePage,
  openPayout,
}) => {
  const classifications = ['consistent','pending','uncertain','failed','settlement_missing','unexpected_settlement','duplicate_settlement','ledger_mismatch','status_mismatch','requires_manual_review'];
  return (
    <>
      <section className="dv-card p-5 mb-6">
        <h2 className="text-sm font-bold mb-4">Reconciliation filters</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <select aria-label="Reconciliation classification" value={classificationFilter} onChange={(e) => setClassificationFilter(e.target.value)} className="dv-input px-3 py-2.5 text-xs">
            <option value="">All classifications</option>
            {classifications.map((classification) => <option key={classification} value={classification}>{classification}</option>)}
          </select>
          <input aria-label="Reconciliation seller" value={sellerFilter} onChange={(e) => setSellerFilter(e.target.value)} placeholder="Seller UUID" className="dv-input px-3 py-2.5 text-xs" />
          <label className="flex items-center gap-2 text-xs text-[#94A3B8]"><input type="checkbox" checked={unresolvedOnly} onChange={(e) => setUnresolvedOnly(e.target.checked)} /> Unresolved only</label>
        </div>
        <button type="button" onClick={applyFilters} className="dv-btn-primary text-xs px-4 py-2.5 mt-3">Apply filters</button>
      </section>
      <section className="dv-card overflow-hidden">
        {loading ? <LoadingState label="Loading reconciliation queue..." /> : !reconciliation.items.length ? (
          <p className="p-8 text-center text-xs text-[#94A3B8]">No reconciliation records match the filters.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead><tr className="bg-[#18243A] text-[#94A3B8] border-b border-[#E5E7EB]"><th className="px-4 py-3">Payout</th><th className="px-4 py-3">Primary classification</th><th className="px-4 py-3">Secondary issues</th><th className="px-4 py-3">Execution</th><th className="px-4 py-3">Settlement</th></tr></thead>
                <tbody className="divide-y divide-[#E5E7EB]">{reconciliation.items.map((item) => (
                  <tr key={item.payout_id} className="hover:bg-[#18243A]">
                    <td className="px-4 py-3"><button type="button" onClick={() => openPayout({ id: item.payout_id })} className="font-mono text-[#93C5FD] hover:underline">{item.payout_id}</button></td>
                    <td className="px-4 py-3"><Badge variant={classificationVariant[item.classification] || 'neutral'}>{item.classification}</Badge></td>
                    <td className="px-4 py-3 text-[#94A3B8]">{item.secondary_issues?.length ? item.secondary_issues.join(', ') : 'None'}</td>
                    <td className="px-4 py-3">{item.latest_attempt?.status || item.payout_status}</td>
                    <td className="px-4 py-3">{item.settlement_count > 0 ? 'Settlement found' : 'No settlement'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <div className="px-5"><Pagination page={reconciliation.page} totalPages={reconciliation.total_pages} totalItems={reconciliation.total} itemLabel="reconciliation records" onPageChange={changePage} /></div>
          </>
        )}
      </section>
    </>
  );
};

const VerificationTab = ({
  accounts,
  loading,
  statusFilter,
  setStatusFilter,
  accountTypeFilter,
  setAccountTypeFilter,
  applyFilters,
  changePage,
  approveAccount,
  setRejectTarget,
  saving,
  adminPayoutAccountApi,
}) => {
  const [historyAccount, setHistoryAccount] = useState(null);
  const [history, setHistory] = useState([]);
  const openHistory = async (account) => {
    setHistoryAccount(account);
    try {
      const data = await adminPayoutAccountApi.getHistory(account.id, { page: 1, page_size: 20 });
      setHistory(data.items || []);
    } catch {
      setHistory([]);
    }
  };
  return (
    <>
      <section className="dv-card p-5 mb-6">
        <h2 className="text-sm font-bold mb-4">Payout account verification</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <select aria-label="Verification status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="dv-input px-3 py-2.5 text-xs">
            <option value="">All statuses</option><option value="pending">Pending</option><option value="verified">Verified</option><option value="rejected">Rejected</option>
          </select>
          <select aria-label="Account type" value={accountTypeFilter} onChange={(e) => setAccountTypeFilter(e.target.value)} className="dv-input px-3 py-2.5 text-xs">
            <option value="">All account types</option><option value="upi">UPI</option><option value="bank">Bank</option>
          </select>
        </div>
        <button type="button" onClick={applyFilters} className="dv-btn-primary text-xs px-4 py-2.5 mt-3">Apply filters</button>
      </section>
      <section className="dv-card overflow-hidden">
        {loading ? <LoadingState label="Loading payout accounts..." /> : !accounts.items.length ? <p className="p-8 text-center text-xs text-[#94A3B8]">No payout accounts match the filters.</p> : (
          <>
            <div className="overflow-x-auto"><table className="w-full text-xs text-left"><thead><tr className="bg-[#18243A] text-[#94A3B8] border-b border-[#E5E7EB]"><th className="px-4 py-3">Seller</th><th className="px-4 py-3">Account</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Actions</th></tr></thead><tbody className="divide-y divide-[#E5E7EB]">{accounts.items.map((account) => (
              <tr key={account.id} className="hover:bg-[#18243A]">
                <td className="px-4 py-3"><p className="font-semibold">{account.store_name || 'Unknown seller'}</p><p className="font-mono text-[10px] text-[#94A3B8]">{account.seller_id}</p></td>
                <td className="px-4 py-3"><p>{account.display_name}</p><p className="text-[#94A3B8]">{account.masked_identifier}</p></td>
                <td className="px-4 py-3 font-medium text-[#F1F5F9]">{String(account.account_type || '').toUpperCase()}</td>
                <td className="px-4 py-3"><Badge variant={statusVariant[account.verification_status] || 'neutral'}>{account.verification_status}</Badge>{account.verification_reason && <p className="text-[10px] text-red-300 mt-1">{account.verification_reason}</p>}</td>
                <td className="px-4 py-3"><div className="flex justify-end gap-2">
                  <button type="button" onClick={() => openHistory(account)} className="dv-btn-secondary text-[11px] px-3 py-1.5">History</button>
                  {account.verification_status !== 'verified' && <button type="button" disabled={saving} onClick={() => approveAccount(account.id)} className="dv-btn-primary text-[11px] px-3 py-1.5">Approve</button>}
                  {account.verification_status !== 'rejected' && <button type="button" disabled={saving} onClick={() => setRejectTarget(account)} className="text-[11px] px-3 py-1.5 rounded-xl border border-red-200 text-red-300">Reject</button>}
                </div></td>
              </tr>
            ))}</tbody></table></div>
            <div className="px-5"><Pagination page={accounts.page} totalPages={accounts.total_pages} totalItems={accounts.total} itemLabel="accounts" onPageChange={changePage} /></div>
          </>
        )}
      </section>
      {historyAccount && <div className="dv-card p-5 mt-6"><h3 className="text-sm font-bold mb-3">Verification history: {historyAccount.masked_identifier}</h3>{history.length ? <div className="space-y-2">{history.map((row) => <div key={row.id} className="border border-[#E5E7EB] rounded-xl p-3 text-xs"><p><strong>{row.previous_status}</strong> → <strong>{row.new_status}</strong></p>{row.rejection_reason && <p className="text-red-300 mt-1">{row.rejection_reason}</p>}<p className="text-[#94A3B8] mt-1">{new Date(row.created_at).toLocaleString()}</p></div>)}</div> : <p className="text-xs text-[#94A3B8]">No verification history.</p>}</div>}
    </>
  );
};

const ReportsTab = ({ report, reconciliationSummary }) => {
  const rows = [
    ['Total requested', reconciliationSummary?.total_requested_amount ?? report?.total_requested_amount],
    ['Approved', reconciliationSummary?.approved_amount ?? report?.approved_amount],
    ['Processing', reconciliationSummary?.processing_amount ?? report?.processing_amount],
    ['Completed', reconciliationSummary?.completed_amount],
    ['Failed', reconciliationSummary?.failed_amount ?? report?.failed_amount],
    ['Pending', reconciliationSummary?.pending_amount],
    ['Uncertain', reconciliationSummary?.uncertain_amount],
    ['Actual settled', reconciliationSummary?.settled_amount],
    ['Reserved', reconciliationSummary?.reserved_amount],
    ['Outstanding debt', reconciliationSummary?.outstanding_seller_debt],
  ];
  return (
    <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="dv-card p-5">
        <h2 className="text-sm font-bold mb-4">Financial report</h2>
        <div className="divide-y divide-[#E5E7EB]">{rows.map(([label, value]) => (
          <div key={label} className="py-3 flex justify-between gap-4 text-xs"><span className="text-[#94A3B8]">{label}</span><strong className="font-mono text-[#F1F5F9]">{value == null ? '-' : formatINR(value)}</strong></div>
        ))}</div>
      </div>
      <div className="dv-card p-5">
        <h2 className="text-sm font-bold mb-4">Reconciliation report</h2>
        <div className="space-y-3 text-xs">
          <div className="flex justify-between"><span className="text-[#94A3B8]">Exception count</span><strong>{reconciliationSummary?.reconciliation_exception_count ?? 0}</strong></div>
          <div className="flex justify-between"><span className="text-[#94A3B8]">Unresolved discrepancies</span><strong>{reconciliationSummary?.unresolved_discrepancy_count ?? 0}</strong></div>
        </div>
        {reconciliationSummary?.classification_counts && (
          <div className="mt-5 divide-y divide-[#E5E7EB]">{Object.entries(reconciliationSummary.classification_counts).map(([classification, count]) => (
            <div key={classification} className="py-2.5 flex justify-between gap-3 text-xs"><span>{classification}</span><strong>{count}</strong></div>
          ))}</div>
        )}
      </div>
    </section>
  );
};

const PayoutDetailDrawer = ({
  payoutDetail,
  reconciliationDetail,
  attempts,
  selectedPayout,
  saving,
  onClose,
  onResolve,
  onExecute,
  onRetry,
}) => {
  const payout = payoutDetail?.payout || selectedPayout;
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="payout-detail-title" className="fixed inset-0 z-50 bg-[#080D19]/70 backdrop-blur-[2px] flex justify-end">
      <div className="w-full max-w-2xl h-full overflow-y-auto bg-[#111C30] border-l border-[#E5E7EB] p-6">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div><p className="text-[12px] text-[#60A5FA] font-semibold">Payout detail</p><h2 id="payout-detail-title" className="text-[17px] font-semibold text-[#F1F5F9] mt-1 font-mono">{payout?.id}</h2></div>
          <button type="button" onClick={onClose} aria-label="Close payout detail" className="p-2 rounded-xl border border-[#E5E7EB]">×</button>
        </div>
        {!payoutDetail ? <LoadingState label="Loading payout detail..." /> : (
          <div className="space-y-6">
            <section className="dv-card p-5">
              <h3 className="text-sm font-bold mb-3">Payout information</h3>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div><dt className="text-[#94A3B8]">Seller</dt><dd className="font-mono mt-1">{payoutDetail.seller?.store_name || payoutDetail.seller?.id}</dd></div>
                <div><dt className="text-[#94A3B8]">Amount</dt><dd className="font-mono font-bold mt-1">{formatINR(payoutDetail.payout?.amount)}</dd></div>
                <div><dt className="text-[#94A3B8]">Masked destination</dt><dd className="mt-1">{payoutDetail.destination?.masked_identifier}</dd></div>
                <div><dt className="text-[#94A3B8]">Status</dt><dd className="mt-1"><Badge variant={statusVariant[payoutDetail.payout?.status] || 'neutral'}>{payoutDetail.payout?.status}</Badge></dd></div>
              </dl>
            </section>
            <section className="dv-card p-5">
              <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-bold">Execution timeline</h3>{payoutDetail.payout?.status === 'approved' && <div className="flex gap-2"><button type="button" disabled={saving} onClick={() => onExecute(payoutDetail.payout.id, 'success')} className="dv-btn-primary text-[11px] px-3 py-1.5">Simulate success</button><button type="button" disabled={saving} onClick={() => onExecute(payoutDetail.payout.id, 'failure')} className="dv-btn-secondary text-[11px] px-3 py-1.5">Simulate failure</button></div>}</div>
              {!attempts.length ? <p className="text-xs text-[#94A3B8]">No execution attempts.</p> : <div className="space-y-3">{attempts.map((attempt) => (
                <div key={attempt.id} className="border border-[#E5E7EB] rounded-xl p-3 text-xs">
                  <div className="flex justify-between gap-3"><strong>Attempt {attempt.attempt_no}</strong><Badge variant={attempt.outcome === 'success' ? 'success' : attempt.outcome === 'uncertain' ? 'warning' : attempt.outcome === 'failed' ? 'danger' : 'neutral'}>{attempt.outcome}</Badge></div>
                  <p className="text-[#94A3B8] mt-1">{attempt.simulated ? 'Simulated execution — no real transfer occurred.' : 'Provider-confirmed execution.'}</p>
                  {attempt.sanitized_error && <p className="text-red-300 mt-1">{attempt.sanitized_error}</p>}
                </div>
              ))}</div>}
              {payoutDetail.payout?.status === 'failed' && <button type="button" disabled={saving} onClick={() => onRetry(payoutDetail.payout.id)} className="dv-btn-secondary text-[11px] px-3 py-1.5 mt-3">Retry failed payout</button>}
            </section>
            <section className="dv-card p-5">
              <h3 className="text-sm font-bold mb-3">Reconciliation</h3>
              {reconciliationDetail ? <>
                <div className="flex items-center gap-2 mb-3"><Badge variant={classificationVariant[reconciliationDetail.classification] || 'neutral'}>{reconciliationDetail.classification}</Badge></div>
                {reconciliationDetail.secondary_issues?.length ? <ul className="list-disc pl-5 text-xs text-[#94A3B8] space-y-1">{reconciliationDetail.secondary_issues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : <p className="text-xs text-[#94A3B8]">No secondary reconciliation issues detected.</p>}
                {reconciliationDetail.settlement && <p className="text-xs mt-3">Settlement: <strong>{formatINR(reconciliationDetail.settlement.amount)}</strong> · {reconciliationDetail.settlement.mock_execution ? 'Simulated' : 'Provider execution'}</p>}
                <button type="button" onClick={() => onResolve(reconciliationDetail)} className="dv-btn-secondary text-xs px-4 py-2.5 mt-4">Record resolution</button>
              </> : <LoadingState label="Loading reconciliation..." />}
            </section>
            <section className="dv-card p-5">
              <h3 className="text-sm font-bold mb-3">Administrative audit</h3>
              {!payoutDetail.audit_history?.length ? <p className="text-xs text-[#94A3B8]">No audit entries.</p> : <div className="space-y-2">{payoutDetail.audit_history.map((row) => <div key={row.id} className="border border-[#E5E7EB] rounded-xl p-3 text-xs"><p className="font-mono text-[#93C5FD]">{row.action}</p><p className="text-[#94A3B8] mt-1">{new Date(row.created_at).toLocaleString()}</p></div>)}</div>}
            </section>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminPayoutPage;
