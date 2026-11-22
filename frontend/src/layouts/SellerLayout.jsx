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
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const SELLER_NAV = [
  { label: 'Overview', to: '/seller', icon: LayoutDashboard, exact: true },
  { label: 'My Products', to: '/seller/products', icon: Package, exact: true },
  { label: 'Add Product', to: '/seller/products/new', icon: PlusCircle },
  { label: 'Orders', to: '/seller/orders', icon: ShoppingBag },
  { label: 'Store Profile', to: '/seller/profile', icon: Store },
  { label: 'Sales Analytics', to: '/seller/analytics', icon: BarChart3 },
  { label: 'Account Settings', to: '/profile', icon: Settings },
];

const SellerLayout = ({ title, subtitle, actions, children }) => {
  const { customer, sellerStoreSlug } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#FFFAF5] text-[#243247] flex flex-col lg:flex-row">
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-68 bg-white border-r border-[#E5E7EB] flex flex-col justify-between transition-transform lg:static lg:translate-x-0 shadow-xs ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div>
          <div className="p-6 border-b border-[#E5E7EB] flex items-center justify-between">
            <Link to="/seller" className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-[#FF6B0A] text-white flex items-center justify-center shadow-[0_4px_12px_-2px_rgba(255,107,10,0.3)]">
                <Store className="w-4 h-4" />
              </div>
              <div>
                <span className="font-bold tracking-tight text-sm text-[#1F2937] block">
                  DIGI-VERSE<span className="text-[#FF6B0A]">.</span>
                </span>
                <span className="text-[10px] uppercase tracking-wider text-[#FF6B0A] font-semibold">
                  Seller Studio
                </span>
              </div>
            </Link>
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close seller navigation"
              className="lg:hidden text-[#64748B] hover:text-[#1F2937]"
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
                        ? 'bg-[#FFF2E6] text-[#FF6B0A] border border-[#FFD4AE] font-semibold'
                        : 'text-[#243247] hover:text-[#FF6B0A] hover:bg-[#FFF6ED]'
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

        <div className="p-4 border-t border-[#E5E7EB] space-y-3 bg-[#FFF6ED]/50">
          {customer && (
            <div className="px-3 py-2.5 rounded-xl bg-white border border-[#E5E7EB]">
              <p className="text-[10px] uppercase tracking-wider text-[#64748B] flex items-center gap-1.5">
                <UserCheck className="w-3 h-3 text-[#FF6B0A]" /> Approved Seller
              </p>
              <p className="text-xs font-semibold text-[#1F2937] truncate mt-0.5">
                {customer.full_name}
              </p>
              <p className="text-[11px] text-[#64748B] truncate">{customer.email}</p>
            </div>
          )}

          {sellerStoreSlug && (
            <Link
              to={`/store/${sellerStoreSlug}`}
              className="flex items-center justify-between px-3 py-2 text-xs text-[#243247] hover:text-[#FF6B0A] border border-[#E5E7EB] bg-white hover:border-[#FFD4AE] rounded-xl transition"
            >
              <span>Public Storefront</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          )}
          <Link
            to="/products"
            className="flex items-center justify-between px-3 py-2 text-xs text-[#64748B] hover:text-[#1F2937] border border-[#E5E7EB] bg-white rounded-xl transition"
          >
            <span>Browse Marketplace</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-[#1F2937]/30 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white/90 backdrop-blur-md border-b border-[#E5E7EB] px-6 py-4 flex items-center justify-between gap-4 sticky top-0 z-20">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open seller navigation"
              className="lg:hidden p-2 border border-[#E5E7EB] bg-white rounded-xl text-[#243247] hover:border-[#FFD4AE]"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div className="min-w-0">
              <h1 className="text-lg font-bold tracking-tight text-[#1F2937] truncate">{title}</h1>
              {subtitle && <p className="text-xs text-[#64748B] truncate">{subtitle}</p>}
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
