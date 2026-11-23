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
    <span className="px-2 py-0.5 rounded-full bg-[#18243A] border border-[#E5E7EB] text-[#94A3B8]">
      Targeted: <strong className="text-[#F1F5F9]">{c.recipient_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-[#18243A] border border-[#E5E7EB] text-[#94A3B8]">
      Queued: <strong className="text-[#F1F5F9]">{c.queued_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-[#18243A] border border-[#BFDBFE] text-[#93C5FD]">
      Processing: <strong>{c.processing_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-amber-950/50 border border-amber-200 text-amber-300">
      Retrying: <strong>{c.retrying_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-sky-950/50 border border-sky-200 text-sky-300">
      Accepted: <strong>{c.accepted_count ?? 0}</strong>
    </span>
    <span className="px-2 py-0.5 rounded-full bg-emerald-950/50 border border-emerald-200 text-emerald-300">
      Delivered: <strong>{c.delivered_count ?? 0}</strong>
    </span>
    {isWhatsApp && (
      <span className="px-2 py-0.5 rounded-full bg-emerald-950/50 border border-emerald-200 text-emerald-300">
        Read: <strong>{c.read_count ?? 0}</strong>
      </span>
    )}
    <span className="px-2 py-0.5 rounded-full bg-red-950/50 border border-red-200 text-red-300">
      Failed/Bounced: <strong>{c.failed_count ?? 0}</strong>
    </span>
    {(c.unresolved_count ?? 0) > 0 && (
      <span className="px-2 py-0.5 rounded-full bg-amber-950/70 border border-amber-300 text-amber-200">
        Unresolved Timeout: <strong>{c.unresolved_count}</strong>
      </span>
    )}
    <span className="px-2 py-0.5 rounded-full bg-[#18243A] border border-[#E5E7EB] text-[#94A3B8]">
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
          <div className="flex items-center gap-2 text-xs font-semibold text-[#F1F5F9]">
            <Activity className="w-4 h-4 text-[#60A5FA]" />
            <span>Background Campaign Worker Queue</span>
          </div>
          <div className="flex flex-wrap gap-2 text-[11px]">
            <span className="px-2.5 py-1 rounded-full bg-[#18243A] border border-[#E5E7EB] text-[#94A3B8]">
              Scheduled Campaigns: <strong className="text-[#F1F5F9]">{workerStatus.scheduled_campaigns}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-full bg-[#18243A] border border-[#E5E7EB] text-[#94A3B8]">
              Queued Jobs: <strong className="text-[#F1F5F9]">{workerStatus.queued_jobs}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-full bg-[#18243A] border border-[#BFDBFE] text-[#93C5FD]">
              Processing: <strong>{workerStatus.processing_jobs}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-full bg-amber-950/50 border border-amber-200 text-amber-300">
              Retrying: <strong>{workerStatus.retrying_jobs}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-full bg-emerald-950/50 border border-emerald-200 text-emerald-300">
              Workers Recorded: <strong>{workerStatus.workers?.length || 0}</strong>
            </span>
          </div>
        </div>
      )}
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-950/50 border border-red-200 text-red-300 text-xs">
          {error}
        </div>
      )}
      {message && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-950/50 border border-emerald-200 text-emerald-300 text-xs">
          {message}
        </div>
      )}

      {/* Channel Tabs */}
      <div className="flex flex-wrap gap-2 mb-6 border-b border-[#D5DEE8] pb-3">
        <button
          type="button"
          onClick={() => setActiveTab('email')}
          className={`px-4 py-2 rounded-lg text-[12.5px] font-semibold inline-flex items-center gap-2 transition ${
            activeTab === 'email'
              ? 'bg-[#2563EB] text-white shadow-xs'
              : 'bg-[#111C30] text-[#F1F5F9] border border-[#D5DEE8] hover:border-[#93C5FD] hover:text-[#60A5FA]'
          }`}
        >
          <Mail className="w-3.5 h-3.5" />
          <span>Email Campaigns ({emailCampaigns.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('whatsapp')}
          className={`px-4 py-2 rounded-lg text-[12.5px] font-semibold inline-flex items-center gap-2 transition ${
            activeTab === 'whatsapp'
              ? 'bg-[#2563EB] text-white shadow-xs'
              : 'bg-[#111C30] text-[#F1F5F9] border border-[#D5DEE8] hover:border-[#93C5FD] hover:text-[#60A5FA]'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>WhatsApp Campaigns ({whatsappCampaigns.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('templates')}
          className={`px-4 py-2 rounded-lg text-[12.5px] font-semibold inline-flex items-center gap-2 transition ${
            activeTab === 'templates'
              ? 'bg-[#2563EB] text-white shadow-xs'
              : 'bg-[#111C30] text-[#F1F5F9] border border-[#D5DEE8] hover:border-[#93C5FD] hover:text-[#60A5FA]'
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
            className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-6 space-y-4 shadow-2xs"
          >
            <h2 className="text-[14.5px] font-semibold text-[#F1F5F9]">
              New Email Marketing Campaign (Opt-In Customers Only)
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
                  Campaign Name *
                </label>
                <input
                  type="text"
                  required
                  value={emailForm.name}
                  onChange={(e) => setEmailForm({ ...emailForm, name: e.target.value })}
                  placeholder="e.g. Monthly Creator Bundle Drop"
                  className="dv-input px-3.5 py-2 text-[13px]"
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
                  Email Subject *
                </label>
                <input
                  type="text"
                  required
                  value={emailForm.subject}
                  onChange={(e) => setEmailForm({ ...emailForm, subject: e.target.value })}
                  placeholder="e.g. New Digital Toolkits Available on DIGI-VERSE"
                  className="dv-input px-3.5 py-2 text-[13px]"
                />
              </div>
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
                Campaign Content *
              </label>
              <textarea
                rows={3}
                required
                value={emailForm.content}
                onChange={(e) => setEmailForm({ ...emailForm, content: e.target.value })}
                placeholder="Write promotional email content..."
                className="dv-input px-3.5 py-2 text-[13px]"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                className="dv-btn-primary text-[12px] font-semibold px-5 py-2 inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create Draft Campaign</span>
              </button>
            </div>
          </form>

          <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl divide-y divide-[#E5E7EB] shadow-2xs overflow-hidden">
            {loading ? (
              <p className="p-6 text-[13px] text-[#94A3B8]">Loading email campaigns...</p>
            ) : emailCampaigns.length === 0 ? (
              <p className="p-6 text-[13px] text-[#94A3B8]">No email campaigns created yet.</p>
            ) : (
              emailCampaigns.map((c) => (
                <div key={c.id} className="p-5 flex flex-wrap items-center justify-between gap-4 hover:bg-[#18243A]/50 transition">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] font-semibold text-[#F1F5F9]">{c.name}</span>
                      <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-[#18243A] border border-[#BFDBFE] text-[#93C5FD] capitalize">
                        {String(c.status || '').replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="text-[12.5px] text-[#CBD5E1]">Subject: {c.subject}</p>
                    <CampaignMetricsPills c={c} />
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleInspectCampaign('email', c.id)}
                      className="dv-btn-secondary px-3 py-1.5 text-[12px] font-medium inline-flex items-center gap-1.5"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Details</span>
                    </button>
                    {['draft', 'failed', 'partially_completed', 'cancelled'].includes(c.status) && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleScheduleCampaign('email', c.id)}
                          className="dv-btn-secondary px-3 py-1.5 text-[12px] font-medium inline-flex items-center gap-1.5"
                        >
                          <Clock className="w-3.5 h-3.5 text-[#60A5FA]" />
                          <span>Schedule</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleQueueCampaign('email', c.id)}
                          className="dv-btn-primary px-3.5 py-1.5 text-[12px] font-semibold inline-flex items-center gap-1.5"
                        >
                          <Clock className="w-3.5 h-3.5" />
                          <span>Queue Worker</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleLaunchEmailCampaign(c.id)}
                          className="rounded-xl text-[12px] font-semibold px-3.5 py-1.5 bg-[#16A34A] text-white hover:bg-[#15803D] transition inline-flex items-center gap-1.5"
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
                        className="rounded-xl px-3 py-1.5 text-[12px] font-medium border border-red-200 text-red-300 hover:bg-red-950/60 transition inline-flex items-center gap-1.5"
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
            className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-6 space-y-4 shadow-2xs"
          >
            <h2 className="text-[14.5px] font-semibold text-[#F1F5F9]">
              New WhatsApp Cloud Campaign (Opt-In Customers Only)
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
                  Campaign Name *
                </label>
                <input
                  type="text"
                  required
                  value={waForm.name}
                  onChange={(e) => setWaForm({ ...waForm, name: e.target.value })}
                  placeholder="e.g. Flash Sale WhatsApp Alert"
                  className="dv-input px-3.5 py-2 text-[13px]"
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
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
                  className="dv-input px-3.5 py-2 text-[13px]"
                />
              </div>
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
                Message Content *
              </label>
              <textarea
                rows={3}
                required
                value={waForm.content}
                onChange={(e) => setWaForm({ ...waForm, content: e.target.value })}
                placeholder="WhatsApp template body..."
                className="dv-input px-3.5 py-2 text-[13px]"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                className="dv-btn-primary text-[12px] font-semibold px-5 py-2 inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create WhatsApp Campaign</span>
              </button>
            </div>
          </form>

          <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl divide-y divide-[#E5E7EB] shadow-2xs overflow-hidden">
            {whatsappCampaigns.length === 0 ? (
              <p className="p-6 text-[13px] text-[#94A3B8]">No WhatsApp campaigns created yet.</p>
            ) : (
              whatsappCampaigns.map((c) => (
                <div key={c.id} className="p-5 flex flex-wrap items-center justify-between gap-4 hover:bg-[#18243A]/50 transition">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[14px] font-semibold text-[#F1F5F9]">{c.name}</span>
                      <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-[#18243A] border border-[#D5DEE8] text-[#CBD5E1]">
                        {c.approved_template_name}
                      </span>
                      <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-[#18243A] border border-[#BFDBFE] text-[#93C5FD] capitalize">
                        {String(c.status || '').replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="text-[12.5px] text-[#CBD5E1]">{c.content}</p>
                    <CampaignMetricsPills c={c} isWhatsApp />
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleInspectCampaign('whatsapp', c.id)}
                      className="dv-btn-secondary px-3 py-1.5 text-[12px] font-medium inline-flex items-center gap-1.5"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Details</span>
                    </button>
                    {['draft', 'failed', 'partially_completed', 'cancelled'].includes(c.status) && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleScheduleCampaign('whatsapp', c.id)}
                          className="dv-btn-secondary px-3 py-1.5 text-[12px] font-medium inline-flex items-center gap-1.5"
                        >
                          <Clock className="w-3.5 h-3.5 text-[#60A5FA]" />
                          <span>Schedule</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleQueueCampaign('whatsapp', c.id)}
                          className="dv-btn-primary px-3.5 py-1.5 text-[12px] font-semibold inline-flex items-center gap-1.5"
                        >
                          <Clock className="w-3.5 h-3.5" />
                          <span>Queue Worker</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleLaunchWhatsAppCampaign(c.id)}
                          className="rounded-xl text-[12px] font-semibold px-3.5 py-1.5 bg-[#16A34A] text-white hover:bg-[#15803D] transition inline-flex items-center gap-1.5"
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
                        className="rounded-xl px-3 py-1.5 text-[12px] font-medium border border-red-200 text-red-300 hover:bg-red-950/60 transition inline-flex items-center gap-1.5"
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
            className="bg-[#111C30] border border-[#D5DEE8] rounded-xl p-6 space-y-4 shadow-2xs"
          >
            <h2 className="text-[14.5px] font-semibold text-[#F1F5F9]">
              Create Reusable Message Template
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
                  Template Name *
                </label>
                <input
                  type="text"
                  required
                  value={tplForm.name}
                  onChange={(e) => setTplForm({ ...tplForm, name: e.target.value })}
                  className="dv-input px-3.5 py-2 text-[13px]"
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
                  Channel *
                </label>
                <select
                  value={tplForm.channel}
                  onChange={(e) => setTplForm({ ...tplForm, channel: e.target.value })}
                  className="dv-input px-3.5 py-2 text-[13px]"
                >
                  <option value="email">Email</option>
                  <option value="whatsapp">WhatsApp</option>
                </select>
              </div>
              {tplForm.channel === 'email' && (
                <div>
                  <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
                    Email Subject *
                  </label>
                  <input
                    type="text"
                    required
                    value={tplForm.subject}
                    onChange={(e) => setTplForm({ ...tplForm, subject: e.target.value })}
                    className="dv-input px-3.5 py-2 text-[13px]"
                  />
                </div>
              )}
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[#F1F5F9] mb-1.5">
                Template Body *
              </label>
              <textarea
                rows={3}
                required
                value={tplForm.content}
                onChange={(e) => setTplForm({ ...tplForm, content: e.target.value })}
                className="dv-input px-3.5 py-2 text-[13px]"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                className="dv-btn-primary text-[12px] font-semibold px-5 py-2 inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Save Template</span>
              </button>
            </div>
          </form>

          <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl divide-y divide-[#E5E7EB] shadow-2xs overflow-hidden">
            {templates.length === 0 ? (
              <p className="p-6 text-[13px] text-[#94A3B8]">No reusable message templates saved yet.</p>
            ) : (
              templates.map((t) => (
                <div key={t.id} className="p-5 flex items-center justify-between gap-4 hover:bg-[#18243A]/50 transition">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] font-semibold text-[#F1F5F9]">{t.name}</span>
                      <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-[#18243A] border border-[#BFDBFE] text-[#93C5FD] capitalize">
                        {t.channel}
                      </span>
                    </div>
                    {t.subject && <p className="text-[12.5px] text-[#F1F5F9]">Subject: {t.subject}</p>}
                    <p className="text-[12.5px] text-[#94A3B8]">{t.content}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteTemplate(t.id)}
                    className="p-2 rounded-lg border border-red-200 bg-[#111C30] text-red-300 hover:bg-red-950/60 transition"
                    aria-label={`Delete template ${t.name}`}
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
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-[#080D19]/70 backdrop-blur-[2px] flex items-center justify-center p-4"
        >
          <div className="bg-[#111C30] border border-[#D5DEE8] rounded-xl shadow-xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden">
            <div className="p-5 border-b border-[#E5E7EB] bg-[#18243A] flex items-center justify-between">
              <div>
                <h3 className="text-[15px] font-semibold text-[#F1F5F9]">{selectedDetail.name}</h3>
                <p className="text-[12px] text-[#94A3B8] capitalize">
                  {selectedDetail.channel} · Status: {String(selectedDetail.status || '').replace(/_/g, ' ')}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDetail(null)}
                className="dv-btn-secondary px-3 py-1.5 text-[12px]"
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
                <div className="p-3.5 rounded-lg bg-red-950/50 border border-red-200 text-[12px] space-y-1">
                  <p className="font-semibold text-red-300">Failure Code Summary</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(selectedDetail.failure_summary).map(([code, cnt]) => (
                      <span
                        key={code}
                        className="px-2 py-0.5 rounded-full bg-[#111C30] border border-red-200 font-mono text-[11px] text-red-300"
                      >
                        {code}: {cnt}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="border border-[#D5DEE8] rounded-lg overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#18243A] border-b border-[#D5DEE8] text-[#CBD5E1] text-[11.5px] font-semibold">
                      <th className="py-2.5 px-3">Recipient</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Attempts</th>
                      <th className="py-2.5 px-3">Message ID</th>
                      <th className="py-2.5 px-3">Failure Detail</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB] text-[12.5px]">
                    {(selectedDetail.recipients || []).length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-[#94A3B8]">
                          No delivery records materialized yet.
                        </td>
                      </tr>
                    ) : (
                      selectedDetail.recipients.map((rec) => (
                        <tr key={rec.id}>
                          <td className="py-2.5 px-3 font-medium text-[#F1F5F9]">
                            {rec.customer_email || rec.customer_id}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[11.5px] text-[#93C5FD] capitalize">
                            {rec.delivery_status}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[#94A3B8]">
                            {rec.attempt_count}/{rec.max_attempts}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[11px] text-[#94A3B8]">
                            {rec.provider_message_id || '—'}
                          </td>
                          <td className="py-2.5 px-3 text-[11.5px] text-red-300 max-w-xs truncate">
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
