import { Link } from 'react-router-dom';
import { Layers, ShieldCheck, Lock, Zap } from 'lucide-react';

const StorefrontFooter = ({ storeSettings = {} }) => {
  const storeName = storeSettings['store.name'] || 'DIGI-VERSE';
  const contactEmail = storeSettings['store.contact_email'];
  const supportPhone = storeSettings['store.support_phone'];

  return (
    <footer className="max-w-7xl w-full mx-auto bg-[#FFF6ED] border border-[#FFD4AE] rounded-3xl px-6 sm:px-8 py-10 mt-16 text-xs text-[#64748B]">
      {/* Trust Pillars */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pb-8 border-b border-[#FFD4AE]/70">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-white border border-[#FFD4AE] flex items-center justify-center text-[#FF6B0A] shrink-0 shadow-xs">
            <Lock className="w-4 h-4" aria-hidden="true" />
          </div>
          <div>
            <p className="font-semibold text-[#1F2937] text-xs">
              Cryptographic Payment Verification
            </p>
            <p className="mt-1 leading-relaxed text-[#64748B]">
              Every transaction is verified on the server using HMAC-SHA256 signatures before order
              fulfillment.
            </p>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-white border border-[#FFD4AE] flex items-center justify-center text-[#FF6B0A] shrink-0 shadow-xs">
            <Zap className="w-4 h-4" aria-hidden="true" />
          </div>
          <div>
            <p className="font-semibold text-[#1F2937] text-xs">
              Instant Signed Digital Delivery
            </p>
            <p className="mt-1 leading-relaxed text-[#64748B]">
              Receive short-lived, authenticated download links immediately after verified payment
              completion.
            </p>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-white border border-[#FFD4AE] flex items-center justify-center text-[#FF6B0A] shrink-0 shadow-xs">
            <ShieldCheck className="w-4 h-4" aria-hidden="true" />
          </div>
          <div>
            <p className="font-semibold text-[#1F2937] text-xs">
              Permanent Order &amp; Invoice Ledger
            </p>
            <p className="mt-1 leading-relaxed text-[#64748B]">
              Access your official purchase invoices, order history, and download quota anytime in
              your account.
            </p>
          </div>
        </div>
      </div>

      {/* Directory Links */}
      <div className="py-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
        <div className="space-y-2.5">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-[#FF6B0A] text-white flex items-center justify-center">
              <Layers className="w-3.5 h-3.5" aria-hidden="true" />
            </div>
            <span className="font-bold tracking-tight text-sm text-[#1F2937]">
              {storeName}
              <span className="text-[#FF6B0A]">.</span>
            </span>
          </div>
          <p className="leading-relaxed text-[#64748B]">
            Curated digital assets, UI systems, code templates, and creator toolkits with instant
            verified fulfillment.
          </p>
        </div>

        <div className="space-y-2.5">
          <p className="font-semibold uppercase tracking-wider text-[#1F2937] text-[11px]">
            Marketplace
          </p>
          <ul className="space-y-1.5">
            <li>
              <Link to="/products" className="text-[#243247] hover:text-[#FF6B0A] transition">
                All Digital Products
              </Link>
            </li>
            <li>
              <Link to="/categories" className="text-[#243247] hover:text-[#FF6B0A] transition">
                Browse Categories
              </Link>
            </li>
            <li>
              <Link
                to="/products?on_sale=true"
                className="text-[#243247] hover:text-[#FF6B0A] transition"
              >
                Promotional Offers
              </Link>
            </li>
            <li>
              <Link
                to="/products?sort_by=popularity"
                className="text-[#243247] hover:text-[#FF6B0A] transition"
              >
                Best-Selling Assets
              </Link>
            </li>
          </ul>
        </div>

        <div className="space-y-2.5">
          <p className="font-semibold uppercase tracking-wider text-[#1F2937] text-[11px]">
            Customer Account
          </p>
          <ul className="space-y-1.5">
            <li>
              <Link to="/profile" className="text-[#243247] hover:text-[#FF6B0A] transition">
                Account &amp; Security
              </Link>
            </li>
            <li>
              <Link to="/orders" className="text-[#243247] hover:text-[#FF6B0A] transition">
                Orders &amp; Invoices
              </Link>
            </li>
            <li>
              <Link to="/downloads" className="text-[#243247] hover:text-[#FF6B0A] transition">
                Digital Downloads Library
              </Link>
            </li>
            <li>
              <Link to="/wishlist" className="text-[#243247] hover:text-[#FF6B0A] transition">
                Saved Wishlist
              </Link>
            </li>
          </ul>
        </div>

        <div className="space-y-2.5">
          <p className="font-semibold uppercase tracking-wider text-[#1F2937] text-[11px]">
            Customer Support
          </p>
          {contactEmail ? (
            <p className="text-[#243247]">
              Email:{' '}
              <a
                href={`mailto:${contactEmail}`}
                className="text-[#FF6B0A] font-medium underline hover:text-[#D94300]"
              >
                {contactEmail}
              </a>
            </p>
          ) : (
            <p>Verified customer support available through your account portal.</p>
          )}
          {supportPhone && <p className="font-mono text-[#243247]">Support: {supportPhone}</p>}
        </div>
      </div>

      {/* Bottom Copyright */}
      <div className="pt-6 border-t border-[#FFD4AE]/70 flex flex-wrap items-center justify-between gap-4">
        <span className="text-[#64748B]">
          © {new Date().getFullYear()} {storeName}. All rights reserved.
        </span>
        <Link
          to="/admin/login"
          className="text-[#D94300] hover:text-[#FF6B0A] font-medium transition"
        >
          Administrator Portal
        </Link>
      </div>
    </footer>
  );
};

export default StorefrontFooter;
