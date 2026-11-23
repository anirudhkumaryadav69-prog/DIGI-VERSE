import { useEffect, useState } from 'react';
import { Building2, IndianRupee, Landmark, Plus, WalletCards } from 'lucide-react';
import SellerLayout from '../../layouts/SellerLayout';
import {
  Badge,
  ConfirmDialog,
  ErrorAlert,
  Input,
  LoadingState,
  Pagination,
  ToastBanner,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import { sellerPayoutApi } from '../../services/api';

const PAGE_SIZE = 10;

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
};

const SellerPayoutPage = () => {
  const [balance, setBalance] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [requests, setRequests] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [accountForm, setAccountForm] = useState({
    account_type: 'upi',
    display_name: '',
    bank_name: '',
    masked_identifier: '',
  });
  const [withdrawal, setWithdrawal] = useState({ accountId: '', amount: '' });
  const [showAccountForm, setShowAccountForm] = useState(false);
  const [editingAccountId, setEditingAccountId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [cancelTarget, setCancelTarget] = useState(null);
  const [detailRequest, setDetailRequest] = useState(null);
  const [detailAttempts, setDetailAttempts] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadPage = (params = {}) => {
    setLoading(true);
    setError('');
    Promise.all([
      sellerPayoutApi.getBalance(),
      sellerPayoutApi.listAccounts(),
      sellerPayoutApi.listRequests({ page: params.page || requests.page, page_size: PAGE_SIZE }),
    ])
      .then(([balanceData, accountData, requestData]) => {
        setBalance(balanceData);
        setAccounts(accountData);
        setRequests(requestData);
        if (!withdrawal.accountId) {
          const defaultAccount = accountData.find((a) => a.is_default && a.is_active);
          if (defaultAccount) setWithdrawal((v) => ({ ...v, accountId: defaultAccount.id }));
        }
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load payout information.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPage();
  }, []);

  const addAccount = async (event) => {
    event.preventDefault();
    setSaving(true);
    setToast(null);
    try {
      const wasEditing = Boolean(editingAccountId);
      if (editingAccountId) {
        await sellerPayoutApi.updateAccount(editingAccountId, {
          display_name: accountForm.display_name,
          bank_name: accountForm.account_type === 'bank' ? accountForm.bank_name : undefined,
          masked_identifier: accountForm.masked_identifier,
        });
      } else {
        await sellerPayoutApi.createAccount({
          account_type: accountForm.account_type,
          display_name: accountForm.display_name,
          bank_name: accountForm.account_type === 'bank' ? accountForm.bank_name : undefined,
          masked_identifier: accountForm.masked_identifier,
          is_default: accounts.length === 0,
        });
      }
      setAccountForm({ account_type: 'upi', display_name: '', bank_name: '', masked_identifier: '' });
      setShowAccountForm(false);
      setEditingAccountId(null);
      setToast({
        type: 'success',
        message: wasEditing
          ? 'Payout account updated and requires re-verification.'
          : 'Payout account added. Verification is pending.',
      });
      loadPage();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to add payout account.');
    } finally {
      setSaving(false);
    }
  };

  const setDefault = async (accountId) => {
    setSaving(true);
    try {
      await sellerPayoutApi.setDefaultAccount(accountId);
      setToast({ type: 'success', message: 'Default payout account updated.' });
      loadPage();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update default account.');
    } finally {
      setSaving(false);
    }
  };

  const deactivateAccount = async (accountId) => {
    setSaving(true);
    try {
      await sellerPayoutApi.deactivateAccount(accountId);
      setToast({ type: 'success', message: 'Payout account deactivated.' });
      loadPage();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to deactivate payout account.');
    } finally {
      setSaving(false);
    }
  };

  const submitWithdrawal = async (event) => {
    event.preventDefault();
    setSaving(true);
    setToast(null);
    try {
      await sellerPayoutApi.createRequest({
        payout_account_id: withdrawal.accountId,
        amount: withdrawal.amount,
        idempotency_key: `seller-payout-ui-${crypto.randomUUID()}`,
      });
      setWithdrawal((v) => ({ ...v, amount: '' }));
      setToast({ type: 'success', message: 'Payout requested. No money has been transferred.' });
      loadPage();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to submit payout request.');
    } finally {
      setSaving(false);
    }
  };

  const cancelRequest = async () => {
    if (!cancelTarget) return;
    setSaving(true);
    try {
      await sellerPayoutApi.cancelRequest(cancelTarget.id, { reason: 'Cancelled by seller' });
      setCancelTarget(null);
      setToast({ type: 'success', message: 'Payout request cancelled and reserved funds released.' });
      loadPage();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to cancel payout request.');
    } finally {
      setSaving(false);
    }
  };

  const openPayoutDetail = async (request) => {
    setDetailRequest(request);
    setDetailLoading(true);
    try {
      const [detail, attempts] = await Promise.all([
        sellerPayoutApi.getRequest(request.id),
        sellerPayoutApi.getAttempts(request.id),
      ]);
      setDetailRequest(detail);
      setDetailAttempts(attempts);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to load payout detail.');
    } finally {
      setDetailLoading(false);
    }
  };

  if (loading && !balance) {
    return (
      <SellerLayout title="Payouts" subtitle="Seller settlement and payout requests">
        <LoadingState label="Loading payout balances..." />
      </SellerLayout>
    );
  }

  const activeAccounts = accounts.filter((account) => account.is_active);
  const verifiedAccounts = activeAccounts.filter((account) => account.verification_status === 'verified');

  return (
    <SellerLayout
      title="Payouts"
      subtitle="Withdraw eligible funds through an approved payout account"
      actions={
        <button type="button" onClick={() => { setEditingAccountId(null); setAccountForm({ account_type: 'upi', display_name: '', bank_name: '', masked_identifier: '' }); setShowAccountForm((v) => !v); }} className="dv-btn-secondary text-xs px-3.5 py-2.5 inline-flex items-center gap-2">
          <Plus className="w-3.5 h-3.5" /> Payout account
        </button>
      }
    >
      {error && <ErrorAlert message={error} onRetry={() => loadPage()} />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-6" />

      {balance && (
        <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4 mb-6">
          {[
            ['Signed payable', balance.seller_net_payable_signed, WalletCards],
            ['Outstanding debt', balance.debt_amount, Building2],
            ['Reserved payout', balance.reserved_amount, Landmark],
            ['Available withdrawal', balance.available_amount, IndianRupee],
            ['Settled payout', balance.total_settled, WalletCards],
          ].map(([label, value, Icon]) => (
            <div key={label} className="dv-card p-5">
              <p className="text-xs font-medium text-[#94A3B8] flex justify-between gap-2">
                {label}<Icon className="w-4 h-4 text-[#60A5FA]" aria-hidden="true" />
              </p>
              <p className={`text-xl font-bold font-mono mt-2 ${Number(value) < 0 ? 'text-red-300' : 'text-[#93C5FD]'}`}>
                {formatINR(value)}
              </p>
            </div>
          ))}
        </section>
      )}

      <div className="bg-[#18243A] border border-[#BFDBFE] rounded-xl p-4 mb-6 text-xs text-[#93C5FD]">
        Available withdrawal is calculated by the backend. Approval does not mean funds have been transferred. Live and mock payout execution are not enabled on this dashboard.
      </div>

      {showAccountForm && (
        <form onSubmit={addAccount} className="dv-card p-5 mb-6">
          <h2 className="text-sm font-bold mb-4">{editingAccountId ? 'Edit masked payout account' : 'Add masked payout account'}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="payout-account-type" className="block text-xs font-medium text-[#94A3B8] mb-1.5">Account type</label>
              <select id="payout-account-type" value={accountForm.account_type} onChange={(e) => setAccountForm((v) => ({ ...v, account_type: e.target.value }))} className="dv-input px-3 py-2.5 text-sm">
                <option value="upi">UPI</option>
                <option value="bank">Bank account</option>
              </select>
            </div>
            <Input id="payout-display-name" label="Account label" value={accountForm.display_name} onChange={(e) => setAccountForm((v) => ({ ...v, display_name: e.target.value }))} required />
            {accountForm.account_type === 'bank' && (
              <Input id="payout-bank-name" label="Bank name" value={accountForm.bank_name} onChange={(e) => setAccountForm((v) => ({ ...v, bank_name: e.target.value }))} required />
            )}
            <Input id="payout-masked-id" label={accountForm.account_type === 'upi' ? 'Masked UPI ID' : 'Masked account number'} value={accountForm.masked_identifier} onChange={(e) => setAccountForm((v) => ({ ...v, masked_identifier: e.target.value }))} required />
          </div>
          <div className="flex justify-end gap-3 mt-5">
            <button type="button" onClick={() => { setShowAccountForm(false); setEditingAccountId(null); setAccountForm({ account_type: 'upi', display_name: '', bank_name: '', masked_identifier: '' }); }} className="dv-btn-secondary text-xs px-4 py-2.5">Cancel</button>
            <button type="submit" disabled={saving} className="dv-btn-primary text-xs px-4 py-2.5">{saving ? 'Saving...' : 'Add account'}</button>
          </div>
        </form>
      )}

      <section className="dv-card overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-[#E5E7EB]"><h2 className="text-sm font-bold">Payout accounts</h2></div>
        {!accounts.length ? (
          <p className="p-8 text-center text-xs text-[#94A3B8]">No payout account has been added.</p>
        ) : (
          <div className="divide-y divide-[#E5E7EB]">
            {accounts.map((account) => (
              <div key={account.id} className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-[#F1F5F9]">{account.display_name}</p>
                    {account.is_default && <Badge variant="accent">Default</Badge>}
                    <Badge variant={account.verification_status === 'verified' ? 'success' : account.verification_status === 'rejected' ? 'danger' : 'warning'}>
                      {account.verification_status}
                    </Badge>
                    {!account.is_active && <Badge variant="neutral">Inactive</Badge>}
                  </div>
                  <p className="text-xs text-[#94A3B8] mt-1">{account.account_type.toUpperCase()} · {account.masked_identifier}</p>
                  {account.verification_status === 'rejected' && account.verification_reason && (
                    <p className="text-[11px] text-red-300 mt-1">Reason: {account.verification_reason}</p>
                  )}
                </div>
                {account.is_active && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingAccountId(account.id);
                        setAccountForm({
                          account_type: account.account_type,
                          display_name: account.display_name,
                          bank_name: account.bank_name || '',
                          masked_identifier: account.masked_identifier,
                        });
                        setShowAccountForm(true);
                      }}
                      className="dv-btn-secondary text-[11px] px-3 py-2"
                    >
                      Edit
                    </button>
                    {!account.is_default && <button type="button" onClick={() => setDefault(account.id)} className="dv-btn-secondary text-[11px] px-3 py-2">Make default</button>}
                    <button type="button" onClick={() => deactivateAccount(account.id)} className="text-[11px] px-3 py-2 rounded-xl border border-red-200 bg-[#111C30] text-red-300 hover:bg-red-950/60">Deactivate</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <form onSubmit={submitWithdrawal} className="dv-card p-5 mb-6">
        <h2 className="text-sm font-bold mb-4">Request withdrawal</h2>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_220px_auto] gap-4 items-end">
          <div>
            <label htmlFor="payout-account" className="block text-xs font-medium text-[#94A3B8] mb-1.5">Verified payout account</label>
            <select id="payout-account" value={withdrawal.accountId} onChange={(e) => setWithdrawal((v) => ({ ...v, accountId: e.target.value }))} className="dv-input px-3 py-2.5 text-sm" required>
              <option value="">Select account</option>
              {verifiedAccounts.map((account) => <option key={account.id} value={account.id}>{account.display_name} · {account.masked_identifier}</option>)}
            </select>
          </div>
          <Input id="withdrawal-amount" label={`Amount (${balance?.currency || 'INR'})`} type="number" min={balance?.minimum_amount || '0'} max={balance?.maximum_amount || undefined} step="0.01" value={withdrawal.amount} onChange={(e) => setWithdrawal((v) => ({ ...v, amount: e.target.value }))} required helperText={balance ? `Minimum ${formatINR(balance.minimum_amount)} · Available ${formatINR(balance.available_amount)}` : undefined} />
          <button type="submit" disabled={saving || !withdrawal.accountId || Number(withdrawal.amount) <= 0} className="dv-btn-primary text-xs px-4 py-2.5">Submit request</button>
        </div>
      </form>

      <section className="dv-card overflow-hidden">
        <div className="px-5 py-4 border-b border-[#E5E7EB]"><h2 className="text-sm font-bold">Payout request history</h2></div>
        {!requests.items.length ? (
          <p className="p-8 text-center text-xs text-[#94A3B8]">No payout requests have been submitted.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead><tr className="bg-[#18243A] text-[#94A3B8] border-b border-[#E5E7EB]"><th className="px-4 py-3">Reference</th><th className="px-4 py-3">Destination</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Created</th><th className="px-4 py-3 text-right">Action</th></tr></thead>
                <tbody className="divide-y divide-[#E5E7EB]">{requests.items.map((request) => (
                  <tr key={request.id} className="hover:bg-[#18243A]">
                    <td className="px-4 py-3 font-mono"><button type="button" onClick={() => openPayoutDetail(request)} className="text-[#93C5FD] hover:underline">{request.id}</button></td>
                    <td className="px-4 py-3">{request.destination_masked_snapshot}</td>
                    <td className="px-4 py-3 text-right font-mono font-bold">{formatINR(request.amount)}</td>
                    <td className="px-4 py-3"><Badge variant={statusVariant[request.status] || 'neutral'}>{request.status}</Badge></td>
                    <td className="px-4 py-3 text-[#94A3B8]">{new Date(request.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">{['requested', 'under_review', 'approved'].includes(request.status) && <button type="button" onClick={() => setCancelTarget(request)} className="dv-btn-secondary text-[11px] px-3 py-1.5">Cancel</button>}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <div className="px-5"><Pagination page={requests.page} totalPages={requests.total_pages} totalItems={requests.total} itemLabel="requests" onPageChange={(page) => sellerPayoutApi.listRequests({ page, page_size: PAGE_SIZE }).then(setRequests)} /></div>
          </>
        )}
      </section>

      <ConfirmDialog open={Boolean(cancelTarget)} title="Cancel payout request?" description="This may release reserved funds if the request is still cancellable." confirmLabel="Cancel request" cancelLabel="Keep request" variant="danger" onConfirm={cancelRequest} onCancel={() => setCancelTarget(null)} />

      {detailRequest && (
        <div role="dialog" aria-modal="true" aria-labelledby="seller-payout-detail-title" className="fixed inset-0 z-50 bg-[#080D19]/70 backdrop-blur-[2px] flex justify-end">
          <div className="w-full max-w-xl h-full overflow-y-auto bg-[#111C30] border-l border-[#E5E7EB] p-6">
            <div className="flex items-start justify-between gap-4 mb-6">
              <div>
                <p className="text-xs text-[#60A5FA] font-semibold">Payout detail</p>
                <h2 id="seller-payout-detail-title" className="text-lg font-bold mt-1 font-mono">{detailRequest.id}</h2>
              </div>
              <button type="button" onClick={() => { setDetailRequest(null); setDetailAttempts([]); }} aria-label="Close payout detail" className="p-2 rounded-xl border border-[#E5E7EB]">×</button>
            </div>
            {detailLoading ? <LoadingState label="Loading payout detail..." /> : (
              <div className="space-y-6">
                <section className="dv-card p-5">
                  <h3 className="text-sm font-bold mb-3">Request information</h3>
                  <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div><dt className="text-[#94A3B8]">Amount</dt><dd className="font-mono font-bold mt-1">{formatINR(detailRequest.amount)}</dd></div>
                    <div><dt className="text-[#94A3B8]">Status</dt><dd className="mt-1"><Badge variant={statusVariant[detailRequest.status] || 'neutral'}>{detailRequest.status}</Badge></dd></div>
                    <div><dt className="text-[#94A3B8]">Masked destination</dt><dd className="mt-1">{detailRequest.destination_masked_snapshot}</dd></div>
                    <div><dt className="text-[#94A3B8]">Settlement</dt><dd className="mt-1">{detailRequest.settlement_status || (detailRequest.status === 'completed' ? 'completed' : 'not_settled')}</dd></div>
                  </dl>
                </section>
                <section className="dv-card p-5">
                  <h3 className="text-sm font-bold mb-3">Execution timeline</h3>
                  {!detailAttempts.length ? (
                    <p className="text-xs text-[#94A3B8]">No execution attempts have been recorded.</p>
                  ) : (
                    <div className="space-y-3">{detailAttempts.map((attempt) => (
                      <div key={attempt.id} className="border border-[#E5E7EB] rounded-xl p-3 text-xs">
                        <div className="flex items-center justify-between gap-3">
                          <strong>Attempt {attempt.attempt_no}</strong>
                          <Badge variant={attempt.outcome === 'success' ? 'success' : attempt.outcome === 'uncertain' ? 'warning' : attempt.outcome === 'failed' ? 'danger' : 'neutral'}>{attempt.outcome}</Badge>
                        </div>
                        <p className="text-[#94A3B8] mt-1">{attempt.simulated ? 'Simulated execution — no real transfer occurred.' : 'Provider execution status.'}</p>
                        {attempt.sanitized_error && <p className="text-red-300 mt-1">{attempt.sanitized_error}</p>}
                        {attempt.started_at && <p className="text-[#94A3B8] mt-1">{new Date(attempt.started_at).toLocaleString()}</p>}
                      </div>
                    ))}</div>
                  )}
                </section>
                {detailRequest.failure_reason && (
                  <section className="dv-card p-5">
                    <h3 className="text-sm font-bold mb-2">Safe status explanation</h3>
                    <p className="text-xs text-red-300">{detailRequest.failure_reason}</p>
                  </section>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </SellerLayout>
  );
};

export default SellerPayoutPage;
