import { useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Shield,
  LayoutDashboard,
  Package,
  FolderTree,
  Percent,
  ShoppingCart,
  Users,
  Image as ImageIcon,
  Video,
  Megaphone,
  Settings,
  KeyRound,
  LogOut,
  ExternalLink,
  Menu,
  Store,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { label: 'Dashboard', to: '/admin', icon: LayoutDashboard, activePhase: true, exact: true },
  { label: 'Products', to: '/admin/products', icon: Package, activePhase: true },
  { label: 'Categories', to: '/admin/categories', icon: FolderTree, activePhase: true },
  { label: 'Sales & Discounts', to: '/admin/products?tab=discounts', icon: Percent, activePhase: true },
  { label: 'Orders', to: '/admin/orders', icon: ShoppingCart, activePhase: true },
  { label: 'Customers', to: '/admin/customers', icon: Users, activePhase: true },
  { label: 'Sellers', to: '/admin/sellers', icon: Store, activePhase: true },
  { label: 'Banners', to: '/admin/banners', icon: ImageIcon, activePhase: true },
  { label: 'Advertisement Videos', to: '/admin/videos', icon: Video, activePhase: true },
  { label: 'Marketing Campaigns', to: '/admin/marketing', icon: Megaphone, activePhase: true },
  { label: 'Settings & Audit', to: '/admin/settings', icon: Settings, activePhase: true },
];

const AdminLayout = ({ title, subtitle, actions, children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { admin, logoutAdmin } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isDiscountsTab =
    location.pathname === '/admin/products' &&
    new URLSearchParams(location.search).get('tab') === 'discounts';

  const isNavItemActive = (item, routerIsActive) => {
    if (item.to === '/admin/products?tab=discounts') {
      return isDiscountsTab;
    }
    if (item.to === '/admin/products') {
      return routerIsActive && !isDiscountsTab;
    }
    return routerIsActive;
  };

  const handleLogout = async () => {
    await logoutAdmin();
    navigate('/admin/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#FFFAF5] text-[#243247] flex flex-col lg:flex-row">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-68 bg-white border-r border-[#E5E7EB] flex flex-col justify-between transition-transform lg:static lg:translate-x-0 shadow-xs ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div>
          <div className="p-6 border-b border-[#E5E7EB] flex items-center justify-between">
            <Link to="/admin" className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-[#FF6B0A] text-white flex items-center justify-center shadow-[0_4px_12px_-2px_rgba(255,107,10,0.3)]">
                <Shield className="w-4 h-4" />
              </div>
              <div>
                <span className="font-bold tracking-tight text-sm text-[#1F2937] block">
                  DIGI-VERSE<span className="text-[#FF6B0A]">.</span>
                </span>
                <span className="text-[10px] uppercase tracking-wider text-[#FF6B0A] font-semibold">
                  Admin Console
                </span>
              </div>
            </Link>
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="lg:hidden text-[#64748B] hover:text-[#1F2937]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <nav className="p-4 space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              if (!item.activePhase) {
                return (
                  <div
                    key={item.label}
                    className="flex items-center justify-between px-3.5 py-2.5 text-xs text-[#8490A0] cursor-not-allowed select-none rounded-xl"
                    title="Scheduled for upcoming phase"
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="w-4 h-4" />
                      <span>{item.label}</span>
                    </div>
                    <span className="text-[9px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#FFF6ED] text-[#8490A0] border border-[#E5E7EB]">
                      Soon
                    </span>
                  </div>
                );
              }

              return (
                <NavLink
                  key={item.label}
                  to={item.to}
                  end={item.exact}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) => {
                    const active = isNavItemActive(item, isActive);
                    return `flex items-center gap-3 px-3.5 py-2.5 text-xs font-medium rounded-xl transition ${
                      active
                        ? 'bg-[#FFE9D6] text-[#D94300] border border-[#FFD4AE] font-semibold'
                        : 'text-[#243247] hover:bg-[#FFF0E2] hover:text-[#FF6B0A]'
                    }`;
                  }}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Admin Profile & Session Controls */}
        <div className="p-4 border-t border-[#E5E7EB] space-y-3 bg-[#FFF6ED]">
          <div className="px-2">
            <p className="text-xs font-semibold text-[#1F2937] truncate">{admin?.username}</p>
            <p className="text-[11px] text-[#64748B] truncate">{admin?.email}</p>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Link
              to="/admin/change-password"
              className="text-[11px] font-medium px-2.5 py-2 rounded-xl border border-[#FFD4AE] bg-white text-[#D94300] hover:bg-[#FFF0E2] transition flex items-center justify-center gap-1.5"
            >
              <KeyRound className="w-3 h-3" />
              <span>Password</span>
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              className="text-[11px] font-medium px-2.5 py-2 rounded-xl border border-[#E5E7EB] bg-white hover:bg-red-50 hover:border-red-300 hover:text-red-700 text-[#243247] transition flex items-center justify-center gap-1.5"
            >
              <LogOut className="w-3 h-3" />
              <span>Logout</span>
            </button>
          </div>

          <Link
            to="/products"
            className="w-full text-[11px] font-semibold text-[#FF6B0A] hover:text-[#D94300] flex items-center justify-center gap-1.5 pt-1"
          >
            <span>View Public Storefront</span>
            <ExternalLink className="w-3 h-3" />
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-[#E5E7EB] px-6 py-5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 rounded-xl border border-[#E5E7EB] text-[#243247] hover:border-[#FFD4AE]"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-[#1F2937]">{title}</h1>
              {subtitle && <p className="text-xs text-[#64748B] mt-0.5">{subtitle}</p>}
            </div>
          </div>

          {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
        </header>

        <main className="p-6 md:p-8 flex-1 overflow-x-hidden">{children}</main>
      </div>
    </div>
  );
};

export default AdminLayout;
