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
  WalletCards,
  Landmark,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { label: 'Dashboard', section: 'Overview', to: '/admin', icon: LayoutDashboard, activePhase: true, exact: true },
  { label: 'Products', section: 'Catalog', to: '/admin/products', icon: Package, activePhase: true },
  { label: 'Categories', section: 'Catalog', to: '/admin/categories', icon: FolderTree, activePhase: true },
  { label: 'Sales & Discounts', section: 'Catalog', to: '/admin/products?tab=discounts', icon: Percent, activePhase: true },
  { label: 'Orders', section: 'Commerce', to: '/admin/orders', icon: ShoppingCart, activePhase: true },
  { label: 'Customers', section: 'Commerce', to: '/admin/customers', icon: Users, activePhase: true },
  { label: 'Sellers', section: 'Commerce', to: '/admin/sellers', icon: Store, activePhase: true },
  { label: 'Financial Management', section: 'Finance & Payouts', to: '/admin/financial', icon: WalletCards, activePhase: true },
  { label: 'Payout Management', section: 'Finance & Payouts', to: '/admin/payouts', icon: Landmark, activePhase: true },
  { label: 'Banners', section: 'Growth & System', to: '/admin/banners', icon: ImageIcon, activePhase: true },
  { label: 'Video Spotlights', section: 'Growth & System', to: '/admin/videos', icon: Video, activePhase: true },
  { label: 'Marketing Campaigns', section: 'Growth & System', to: '/admin/marketing', icon: Megaphone, activePhase: true },
  { label: 'Settings & Audit', section: 'Growth & System', to: '/admin/settings', icon: Settings, activePhase: true },
];

const NAV_SECTIONS = ['Overview', 'Catalog', 'Commerce', 'Finance & Payouts', 'Growth & System'];

