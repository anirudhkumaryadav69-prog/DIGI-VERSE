import { useEffect } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Info,
  RefreshCw,
  X,
} from 'lucide-react';

/**
 * Format numeric/decimal INR values consistently across the storefront.
 */
export const formatINR = (val) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(val || 0));

/**
 * Set document title, meta description, and canonical link for SEO.
 */
export const useDocumentMeta = ({ title, description, canonicalPath }) => {
  useEffect(() => {
    const fullTitle = title ? `${title} — DIGI-VERSE` : 'DIGI-VERSE — Curated Digital Marketplace';
    document.title = fullTitle;

    if (description) {
      let metaDesc = document.querySelector('meta[name="description"]');
      if (!metaDesc) {
        metaDesc = document.createElement('meta');
        metaDesc.setAttribute('name', 'description');
        document.head.appendChild(metaDesc);
      }
      metaDesc.setAttribute('content', description);
    }

    if (canonicalPath && typeof window !== 'undefined') {
      let canonical = document.querySelector('link[rel="canonical"]');
      if (!canonical) {
        canonical = document.createElement('link');
        canonical.setAttribute('rel', 'canonical');
        document.head.appendChild(canonical);
      }
      canonical.setAttribute('href', `${window.location.origin}${canonicalPath}`);
    }
  }, [title, description, canonicalPath]);
};

/**
 * Reusable Button component following the DIGI-VERSE Light Blue & Slate design system.
 */
export const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  type = 'button',
  disabled = false,
  className = '',
  onClick,
  ...rest
}) => {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-xl font-semibold tracking-wide transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2563EB] disabled:opacity-45 disabled:cursor-not-allowed';

  const variants = {
    primary: 'dv-btn-primary',
    accent:
      'bg-[#0EA5E9] text-white hover:bg-[#0284C7] border border-[#0EA5E9] rounded-xl shadow-xs',
    secondary: 'dv-btn-secondary',
    outline:
      'bg-white text-[#263445] border border-[#D5DEE8] hover:border-[#93C5FD] hover:bg-[#EDF5FC] hover:text-[#1D4ED8] rounded-xl',
    danger:
      'bg-white text-[#DC2626] border border-red-200 hover:border-[#DC2626] hover:bg-red-50 rounded-xl',
    ghost:
      'bg-transparent text-[#2563EB] hover:text-[#1D4ED8] underline-offset-4 hover:underline rounded-xl',
  };

  const sizes = {
    sm: 'text-xs px-3.5 py-2',
    md: 'text-xs px-5 py-2.5',
    lg: 'text-sm px-6 py-3.5',
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`${base} ${variants[variant] || variants.primary} ${sizes[size] || sizes.md} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
};

/**
 * Reusable accessible Input component with label, optional helper text, and error state.
 */
export const Input = ({
  id,
  label,
  error,
  helperText,
  icon: Icon,
  className = '',
  containerClassName = '',
  ...props
}) => {
  return (
    <div className={containerClassName}>
      {label && (
        <label
          htmlFor={id}
          className="block text-xs font-medium text-[#263445] mb-1.5"
        >
          {label}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <Icon
            className="w-4 h-4 text-[#64748B] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
            aria-hidden="true"
          />
        )}
        <input
          id={id}
          className={`dv-input ${
            error ? 'border-[#DC2626] focus:border-[#DC2626]' : ''
          } ${
            Icon ? 'pl-10' : 'pl-3.5'
          } pr-3.5 py-2.5 text-sm text-[#263445] placeholder:text-[#94A3B8] disabled:bg-[#F8FAFC] disabled:text-[#94A3B8] ${className}`}
          {...props}
        />
      </div>
      {helperText && !error && <p className="mt-1 text-[11px] text-[#64748B]">{helperText}</p>}
      {error && (
        <p role="alert" className="mt-1 text-[11px] text-[#DC2626]">
          {error}
        </p>
      )}
    </div>
  );
};

/**
 * Reusable Badge component.
 */
