import { Link } from 'react-router-dom';
import {
  ArrowUpRight,
  Compass,
  Download,
  FolderTree,
  Globe,
  Heart,
  HelpCircle,
  KeyRound,
  Layers,
  Lock,
  Mail,
  Package,
  Phone,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Store,
  User,
  Zap,
} from 'lucide-react';

const EXPLORE_LINKS = [
  { label: 'Browse Products', to: '/products', icon: Layers },
  { label: 'Categories', to: '/categories', icon: FolderTree },
  { label: 'Creator Storefronts', to: '/stores', icon: Store },
  { label: 'Featured Products', to: '/products?sort_by=popularity', icon: Sparkles },
  { label: 'Promotional Offers', to: '/products?on_sale=true', icon: Compass },
];

const ACCOUNT_LINKS = [
  { label: 'My Account', to: '/profile', icon: User },
  { label: 'Wishlist', to: '/wishlist', icon: Heart },
  { label: 'Cart', to: '/cart', icon: ShoppingBag },
  { label: 'Orders', to: '/orders', icon: Package },
  { label: 'Downloads', to: '/downloads', icon: Download },
];

const SUPPORT_LINKS = [
  { label: 'Become a Creator', to: '/seller/apply', icon: Store },
  { label: 'Account Recovery', to: '/forgot-password', icon: KeyRound },
  { label: 'Order & Invoice Help', to: '/orders', icon: HelpCircle },
  { label: 'Administrator Portal', to: '/admin/login', icon: ShieldCheck },
];

