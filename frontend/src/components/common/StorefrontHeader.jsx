import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
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
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const StorefrontHeader = ({ announcementText, storeName = 'DIGI-VERSE' }) => {
  const { isAuthenticated, customer, cartCount, wishlistCount } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="w-full">
      {announcementText && (
        <div className="max-w-7xl w-full mx-auto mb-4 px-4 py-2 rounded-xl bg-[#FFF2E6] border border-[#FFD4AE] text-[#D94300] text-xs font-medium flex items-center justify-center gap-2 text-center">
          <Sparkles className="w-3.5 h-3.5 text-[#FF6B0A] shrink-0" aria-hidden="true" />
          <span className="truncate">{announcementText}</span>
        </div>
      )}

      <header className="max-w-7xl w-full mx-auto bg-white border border-[#E5E7EB] rounded-2xl px-4 sm:px-6 py-3.5 shadow-[0_2px_10px_-2px_rgba(31,41,55,0.05)]">
        <div className="flex items-center justify-between gap-4">
          {/* Brand + Primary Nav */}
          <div className="flex items-center gap-6 lg:gap-8 min-w-0">
            <Link
              to="/"
              className="flex items-center gap-2.5 shrink-0 focus-visible:outline-2 focus-visible:outline-[#FF6B0A] rounded-xl"
            >
              <div className="w-9 h-9 rounded-xl bg-[#FF6B0A] text-white flex items-center justify-center shrink-0 shadow-[0_4px_12px_-2px_rgba(255,107,10,0.35)]">
                <Layers className="w-4 h-4" aria-hidden="true" />
              </div>
              <span className="font-bold tracking-tight text-base text-[#1F2937] whitespace-nowrap">
                {storeName}
                <span className="text-[#FF6B0A]">.</span>
              </span>
            </Link>

            <nav
              aria-label="Primary Navigation"
              className="hidden lg:flex items-center gap-4 xl:gap-6 text-xs font-semibold tracking-wide shrink-0"
            >
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  isActive
                    ? 'text-[#FF6B0A] border-b-2 border-[#FF6B0A] pb-1 transition'
                    : 'text-[#243247] hover:text-[#FF6B0A] pb-1 transition'
                }
              >
                Home
              </NavLink>
              <NavLink
                to="/products"
                className={({ isActive }) =>
                  isActive
                    ? 'text-[#FF6B0A] border-b-2 border-[#FF6B0A] pb-1 transition'
                    : 'text-[#243247] hover:text-[#FF6B0A] pb-1 transition'
                }
              >
                Products
              </NavLink>
              <NavLink
                to="/categories"
                className={({ isActive }) =>
                  isActive
                    ? 'text-[#FF6B0A] border-b-2 border-[#FF6B0A] pb-1 transition'
                    : 'text-[#243247] hover:text-[#FF6B0A] pb-1 transition'
                }
              >
                Categories
              </NavLink>
              <NavLink
                to="/stores"
                className={({ isActive }) =>
                  isActive
                    ? 'text-[#FF6B0A] border-b-2 border-[#FF6B0A] pb-1 transition'
                    : 'text-[#243247] hover:text-[#FF6B0A] pb-1 transition'
                }
              >
                Stores
              </NavLink>
              <NavLink
                to="/products?on_sale=true"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#FFF2E6] border border-[#FFD4AE] text-[#D94300] hover:bg-[#FFE9D6] transition"
              >
                Deals
              </NavLink>
            </nav>
          </div>

          {/* Customer Quick Actions */}
          <div className="flex items-center gap-2 sm:gap-2.5">
            {isAuthenticated ? (
              <>
                <NavLink
                  to="/wishlist"
                  aria-label={`Wishlist (${wishlistCount} items)`}
                  title="Wishlist"
                  className={({ isActive }) =>
                    `px-2.5 sm:px-3 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition ${
                      isActive
                        ? 'border-[#FFD4AE] bg-[#FFF2E6] text-[#D94300]'
                        : 'border-[#E5E7EB] bg-white text-[#243247] hover:border-[#FFD4AE] hover:bg-[#FFF0E2]'
                    }`
                  }
                >
                  <Heart className="w-3.5 h-3.5 text-[#FF6B0A]" aria-hidden="true" />
                  <span className="hidden xl:inline">Wishlist</span>
                  <span className="font-mono text-[11px] rounded-md bg-[#FFF6ED] text-[#D94300] px-1.5 py-0.5">
                    {wishlistCount}
                  </span>
                </NavLink>

                <NavLink
                  to="/cart"
                  aria-label={`Shopping Cart (${cartCount} items)`}
                  title="Shopping Cart"
                  className={({ isActive }) =>
                    `px-2.5 sm:px-3 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition ${
                      isActive
                        ? 'border-[#FFD4AE] bg-[#FFF2E6] text-[#D94300]'
                        : 'border-[#E5E7EB] bg-white text-[#243247] hover:border-[#FFD4AE] hover:bg-[#FFF0E2]'
                    }`
                  }
                >
                  <ShoppingBag className="w-3.5 h-3.5 text-[#FF6B0A]" aria-hidden="true" />
                  <span className="hidden xl:inline">Cart</span>
                  <span className="font-mono text-[11px] rounded-md bg-[#FF6B0A] text-white px-1.5 py-0.5">
                    {cartCount}
                  </span>
                </NavLink>

                <NavLink
                  to="/orders"
                  title="Orders"
                  className={({ isActive }) =>
                    `hidden lg:flex px-3 py-1.5 rounded-xl border text-xs font-medium items-center gap-1.5 transition ${
                      isActive
                        ? 'border-[#FFD4AE] bg-[#FFF2E6] text-[#D94300]'
                        : 'border-[#E5E7EB] bg-white text-[#243247] hover:border-[#FFD4AE] hover:bg-[#FFF0E2]'
                    }`
                  }
                >
                  <Package className="w-3.5 h-3.5 text-[#FF6B0A]" aria-hidden="true" />
                  <span className="hidden xl:inline">Orders</span>
                </NavLink>

                <NavLink
                  to="/downloads"
                  title="Digital Downloads"
                  className={({ isActive }) =>
                    `hidden lg:flex px-3 py-1.5 rounded-xl border text-xs font-medium items-center gap-1.5 transition ${
                      isActive
                        ? 'border-[#FFD4AE] bg-[#FFF2E6] text-[#D94300]'
                        : 'border-[#E5E7EB] bg-white text-[#243247] hover:border-[#FFD4AE] hover:bg-[#FFF0E2]'
                    }`
                  }
                >
                  <Download className="w-3.5 h-3.5 text-[#FF6B0A]" aria-hidden="true" />
                  <span className="hidden xl:inline">Downloads</span>
                </NavLink>

                <Link
                  to="/profile"
                  className="hidden lg:flex text-xs font-semibold px-3.5 py-1.5 rounded-xl bg-[#FF6B0A] text-white hover:bg-[#D94300] shadow-[0_4px_12px_-2px_rgba(255,107,10,0.28)] items-center gap-1.5 transition"
                >
                  <User className="w-3.5 h-3.5" aria-hidden="true" />
                  <span className="truncate max-w-[110px]">
                    {customer?.full_name || 'Account'}
                  </span>
                </Link>
              </>
            ) : (
              <div className="hidden sm:flex items-center gap-2.5">
                <Link
                  to="/login"
                  className="text-xs font-semibold text-[#243247] hover:text-[#FF6B0A] px-3 py-2 rounded-xl hover:bg-[#FFF0E2] transition"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="text-xs font-semibold px-4 py-2 rounded-xl bg-[#FF6B0A] text-white hover:bg-[#D94300] shadow-[0_4px_12px_-2px_rgba(255,107,10,0.28)] transition"
                >
                  Register
                </Link>
              </div>
            )}

            {/* Mobile Hamburger Button */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen((prev) => !prev)}
              aria-expanded={mobileMenuOpen}
              aria-label="Toggle navigation menu"
              className="lg:hidden p-2 rounded-xl border border-[#E5E7EB] bg-white text-[#243247] hover:border-[#FFD4AE] hover:bg-[#FFF0E2] transition"
            >
              {mobileMenuOpen ? (
                <X className="w-4 h-4" aria-hidden="true" />
              ) : (
                <Menu className="w-4 h-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Drawer Navigation */}
        {mobileMenuOpen && (
          <nav
            aria-label="Mobile Navigation"
            className="lg:hidden mt-4 pt-4 border-t border-[#E5E7EB] bg-[#FFFAF5] rounded-xl p-3 space-y-3 text-xs font-semibold"
          >
            <div className="grid grid-cols-2 gap-2">
              <Link
                to="/"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-white border border-[#E5E7EB] text-[#243247] hover:border-[#FFD4AE] hover:text-[#FF6B0A]"
              >
                Home
              </Link>
              <Link
                to="/products"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-white border border-[#E5E7EB] text-[#243247] hover:border-[#FFD4AE] hover:text-[#FF6B0A]"
              >
                Products
              </Link>
              <Link
                to="/categories"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-white border border-[#E5E7EB] text-[#243247] hover:border-[#FFD4AE] hover:text-[#FF6B0A]"
              >
                Categories
              </Link>
              <Link
                to="/stores"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-white border border-[#E5E7EB] text-[#243247] hover:border-[#FFD4AE] hover:text-[#FF6B0A]"
              >
                Creator Stores
              </Link>
              <Link
                to="/products?on_sale=true"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 rounded-xl bg-[#FFF2E6] border border-[#FFD4AE] text-[#D94300]"
              >
                Promotional Deals
              </Link>
            </div>

            {isAuthenticated ? (
              <div className="pt-2 border-t border-[#E5E7EB] grid grid-cols-2 gap-2">
                <Link
                  to="/orders"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2.5 rounded-xl bg-white border border-[#E5E7EB] text-[#243247] flex items-center gap-1.5"
                >
                  <Package className="w-3.5 h-3.5 text-[#FF6B0A]" />
                  <span>Orders</span>
                </Link>
                <Link
                  to="/downloads"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2.5 rounded-xl bg-white border border-[#E5E7EB] text-[#243247] flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5 text-[#FF6B0A]" />
                  <span>Downloads</span>
                </Link>
                <Link
                  to="/profile"
                  onClick={() => setMobileMenuOpen(false)}
                  className="col-span-2 px-3 py-2.5 rounded-xl bg-[#FF6B0A] text-white flex items-center justify-center gap-1.5"
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
                  className="px-3 py-2.5 rounded-xl bg-white border border-[#FFD4AE] text-[#D94300] text-center"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2.5 rounded-xl bg-[#FF6B0A] text-white text-center"
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
