import { useEffect, useMemo, useState } from 'react';
import { CalendarDays, IndianRupee, ReceiptText, WalletCards } from 'lucide-react';
import SellerLayout from '../../layouts/SellerLayout';
import {
  ErrorAlert,
  LoadingState,
  Pagination,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import { sellerApi } from '../../services/api';

const PAGE_SIZE = 10;

const SellerFinancialPage = () => {
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [orders, setOrders] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [items, setItems] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = (overrides = {}) => {
    setLoading(true);
    setError('');
    const params = {
      date_from: overrides.dateFrom !== undefined ? (overrides.dateFrom || undefined) : (dateFrom || undefined),
      date_to: overrides.dateTo !== undefined ? (overrides.dateTo || undefined) : (dateTo || undefined),
    };
    Promise.all([
      sellerApi.getFinancialSummary(params),
      sellerApi.getFinancialTransactions({ ...params, page: overrides.transactionPage ?? transactions.page, page_size: PAGE_SIZE }),
      sellerApi.getFinancialOrders({ ...params, page: overrides.orderPage ?? orders.page, page_size: PAGE_SIZE }),
      sellerApi.getFinancialOrderItems({ ...params, page: overrides.itemPage ?? items.page, page_size: PAGE_SIZE }),
    ])
      .then(([summaryData, transactionData, orderData, itemData]) => {
        setSummary(summaryData);
        setTransactions(transactionData);
        setOrders(orderData);
        setItems(itemData);
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load financial information.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData({
      dateFrom,
      dateTo,
      transactionPage: 1,
      orderPage: 1,
      itemPage: 1,
    });
  }, []);

  const cards = useMemo(() => {
    if (!summary) return [];
    return [
      { label: 'Gross sales', value: summary.gross_sales, icon: IndianRupee },
      { label: 'Platform commission', value: summary.platform_commission, icon: ReceiptText },
      { label: 'Net seller earnings', value: summary.net_earnings, icon: WalletCards },
      { label: 'Pending earnings', value: summary.pending_earnings, icon: CalendarDays },
      { label: 'Available earnings', value: summary.available_earnings, icon: WalletCards },
      { label: 'Refunded amount', value: summary.refunded_amount, icon: ReceiptText },
      { label: 'Settled amount', value: summary.total_settled, icon: WalletCards },
    ];
  }, [summary]);

  const applyFilters = (event) => {
    event.preventDefault();
    setTransactions((current) => ({ ...current, page: 1 }));
    setOrders((current) => ({ ...current, page: 1 }));
    setItems((current) => ({ ...current, page: 1 }));
    loadData();
  };

  if (loading && !summary) {
    return (
      <SellerLayout title="Financials" subtitle="Authoritative earnings and commission data">
        <LoadingState label="Loading financial records..." />
      </SellerLayout>
    );
  }

  return (
    <SellerLayout
      title="Financials"
      subtitle="Ledger-backed gross sales, commissions, refunds and earnings"
    >
      {error && <ErrorAlert message={error} onRetry={() => loadData()} />}

      <form onSubmit={applyFilters} className="dv-card p-4 mb-6 flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="seller-financial-from" className="block text-xs font-medium text-[#64748B] mb-1.5">From</label>
          <input id="seller-financial-from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="dv-input px-3 py-2 text-xs" />
        </div>
        <div>
          <label htmlFor="seller-financial-to" className="block text-xs font-medium text-[#64748B] mb-1.5">To</label>
          <input id="seller-financial-to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="dv-input px-3 py-2 text-xs" />
        </div>
        <button type="submit" className="dv-btn-primary text-xs px-4 py-2.5">Apply filters</button>
        <button type="button" onClick={() => { setDateFrom(''); setDateTo(''); setTransactions((c) => ({ ...c, page: 1 })); setOrders((c) => ({ ...c, page: 1 })); setItems((c) => ({ ...c, page: 1 })); sellerApi.getFinancialSummary({}).then(setSummary); sellerApi.getFinancialTransactions({ page: 1, page_size: PAGE_SIZE }).then(setTransactions); sellerApi.getFinancialOrders({ page: 1, page_size: PAGE_SIZE }).then(setOrders); sellerApi.getFinancialOrderItems({ page: 1, page_size: PAGE_SIZE }).then(setItems); }} className="dv-btn-secondary text-xs px-4 py-2.5">Clear</button>
      </form>

      {summary && (
        <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
          {cards.map(({ label, value, icon: Icon }) => (
            <div key={label} className="dv-card p-5">
              <p className="text-xs font-medium text-[#64748B] flex justify-between items-center">
                {label}<Icon className="w-4 h-4 text-[#2563EB]" aria-hidden="true" />
              </p>
              <p className="text-xl font-bold text-[#1D4ED8] font-mono mt-2">{formatINR(value)}</p>
            </div>
          ))}
        </section>
      )}

      <div className="bg-[#EAF4FC] border border-[#BFDBFE] rounded-xl p-4 mb-6 text-xs text-[#1D4ED8]">
        Pending and settled balances are shown only from backend ledger data. Payout settlement is not yet configured, so zero or unavailable values are not assumed to be real paid funds.
      </div>

      <section className="dv-card overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-[#E5E7EB]"><h2 className="text-sm font-bold text-[#263445]">Financial transactions</h2></div>
        {!transactions.items.length ? (
          <p className="p-8 text-center text-xs text-[#64748B]">No financial transactions found for this period.</p>
        ) : (
          <>
            <div className="overflow-x-auto"><table className="w-full text-xs text-left">
              <thead><tr className="bg-[#F8FAFC] text-[#64748B] border-b border-[#E5E7EB]">
                <th className="px-4 py-3">Reference</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Debit</th><th className="px-4 py-3 text-right">Credit</th><th className="px-4 py-3">Posted</th>
              </tr></thead>
              <tbody className="divide-y divide-[#E5E7EB]">{transactions.items.map((row) => (
                <tr key={row.id} className="hover:bg-[#EAF4FC]">
                  <td className="px-4 py-3 font-mono text-[#263445]">{row.order_id || row.provider_transaction_id || row.id}</td>
                  <td className="px-4 py-3">{row.transaction_type}</td><td className="px-4 py-3">{row.status}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatINR(row.debit_total)}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatINR(row.credit_total)}</td>
                  <td className="px-4 py-3 text-[#64748B]">{row.posted_at ? new Date(row.posted_at).toLocaleString() : '-'}</td>
                </tr>
              ))}</tbody>
            </table></div>
            <div className="px-5"><Pagination page={transactions.page} totalPages={transactions.total_pages} totalItems={transactions.total} itemLabel="transactions" onPageChange={(page) => { setTransactions((c) => ({ ...c, page })); sellerApi.getFinancialTransactions({ date_from: dateFrom || undefined, date_to: dateTo || undefined, page, page_size: PAGE_SIZE }).then(setTransactions); }} /></div>
          </>
        )}
      </section>

      <section className="dv-card overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-[#E5E7EB]"><h2 className="text-sm font-bold text-[#263445]">Order-wise commission</h2></div>
        {!orders.items.length ? <p className="p-8 text-center text-xs text-[#64748B]">No order financial data found.</p> : (
          <>
            <div className="overflow-x-auto"><table className="w-full text-xs text-left">
              <thead><tr className="bg-[#F8FAFC] text-[#64748B] border-b border-[#E5E7EB]"><th className="px-4 py-3">Order</th><th className="px-4 py-3 text-right">Gross</th><th className="px-4 py-3 text-right">Commission</th><th className="px-4 py-3 text-right">Net</th><th className="px-4 py-3 text-right">Refunded</th></tr></thead>
              <tbody className="divide-y divide-[#E5E7EB]">{orders.items.map((row) => (
                <tr key={row.order_id} className="hover:bg-[#EAF4FC]"><td className="px-4 py-3 font-mono font-semibold">{row.order_number}</td><td className="px-4 py-3 text-right font-mono">{formatINR(row.gross_amount)}</td><td className="px-4 py-3 text-right font-mono">{formatINR(row.commission_amount)}</td><td className="px-4 py-3 text-right font-mono font-bold">{formatINR(row.net_amount)}</td><td className="px-4 py-3 text-right font-mono">{formatINR(row.refunded_amount)}</td></tr>
              ))}</tbody>
            </table></div>
            <div className="px-5"><Pagination page={orders.page} totalPages={orders.total_pages} totalItems={orders.total} itemLabel="orders" onPageChange={(page) => sellerApi.getFinancialOrders({ date_from: dateFrom || undefined, date_to: dateTo || undefined, page, page_size: PAGE_SIZE }).then(setOrders)} /></div>
          </>
        )}
      </section>

      <section className="dv-card overflow-hidden">
        <div className="px-5 py-4 border-b border-[#E5E7EB]"><h2 className="text-sm font-bold text-[#263445]">Item-wise earnings</h2></div>
        {!items.items.length ? <p className="p-8 text-center text-xs text-[#64748B]">No item-wise commission data found.</p> : (
          <>
            <div className="overflow-x-auto"><table className="w-full text-xs text-left">
              <thead><tr className="bg-[#F8FAFC] text-[#64748B] border-b border-[#E5E7EB]"><th className="px-4 py-3">Product</th><th className="px-4 py-3">Order</th><th className="px-4 py-3 text-right">Gross</th><th className="px-4 py-3 text-right">Rate</th><th className="px-4 py-3 text-right">Commission</th><th className="px-4 py-3 text-right">Net</th></tr></thead>
              <tbody className="divide-y divide-[#E5E7EB]">{items.items.map((row) => (
                <tr key={row.order_item_id} className="hover:bg-[#EAF4FC]"><td className="px-4 py-3 font-semibold text-[#263445]">{row.product_name_snapshot}</td><td className="px-4 py-3 font-mono">{row.order_number}</td><td className="px-4 py-3 text-right font-mono">{formatINR(row.gross_amount)}</td><td className="px-4 py-3 text-right font-mono">{row.commission_rate == null ? '-' : `${row.commission_rate}%`}</td><td className="px-4 py-3 text-right font-mono">{formatINR(row.commission_amount)}</td><td className="px-4 py-3 text-right font-mono font-bold">{formatINR(row.net_amount)}</td></tr>
              ))}</tbody>
            </table></div>
            <div className="px-5"><Pagination page={items.page} totalPages={items.total_pages} totalItems={items.total} itemLabel="items" onPageChange={(page) => sellerApi.getFinancialOrderItems({ date_from: dateFrom || undefined, date_to: dateTo || undefined, page, page_size: PAGE_SIZE }).then(setItems)} /></div>
          </>
        )}
      </section>
    </SellerLayout>
  );
};

export default SellerFinancialPage;
