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
 * Reusable Button component following the DIGI-VERSE warm orange & white design system.
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
    'inline-flex items-center justify-center gap-2 rounded-xl font-semibold tracking-wide transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FF6B0A] disabled:opacity-45 disabled:cursor-not-allowed';

  const variants = {
    primary: 'dv-btn-primary',
    accent:
      'bg-[#F4510B] text-white hover:bg-[#D94300] border border-[#F4510B] rounded-xl shadow-[0_4px_14px_-2px_rgba(244,81,11,0.28)]',
    secondary: 'dv-btn-secondary',
    outline:
      'bg-white text-[#243247] border border-[#E5E7EB] hover:border-[#FFD4AE] hover:bg-[#FFF0E2] hover:text-[#D94300] rounded-xl',
    danger:
      'bg-white text-red-700 border border-red-200 hover:border-red-500 hover:bg-red-50 rounded-xl',
    ghost:
      'bg-transparent text-[#FF6B0A] hover:text-[#D94300] underline-offset-4 hover:underline rounded-xl',
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
          className="block text-xs font-medium text-[#243247] mb-1.5"
        >
          {label}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <Icon
            className="w-4 h-4 text-[#8490A0] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
            aria-hidden="true"
          />
        )}
        <input
          id={id}
          className={`dv-input ${
            error ? 'border-red-500 focus:border-red-500' : ''
          } ${
            Icon ? 'pl-10' : 'pl-3.5'
          } pr-3.5 py-2.5 text-sm text-[#243247] placeholder:text-[#8490A0] disabled:bg-[#FFF6ED] disabled:text-[#8490A0] ${className}`}
          {...props}
        />
      </div>
      {helperText && !error && <p className="mt-1 text-[11px] text-[#64748B]">{helperText}</p>}
      {error && (
        <p role="alert" className="mt-1 text-[11px] text-red-700">
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
    neutral: 'bg-[#FFF6ED] text-[#243247] border-[#E5E7EB]',
    accent: 'bg-[#FFE9D6] text-[#D94300] border-[#FFD4AE]',
    dark: 'bg-[#FF6B0A] text-white border-[#FF6B0A]',
    success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    warning: 'bg-[#FFF2E6] text-[#D94300] border-[#FFD4AE]',
    danger: 'bg-red-50 text-red-700 border-red-200',
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
        <p className="text-xs uppercase tracking-[0.2em] text-[#FF6B0A] font-semibold mb-2">
          {eyebrow}
        </p>
      )}
      <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-[#1F2937]">{title}</h2>
      {subtitle && <p className="text-sm text-[#64748B] mt-1.5 max-w-2xl">{subtitle}</p>}
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
    <div className="w-7 h-7 border-2 border-[#FFD4AE] border-t-[#FF6B0A] rounded-full animate-spin" />
    <span className="text-xs font-medium tracking-wider uppercase text-[#64748B]">{label}</span>
  </div>
);

export const ProductCardSkeleton = ({ count = 6 }) => (
  <div
    role="status"
    aria-label="Loading products"
    className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6"
  >
    {Array.from({ length: count }).map((_, i) => (
      <div
        key={i}
        className="dv-card overflow-hidden animate-pulse"
      >
        <div className="aspect-16/10 bg-[#FFF6ED] border-b border-[#E5E7EB]" />
        <div className="p-5 space-y-3">
          <div className="h-3 bg-[#FFE9D6] rounded w-1/3" />
          <div className="h-5 bg-[#FFF2E6] rounded w-3/4" />
          <div className="h-3 bg-[#FFF6ED] rounded w-full" />
        </div>
        <div className="px-5 py-4 border-t border-[#E5E7EB] flex justify-between items-center">
          <div className="h-4 bg-[#FFE9D6] rounded w-20" />
          <div className="h-8 bg-[#FFF2E6] rounded-xl w-24" />
        </div>
      </div>
    ))}
  </div>
);

/**
 * Reusable EmptyState component.
 */
export const EmptyState = ({ icon: Icon, title, description, action }) => (
  <div className="dv-card-warm p-10 md:p-14 text-center max-w-2xl mx-auto space-y-4">
    {Icon && (
      <div className="w-12 h-12 mx-auto rounded-2xl bg-[#FFF2E6] border border-[#FFD4AE] flex items-center justify-center text-[#FF6B0A]">
        <Icon className="w-5 h-5" aria-hidden="true" />
      </div>
    )}
    <h3 className="text-lg font-semibold text-[#1F2937]">{title}</h3>
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
      className={`p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex flex-wrap items-center justify-between gap-3 ${className}`}
    >
      <div className="flex items-start gap-2.5">
        <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-600" aria-hidden="true" />
        <span>{message}</span>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-white border border-red-200 text-red-700 hover:bg-red-100 transition"
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
export const ToastBanner = ({ toast, onDismiss, className = '' }) => {
  if (!toast || !toast.message) return null;
  const isError = toast.type === 'error';
  const isInfo = toast.type === 'info';

  return (
    <div
      role={isError ? 'alert' : 'status'}
      aria-live="polite"
      className={`p-3.5 rounded-xl border text-xs flex items-center justify-between gap-3 shadow-xs ${
        isError
          ? 'bg-red-50 border-red-200 text-red-800'
          : isInfo
          ? 'bg-[#FFF2E6] border-[#FFD4AE] text-[#D94300]'
          : 'bg-emerald-50 border-emerald-200 text-emerald-800'
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
        <span>{toast.message}</span>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss notification"
          className="p-1 rounded-lg opacity-70 hover:opacity-100"
        >
          <X className="w-3.5 h-3.5" />
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
      className="fixed inset-0 z-50 bg-[#1F2937]/30 backdrop-blur-[2px] flex items-center justify-center p-4"
    >
      <div className="bg-white border border-[#FFD4AE] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-lg">
        <h3 id="confirm-dialog-title" className="text-base font-semibold text-[#1F2937]">
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
      className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-[#E5E7EB] pt-6 text-xs text-[#64748B]"
    >
      <span>
        Showing page <strong className="text-[#1F2937]">{page}</strong> of{' '}
        <strong className="text-[#1F2937]">{totalPages}</strong>
        {typeof totalItems === 'number' ? ` (${totalItems} ${itemLabel})` : ''}
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(Math.max(1, page - 1))}
          aria-label="Previous page"
          className="px-3.5 py-2 rounded-xl border border-[#E5E7EB] bg-white text-[#243247] hover:border-[#FFD4AE] hover:bg-[#FFF0E2] hover:text-[#D94300] disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1 transition"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          <span>Previous</span>
        </button>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          aria-label="Next page"
          className="px-3.5 py-2 rounded-xl border border-[#E5E7EB] bg-white text-[#243247] hover:border-[#FFD4AE] hover:bg-[#FFF0E2] hover:text-[#D94300] disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1 transition"
        >
          <span>Next</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </nav>
  );
};
