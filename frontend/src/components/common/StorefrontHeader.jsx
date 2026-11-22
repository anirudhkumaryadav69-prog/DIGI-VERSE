import { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import {
  Layers,
  Heart,
  ShoppingBag,
  Package,
  Download,
  User,
  Menu,
  X,
  Sparkles,
  Search,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const StorefrontHeader = ({ announcementText, storeName = 'DIGI-VERSE' }) => {
  const navigate = useNavigate();
  const { isAuthenticated, customer, cartCount, wishlistCount } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [headerQuery, setHeaderQuery] = useState('');

  const handleHeaderSearch = (e) => {
    e.preventDefault();
    const q = headerQuery.trim();
    navigate(q ? `/products?search=${encodeURIComponent(q)}` : '/products');
    setMobileMenuOpen(false);
  };

  return (
    <div className="w-full">
      {announcementText && (
        <div className="max-w-7xl w-full mx-auto mb-4 px-4 py-2 rounded-xl bg-[#DCE6EF] border border-[#D5DEE8] text-[#263445] text-xs font-medium flex items-center justify-center gap-2 text-center">
          <Sparkles className="w-3.5 h-3.5 text-[#2563EB] shrink-0" aria-hidden="true" />
          <span className="truncate">{announcementText}</span>
        </div>
      )}

      <header className="max-w-7xl w-full mx-auto bg-white border border-[#D5DEE8] rounded-2xl px-4 sm:px-6 py-3.5 shadow-[0_2px_10px_-2px_rgba(38,52,69,0.06)]">
        <div className="flex items-center justify-between gap-3 lg:gap-5">
          {/* Brand + Primary Nav */}
          <div className="flex items-center gap-4 xl:gap-6 shrink-0">
            <Link
              to="/"
              className="flex items-center gap-2.5 shrink-0 focus-visible:outline-2 focus-visible:outline-[#2563EB] rounded-xl"
            >
              <div className="w-9 h-9 rounded-xl bg-[#2563EB] text-white flex items-center justify-center shrink-0 shadow-[0_4px_12px_-2px_rgba(37,99,235,0.3)]">
                <Layers className="w-4 h-4" aria-hidden="true" />
              </div>
              <span className="font-bold tracking-tight text-base text-[#263445] whitespace-nowrap">
                {storeName}
                <span className="text-[#0EA5E9]">.</span>
              </span>
            </Link>

            <nav
              aria-label="Primary Navigation"
              className="hidden lg:flex items-center gap-3.5 xl:gap-4.5 text-[13px] font-semibold shrink-0 whitespace-nowrap"
            >
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  isActive
                    ? 'text-[#2563EB] border-b-2 border-[#2563EB] pb-1 transition whitespace-nowrap'
                    : 'text-[#263445] hover:text-[#2563EB] pb-1 transition whitespace-nowrap'
                }
              >
                Home
              </NavLink>
              <NavLink
                to="/products"
                className={({ isActive }) =>
                  isActive
                    ? 'text-[#2563EB] border-b-2 border-[#2563EB] pb-1 transition whitespace-nowrap'
                    : 'text-[#263445] hover:text-[#2563EB] pb-1 transition whitespace-nowrap'
                }
              >
                Products
              </NavLink>
              <NavLink
                to="/categories"
                className={({ isActive }) =>
                  isActive
                    ? 'text-[#2563EB] border-b-2 border-[#2563EB] pb-1 transition whitespace-nowrap'
                    : 'text-[#263445] hover:text-[#2563EB] pb-1 transition whitespace-nowrap'
                }
              >
                Categories
              </NavLink>
              <NavLink
                to="/stores"
                className={({ isActive }) =>
                  isActive
                    ? 'text-[#2563EB] border-b-2 border-[#2563EB] pb-1 transition whitespace-nowrap'
                    : 'text-[#263445] hover:text-[#2563EB] pb-1 transition whitespace-nowrap'
                }
              >
                Stores
              </NavLink>
              <NavLink
                to="/products?on_sale=true"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#EAF4FC] border border-[#D5DEE8] text-[#2563EB] hover:bg-[#EDF5FC] transition whitespace-nowrap"
              >
                Deals
              </NavLink>
            </nav>
          </div>

          {/* Search & Customer Quick Actions */}
          <div className="flex items-center justify-end gap-2 sm:gap-2.5 flex-1 min-w-0">
            <form
              onSubmit={handleHeaderSearch}
              className="hidden md:block relative flex-1 min-w-[140px] max-w-[230px]"
            >
              <label htmlFor="header-search-input" className="sr-only">
                Search marketplace
              </label>
              <Search
                className="w-3.5 h-3.5 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                aria-hidden="true"
              />
              <input
                id="header-search-input"
                type="search"
                value={headerQuery}
                onChange={(e) => setHeaderQuery(e.target.value)}
                placeholder="Search products..."
                className="w-full rounded-xl border border-[#D5DEE8] bg-[#F8FAFC] pl-9 pr-3 py-1.5 text-xs text-[#263445] placeholder:text-[#64748B] focus:bg-white focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/15 transition"
              />
            </form>

            {isAuthenticated ? (
              <>
                <NavLink
                  to="/wishlist"
                  aria-label={`Wishlist (${wishlistCount} items)`}
                  title="Wishlist"
                  className={({ isActive }) =>
                    `shrink-0 whitespace-nowrap px-2.5 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition ${
                      isActive
                        ? 'border-[#93C5FD] bg-[#EDF5FC] text-[#1D4ED8]'
                        : 'border-[#D5DEE8] bg-white text-[#263445] hover:border-[#93C5FD] hover:bg-[#EDF5FC]'
                    }`
                  }
                >
                  <Heart className="w-3.5 h-3.5 text-[#2563EB] shrink-0" aria-hidden="true" />
                  <span className="font-mono text-[11px] rounded-md bg-[#EAF4FC] text-[#1D4ED8] px-1.5 py-0.5">
                    {wishlistCount}
                  </span>
                </NavLink>

                <NavLink
                  to="/cart"
                  aria-label={`Shopping Cart (${cartCount} items)`}
                  title="Shopping Cart"
                  className={({ isActive }) =>
                    `shrink-0 whitespace-nowrap px-2.5 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition ${
                      isActive
                        ? 'border-[#93C5FD] bg-[#EDF5FC] text-[#1D4ED8]'
                        : 'border-[#D5DEE8] bg-white text-[#263445] hover:border-[#93C5FD] hover:bg-[#EDF5FC]'
                    }`
                  }
                >
                  <ShoppingBag className="w-3.5 h-3.5 text-[#2563EB] shrink-0" aria-hidden="true" />
                  <span className="font-mono text-[11px] rounded-md bg-[#2563EB] text-white px-1.5 py-0.5">
                    {cartCount}
                  </span>
                </NavLink>

                <NavLink
                  to="/orders"
                  aria-label="Orders"
                  title="Orders"
                  className={({ isActive }) =>
                    `hidden xl:flex shrink-0 whitespace-nowrap px-2.5 py-1.5 rounded-xl border text-xs font-medium items-center gap-1.5 transition ${
                      isActive
                        ? 'border-[#93C5FD] bg-[#EDF5FC] text-[#1D4ED8]'
                        : 'border-[#D5DEE8] bg-white text-[#263445] hover:border-[#93C5FD] hover:bg-[#EDF5FC]'
                    }`
                  }
                >
                  <Package className="w-3.5 h-3.5 text-[#2563EB] shrink-0" aria-hidden="true" />
                </NavLink>

                <NavLink
                  to="/downloads"
                  aria-label="Digital Downloads"
                  title="Digital Downloads"
                  className={({ isActive }) =>
                    `hidden xl:flex shrink-0 whitespace-nowrap px-2.5 py-1.5 rounded-xl border text-xs font-medium items-center gap-1.5 transition ${
                      isActive
                        ? 'border-[#93C5FD] bg-[#EDF5FC] text-[#1D4ED8]'
                        : 'border-[#D5DEE8] bg-white text-[#263445] hover:border-[#93C5FD] hover:bg-[#EDF5FC]'
                    }`
                  }
                >
                  <Download className="w-3.5 h-3.5 text-[#2563EB] shrink-0" aria-hidden="true" />
                </NavLink>

                <Link
                  to="/profile"
                  aria-label={`Account: ${customer?.full_name || 'My Account'}`}
                  title={customer?.full_name || 'Account'}
                  className="hidden lg:flex shrink-0 whitespace-nowrap text-xs font-semibold px-2.5 xl:px-3.5 py-1.5 rounded-xl bg-[#2563EB] text-white hover:bg-[#1D4ED8] shadow-[0_2px_8px_-1px_rgba(37,99,235,0.25)] items-center gap-1.5 transition"
                >
                  <User className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                  <span className="hidden xl:inline truncate max-w-[110px]">
                    {customer?.full_name || 'Account'}
                  </span>
                </Link>
              </>
            ) : (
              <div className="hidden sm:flex items-center gap-2 shrink-0">
                <Link
                  to="/login"
                  className="text-xs font-semibold text-[#263445] hover:text-[#2563EB] px-3 py-2 rounded-xl hover:bg-[#EDF5FC] transition whitespace-nowrap"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="text-xs font-semibold px-4 py-2 rounded-xl bg-[#2563EB] text-white hover:bg-[#1D4ED8] shadow-[0_2px_8px_-1px_rgba(37,99,235,0.25)] transition whitespace-nowrap"
                >
                  Register
                </Link>
              </div>
            )}

            {/* Responsive Drawer Toggle Button (collapses Orders/Downloads/nav below desktop xl when signed in) */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen((prev) => !prev)}
              aria-expanded={mobileMenuOpen}
              aria-label="Toggle navigation menu"
              className={`${
                isAuthenticated ? 'xl:hidden' : 'lg:hidden'
              } shrink-0 p-2 rounded-xl border border-[#D5DEE8] bg-white text-[#263445] hover:border-[#93C5FD] hover:bg-[#EDF5FC] transition`}
            >
              {mobileMenuOpen ? (
                <X className="w-4 h-4" aria-hidden="true" />
              ) : (
                <Menu className="w-4 h-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile / Narrow-Desktop Drawer Navigation */}
        {mobileMenuOpen && (
          <nav
            aria-label="Mobile Navigation"
            className={`${
              isAuthenticated ? 'xl:hidden' : 'lg:hidden'
            } mt-4 pt-4 border-t border-[#E5E7EB] bg-[#F8FAFC] rounded-xl p-3 space-y-3 text-xs font-semibold`}
          >
            <form onSubmit={handleHeaderSearch} className="relative">
              <Search
                className="w-3.5 h-3.5 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                aria-hidden="true"
              />
              <input
                type="search"
                value={headerQuery}
                onChange={(e) => setHeaderQuery(e.target.value)}
                placeholder="Search products..."
                className="w-full rounded-xl border border-[#D5DEE8] bg-white pl-8.5 pr-3 py-2 text-xs text-[#263445] placeholder:text-[#64748B]"
              />
            </form>

            <div className="grid grid-cols-2 gap-2">
              <Link
                to="/"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-white border border-[#D5DEE8] text-[#263445] hover:border-[#93C5FD] hover:text-[#2563EB]"
              >
                Home
              </Link>
              <Link
                to="/products"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-white border border-[#D5DEE8] text-[#263445] hover:border-[#93C5FD] hover:text-[#2563EB]"
              >
                Products
              </Link>
              <Link
                to="/categories"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-white border border-[#D5DEE8] text-[#263445] hover:border-[#93C5FD] hover:text-[#2563EB]"
              >
                Categories
              </Link>
              <Link
                to="/stores"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-white border border-[#D5DEE8] text-[#263445] hover:border-[#93C5FD] hover:text-[#2563EB]"
              >
                Creator Stores
              </Link>
              <Link
                to="/products?on_sale=true"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-[#EAF4FC] border border-[#BFDBFE] text-[#1D4ED8]"
              >
                Promotional Deals
              </Link>
            </div>

            {isAuthenticated ? (
              <div className="pt-2 border-t border-[#E5E7EB] grid grid-cols-2 gap-2">
                <Link
                  to="/orders"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2.5 rounded-xl bg-white border border-[#D5DEE8] text-[#263445] flex items-center gap-1.5"
                >
                  <Package className="w-3.5 h-3.5 text-[#2563EB]" />
                  <span>Orders</span>
                </Link>
                <Link
                  to="/downloads"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2.5 rounded-xl bg-white border border-[#D5DEE8] text-[#263445] flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5 text-[#2563EB]" />
                  <span>Downloads</span>
                </Link>
                <Link
                  to="/profile"
                  onClick={() => setMobileMenuOpen(false)}
                  className="col-span-2 px-3 py-2.5 rounded-xl bg-[#2563EB] text-white flex items-center justify-center gap-1.5"
                >
                  <User className="w-3.5 h-3.5" />
                  <span>{customer?.full_name || 'My Account'}</span>
                </Link>
              </div>
            ) : (
              <div className="pt-2 border-t border-[#E5E7EB] grid grid-cols-2 gap-2">
                <Link
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2.5 rounded-xl bg-[#EAF4FC] border border-[#D5DEE8] text-[#263445] text-center"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2.5 rounded-xl bg-[#2563EB] text-white text-center"
                >
                  Register
                </Link>
              </div>
            )}
          </nav>
        )}
      </header>
    </div>
  );
};

export default StorefrontHeader;