const StorefrontFooter = ({ storeSettings = {} }) => {
  const storeName = storeSettings['store.name'] || 'DIGI-VERSE';
  const contactEmail = storeSettings['store.contact_email'];
  const supportPhone = storeSettings['store.support_phone'];

  return (
    <footer className="max-w-7xl w-full mx-auto mt-20 bg-[#0D1424] border border-[#D5DEE8] rounded-3xl shadow-[0_6px_28px_-8px_rgba(38,52,69,0.08)] overflow-hidden">
      <div className="px-6 sm:px-10 lg:px-12 pt-8 sm:pt-10 pb-8">
        {/* Trust Pillars Strip */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 sm:gap-6 bg-[#111C30] border border-[#D5DEE8] rounded-2xl p-5 sm:p-6 shadow-2xs">
          <div className="flex items-start gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#18243A] border border-[#BFDBFE] flex items-center justify-center text-[#60A5FA] shrink-0">
              <Lock className="w-4.5 h-4.5" aria-hidden="true" />
            </div>
            <div>
              <p className="font-display font-bold text-[#F1F5F9] text-[14.5px] leading-snug">
                Cryptographic Payment Verification
              </p>
              <p className="mt-1 text-[13px] leading-relaxed text-[#94A3B8]">
                Every transaction is verified on the server with HMAC-SHA256 signatures before
                fulfillment.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#18243A] border border-[#BFDBFE] flex items-center justify-center text-[#0EA5E9] shrink-0">
              <Zap className="w-4.5 h-4.5" aria-hidden="true" />
            </div>
            <div>
              <p className="font-display font-bold text-[#F1F5F9] text-[14.5px] leading-snug">
                Instant Signed Digital Delivery
              </p>
              <p className="mt-1 text-[13px] leading-relaxed text-[#94A3B8]">
                Unlock authenticated, time-limited download links immediately after verified payment
                completion.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#18243A] border border-[#BFDBFE] flex items-center justify-center text-emerald-400 shrink-0">
              <ShieldCheck className="w-4.5 h-4.5" aria-hidden="true" />
            </div>
            <div>
              <p className="font-display font-bold text-[#F1F5F9] text-[14.5px] leading-snug">
                Permanent Order &amp; Invoice Ledger
              </p>
              <p className="mt-1 text-[13px] leading-relaxed text-[#94A3B8]">
                Access official purchase invoices, order history, and download quotas anytime in your
                account.
              </p>
            </div>
          </div>
        </div>

        {/* Main Footer Directory */}
        <div className="py-10 lg:py-12 grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-10">
          {/* Brand Column */}
          <div className="lg:col-span-4 space-y-4">
            <Link
              to="/"
              className="inline-flex items-center gap-3 rounded-xl focus-visible:outline-2 focus-visible:outline-[#2563EB]"
            >
              <div className="w-11 h-11 rounded-2xl bg-[#2563EB] text-white flex items-center justify-center shrink-0 shadow-[0_6px_16px_-3px_rgba(37,99,235,0.35)]">
                <Layers className="w-5 h-5" aria-hidden="true" />
              </div>
              <span className="font-display font-extrabold tracking-tight text-2xl text-[#F1F5F9]">
                {storeName}
                <span className="text-[#0EA5E9]">.</span>
              </span>
            </Link>

            <p className="font-display text-[16px] font-semibold text-[#F1F5F9] leading-snug max-w-sm">
              Curated digital products engineered for modern creators and teams.
            </p>

            <p className="text-[14px] leading-relaxed text-[#94A3B8] max-w-sm">
              Discover vetted UI kits, software starters, mathematical handbooks, and business
              templates with verified checkout and instant signed delivery.
            </p>

            {/* Interactive Platform & Contact Quick Icons */}
            <div className="pt-2 flex flex-wrap items-center gap-2.5">
              <Link
                to="/stores"
                aria-label="Explore Creator Storefronts"
                title="Creator Storefronts"
                className="w-10 h-10 rounded-xl bg-[#111C30] border border-[#D5DEE8] text-[#F1F5F9] hover:border-[#2563EB] hover:bg-[#18243A] hover:text-[#60A5FA] hover:-translate-y-0.5 transition flex items-center justify-center shadow-2xs"
              >
                <Globe className="w-4 h-4" aria-hidden="true" />
              </Link>
              <Link
                to="/products"
                aria-label="Browse Digital Catalog"
                title="Browse Digital Catalog"
                className="w-10 h-10 rounded-xl bg-[#111C30] border border-[#D5DEE8] text-[#F1F5F9] hover:border-[#2563EB] hover:bg-[#18243A] hover:text-[#60A5FA] hover:-translate-y-0.5 transition flex items-center justify-center shadow-2xs"
              >
                <Compass className="w-4 h-4" aria-hidden="true" />
              </Link>
              <Link
                to="/seller/apply"
                aria-label="Sell on DIGI-VERSE"
                title="Sell on DIGI-VERSE"
                className="w-10 h-10 rounded-xl bg-[#111C30] border border-[#D5DEE8] text-[#F1F5F9] hover:border-[#2563EB] hover:bg-[#18243A] hover:text-[#60A5FA] hover:-translate-y-0.5 transition flex items-center justify-center shadow-2xs"
              >
                <Store className="w-4 h-4" aria-hidden="true" />
              </Link>
              {contactEmail && (
                <a
                  href={`mailto:${contactEmail}`}
                  aria-label={`Email support at ${contactEmail}`}
                  title={contactEmail}
                  className="w-10 h-10 rounded-xl bg-[#111C30] border border-[#D5DEE8] text-[#F1F5F9] hover:border-[#2563EB] hover:bg-[#18243A] hover:text-[#60A5FA] hover:-translate-y-0.5 transition flex items-center justify-center shadow-2xs"
                >
                  <Mail className="w-4 h-4" aria-hidden="true" />
                </a>
              )}
            </div>
          </div>

          {/* 3-Column Navigation Directory */}
          <div className="lg:col-span-8 grid grid-cols-1 sm:grid-cols-3 gap-8 sm:gap-6">
            {/* Explore */}
            <div className="space-y-4">
              <h2 className="font-display text-[15px] font-bold tracking-[-0.01em] text-[#F1F5F9] pb-2 border-b border-[#DCE6EF]">
                Explore
              </h2>
              <ul className="space-y-2.5">
                {EXPLORE_LINKS.map((item) => {
                  const Icon = item.icon;
                  return (
                    <li key={item.to + item.label}>
                      <Link
                        to={item.to}
                        className="group inline-flex items-center gap-2 text-[14px] font-medium text-[#CBD5E1] hover:text-[#60A5FA] transition"
                      >
                        <Icon
                          className="w-4 h-4 text-[#94A3B8] group-hover:text-[#60A5FA] transition shrink-0"
                          aria-hidden="true"
                        />
                        <span>{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>

            {/* Account */}
            <div className="space-y-4">
              <h2 className="font-display text-[15px] font-bold tracking-[-0.01em] text-[#F1F5F9] pb-2 border-b border-[#DCE6EF]">
                Account
              </h2>
              <ul className="space-y-2.5">
                {ACCOUNT_LINKS.map((item) => {
                  const Icon = item.icon;
                  return (
                    <li key={item.to}>
                      <Link
                        to={item.to}
                        className="group inline-flex items-center gap-2 text-[14px] font-medium text-[#CBD5E1] hover:text-[#60A5FA] transition"
                      >
                        <Icon
                          className="w-4 h-4 text-[#94A3B8] group-hover:text-[#60A5FA] transition shrink-0"
                          aria-hidden="true"
                        />
                        <span>{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>

            {/* Support */}
            <div className="space-y-4">
              <h2 className="font-display text-[15px] font-bold tracking-[-0.01em] text-[#F1F5F9] pb-2 border-b border-[#DCE6EF]">
                Support
              </h2>
              <ul className="space-y-2.5">
                {SUPPORT_LINKS.map((item) => {
                  const Icon = item.icon;
                  return (
                    <li key={item.to + item.label}>
                      <Link
                        to={item.to}
                        className="group inline-flex items-center gap-2 text-[14px] font-medium text-[#CBD5E1] hover:text-[#60A5FA] transition"
                      >
                        <Icon
                          className="w-4 h-4 text-[#94A3B8] group-hover:text-[#60A5FA] transition shrink-0"
                          aria-hidden="true"
                        />
                        <span>{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>

              {(contactEmail || supportPhone) && (
                <div className="pt-2 space-y-2 border-t border-[#E5E7EB]">
                  {contactEmail && (
                    <a
                      href={`mailto:${contactEmail}`}
                      className="flex items-center gap-2 text-[13.5px] font-medium text-[#60A5FA] hover:text-[#93C5FD] hover:underline break-all"
                    >
                      <Mail className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                      <span>{contactEmail}</span>
                    </a>
                  )}
                  {supportPhone && (
                    <a
                      href={`tel:${supportPhone.replace(/\s+/g, '')}`}
                      className="flex items-center gap-2 text-[13.5px] font-mono text-[#CBD5E1] hover:text-[#60A5FA]"
                    >
                      <Phone className="w-3.5 h-3.5 text-[#94A3B8] shrink-0" aria-hidden="true" />
                      <span>{supportPhone}</span>
                    </a>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Signature Brand Wordmark Band */}
        <div className="py-5 px-5 sm:px-7 rounded-2xl bg-[#18243A] border border-[#D5DEE8] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="font-display font-extrabold tracking-[-0.03em] text-2xl sm:text-3xl text-[#F1F5F9]">
              {storeName}
              <span className="text-[#60A5FA]">.</span>
            </span>
            <span className="text-[13.5px] font-medium text-[#94A3B8]">
              Verified Digital Commerce &amp; Creator Storefronts
            </span>
          </div>
          <Link
            to="/products"
            className="inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-[#60A5FA] hover:text-[#93C5FD] transition shrink-0"
          >
            <span>Explore full catalog</span>
            <ArrowUpRight className="w-4 h-4" aria-hidden="true" />
          </Link>
        </div>
      </div>

      {/* Bottom Copyright Bar */}
      <div className="bg-[#080D19] border-t border-[#D5DEE8] px-6 sm:px-10 lg:px-12 py-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-[13.5px] text-[#94A3B8]">
        <p className="text-center sm:text-left">
          © {new Date().getFullYear()} <strong className="font-semibold text-[#F1F5F9]">{storeName}</strong>. All rights reserved.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-5 font-medium">
          <Link to="/stores" className="text-[#CBD5E1] hover:text-[#60A5FA] transition">
            Creator Directory
          </Link>
          <Link to="/seller/apply" className="text-[#CBD5E1] hover:text-[#60A5FA] transition">
            Seller Onboarding
          </Link>
          <Link to="/admin/login" className="text-[#60A5FA] hover:text-[#93C5FD] font-semibold transition">
            Administrator Portal
          </Link>
        </div>
      </div>
    </footer>
  );
};

export default StorefrontFooter;
