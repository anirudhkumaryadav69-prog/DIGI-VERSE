import { useEffect, useState } from 'react';
import { Activity, Save, ShieldCheck } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import {
  ErrorAlert,
  LoadingState,
  ToastBanner,
} from '../../components/common/StorefrontDesignSystem';
import { AdminSectionHeader, formatAdminDateTime } from '../../components/admin/AdminPrimitives';
import { adminOperationsApi } from '../../services/api';

const DEFAULT_SETTINGS_KEYS = [
  { key: 'store.name', label: 'Public Store Name', placeholder: 'DIGI-VERSE' },
  {
    key: 'store.announcement_text',
    label: 'Top Announcement Banner Text',
    placeholder: 'Instant digital downloads on every verified purchase',
  },
  {
    key: 'store.contact_email',
    label: 'Public Customer Support Email',
    placeholder: 'support@digiverse.example',
  },
  {
    key: 'store.support_phone',
    label: 'Public Support Phone / WhatsApp',
    placeholder: '+91 98765 43210',
  },
  {
    key: 'checkout.invoice_footer',
    label: 'Invoice Footer Note (Receipt)',
    placeholder: 'Thank you for supporting digital creators on DIGI-VERSE.',
  },
];

const AdminSettingsPage = () => {
  const [settingsMap, setSettingsMap] = useState({});
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);

  const loadSettingsAndAudit = () => {
    setLoading(true);
    Promise.all([
      adminOperationsApi.listSettings(),
      adminOperationsApi.listAuditLogs({ page: 1, page_size: 25 }),
    ])
      .then(([settingsList, logsRes]) => {
        const map = {};
        (settingsList || []).forEach((s) => {
          map[s.key] = typeof s.value === 'string' ? s.value : JSON.stringify(s.value);
        });
        setSettingsMap(map);
        setAuditLogs(logsRes?.items || []);
        setAuditTotal(logsRes?.total || 0);
        setError('');
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load store settings.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadSettingsAndAudit();
  }, []);

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setToast(null);
    try {
      const payload = {};
      DEFAULT_SETTINGS_KEYS.forEach(({ key }) => {
        if (settingsMap[key] !== undefined) {
          payload[key] = settingsMap[key];
        }
      });
      await adminOperationsApi.batchUpdateSettings(payload);
      setToast({ type: 'success', message: 'Store configuration saved and audited.' });
      loadSettingsAndAudit();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to save store settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout
      title="Settings & Security Audit"
      subtitle="Manage storefront configuration parameters and inspect immutable administrative audit logs"
    >
      {error && <ErrorAlert message={error} onRetry={loadSettingsAndAudit} className="mb-5" />}
      <ToastBanner toast={toast} onDismiss={() => setToast(null)} className="mb-5" />

      {loading && !auditLogs.length ? (
        <LoadingState label="Loading settings and audit logs..." />
      ) : (
        <div className="space-y-6">
          {/* Store Settings Form */}
          <form
            onSubmit={handleSaveSettings}
            className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-6 space-y-5 shadow-2xs"
          >
            <div className="border-b border-[#E5E7EB] pb-4">
              <AdminSectionHeader
                icon={ShieldCheck}
                title="Storefront & Receipt Configuration"
                subtitle="Non-sensitive storefront settings (secrets and API keys are strictly excluded)"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {DEFAULT_SETTINGS_KEYS.map((item) => (
                <div key={item.key}>
                  <label
                    htmlFor={`setting-${item.key}`}
                    className="block text-[12.5px] font-medium text-[#F1F5F9] mb-1.5"
                  >
                    {item.label}{' '}
                    <span className="font-mono text-[11px] text-[#94A3B8]">({item.key})</span>
                  </label>
                  <input
                    id={`setting-${item.key}`}
                    type="text"
                    value={settingsMap[item.key] || ''}
                    onChange={(e) =>
                      setSettingsMap({ ...settingsMap, [item.key]: e.target.value })
                    }
                    placeholder={item.placeholder}
                    className="dv-input px-3.5 py-2 text-[13px]"
                  />
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={saving || loading}
                className="dv-btn-primary text-[12px] font-semibold px-5 py-2 inline-flex items-center gap-1.5 disabled:opacity-50"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{saving ? 'Saving...' : 'Save Configuration'}</span>
              </button>
            </div>
          </form>

          {/* Administrative Audit Logs */}
          <section className="bg-[#111C30] border border-[#D5DEE8] rounded-xl overflow-hidden shadow-2xs">
            <div className="p-5 border-b border-[#E5E7EB]">
              <AdminSectionHeader
                icon={Activity}
                title={`Administrative Audit Logs (${auditTotal})`}
                subtitle="Latest 25 recorded administrative actions"
              />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[#D5DEE8] bg-[#18243A] text-[#CBD5E1] text-[11.5px] font-semibold">
                    <th className="py-3 px-4">Administrator</th>
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-4">Entity</th>
                    <th className="py-3 px-4">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB] text-[13px]">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-[#18243A]/70 transition">
                      <td className="py-3 px-4 font-medium text-[#F1F5F9]">
                        {log.admin_username || 'System'}
                      </td>
                      <td className="py-3 px-4 font-mono text-[12px] text-[#93C5FD]">
                        {log.action}
                      </td>
                      <td className="py-3 px-4 text-[#94A3B8]">
                        {log.entity_type} {log.entity_id ? `(${log.entity_id})` : ''}
                      </td>
                      <td className="py-3 px-4 text-[#94A3B8] tabular-nums whitespace-nowrap">
                        {formatAdminDateTime(log.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </AdminLayout>
  );
};

export default AdminSettingsPage;
