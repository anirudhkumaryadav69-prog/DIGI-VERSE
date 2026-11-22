import { useEffect, useState } from 'react';
import { Landmark, Percent, ReceiptText, Save, Search, Trash2 } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  ErrorAlert,
  LoadingState,
  Pagination,
  ToastBanner,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import { adminFinancialApi, adminOperationsApi } from '../../services/api';

const PAGE_SIZE = 20;

const AdminFinancialPage = () => {
  const [commission, setCommission] = useState(null);
  const [globalRate, setGlobalRate] = useState('');
  const [sellers, setSellers] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [ledger, setLedger] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [search, setSearch] = useState('');
  const [sellerFilter, setSellerFilter] = useState('');
  const [orderFilter, setOrderFilter] = useState('');
  const [transactionFilter, setTransactionFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);

  const loadPage = (overrides = {}) => {
    setLoading(true);
    setError('');
    const sellerPage = overrides.sellerPage ?? sellers.page;
    const ledgerPage = overrides.ledgerPage ?? ledger.page;
    const nextSellerFilter = overrides.sellerFilter !== undefined ? overrides.sellerFilter : sellerFilter;
    const nextOrderFilter = overrides.orderFilter !== undefined ? overrides.orderFilter : orderFilter;
    const nextTransactionFilter = overrides.transactionFilter !== undefined ? overrides.transactionFilter : transactionFilter;
    const nextDateFrom = overrides.dateFrom !== undefined ? overrides.dateFrom : dateFrom;
    const nextDateTo = overrides.dateTo !== undefined ? overrides.dateTo : dateTo;
    const nextSearch = overrides.search !== undefined ? overrides.search : search;
    Promise.all([
      adminFinancialApi.getCommission(),
      adminFinancialApi.listSellerCommissions({ page: sellerPage, page_size: PAGE_SIZE, search: nextSearch || undefined }),
      adminFinancialApi.getLedger({
        page: ledgerPage,
        page_size: PAGE_SIZE,
        seller_id: nextSellerFilter || undefined,
        order_id: nextOrderFilter || undefined,
        transaction_type: nextTransactionFilter || undefined,
        date_from: nextDateFrom || undefined,
        date_to: nextDateTo || undefined,
      }),
      adminFinancialApi.getCommissionReport({ date_from: nextDateFrom || undefined, date_to: nextDateTo || undefined }),
      adminOperationsApi.listAuditLogs({ page: 1, page_size: 25 }),
    ])
      .then(([commissionData, sellerData, ledgerData, reportData, auditData]) => {
        setCommission(commissionData);
        setGlobalRate(commissionData.default_rate);
        setSellers(sellerData);
        setLedger(ledgerData);
        setReport(reportData);
        setHistory((auditData.items || []).filter((row) => row.action?.startsWith('commission.')));
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load financial management data.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPage();
  }, []);

  const saveGlobalRate = async (event) => {
    event.preventDefault();
    setSaving(true);
    setToast(null);
    try {
      const result = await adminFinancialApi.updateCommission({ default_rate: globalRate });
      setCommission(result);
      setGlobalRate(result.default_rate);
      setToast({ type: 'success', message: 'Global commission configuration updated.' });
      loadPage();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update global commission.');
    } finally {
      setSaving(false);
    }
  };

  const updateSellerOverride = async (sellerId, rate) => {
    if (!rate || Number(rate) < 0) return;
    setSaving(true);
    try {
      await adminFinancialApi.updateSellerCommission(sellerId, { rate });
      setToast({ type: 'success', message: 'Seller commission override saved.' });
      loadPage();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to update seller commission.');
    } finally {
      setSaving(false);
    }
  };

  const removeSellerOverride = async (sellerId) => {
    setSaving(true);
    try {
      await adminFinancialApi.removeSellerCommission(sellerId, 'Removed from financial dashboard');
      setToast({ type: 'success', message: 'Seller commission override removed.' });
      loadPage();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to remove seller commission override.');
    } finally {
      setSaving(false);
    }
  };

  if (loading && !commission) {
    return (
      <AdminLayout title="Financial Management" subtitle="Commission and ledger administration">
        <LoadingState label="Loading financial management..." />
      </AdminLayout>
    );
  }

  return (
    <AdminLayout
      title="Financial Management"
      subtitle="Global and seller commissions, ledger entries and reports"
    >
      {error && <ErrorAlert message={error} onRetry={loadPage} />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-6" />

      <form onSubmit={saveGlobalRate} className="dv-card p-6 mb-6">
        <div className="flex items-center gap-2 mb-4"><Percent className="w-4 h-4 text-[#FF6B0A]" /><h2 className="text-sm font-bold">Global commission</h2></div>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label htmlFor="global-commission" className="block text-xs font-medium text-[#64748B] mb-1.5">Default rate (%)</label>
            <input id="global-commission" type="number" min="0" max={commission?.maximum_rate || 100} step="0.000001" value={globalRate} onChange={(e) => setGlobalRate(e.target.value)} className="dv-input px-3 py-2.5 text-sm w-44" />
          </div>
          <div className="text-xs text-[#64748B] pb-2">Maximum: <strong className="text-[#1F2937]">{commission?.maximum_rate}%</strong> · Currency: <strong className="text-[#1F2937]">{commission?.currency}</strong></div>
          <button type="submit" disabled={saving} className="dv-btn-primary text-xs px-4 py-2.5 inline-flex items-center gap-2"><Save className="w-3.5 h-3.5" />Save global rate</button>
        </div>
      </form>

      <section className="dv-card overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-[#E5E7EB] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2"><Landmark className="w-4 h-4 text-[#FF6B0A]" /><h2 className="text-sm font-bold">Seller commission overrides</h2></div>
          <div className="relative">
            <Search className="w-4 h-4 text-[#8490A0] absolute left-3 top-1/2 -translate-y-1/2" />
            <input aria-label="Search sellers" value={search} onChange={(e) => setSearch(e.target.value)} onBlur={() => { setSellers((c) => ({ ...c, page: 1 })); loadPage({ sellerPage: 1, search }); }} placeholder="Search seller..." className="dv-input pl-9 pr-3 py-2 text-xs w-52" />
          </div>
        </div>
        {!sellers.items.length ? <p className="p-8 text-center text-xs text-[#64748B]">No sellers found.</p> : (
          <>
            <div className="overflow-x-auto"><table className="w-full text-xs text-left">
              <thead><tr className="bg-[#FFF6ED] text-[#64748B] border-b border-[#E5E7EB]"><th className="px-4 py-3">Seller</th><th className="px-4 py-3 text-right">Override</th><th className="px-4 py-3 text-right">Effective rate</th><th className="px-4 py-3 text-right">Actions</th></tr></thead>
              <tbody className="divide-y divide-[#E5E7EB]">{sellers.items.map((row) => (
                <SellerCommissionRow key={row.seller_id} row={row} saving={saving} onSave={updateSellerOverride} onRemove={removeSellerOverride} />
              ))}</tbody>
            </table></div>
            <div className="px-5"><Pagination page={sellers.page} totalPages={sellers.total_pages} totalItems={sellers.total} itemLabel="sellers" onPageChange={(page) => adminFinancialApi.listSellerCommissions({ page, page_size: PAGE_SIZE, search: search || undefined }).then(setSellers)} /></div>
          </>
        )}
      </section>

      <section className="dv-card p-5 mb-6">
        <h2 className="text-sm font-bold mb-4 flex items-center gap-2"><ReceiptText className="w-4 h-4 text-[#FF6B0A]" />Financial ledger filters</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
          <input aria-label="Seller filter" value={sellerFilter} onChange={(e) => setSellerFilter(e.target.value)} placeholder="Seller UUID" className="dv-input px-3 py-2 text-xs" />
          <input aria-label="Order filter" value={orderFilter} onChange={(e) => setOrderFilter(e.target.value)} placeholder="Order UUID" className="dv-input px-3 py-2 text-xs" />
          <input aria-label="Transaction type" value={transactionFilter} onChange={(e) => setTransactionFilter(e.target.value)} placeholder="payment_capture" className="dv-input px-3 py-2 text-xs" />
          <input aria-label="Date from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="dv-input px-3 py-2 text-xs" />
          <input aria-label="Date to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="dv-input px-3 py-2 text-xs" />
        </div>
        <button type="button" onClick={() => { setLedger((c) => ({ ...c, page: 1 })); loadPage({ ledgerPage: 1, sellerFilter, orderFilter, transactionFilter, dateFrom, dateTo }); }} className="dv-btn-primary text-xs px-4 py-2.5 mt-3">Apply ledger filters</button>
      </section>

      <section className="dv-card overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-[#E5E7EB]"><h2 className="text-sm font-bold">Financial ledger</h2></div>
        {!ledger.items.length ? <p className="p-8 text-center text-xs text-[#64748B]">No ledger entries match the filters.</p> : (
          <>
            <div className="overflow-x-auto"><table className="w-full text-xs text-left">
              <thead><tr className="bg-[#FFF6ED] text-[#64748B] border-b border-[#E5E7EB]"><th className="px-4 py-3">Transaction</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Account</th><th className="px-4 py-3">Direction</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3">Posted</th></tr></thead>
              <tbody className="divide-y divide-[#E5E7EB]">{ledger.items.map((row) => (
                <tr key={row.id} className="hover:bg-[#FFFAF5]"><td className="px-4 py-3 font-mono">{row.order_id || row.transaction_id}</td><td className="px-4 py-3">{row.entry_type}</td><td className="px-4 py-3 font-mono">{row.account_code}</td><td className="px-4 py-3">{row.direction}</td><td className="px-4 py-3 text-right font-mono font-bold">{formatINR(row.amount)}</td><td className="px-4 py-3 text-[#64748B]">{new Date(row.posted_at).toLocaleString()}</td></tr>
              ))}</tbody>
            </table></div>
            <div className="px-5"><Pagination page={ledger.page} totalPages={ledger.total_pages} totalItems={ledger.total} itemLabel="entries" onPageChange={(page) => adminFinancialApi.getLedger({ page, page_size: PAGE_SIZE, seller_id: sellerFilter || undefined, order_id: orderFilter || undefined, transaction_type: transactionFilter || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }).then(setLedger)} /></div>
          </>
        )}
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <section className="dv-card overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E5E7EB]"><h2 className="text-sm font-bold">Commission report</h2></div>
          {!report?.sellers?.length ? <p className="p-8 text-center text-xs text-[#64748B]">No commission report data.</p> : (
            <div className="overflow-x-auto"><table className="w-full text-xs text-left"><thead><tr className="bg-[#FFF6ED] text-[#64748B]"><th className="px-4 py-3">Seller</th><th className="px-4 py-3 text-right">Gross</th><th className="px-4 py-3 text-right">Commission</th><th className="px-4 py-3 text-right">Net</th></tr></thead><tbody className="divide-y divide-[#E5E7EB]">{report.sellers.map((row) => <tr key={row.seller_id}><td className="px-4 py-3 font-semibold">{row.store_name}</td><td className="px-4 py-3 text-right font-mono">{formatINR(row.gross_sales)}</td><td className="px-4 py-3 text-right font-mono">{formatINR(row.commission_amount)}</td><td className="px-4 py-3 text-right font-mono font-bold">{formatINR(row.net_earnings)}</td></tr>)}</tbody></table></div>
          )}
        </section>
        <section className="dv-card overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E5E7EB]"><h2 className="text-sm font-bold">Commission history</h2></div>
          {!history.length ? <p className="p-8 text-center text-xs text-[#64748B]">No commission configuration changes recorded.</p> : (
            <div className="divide-y divide-[#E5E7EB]">{history.map((row) => <div key={row.id} className="px-5 py-3 text-xs flex justify-between gap-4"><div><p className="font-mono text-[#D94300]">{row.action}</p><p className="text-[#64748B] mt-1">{row.entity_type} {row.entity_id ? `· ${row.entity_id}` : ''}</p></div><time className="text-[#64748B] shrink-0">{new Date(row.created_at).toLocaleString()}</time></div>)}</div>
          )}
        </section>
      </div>
    </AdminLayout>
  );
};

const SellerCommissionRow = ({ row, saving, onSave, onRemove }) => {
  const [rate, setRate] = useState(row.override_rate ?? '');
  return (
    <tr className="hover:bg-[#FFFAF5]">
      <td className="px-4 py-3"><p className="font-semibold text-[#1F2937]">{row.store_name}</p><p className="text-[10px] font-mono text-[#64748B]">{row.store_slug}</p></td>
      <td className="px-4 py-3 text-right"><input aria-label={`Commission override for ${row.store_name}`} type="number" min="0" max="100" step="0.000001" value={rate} onChange={(e) => setRate(e.target.value)} className="dv-input px-2 py-1.5 text-xs w-28 text-right" /></td>
      <td className="px-4 py-3 text-right font-mono font-bold">{row.effective_rate}%</td>
      <td className="px-4 py-3"><div className="flex justify-end gap-2"><button type="button" disabled={saving} onClick={() => onSave(row.seller_id, rate)} className="dv-btn-primary px-3 py-1.5 text-[11px]">Save</button>{row.override_rate != null && <button type="button" disabled={saving} aria-label={`Remove override for ${row.store_name}`} onClick={() => onRemove(row.seller_id)} className="dv-btn-secondary px-2 py-1.5"><Trash2 className="w-3.5 h-3.5" /></button>}</div></td>
    </tr>
  );
};

export default AdminFinancialPage;
