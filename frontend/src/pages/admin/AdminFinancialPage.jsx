import { useEffect, useState } from 'react';
import { History, Landmark, Percent, ReceiptText, Save, Search, Trash2, TrendingUp } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  ErrorAlert,
  LoadingState,
  Pagination,
  ToastBanner,
  formatINR,
} from '../../components/common/StorefrontDesignSystem';
import {
  AdminSectionHeader,
  AdminStatusBadge,
  formatAdminDateTime,
} from '../../components/admin/AdminPrimitives';
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
    const nextSellerFilter =
      overrides.sellerFilter !== undefined ? overrides.sellerFilter : sellerFilter;
    const nextOrderFilter =
      overrides.orderFilter !== undefined ? overrides.orderFilter : orderFilter;
    const nextTransactionFilter =
      overrides.transactionFilter !== undefined ? overrides.transactionFilter : transactionFilter;
    const nextDateFrom = overrides.dateFrom !== undefined ? overrides.dateFrom : dateFrom;
    const nextDateTo = overrides.dateTo !== undefined ? overrides.dateTo : dateTo;
    const nextSearch = overrides.search !== undefined ? overrides.search : search;
    Promise.all([
      adminFinancialApi.getCommission(),
      adminFinancialApi.listSellerCommissions({
        page: sellerPage,
        page_size: PAGE_SIZE,
        search: nextSearch || undefined,
      }),
      adminFinancialApi.getLedger({
        page: ledgerPage,
        page_size: PAGE_SIZE,
        seller_id: nextSellerFilter || undefined,
        order_id: nextOrderFilter || undefined,
        transaction_type: nextTransactionFilter || undefined,
        date_from: nextDateFrom || undefined,
        date_to: nextDateTo || undefined,
      }),
      adminFinancialApi.getCommissionReport({
        date_from: nextDateFrom || undefined,
        date_to: nextDateTo || undefined,
      }),
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      subtitle="Global and seller commission governance, financial ledger entries, and commission reports"
    >
      {error && <ErrorAlert message={error} onRetry={loadPage} className="mb-5" />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-5" />

      <form
        onSubmit={saveGlobalRate}
        className="bg-white border border-[#D5DEE8] rounded-xl p-6 mb-6 shadow-2xs space-y-4"
      >
        <AdminSectionHeader
          icon={Percent}
          title="Global commission"
          subtitle="Default marketplace commission percentage applied to sellers without a custom override"
        />
        <div className="flex flex-wrap items-end gap-4 pt-1">
          <div>
            <label
              htmlFor="global-commission"
              className="block text-[12px] font-medium text-[#263445] mb-1.5"
            >
              Default rate (%)
            </label>
            <input
              id="global-commission"
              type="number"
              min="0"
              max={commission?.maximum_rate || 100}
              step="0.000001"
              value={globalRate}
              onChange={(e) => setGlobalRate(e.target.value)}
              className="dv-input px-3.5 py-2 text-[13.5px] w-44 font-mono"
            />
          </div>
          <div className="text-[12.5px] text-[#64748B] pb-2">
            Maximum: <strong className="text-[#263445]">{commission?.maximum_rate}%</strong> ·
            Currency: <strong className="text-[#263445]">{commission?.currency}</strong>
          </div>
          <button
            type="submit"
            disabled={saving}
            className="dv-btn-primary text-[12px] font-semibold px-4 py-2 inline-flex items-center gap-2 disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save global rate</span>
          </button>
        </div>
      </form>

      <section className="bg-white border border-[#D5DEE8] rounded-xl overflow-hidden mb-6 shadow-2xs">
        <div className="px-5 py-4 border-b border-[#E5E7EB] flex flex-wrap items-center justify-between gap-3">
          <AdminSectionHeader
            icon={Landmark}
            title="Seller commission overrides"
            subtitle="Set store-specific commission rates or revert to the global default"
          />
          <div className="relative">
            <Search className="w-4 h-4 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              aria-label="Search sellers"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onBlur={() => {
                setSellers((c) => ({ ...c, page: 1 }));
                loadPage({ sellerPage: 1, search });
              }}
              placeholder="Search seller..."
              className="dv-input pl-9 pr-3 py-2 text-[13px] w-56"
            />
          </div>
        </div>
        {!sellers.items.length ? (
          <p className="p-8 text-center text-[13px] text-[#64748B]">No sellers found.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#F8FAFC] text-[#475569] border-b border-[#D5DEE8] text-[11.5px] font-semibold">
                    <th className="px-4 py-3">Seller</th>
                    <th className="px-4 py-3 text-right">Override (%)</th>
                    <th className="px-4 py-3 text-right">Effective Rate</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                  {sellers.items.map((row) => (
                    <SellerCommissionRow
                      key={row.seller_id}
                      row={row}
                      saving={saving}
                      onSave={updateSellerOverride}
                      onRemove={removeSellerOverride}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-5 pb-3">
              <Pagination
                page={sellers.page}
                totalPages={sellers.total_pages}
                totalItems={sellers.total}
                itemLabel="sellers"
                onPageChange={(page) =>
                  adminFinancialApi
                    .listSellerCommissions({
                      page,
                      page_size: PAGE_SIZE,
                      search: search || undefined,
                    })
                    .then(setSellers)
                }
              />
            </div>
          </>
        )}
      </section>

      <section className="bg-white border border-[#D5DEE8] rounded-xl p-5 mb-6 shadow-2xs">
        <AdminSectionHeader
          icon={ReceiptText}
          title="Financial ledger filters"
          subtitle="Filter immutable double-entry accounting postings"
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end mt-4">
          <input
            aria-label="Seller filter"
            value={sellerFilter}
            onChange={(e) => setSellerFilter(e.target.value)}
            placeholder="Seller UUID"
            className="dv-input px-3 py-2 text-[13px]"
          />
          <input
            aria-label="Order filter"
            value={orderFilter}
            onChange={(e) => setOrderFilter(e.target.value)}
            placeholder="Order UUID"
            className="dv-input px-3 py-2 text-[13px]"
          />
          <input
            aria-label="Transaction type"
            value={transactionFilter}
            onChange={(e) => setTransactionFilter(e.target.value)}
            placeholder="payment_capture"
            className="dv-input px-3 py-2 text-[13px]"
          />
          <input
            aria-label="Date from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="dv-input px-3 py-2 text-[13px]"
          />
          <input
            aria-label="Date to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="dv-input px-3 py-2 text-[13px]"
          />
        </div>
        <button
          type="button"
          onClick={() => {
            setLedger((c) => ({ ...c, page: 1 }));
            loadPage({
              ledgerPage: 1,
              sellerFilter,
              orderFilter,
              transactionFilter,
              dateFrom,
              dateTo,
            });
          }}
          className="dv-btn-primary text-[12px] font-semibold px-4 py-2 mt-3.5"
        >
          Apply ledger filters
        </button>
      </section>

      <section className="bg-white border border-[#D5DEE8] rounded-xl overflow-hidden mb-6 shadow-2xs">
        <div className="px-5 py-4 border-b border-[#E5E7EB]">
          <AdminSectionHeader icon={ReceiptText} title="Financial ledger" />
        </div>
        {!ledger.items.length ? (
          <p className="p-8 text-center text-[13px] text-[#64748B]">
            No ledger entries match the filters.
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#F8FAFC] text-[#475569] border-b border-[#D5DEE8] text-[11.5px] font-semibold">
                    <th className="px-4 py-3">Transaction / Order</th>
                    <th className="px-4 py-3">Entry Type</th>
                    <th className="px-4 py-3">Account</th>
                    <th className="px-4 py-3">Direction</th>
                    <th className="px-4 py-3 text-right">Amount</th>
                    <th className="px-4 py-3">Posted</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                  {ledger.items.map((row) => (
                    <tr key={row.id} className="hover:bg-[#EDF5FC]/45 transition">
                      <td className="px-4 py-3 font-mono text-[12px] text-[#263445]">
                        {row.order_id || row.transaction_id}
                      </td>
                      <td className="px-4 py-3 text-[#263445]">{row.entry_type}</td>
                      <td className="px-4 py-3 font-mono text-[12px] text-[#475569]">
                        {row.account_code}
                      </td>
                      <td className="px-4 py-3">
                        <AdminStatusBadge
                          status={row.direction === 'credit' ? 'completed' : 'processing'}
                          label={row.direction}
                        />
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-semibold text-[#263445] tabular-nums">
                        {formatINR(row.amount)}
                      </td>
                      <td className="px-4 py-3 text-[#64748B] tabular-nums whitespace-nowrap">
                        {formatAdminDateTime(row.posted_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-5 pb-3">
              <Pagination
                page={ledger.page}
                totalPages={ledger.total_pages}
                totalItems={ledger.total}
                itemLabel="entries"
                onPageChange={(page) =>
                  adminFinancialApi
                    .getLedger({
                      page,
                      page_size: PAGE_SIZE,
                      seller_id: sellerFilter || undefined,
                      order_id: orderFilter || undefined,
                      transaction_type: transactionFilter || undefined,
                      date_from: dateFrom || undefined,
                      date_to: dateTo || undefined,
                    })
                    .then(setLedger)
                }
              />
            </div>
          </>
        )}
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <section className="bg-white border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
          <div className="px-5 py-4 border-b border-[#E5E7EB]">
            <AdminSectionHeader icon={TrendingUp} title="Commission report" />
          </div>
          {!report?.sellers?.length ? (
            <p className="p-8 text-center text-[13px] text-[#64748B]">
              No commission report data.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#F8FAFC] text-[#475569] border-b border-[#D5DEE8] text-[11.5px] font-semibold">
                    <th className="px-4 py-3">Seller</th>
                    <th className="px-4 py-3 text-right">Gross</th>
                    <th className="px-4 py-3 text-right">Commission</th>
                    <th className="px-4 py-3 text-right">Net Earnings</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                  {report.sellers.map((row) => (
                    <tr key={row.seller_id} className="hover:bg-[#EDF5FC]/45 transition">
                      <td className="px-4 py-3 font-semibold text-[#263445]">{row.store_name}</td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {formatINR(row.gross_sales)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums text-[#475569]">
                        {formatINR(row.commission_amount)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-bold text-[#1D4ED8] tabular-nums">
                        {formatINR(row.net_earnings)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="bg-white border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
          <div className="px-5 py-4 border-b border-[#E5E7EB]">
            <AdminSectionHeader icon={History} title="Commission history" />
          </div>
          {!history.length ? (
            <p className="p-8 text-center text-[13px] text-[#64748B]">
              No commission configuration changes recorded.
            </p>
          ) : (
            <div className="divide-y divide-[#E5E7EB]">
              {history.map((row) => (
                <div key={row.id} className="px-5 py-3.5 text-[13px] flex justify-between gap-4">
                  <div className="min-w-0">
                    <p className="font-mono text-[12px] font-medium text-[#1D4ED8]">{row.action}</p>
                    <p className="text-[12px] text-[#64748B] mt-0.5 truncate">
                      {row.entity_type} {row.entity_id ? `· ${row.entity_id}` : ''}
                    </p>
                  </div>
                  <time className="text-[12px] text-[#64748B] shrink-0 tabular-nums">
                    {formatAdminDateTime(row.created_at)}
                  </time>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </AdminLayout>
  );
};

const SellerCommissionRow = ({ row, saving, onSave, onRemove }) => {
  const [rate, setRate] = useState(row.override_rate ?? '');
  return (
    <tr className="hover:bg-[#EDF5FC]/45 transition">
      <td className="px-4 py-3.5">
        <p className="font-semibold text-[#263445]">{row.store_name}</p>
        <p className="text-[11.5px] font-mono text-[#64748B]">{row.store_slug}</p>
      </td>
      <td className="px-4 py-3.5 text-right">
        <input
          aria-label={`Commission override for ${row.store_name}`}
          type="number"
          min="0"
          max="100"
          step="0.000001"
          value={rate}
          onChange={(e) => setRate(e.target.value)}
          className="dv-input px-2.5 py-1.5 text-[13px] w-28 text-right font-mono inline-block"
        />
      </td>
      <td className="px-4 py-3.5 text-right font-mono font-semibold text-[#263445] tabular-nums">
        {row.effective_rate}%
      </td>
      <td className="px-4 py-3.5">
        <div className="flex justify-end gap-2">
          <button
            type="button"
            disabled={saving}
            onClick={() => onSave(row.seller_id, rate)}
            className="dv-btn-primary px-3 py-1.5 text-[12px] font-semibold"
          >
            Save
          </button>
          {row.override_rate != null && (
            <button
              type="button"
              disabled={saving}
              aria-label={`Remove override for ${row.store_name}`}
              onClick={() => onRemove(row.seller_id)}
              className="p-1.5 rounded-lg border border-red-200 bg-white text-[#DC2626] hover:bg-red-50 transition"
              title="Remove Override"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
};

export default AdminFinancialPage;