const AdminLayout = ({ title, subtitle, actions, children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { admin, logoutAdmin } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

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

  const adminInitials = (admin?.username || 'A')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="min-h-screen bg-[#E5E7EB] text-[#263445] flex flex-col lg:flex-row">
      {/* Sidebar */}
      <aside
        aria-label="Admin Sidebar"
        className={`fixed inset-y-0 left-0 z-40 bg-white border-r border-[#D5DEE8] flex flex-col justify-between transition-all duration-200 lg:static lg:translate-x-0 shadow-xs shrink-0 ${
          collapsed ? 'w-64 lg:w-[76px]' : 'w-64'
        } ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex-1 overflow-y-auto">
          {/* Brand Header */}
          <div
            className={`px-4 py-4 border-b border-[#D5DEE8] flex items-center ${
              collapsed ? 'lg:justify-center justify-between' : 'justify-between'
            }`}
          >
            <Link
              to="/admin"
              title="DIGI-VERSE Admin Console"
              className="flex items-center gap-2.5 min-w-0"
            >
              <div className="w-9 h-9 rounded-lg bg-[#2563EB] text-white flex items-center justify-center shrink-0 shadow-[0_4px_10px_-2px_rgba(37,99,235,0.28)]">
                <Shield className="w-4 h-4" aria-hidden="true" />
              </div>
              <div className={collapsed ? 'lg:hidden' : ''}>
                <span className="font-bold tracking-tight text-[14px] text-[#263445] block leading-tight">
                  DIGI-VERSE<span className="text-[#2563EB]">.</span>
                </span>
                <span className="text-[11px] text-[#64748B] font-medium block leading-tight mt-0.5">
                  Admin Console
                </span>
              </div>
            </Link>

            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation menu"
              className="lg:hidden p-1.5 rounded-lg text-[#64748B] hover:text-[#263445] hover:bg-[#EDF5FC]"
            >
              <X className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={() => setCollapsed((prev) => !prev)}
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              className={`hidden lg:inline-flex p-1.5 rounded-lg text-[#64748B] hover:text-[#2563EB] hover:bg-[#EDF5FC] transition ${
                collapsed ? 'lg:hidden' : ''
              }`}
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>

          {collapsed && (
            <div className="hidden lg:flex justify-center pt-3">
              <button
                type="button"
                onClick={() => setCollapsed(false)}
                aria-label="Expand sidebar"
                title="Expand sidebar"
                className="p-2 rounded-lg border border-[#D5DEE8] bg-[#F8FAFC] text-[#64748B] hover:text-[#2563EB] hover:border-[#93C5FD] transition"
              >
                <PanelLeftOpen className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Grouped Navigation */}
          <nav aria-label="Admin Navigation" className="p-3 space-y-4">
            {NAV_SECTIONS.map((section) => {
              const items = NAV_ITEMS.filter((it) => it.section === section);
              return (
                <div key={section}>
                  {!collapsed && (
                    <p className="px-3 pb-1.5 text-[11px] font-semibold text-[#64748B]">
                      {section}
                    </p>
                  )}
                  <div className="space-y-0.5">
                    {items.map((item) => {
                      const Icon = item.icon;
                      return (
                        <NavLink
                          key={item.label}
                          to={item.to}
                          end={item.exact}
                          title={item.label}
                          onClick={() => setMobileOpen(false)}
                          className={({ isActive }) => {
                            const active = isNavItemActive(item, isActive);
                            return `flex items-center gap-3 px-3 py-2 text-[13px] rounded-lg transition ${
                              collapsed ? 'lg:justify-center lg:px-2' : ''
                            } ${
                              active
                                ? 'bg-[#EAF4FC] text-[#1D4ED8] border border-[#BFDBFE] font-semibold shadow-2xs'
                                : 'text-[#263445] font-medium border border-transparent hover:bg-[#EDF5FC] hover:text-[#2563EB]'
                            }`;
                          }}
                        >
                          <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
                          <span className={`truncate ${collapsed ? 'lg:hidden' : ''}`}>
                            {item.label}
                          </span>
                        </NavLink>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </nav>
        </div>

        {/* Admin Identity & Session Controls */}
        <div className="p-3.5 border-t border-[#D5DEE8] space-y-2.5 bg-[#F8FAFC]">
          <div className={`flex items-center gap-2.5 px-1 ${collapsed ? 'lg:justify-center' : ''}`}>
            <div className="w-8 h-8 rounded-full bg-[#EAF4FC] border border-[#BFDBFE] text-[#1D4ED8] text-[11px] font-bold flex items-center justify-center shrink-0">
              {adminInitials}
            </div>
            <div className={`min-w-0 ${collapsed ? 'lg:hidden' : ''}`}>
              <p className="text-[12.5px] font-semibold text-[#263445] truncate">
                {admin?.username || 'Administrator'}
              </p>
              <p className="text-[11px] text-[#64748B] truncate">{admin?.email || ''}</p>
            </div>
          </div>

          <div className={`grid gap-2 ${collapsed ? 'lg:grid-cols-1 grid-cols-2' : 'grid-cols-2'}`}>
            <Link
              to="/admin/change-password"
              title="Change Password"
              className="text-[11.5px] font-medium px-2.5 py-2 rounded-lg border border-[#D5DEE8] bg-white text-[#263445] hover:bg-[#EDF5FC] hover:text-[#2563EB] hover:border-[#93C5FD] transition flex items-center justify-center gap-1.5"
            >
              <KeyRound className="w-3.5 h-3.5 shrink-0" />
              <span className={collapsed ? 'lg:hidden' : ''}>Password</span>
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              title="Sign Out"
              className="text-[11.5px] font-medium px-2.5 py-2 rounded-lg border border-[#D5DEE8] bg-white hover:bg-red-50 hover:border-red-200 hover:text-[#DC2626] text-[#263445] transition flex items-center justify-center gap-1.5"
            >
              <LogOut className="w-3.5 h-3.5 shrink-0" />
              <span className={collapsed ? 'lg:hidden' : ''}>Logout</span>
            </button>
          </div>

          <Link
            to="/products"
            title="View Public Storefront"
            className="w-full text-[11.5px] font-semibold text-[#2563EB] hover:text-[#1D4ED8] flex items-center justify-center gap-1.5 pt-0.5"
          >
            <ExternalLink className="w-3.5 h-3.5 shrink-0" />
            <span className={collapsed ? 'lg:hidden' : ''}>View Storefront</span>
          </Link>
        </div>
      </aside>

      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-[#263445]/35 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-[#D5DEE8] px-6 py-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open admin menu"
              className="lg:hidden p-2 rounded-lg border border-[#D5DEE8] text-[#263445] hover:border-[#93C5FD] hover:bg-[#EDF5FC]"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div className="min-w-0">
              <h1 className="text-[20px] font-semibold tracking-tight text-[#263445] leading-snug truncate">
                {title}
              </h1>
              {subtitle && (
                <p className="text-[13px] text-[#64748B] mt-0.5 truncate">{subtitle}</p>
              )}
            </div>
          </div>

          {actions && <div className="flex flex-wrap items-center gap-2.5">{actions}</div>}
        </header>

        <main className="p-5 md:p-7 flex-1 overflow-x-hidden max-w-[1440px] w-full">
          {children}
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;
