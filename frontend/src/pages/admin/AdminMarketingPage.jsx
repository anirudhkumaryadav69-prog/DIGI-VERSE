import { useEffect, useState } from 'react';
import {
  Mail,
  MessageSquare,
  FileText,
  Send,
  Plus,
  Trash2,
  Clock,
  Activity,
  XCircle,
  Eye,
} from 'lucide-react';
import AdminLayout from '../../layouts/AdminLayout';
import { adminOperationsApi } from '../../services/api';

const CampaignMetricsPills = ({ c, isWhatsApp = false }) => (
  <div className="flex flex-wrap gap-1.5 pt-1 text-[10px]">
    <span className="px-2 py-0.5 rounded-full bg-[#FFF6ED] border border-[#E5E7EB] text-[#64748B]">
      Targeted: <strong className="text-[#1F2937]">{c.recipient_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-[#FFF6ED] border border-[#E5E7EB] text-[#64748B]">
      Queued: <strong className="text-[#1F2937]">{c.queued_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-[#FFE9D6] border border-[#FFD4AE] text-[#D94300]">
      Processing: <strong>{c.processing_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-800">
      Retrying: <strong>{c.retrying_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-sky-50 border border-sky-200 text-sky-800">
      Accepted: <strong>{c.accepted_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700">
      Delivered: <strong>{c.delivered_count ?? 0}</strong>
    </span>
    {isWhatsApp && (
      <span className="px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800">
        Read: <strong>{c.read_count ?? 0}</strong>
      </span>
    )}
    <span className="px-2 py-0.5 rounded-full bg-red-50 border border-red-200 text-red-700">
      Failed/Bounced: <strong>{c.failed_count ?? 0}</strong>
    </span>
    {(c.unresolved_count ?? 0) > 0 && (
      <span className="px-2 py-0.5 rounded-full bg-amber-100 border border-amber-300 text-amber-900">
        Unresolved Timeout: <strong>{c.unresolved_count}</strong>
      </span>
    )}
    <span className="px-2 py-0.5 rounded-full bg-slate-100 border border-[#E5E7EB] text-[#64748B]">
      Skipped: <strong>{c.skipped_count ?? 0}</strong>
    </span>
  </div>
);

const AdminMarketingPage = () => {
  const [activeTab, setActiveTab] = useState('email');
  const [templates, setTemplates] = useState([]);
  const [emailCampaigns, setEmailCampaigns] = useState([]);
  const [whatsappCampaigns, setWhatsappCampaigns] = useState([]);
  const [workerStatus, setWorkerStatus] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const [emailForm, setEmailForm] = useState({ name: '', subject: '', content: '' });
  const [waForm, setWaForm] = useState({
    name: '',
    approved_template_name: '',
    content: '',
  });
  const [tplForm, setTplForm] = useState({
    name: '',
    channel: 'email',
    subject: '',
    content: '',
  });

  const loadAll = () => {
    setLoading(true);
    Promise.all([
      adminOperationsApi.listTemplates(),
      adminOperationsApi.listEmailCampaigns(),
      adminOperationsApi.listWhatsAppCampaigns(),
      adminOperationsApi.getMarketingWorkerStatus().catch(() => null),
    ])
      .then(([tpls, emails, was, worker]) => {
        setTemplates(tpls || []);
        setEmailCampaigns(emails || []);
        setWhatsappCampaigns(was || []);
        setWorkerStatus(worker);
        setError('');
      })
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load marketing campaigns.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleCreateEmailCampaign = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    try {
      await adminOperationsApi.createEmailCampaign(emailForm);
      setEmailForm({ name: '', subject: '', content: '' });
      setMessage('Email campaign created in draft status.');
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to create email campaign.');
    }
  };

  const handleLaunchEmailCampaign = async (campaignId) => {
    setError('');
    setMessage('');
    try {
      const res = await adminOperationsApi.launchEmailCampaign(campaignId);
      setMessage(
        `Email campaign launched: delivered to ${res.sent_count} consented active customers.`
      );
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to launch email campaign.');
    }
  };

  const handleCreateWhatsAppCampaign = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    try {
      await adminOperationsApi.createWhatsAppCampaign(waForm);
      setWaForm({ name: '', approved_template_name: '', content: '' });
      setMessage('WhatsApp campaign created in draft status.');
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to create WhatsApp campaign.');
    }
  };

  const handleLaunchWhatsAppCampaign = async (campaignId) => {
    setError('');
    setMessage('');
    try {
      const res = await adminOperationsApi.launchWhatsAppCampaign(campaignId);
      setMessage(
        `WhatsApp campaign launched: delivered to ${res.sent_count} consented active customers.`
      );
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to launch WhatsApp campaign.');
    }
  };

  const handleCreateTemplate = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    try {
      await adminOperationsApi.createTemplate({
        name: tplForm.name,
        channel: tplForm.channel,
        subject: tplForm.channel === 'email' ? tplForm.subject : null,
        content: tplForm.content,
      });
      setTplForm({ name: '', channel: 'email', subject: '', content: '' });
      setMessage('Reusable message template saved.');
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to create template.');
    }
  };

  const handleDeleteTemplate = async (id) => {
    try {
      await adminOperationsApi.deleteTemplate(id);
      setTemplates((prev) => prev.filter((t) => t.id !== id));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to delete template.');
    }
  };

  const handleQueueCampaign = async (channel, campaignId) => {
    setError('');
    setMessage('');
    try {
      const res = await adminOperationsApi.queueCampaign(channel, campaignId);
      setMessage(
        `${channel === 'email' ? 'Email' : 'WhatsApp'} campaign queued for background worker (${res.targeted_recipients} recipients).`
      );
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to queue campaign.');
    }
  };

  const handleScheduleCampaign = async (channel, campaignId) => {
    setError('');
    setMessage('');
    try {
      await adminOperationsApi.scheduleCampaign(channel, campaignId);
      setMessage('Campaign scheduled for persistent worker execution.');
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to schedule campaign.');
    }
  };

  const handleCancelCampaign = async (channel, campaignId) => {
    setError('');
    setMessage('');
    try {
      await adminOperationsApi.cancelCampaign(channel, campaignId);
      setMessage('Campaign cancelled.');
      loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to cancel campaign.');
    }
  };

  const handleInspectCampaign = async (channel, campaignId) => {
    setError('');
    try {
      const detail = await adminOperationsApi.getCampaignDetail(channel, campaignId);
      setSelectedDetail(detail);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to load campaign delivery details.');
    }
  };

  return (
    <AdminLayout
      title="Marketing Automation & Campaigns"
      subtitle="Persistent background worker queues, consent-verified Email & WhatsApp delivery, and webhook tracking"
    >
      {workerStatus && (
        <div className="mb-6 dv-card p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-[#1F2937]">
            <Activity className="w-4 h-4 text-[#FF6B0A]" />
            <span>Background Campaign Worker Queue</span>
          </div>
          <div className="flex flex-wrap gap-2 text-[11px]">
            <span className="px-2.5 py-1 rounded-full bg-[#FFF6ED] border border-[#E5E7EB] text-[#64748B]">
              Scheduled Campaigns: <strong className="text-[#1F2937]">{workerStatus.scheduled_campaigns}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-full bg-[#FFF6ED] border border-[#E5E7EB] text-[#64748B]">
              Queued Jobs: <strong className="text-[#1F2937]">{workerStatus.queued_jobs}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-full bg-[#FFE9D6] border border-[#FFD4AE] text-[#D94300]">
              Processing: <strong>{workerStatus.processing_jobs}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800">
              Retrying: <strong>{workerStatus.retrying_jobs}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700">
              Workers Recorded: <strong>{workerStatus.workers?.length || 0}</strong>
            </span>
          </div>
        </div>
      )}
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
          {error}
        </div>
      )}
      {message && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs">
          {message}
        </div>
      )}

      {/* Channel Tabs */}
      <div className="flex flex-wrap gap-2 mb-6 border-b border-[#E5E7EB] pb-3">
        <button
          type="button"
          onClick={() => setActiveTab('email')}
          className={`px-4 py-2 rounded-xl text-xs font-medium uppercase tracking-wider inline-flex items-center gap-2 transition ${
            activeTab === 'email'
              ? 'bg-[#FF6B0A] text-white shadow-sm'
              : 'bg-white text-[#243247] border border-[#E5E7EB] hover:border-[#FFD4AE] hover:text-[#FF6B0A]'
          }`}
        >
          <Mail className="w-3.5 h-3.5" />
          <span>Email Campaigns ({emailCampaigns.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('whatsapp')}
          className={`px-4 py-2 rounded-xl text-xs font-medium uppercase tracking-wider inline-flex items-center gap-2 transition ${
            activeTab === 'whatsapp'
              ? 'bg-[#FF6B0A] text-white shadow-sm'
              : 'bg-white text-[#243247] border border-[#E5E7EB] hover:border-[#FFD4AE] hover:text-[#FF6B0A]'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>WhatsApp Campaigns ({whatsappCampaigns.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('templates')}
          className={`px-4 py-2 rounded-xl text-xs font-medium uppercase tracking-wider inline-flex items-center gap-2 transition ${
            activeTab === 'templates'
              ? 'bg-[#FF6B0A] text-white shadow-sm'
              : 'bg-white text-[#243247] border border-[#E5E7EB] hover:border-[#FFD4AE] hover:text-[#FF6B0A]'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Message Templates ({templates.length})</span>
        </button>
      </div>

      {/* EMAIL CAMPAIGNS TAB */}
      {activeTab === 'email' && (
        <div className="space-y-6">
          <form
            onSubmit={handleCreateEmailCampaign}
            className="dv-card p-6 space-y-4"
          >
            <h2 className="text-xs font-semibold text-[#1F2937] uppercase tracking-widest">
              New Email Marketing Campaign (Opt-In Customers Only)
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                  Campaign Name *
                </label>
                <input
                  type="text"
                  required
                  value={emailForm.name}
                  onChange={(e) => setEmailForm({ ...emailForm, name: e.target.value })}
                  placeholder="e.g. Monthly Creator Bundle Drop"
                  className="dv-input px-3 py-2 text-xs"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                  Email Subject *
                </label>
                <input
                  type="text"
                  required
                  value={emailForm.subject}
                  onChange={(e) => setEmailForm({ ...emailForm, subject: e.target.value })}
                  placeholder="e.g. New Digital Toolkits Available on DIGI-VERSE"
                  className="dv-input px-3 py-2 text-xs"
                />
              </div>
            </div>
            <div>
              <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                Campaign Content *
              </label>
              <textarea
                rows={3}
                required
                value={emailForm.content}
                onChange={(e) => setEmailForm({ ...emailForm, content: e.target.value })}
                placeholder="Write promotional email content..."
                className="dv-input px-3 py-2 text-xs"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                className="dv-btn-primary text-xs uppercase tracking-wider px-5 py-2.5 inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create Draft Campaign</span>
              </button>
            </div>
          </form>

          <div className="dv-card divide-y divide-[#E5E7EB]">
            {loading ? (
              <p className="p-6 text-xs text-[#64748B]">Loading email campaigns...</p>
            ) : emailCampaigns.length === 0 ? (
              <p className="p-6 text-xs text-[#64748B]">No email campaigns created yet.</p>
            ) : (
              emailCampaigns.map((c) => (
                <div key={c.id} className="p-5 flex flex-wrap items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-[#1F2937]">{c.name}</span>
                      <span className="text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full bg-[#FFE9D6] border border-[#FFD4AE] text-[#D94300]">
                        {c.status}
                      </span>
                    </div>
                    <p className="text-xs text-[#243247]">Subject: {c.subject}</p>
                    <CampaignMetricsPills c={c} />
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleInspectCampaign('email', c.id)}
                      className="dv-btn-secondary px-3 py-2 text-[11px] uppercase tracking-wider inline-flex items-center gap-1"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Details</span>
                    </button>
                    {['draft', 'failed', 'partially_completed', 'cancelled'].includes(c.status) && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleScheduleCampaign('email', c.id)}
                          className="dv-btn-secondary px-3 py-2 text-[11px] uppercase tracking-wider inline-flex items-center gap-1"
                        >
                          <Clock className="w-3.5 h-3.5 text-[#FF6B0A]" />
                          <span>Schedule</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleQueueCampaign('email', c.id)}
                          className="dv-btn-primary px-3.5 py-2 text-[11px] uppercase tracking-wider inline-flex items-center gap-1"
                        >
                          <Clock className="w-3.5 h-3.5" />
                          <span>Queue Worker</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleLaunchEmailCampaign(c.id)}
                          className="rounded-xl text-[11px] font-medium uppercase tracking-wider px-3.5 py-2 bg-emerald-600 text-white hover:bg-emerald-700 transition inline-flex items-center gap-1"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>Send Now</span>
                        </button>
                      </>
                    )}
                    {['draft', 'scheduled', 'queued'].includes(c.status) && (
                      <button
                        type="button"
                        onClick={() => handleCancelCampaign('email', c.id)}
                        className="rounded-xl px-3 py-2 text-[11px] font-medium uppercase tracking-wider border border-red-200 text-red-600 hover:bg-red-50 transition inline-flex items-center gap-1"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Cancel</span>
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* WHATSAPP CAMPAIGNS TAB */}
      {activeTab === 'whatsapp' && (
        <div className="space-y-6">
          <form
            onSubmit={handleCreateWhatsAppCampaign}
            className="dv-card p-6 space-y-4"
          >
            <h2 className="text-xs font-semibold text-[#1F2937] uppercase tracking-widest">
              New WhatsApp Cloud Campaign (Opt-In Customers Only)
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                  Campaign Name *
                </label>
                <input
                  type="text"
                  required
                  value={waForm.name}
                  onChange={(e) => setWaForm({ ...waForm, name: e.target.value })}
                  placeholder="e.g. Flash Sale WhatsApp Alert"
                  className="dv-input px-3 py-2 text-xs"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                  Approved Meta Template Name *
                </label>
                <input
                  type="text"
                  required
                  value={waForm.approved_template_name}
                  onChange={(e) =>
                    setWaForm({ ...waForm, approved_template_name: e.target.value })
                  }
                  placeholder="e.g. digiverse_flash_sale_v1"
                  className="dv-input px-3 py-2 text-xs"
                />
              </div>
            </div>
            <div>
              <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                Message Content *
              </label>
              <textarea
                rows={3}
                required
                value={waForm.content}
                onChange={(e) => setWaForm({ ...waForm, content: e.target.value })}
                placeholder="WhatsApp template body..."
                className="dv-input px-3 py-2 text-xs"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                className="dv-btn-primary text-xs uppercase tracking-wider px-5 py-2.5 inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create WhatsApp Campaign</span>
              </button>
            </div>
          </form>

          <div className="dv-card divide-y divide-[#E5E7EB]">
            {whatsappCampaigns.length === 0 ? (
              <p className="p-6 text-xs text-[#64748B]">No WhatsApp campaigns created yet.</p>
            ) : (
              whatsappCampaigns.map((c) => (
                <div key={c.id} className="p-5 flex flex-wrap items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-[#1F2937]">{c.name}</span>
                      <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#FFF6ED] border border-[#E5E7EB] text-[#64748B]">
                        {c.approved_template_name}
                      </span>
                      <span className="text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full bg-[#FFE9D6] border border-[#FFD4AE] text-[#D94300]">
                        {c.status}
                      </span>
                    </div>
                    <p className="text-xs text-[#243247]">{c.content}</p>
                    <CampaignMetricsPills c={c} isWhatsApp />
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleInspectCampaign('whatsapp', c.id)}
                      className="dv-btn-secondary px-3 py-2 text-[11px] uppercase tracking-wider inline-flex items-center gap-1"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Details</span>
                    </button>
                    {['draft', 'failed', 'partially_completed', 'cancelled'].includes(c.status) && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleScheduleCampaign('whatsapp', c.id)}
                          className="dv-btn-secondary px-3 py-2 text-[11px] uppercase tracking-wider inline-flex items-center gap-1"
                        >
                          <Clock className="w-3.5 h-3.5 text-[#FF6B0A]" />
                          <span>Schedule</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleQueueCampaign('whatsapp', c.id)}
                          className="dv-btn-primary px-3.5 py-2 text-[11px] uppercase tracking-wider inline-flex items-center gap-1"
                        >
                          <Clock className="w-3.5 h-3.5" />
                          <span>Queue Worker</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleLaunchWhatsAppCampaign(c.id)}
                          className="rounded-xl text-[11px] font-medium uppercase tracking-wider px-3.5 py-2 bg-emerald-600 text-white hover:bg-emerald-700 transition inline-flex items-center gap-1"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>Send Now</span>
                        </button>
                      </>
                    )}
                    {['draft', 'scheduled', 'queued'].includes(c.status) && (
                      <button
                        type="button"
                        onClick={() => handleCancelCampaign('whatsapp', c.id)}
                        className="rounded-xl px-3 py-2 text-[11px] font-medium uppercase tracking-wider border border-red-200 text-red-600 hover:bg-red-50 transition inline-flex items-center gap-1"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Cancel</span>
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* MESSAGE TEMPLATES TAB */}
      {activeTab === 'templates' && (
        <div className="space-y-6">
          <form
            onSubmit={handleCreateTemplate}
            className="dv-card p-6 space-y-4"
          >
            <h2 className="text-xs font-semibold text-[#1F2937] uppercase tracking-widest">
              Create Reusable Message Template
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                  Template Name *
                </label>
                <input
                  type="text"
                  required
                  value={tplForm.name}
                  onChange={(e) => setTplForm({ ...tplForm, name: e.target.value })}
                  className="dv-input px-3 py-2 text-xs"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                  Channel *
                </label>
                <select
                  value={tplForm.channel}
                  onChange={(e) => setTplForm({ ...tplForm, channel: e.target.value })}
                  className="dv-input px-3 py-2 text-xs"
                >
                  <option value="email">Email</option>
                  <option value="whatsapp">WhatsApp</option>
                </select>
              </div>
              {tplForm.channel === 'email' && (
                <div>
                  <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                    Email Subject *
                  </label>
                  <input
                    type="text"
                    required
                    value={tplForm.subject}
                    onChange={(e) => setTplForm({ ...tplForm, subject: e.target.value })}
                    className="dv-input px-3 py-2 text-xs"
                  />
                </div>
              )}
            </div>
            <div>
              <label className="block text-[11px] font-medium uppercase tracking-wider text-[#64748B] mb-1">
                Template Body *
              </label>
              <textarea
                rows={3}
                required
                value={tplForm.content}
                onChange={(e) => setTplForm({ ...tplForm, content: e.target.value })}
                className="dv-input px-3 py-2 text-xs"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                className="dv-btn-primary text-xs uppercase tracking-wider px-5 py-2.5 inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Save Template</span>
              </button>
            </div>
          </form>

          <div className="dv-card divide-y divide-[#E5E7EB]">
            {templates.length === 0 ? (
              <p className="p-6 text-xs text-[#64748B]">No reusable message templates saved yet.</p>
            ) : (
              templates.map((t) => (
                <div key={t.id} className="p-5 flex items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-[#1F2937]">{t.name}</span>
                      <span className="text-[10px] uppercase tracking-wider font-medium px-2.5 py-0.5 rounded-full bg-[#FFE9D6] border border-[#FFD4AE] text-[#D94300]">
                        {t.channel}
                      </span>
                    </div>
                    {t.subject && <p className="text-xs text-[#243247]">Subject: {t.subject}</p>}
                    <p className="text-xs text-[#64748B]">{t.content}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteTemplate(t.id)}
                    className="p-2 rounded-lg border border-red-200 bg-white text-red-600 hover:bg-red-50 transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* CAMPAIGN DELIVERY DETAIL MODAL */}
      {selectedDetail && (
        <div className="fixed inset-0 z-50 bg-[#1F2937]/30 backdrop-blur-[2px] flex items-center justify-center p-4">
          <div className="bg-white border border-[#FFD4AE] rounded-2xl shadow-xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden">
            <div className="p-5 border-b border-[#E5E7EB] bg-[#FFF6ED] flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-[#1F2937]">{selectedDetail.name}</h3>
                <p className="text-[11px] text-[#64748B] uppercase tracking-wider">
                  {selectedDetail.channel} · Status: {selectedDetail.status}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDetail(null)}
                className="dv-btn-secondary px-3 py-1.5 text-xs"
              >
                Close
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4">
              <CampaignMetricsPills
                c={selectedDetail}
                isWhatsApp={selectedDetail.channel === 'whatsapp'}
              />

              {Object.keys(selectedDetail.failure_summary || {}).length > 0 && (
                <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-xs space-y-1">
                  <p className="font-semibold text-red-700">Failure Code Summary</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(selectedDetail.failure_summary).map(([code, cnt]) => (
                      <span
                        key={code}
                        className="px-2 py-0.5 rounded-full bg-white border border-red-200 font-mono text-[11px] text-red-700"
                      >
                        {code}: {cnt}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="border border-[#E5E7EB] rounded-xl overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="bg-[#FFF6ED] border-b border-[#E5E7EB] text-[#64748B] uppercase">
                      <th className="py-2.5 px-3 font-semibold">Recipient</th>
                      <th className="py-2.5 px-3 font-semibold">Status</th>
                      <th className="py-2.5 px-3 font-semibold">Attempts</th>
                      <th className="py-2.5 px-3 font-semibold">Message ID</th>
                      <th className="py-2.5 px-3 font-semibold">Failure Detail</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB]">
                    {(selectedDetail.recipients || []).length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-[#64748B]">
                          No delivery records materialized yet.
                        </td>
                      </tr>
                    ) : (
                      selectedDetail.recipients.map((rec) => (
                        <tr key={rec.id}>
                          <td className="py-2.5 px-3 font-medium text-[#1F2937]">
                            {rec.customer_email || rec.customer_id}
                          </td>
                          <td className="py-2.5 px-3 uppercase font-mono text-[11px] text-[#D94300]">
                            {rec.delivery_status}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[#64748B]">
                            {rec.attempt_count}/{rec.max_attempts}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[11px] text-[#64748B]">
                            {rec.provider_message_id || '—'}
                          </td>
                          <td className="py-2.5 px-3 text-[11px] text-red-600 max-w-xs truncate">
                            {rec.failure_reason || '—'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
};

export default AdminMarketingPage;