export const Badge = ({ children, variant = 'neutral', className = '' }) => {
  const styles = {
    neutral: 'bg-[#F8FAFC] text-[#263445] border-[#D5DEE8]',
    accent: 'bg-[#EAF4FC] text-[#1D4ED8] border-[#BFDBFE]',
    dark: 'bg-[#2563EB] text-white border-[#2563EB]',
    success: 'bg-emerald-50 text-[#16A34A] border-emerald-200',
    warning: 'bg-amber-50 text-[#D97706] border-amber-200',
    danger: 'bg-red-50 text-[#DC2626] border-red-200',
  };

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full text-[11px] font-medium px-2.5 py-0.5 border ${
        styles[variant] || styles.neutral
      } ${className}`}
    >
      {children}
    </span>
  );
};

/**
 * Reusable SectionHeading component.
 */
export const SectionHeading = ({ eyebrow, title, subtitle, action, className = '' }) => (
  <div
    className={`flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8 ${className}`}
  >
    <div>
      {eyebrow && (
        <p className="text-[12px] tracking-[0.02em] text-[#2563EB] font-semibold mb-1.5">
          {eyebrow}
        </p>
      )}
      <h2 className="text-[26px] sm:text-[32px] leading-[1.2] font-bold tracking-tight text-[#263445]">
        {title}
      </h2>
      {subtitle && (
        <p className="text-[15px] leading-relaxed text-[#64748B] mt-2 max-w-2xl">{subtitle}</p>
      )}
    </div>
    {action && <div className="shrink-0">{action}</div>}
  </div>
);

/**
 * Reusable LoadingState & ProductCardSkeleton components.
 */
export const LoadingState = ({ label = 'Loading...' }) => (
  <div
    role="status"
    aria-live="polite"
    className="py-16 text-center flex flex-col items-center justify-center gap-3"
  >
    <div className="w-7 h-7 border-2 border-[#DCE6EF] border-t-[#2563EB] rounded-full animate-spin" />
    <span className="text-xs font-medium text-[#64748B]">{label}</span>
  </div>
);

export const ProductCardSkeleton = ({
  count = 6,
  gridClassName = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6',
}) => (
  <div
    role="status"
    aria-label="Loading products"
    className={gridClassName}
  >
    {Array.from({ length: count }).map((_, i) => (
      <div
        key={i}
        className="dv-card overflow-hidden animate-pulse"
      >
        <div className="aspect-16/10 bg-[#DCE6EF] border-b border-[#E5E7EB]" />
        <div className="p-5 space-y-3">
          <div className="h-3 bg-[#DCE6EF] rounded w-1/3" />
          <div className="h-5 bg-[#EDF5FC] rounded w-3/4" />
          <div className="h-3 bg-[#F8FAFC] rounded w-full" />
        </div>
        <div className="px-5 py-4 border-t border-[#E5E7EB] flex justify-between items-center">
          <div className="h-5 bg-[#DCE6EF] rounded w-20" />
          <div className="h-9 bg-[#EDF5FC] rounded-xl w-24" />
        </div>
      </div>
    ))}
  </div>
);

/**
 * Reusable EmptyState component.
 */
export const EmptyState = ({ icon: Icon, title, description, action }) => (
  <div className="dv-card p-10 md:p-14 text-center max-w-2xl mx-auto space-y-4">
    {Icon && (
      <div className="w-12 h-12 mx-auto rounded-2xl bg-[#EAF4FC] border border-[#D5DEE8] flex items-center justify-center text-[#2563EB]">
        <Icon className="w-5 h-5" aria-hidden="true" />
      </div>
    )}
    <h3 className="text-lg font-semibold text-[#263445]">{title}</h3>
    {description && <p className="text-sm text-[#64748B] leading-relaxed max-w-md mx-auto">{description}</p>}
    {action && <div className="pt-2">{action}</div>}
  </div>
);

/**
 * Reusable ErrorAlert component with optional retry button.
 */
export const ErrorAlert = ({ message, onRetry, className = '' }) => {
  if (!message) return null;
  return (
    <div
      role="alert"
      className={`p-4 rounded-xl bg-red-50 border border-red-200 text-[#DC2626] text-xs flex flex-wrap items-center justify-between gap-3 ${className}`}
    >
      <div className="flex items-start gap-2.5">
        <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-[#DC2626]" aria-hidden="true" />
        <span>{message}</span>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-white border border-red-200 text-[#DC2626] hover:bg-red-100 transition"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};

/**
 * Reusable ToastBanner notification component.
 */
export const ToastBanner = ({ toast, type, message, onDismiss, className = '' }) => {
  const resolved = toast?.message ? toast : message ? { type: type || 'info', message } : null;
  if (!resolved) return null;
  const isError = resolved.type === 'error';
  const isInfo = resolved.type === 'info';

  return (
    <div
      role={isError ? 'alert' : 'status'}
      aria-live="polite"
      className={`p-3.5 rounded-xl border text-xs flex items-center justify-between gap-3 shadow-xs ${
        isError
          ? 'bg-red-50 border-red-200 text-[#DC2626]'
          : isInfo
          ? 'bg-[#EAF4FC] border-[#BFDBFE] text-[#1D4ED8]'
          : 'bg-emerald-50 border-emerald-200 text-[#16A34A]'
      } ${className}`}
    >
      <div className="flex items-center gap-2.5">
        {isError ? (
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
        ) : isInfo ? (
          <Info className="w-4 h-4 shrink-0" aria-hidden="true" />
        ) : (
          <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
        )}
        <span>{resolved.message}</span>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss notification"
          className="p-1 rounded-lg opacity-70 hover:opacity-100"
        >
          <X className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      )}
    </div>
  );
};

/**
 * Reusable Confirmation Dialog component.
 */
export const ConfirmDialog = ({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  onConfirm,
  onCancel,
}) => {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      className="fixed inset-0 z-50 bg-[#263445]/35 backdrop-blur-[2px] flex items-center justify-center p-4"
    >
      <div className="bg-white border border-[#D5DEE8] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-lg">
        <h3 id="confirm-dialog-title" className="text-base font-semibold text-[#263445]">
          {title}
        </h3>
        {description && <p className="text-xs text-[#64748B] leading-relaxed">{description}</p>}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button variant="secondary" size="sm" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={variant} size="sm" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};

/**
 * Reusable Pagination component.
 */
export const Pagination = ({ page, totalPages, totalItems, itemLabel = 'items', onPageChange }) => {
  if (!totalPages || totalPages <= 1) return null;

  return (
    <nav
      aria-label="Pagination"
      className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-[#D5DEE8] pt-6 text-xs text-[#64748B]"
    >
      <span>
        Showing page <strong className="text-[#263445]">{page}</strong> of{' '}
        <strong className="text-[#263445]">{totalPages}</strong>
        {typeof totalItems === 'number' ? ` (${totalItems} ${itemLabel})` : ''}
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(Math.max(1, page - 1))}
          aria-label="Previous page"
          className="px-3.5 py-2 rounded-xl border border-[#D5DEE8] bg-white text-[#263445] hover:border-[#93C5FD] hover:bg-[#EDF5FC] hover:text-[#1D4ED8] disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1 transition"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          <span>Previous</span>
        </button>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          aria-label="Next page"
          className="px-3.5 py-2 rounded-xl border border-[#D5DEE8] bg-white text-[#263445] hover:border-[#93C5FD] hover:bg-[#EDF5FC] hover:text-[#1D4ED8] disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1 transition"
        >
          <span>Next</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </nav>
  );
};
