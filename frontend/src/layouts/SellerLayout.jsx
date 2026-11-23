import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import {
  BarChart3,
  ExternalLink,
  LayoutDashboard,
  Menu,
  Package,
  PlusCircle,
  Settings,
  ShoppingBag,
  Store,
  UserCheck,
  X,
  WalletCards,
  Landmark,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const SELLER_NAV = [
  { label: 'Overview', to: '/seller', icon: LayoutDashboard, exact: true },
  { label: 'My Products', to: '/seller/products', icon: Package, exact: true },
  { label: 'Add Product', to: '/seller/products/new', icon: PlusCircle },
  { label: 'Orders', to: '/seller/orders', icon: ShoppingBag },
  { label: 'Store Profile', to: '/seller/profile', icon: Store },
  { label: 'Sales Analytics', to: '/seller/analytics', icon: BarChart3 },
  { label: 'Financials', to: '/seller/financial', icon: WalletCards, exact: true },
  { label: 'Payouts', to: '/seller/payouts', icon: Landmark, exact: true },
  { label: 'Account Settings', to: '/profile', icon: Settings },
];

const SellerLayout = ({ title, subtitle, actions, children }) => {
  const { customer, sellerStoreSlug } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#0D1424] text-[#F1F5F9] flex flex-col lg:flex-row">
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-68 bg-[#111C30] border-r border-[#D5DEE8] flex flex-col justify-between transition-transform lg:static lg:translate-x-0 shadow-xs ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div>
          <div className="p-6 border-b border-[#D5DEE8] flex items-center justify-between">
            <Link to="/seller" className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-[#2563EB] text-white flex items-center justify-center shadow-[0_4px_12px_-2px_rgba(37,99,235,0.3)]">
                <Store className="w-4 h-4" />
              </div>
              <div>
                <span className="font-bold tracking-tight text-sm text-[#F1F5F9] block">
                  DIGI-VERSE<span className="text-[#60A5FA]">.</span>
                </span>
                <span className="text-[11px] text-[#60A5FA] font-semibold">
                  Seller Studio
                </span>
              </div>
            </Link>
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close seller navigation"
              className="lg:hidden text-[#94A3B8] hover:text-[#F1F5F9]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <nav aria-label="Seller Studio Navigation" className="p-4 space-y-1">
            {SELLER_NAV.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.exact}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3.5 py-2.5 text-xs font-medium rounded-xl transition ${
                      isActive
                        ? 'bg-[#18243A] text-[#93C5FD] border border-[#BFDBFE] font-semibold'
                        : 'text-[#F1F5F9] hover:text-[#60A5FA] hover:bg-[#18243A]'
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        <div className="p-4 border-t border-[#D5DEE8] space-y-3 bg-[#18243A]">
          {customer && (
            <div className="px-3 py-2.5 rounded-xl bg-[#111C30] border border-[#D5DEE8]">
              <p className="text-[11px] font-medium text-[#94A3B8] flex items-center gap-1.5">
                <UserCheck className="w-3.5 h-3.5 text-[#60A5FA]" aria-hidden="true" /> Approved Seller
              </p>
              <p className="text-xs font-semibold text-[#F1F5F9] truncate mt-0.5">
                {customer.full_name}
              </p>
              <p className="text-[11px] text-[#94A3B8] truncate">{customer.email}</p>
            </div>
          )}

          {sellerStoreSlug && (
            <Link
              to={`/store/${sellerStoreSlug}`}
              className="flex items-center justify-between px-3 py-2 text-xs text-[#F1F5F9] hover:text-[#60A5FA] border border-[#D5DEE8] bg-[#111C30] hover:border-[#93C5FD] hover:bg-[#18243A] rounded-xl transition"
            >
              <span>Public Storefront</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          )}
          <Link
            to="/products"
            className="flex items-center justify-between px-3 py-2 text-xs text-[#94A3B8] hover:text-[#F1F5F9] border border-[#D5DEE8] bg-[#111C30] hover:bg-[#18243A] rounded-xl transition"
          >
            <span>Browse Marketplace</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-[#080D19]/70 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-[#111C30]/95 backdrop-blur-md border-b border-[#D5DEE8] px-6 py-4 flex items-center justify-between gap-4 sticky top-0 z-20">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open seller navigation"
              className="lg:hidden p-2 border border-[#D5DEE8] bg-[#111C30] rounded-xl text-[#F1F5F9] hover:border-[#93C5FD] hover:bg-[#18243A]"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div className="min-w-0">
              <h1 className="text-lg font-bold tracking-tight text-[#F1F5F9] truncate">{title}</h1>
              {subtitle && <p className="text-xs text-[#94A3B8] truncate">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
        </header>

        <main className="flex-1 p-6 lg:p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
};

export default SellerLayout;
