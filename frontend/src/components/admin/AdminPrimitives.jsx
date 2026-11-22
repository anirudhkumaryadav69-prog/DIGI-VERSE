import { Link } from 'react-router-dom';
import { ArrowUpRight, X } from 'lucide-react';

const STATUS_STYLE_MAP = {
  // Emerald: positive, verified, completed
  active: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  approved: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  paid: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  captured: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  completed: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  verified: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  published: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  confirmed: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  fulfilled: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  delivered: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  consistent: 'bg-emerald-50 text-[#15803D] border-emerald-200',
  resolved: 'bg-emerald-50 text-[#15803D] border-emerald-200',

  // Amber: awaiting review, warning, retrying
  pending: 'bg-amber-50 text-[#B45309] border-amber-200',
  requested: 'bg-amber-50 text-[#B45309] border-amber-200',
  under_review: 'bg-amber-50 text-[#B45309] border-amber-200',
  submitted: 'bg-amber-50 text-[#B45309] border-amber-200',
  retrying: 'bg-amber-50 text-[#B45309] border-amber-200',
  requires_manual_review: 'bg-amber-50 text-[#B45309] border-amber-200',
  investigating: 'bg-amber-50 text-[#B45309] border-amber-200',

  // Red: error, rejected, failed, suspended
  rejected: 'bg-red-50 text-[#DC2626] border-red-200',
  failed: 'bg-red-50 text-[#DC2626] border-red-200',
  uncertain: 'bg-red-50 text-[#DC2626] border-red-200',
  suspended: 'bg-red-50 text-[#DC2626] border-red-200',
  deactivated: 'bg-red-50 text-[#DC2626] border-red-200',
  cancelled: 'bg-red-50 text-[#DC2626] border-red-200',
  refunded: 'bg-red-50 text-[#DC2626] border-red-200',
  settlement_missing: 'bg-red-50 text-[#DC2626] border-red-200',
  unexpected_settlement: 'bg-red-50 text-[#DC2626] border-red-200',
  duplicate_settlement: 'bg-red-50 text-[#DC2626] border-red-200',
  ledger_mismatch: 'bg-red-50 text-[#DC2626] border-red-200',
  status_mismatch: 'bg-red-50 text-[#DC2626] border-red-200',

  // Blue: active processing, informational
  processing: 'bg-[#EAF4FC] text-[#1D4ED8] border-[#BFDBFE]',
  accepted: 'bg-[#EAF4FC] text-[#1D4ED8] border-[#BFDBFE]',
  queued: 'bg-[#EAF4FC] text-[#1D4ED8] border-[#BFDBFE]',
  draft: 'bg-[#EAF4FC] text-[#1D4ED8] border-[#BFDBFE]',
};

export const formatAdminStatusLabel = (status) => {
  if (!status) return 'Unknown';
  return String(status)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

export const formatAdminDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
};

