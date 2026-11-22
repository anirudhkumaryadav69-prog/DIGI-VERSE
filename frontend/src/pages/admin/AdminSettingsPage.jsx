import { useEffect, useState } from 'react';
import { Save, Activity, ShieldCheck } from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
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
    label: 'Invoice Footer Note (Internal/Receipt)',
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
  const [success, setSuccess] = useState('');

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
    setSuccess('');
    try {
      const payload = {};
      DEFAULT_SETTINGS_KEYS.forEach(({ key }) => {
        if (settingsMap[key] !== undefined) {
          payload[key] = settingsMap[key];
        }
      });
      await adminOperationsApi.batchUpdateSettings(payload);
      setSuccess('Store configuration saved and audited.');
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
      title="Store Settings & Security Audit Ledger"
      subtitle="Manage non-sensitive storefront parameters and inspect immutable administrative audit logs"
    >
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs">
          {success}
        </div>
      )}

      {/* Store Settings Form */}
      <form
        onSubmit={handleSaveSettings}
        className="dv-card p-6 mb-8 space-y-5"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E7EB] pb-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#FF6B0A]" />
            <h2 className="text-xs font-semibold text-[#1F2937] uppercase tracking-widest">
              Storefront & Receipt Configuration
            </h2>
          </div>
          <span className="text-[11px] text-[#64748B]">
            Secrets & API keys are strictly blocked from database settings
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {DEFAULT_SETTINGS_KEYS.map((item) => (
            <div key={item.key}>
              <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                {item.label} <span className="font-mono text-[10px]">({item.key})</span>
              </label>
              <input
                type="text"
                value={settingsMap[item.key] || ''}
                onChange={(e) =>
                  setSettingsMap({ ...settingsMap, [item.key]: e.target.value })
                }
                placeholder={item.placeholder}
                className="dv-input px-3 py-2 text-xs"
              />
            </div>
          ))}
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving || loading}
            className="dv-btn-primary text-xs uppercase tracking-wider px-5 py-2.5 inline-flex items-center gap-1.5 disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{saving ? 'Saving...' : 'Save Configuration'}</span>
          </button>
        </div>
      </form>

      {/* Administrative Audit Logs */}
      <section className="dv-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-[#FF6B0A]" />
            <h2 className="text-xs font-semibold text-[#1F2937] uppercase tracking-widest">
              Administrative Audit Logs ({auditTotal})
            </h2>
          </div>
          <span className="text-[11px] text-[#64748B]">Latest 25 Events</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E5E7EB] text-[#64748B] uppercase">
                <th className="py-2.5 pr-4 font-semibold">Administrator</th>
                <th className="py-2.5 pr-4 font-semibold">Action</th>
                <th className="py-2.5 pr-4 font-semibold">Entity</th>
                <th className="py-2.5 pr-4 font-semibold">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              {auditLogs.map((log) => (
                <tr key={log.id} className="hover:bg-[#FFF0E2]/45 transition">
                  <td className="py-2.5 pr-4 font-medium text-[#1F2937]">{log.admin_username || 'System'}</td>
                  <td className="py-2.5 pr-4 font-mono text-[#D94300]">{log.action}</td>
                  <td className="py-2.5 pr-4 text-[#64748B]">
                    {log.entity_type} {log.entity_id ? `(${log.entity_id})` : ''}
                  </td>
                  <td className="py-2.5 pr-4 text-[#64748B]">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AdminLayout>
  );
};

export default AdminSettingsPage;