export const AdminStatusBadge = ({ status, label, className = '' }) => {
  const key = String(status || '').toLowerCase();
  const styles =
    STATUS_STYLE_MAP[key] || 'bg-[#F8FAFC] text-[#475569] border-[#D5DEE8]';
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium leading-tight whitespace-nowrap ${styles} ${className}`}
    >
      {label || formatAdminStatusLabel(status)}
    </span>
  );
};

export const AdminSectionHeader = ({ icon: Icon, title, subtitle, badge, action }) => (
  <div className="flex flex-wrap items-center justify-between gap-3">
    <div className="flex items-center gap-2.5 min-w-0">
      {Icon && (
        <div className="w-8 h-8 rounded-lg bg-[#EAF4FC] border border-[#BFDBFE] text-[#2563EB] flex items-center justify-center shrink-0">
          <Icon className="w-4 h-4" aria-hidden="true" />
        </div>
      )}
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-[#263445]">{title}</h2>
          {badge}
        </div>
        {subtitle && <p className="text-[12px] text-[#64748B] mt-0.5">{subtitle}</p>}
      </div>
    </div>
    {action && <div className="shrink-0">{action}</div>}
  </div>
);

export const AdminKpiCard = ({
  label,
  value,
  icon: Icon,
  hint,
  tone = 'blue',
  to,
  compact = false,
}) => {
  const toneClasses = {
    blue: 'bg-[#EAF4FC] border-[#BFDBFE] text-[#2563EB]',
    success: 'bg-emerald-50 border-emerald-200 text-[#16A34A]',
    warning: 'bg-amber-50 border-amber-200 text-[#D97706]',
    neutral: 'bg-[#F8FAFC] border-[#D5DEE8] text-[#475569]',
  };

  const inner = (
    <div
      className={`bg-white border border-[#D5DEE8] rounded-xl shadow-2xs transition ${
        to ? 'hover:border-[#93C5FD] hover:bg-[#EDF5FC]/35' : ''
      } ${compact ? 'p-4' : 'p-5'}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[12px] font-medium text-[#64748B] truncate">{label}</p>
          <p
            className={`font-bold tracking-tight text-[#263445] tabular-nums mt-1.5 ${
              compact ? 'text-[20px] leading-snug' : 'text-[24px] leading-tight'
            }`}
          >
            {value}
          </p>
          {hint && <p className="text-[11.5px] text-[#64748B] mt-1">{hint}</p>}
        </div>
        {Icon && (
          <div
            className={`rounded-lg border flex items-center justify-center shrink-0 ${
              compact ? 'w-8 h-8' : 'w-10 h-10'
            } ${toneClasses[tone] || toneClasses.blue}`}
          >
            <Icon className="w-4 h-4" aria-hidden="true" />
          </div>
        )}
      </div>
      {to && (
        <div className="mt-3 pt-2.5 border-t border-[#E5E7EB] flex items-center justify-between text-[11.5px] font-medium text-[#2563EB]">
          <span>Review queue</span>
          <ArrowUpRight className="w-3.5 h-3.5" aria-hidden="true" />
        </div>
      )}
    </div>
  );

  if (to) {
    return (
      <Link to={to} className="block focus-visible:outline-2 focus-visible:outline-[#2563EB] rounded-xl">
        {inner}
      </Link>
    );
  }
  return inner;
};

export const AdminReasonModal = ({
  open,
  title,
  description,
  label = 'Administrative reason',
  placeholder = 'Provide a clear reason for the audit log...',
  value,
  onChange,
  confirmLabel = 'Confirm action',
  variant = 'danger',
  busy = false,
  onConfirm,
  onClose,
}) => {
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="admin-reason-modal-title"
      className="fixed inset-0 z-50 bg-[#263445]/35 backdrop-blur-[2px] flex items-center justify-center p-4"
    >
      <div className="bg-white border border-[#D5DEE8] rounded-xl max-w-md w-full p-6 space-y-4 shadow-lg">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3
              id="admin-reason-modal-title"
              className="text-[15px] font-semibold text-[#263445]"
            >
              {title}
            </h3>
            {description && (
              <p className="text-[12.5px] text-[#64748B] mt-1 leading-relaxed">{description}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="p-1 rounded-lg text-[#64748B] hover:text-[#263445] hover:bg-[#EDF5FC]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div>
          <label
            htmlFor="admin-reason-textarea"
            className="block text-[12px] font-medium text-[#263445] mb-1.5"
          >
            {label}
          </label>
          <textarea
            id="admin-reason-textarea"
            rows={3}
            required
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className="dv-input px-3.5 py-2.5 text-[13px]"
          />
        </div>

        <div className="flex justify-end gap-2.5 pt-2">
          <button
            type="button"
            disabled={busy}
            onClick={onClose}
            className="dv-btn-secondary px-4 py-2 text-[12px] font-medium"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy || !String(value || '').trim()}
            onClick={onConfirm}
            className={`px-4 py-2 rounded-xl text-[12px] font-semibold text-white transition disabled:opacity-45 ${
              variant === 'danger'
                ? 'bg-[#DC2626] hover:bg-red-700'
                : 'bg-[#2563EB] hover:bg-[#1D4ED8]'
            }`}
          >
            {busy ? 'Saving...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
