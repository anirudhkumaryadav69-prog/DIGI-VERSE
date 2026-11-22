import { Suspense, lazy } from 'react';
import { Routes, Route } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import AdminRoute from './AdminRoute';
import SellerRoute from './SellerRoute';
import { LoadingState } from '../components/common/StorefrontDesignSystem';

import HomePage from '../pages/customer/HomePage';

// Lazy-loaded Storefront & Customer Routes (Code-Split for fast initial Homepage LCP)
const ProductsCatalogPage = lazy(() => import('../pages/customer/ProductsCatalogPage'));
const ProductDetailPage = lazy(() => import('../pages/customer/ProductDetailPage'));
const CategoriesPage = lazy(() => import('../pages/customer/CategoriesPage'));
const CategoryDetailPage = lazy(() => import('../pages/customer/CategoryDetailPage'));
const WishlistPage = lazy(() => import('../pages/customer/WishlistPage'));
const CartPage = lazy(() => import('../pages/customer/CartPage'));
const CheckoutPage = lazy(() => import('../pages/customer/CheckoutPage'));
const CustomerOrdersPage = lazy(() => import('../pages/customer/CustomerOrdersPage'));
const CustomerOrderDetailPage = lazy(() => import('../pages/customer/CustomerOrderDetailPage'));
const CustomerDownloadsPage = lazy(() => import('../pages/customer/CustomerDownloadsPage'));
const StoresDirectoryPage = lazy(() => import('../pages/customer/StoresDirectoryPage'));
const SellerStorefrontPage = lazy(() => import('../pages/customer/SellerStorefrontPage'));
const NotFoundPage = lazy(() => import('../pages/customer/NotFoundPage'));

const SellerOnboardingPage = lazy(() => import('../pages/seller/SellerOnboardingPage'));
const SellerOverviewPage = lazy(() => import('../pages/seller/SellerOverviewPage'));
const SellerProductsPage = lazy(() => import('../pages/seller/SellerProductsPage'));
const SellerProductFormPage = lazy(() => import('../pages/seller/SellerProductFormPage'));
const SellerOrdersPage = lazy(() => import('../pages/seller/SellerOrdersPage'));
const SellerProfilePage = lazy(() => import('../pages/seller/SellerProfilePage'));
const SellerAnalyticsPage = lazy(() => import('../pages/seller/SellerAnalyticsPage'));
const SellerFinancialPage = lazy(() => import('../pages/seller/SellerFinancialPage'));
const SellerPayoutPage = lazy(() => import('../pages/seller/SellerPayoutPage'));

const RegisterPage = lazy(() => import('../pages/auth/RegisterPage'));
const LoginPage = lazy(() => import('../pages/auth/LoginPage'));
const VerifyPhonePage = lazy(() => import('../pages/auth/VerifyPhonePage'));
const ForgotPasswordPage = lazy(() => import('../pages/auth/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('../pages/auth/ResetPasswordPage'));
const CustomerProfilePage = lazy(() => import('../pages/customer-dashboard/CustomerProfilePage'));

// Lazy-loaded Administrative Console Routes (Code-Split from Customer Storefront)
const AdminLoginPage = lazy(() => import('../pages/admin/AdminLoginPage'));
const AdminChangePasswordPage = lazy(() => import('../pages/admin/AdminChangePasswordPage'));
const AdminDashboardPage = lazy(() => import('../pages/admin/AdminDashboardPage'));
const AdminCategoriesPage = lazy(() => import('../pages/admin/AdminCategoriesPage'));
const AdminCategoryFormPage = lazy(() => import('../pages/admin/AdminCategoryFormPage'));
const AdminProductsPage = lazy(() => import('../pages/admin/AdminProductsPage'));
const AdminProductFormPage = lazy(() => import('../pages/admin/AdminProductFormPage'));
const AdminOrdersPage = lazy(() => import('../pages/admin/AdminOrdersPage'));
const AdminOrderDetailPage = lazy(() => import('../pages/admin/AdminOrderDetailPage'));
const AdminCustomersPage = lazy(() => import('../pages/admin/AdminCustomersPage'));
const AdminSellersPage = lazy(() => import('../pages/admin/AdminSellersPage'));
const AdminBannersPage = lazy(() => import('../pages/admin/AdminBannersPage'));
const AdminVideosPage = lazy(() => import('../pages/admin/AdminVideosPage'));
const AdminMarketingPage = lazy(() => import('../pages/admin/AdminMarketingPage'));
const AdminSettingsPage = lazy(() => import('../pages/admin/AdminSettingsPage'));
const AdminFinancialPage = lazy(() => import('../pages/admin/AdminFinancialPage'));
const AdminPayoutPage = lazy(() => import('../pages/admin/AdminPayoutPage'));

const AppRoutes = () => {
  return (
    <Suspense fallback={<LoadingState label="Loading Application..." />}>
      <Routes>
        {/* Public Storefront, Catalog & Customer Authentication Routes */}
        <Route path="/" element={<HomePage />} />
        <Route path="/products" element={<ProductsCatalogPage />} />
        <Route path="/products/:slug" element={<ProductDetailPage />} />
        <Route path="/categories" element={<CategoriesPage />} />
        <Route path="/categories/:slug" element={<CategoryDetailPage />} />
        <Route path="/stores" element={<StoresDirectoryPage />} />
        <Route path="/store/:storeSlug" element={<SellerStorefrontPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/* Customer Protected Routes */}
        <Route element={<ProtectedRoute />}>
          <Route path="/verify-phone" element={<VerifyPhonePage />} />
          <Route path="/profile" element={<CustomerProfilePage />} />
          <Route path="/dashboard" element={<CustomerProfilePage />} />
          <Route path="/wishlist" element={<WishlistPage />} />
          <Route path="/cart" element={<CartPage />} />
          <Route path="/checkout" element={<CheckoutPage />} />
          <Route path="/orders" element={<CustomerOrdersPage />} />
          <Route path="/orders/:order_id" element={<CustomerOrderDetailPage />} />
          <Route path="/downloads" element={<CustomerDownloadsPage />} />
          <Route path="/seller/apply" element={<SellerOnboardingPage />} />
          <Route path="/seller/onboarding" element={<SellerOnboardingPage />} />
        </Route>

        {/* Approved Seller Studio Routes */}
        <Route element={<SellerRoute />}>
          <Route path="/seller" element={<SellerOverviewPage />} />
          <Route path="/seller/products" element={<SellerProductsPage />} />
          <Route path="/seller/products/new" element={<SellerProductFormPage />} />
          <Route path="/seller/products/:id/edit" element={<SellerProductFormPage />} />
          <Route path="/seller/orders" element={<SellerOrdersPage />} />
          <Route path="/seller/profile" element={<SellerProfilePage />} />
          <Route path="/seller/analytics" element={<SellerAnalyticsPage />} />
          <Route path="/seller/financial" element={<SellerFinancialPage />} />
          <Route path="/seller/payouts" element={<SellerPayoutPage />} />
        </Route>

        {/* Administrator Authentication & Protected Routes */}
        <Route path="/admin/login" element={<AdminLoginPage />} />
        <Route element={<AdminRoute allowPasswordChangePending={true} />}>
          <Route path="/admin/change-password" element={<AdminChangePasswordPage />} />
        </Route>
        <Route element={<AdminRoute />}>
          <Route path="/admin" element={<AdminDashboardPage />} />
          <Route path="/admin/categories" element={<AdminCategoriesPage />} />
          <Route path="/admin/categories/new" element={<AdminCategoryFormPage />} />
          <Route path="/admin/categories/:id/edit" element={<AdminCategoryFormPage />} />
          <Route path="/admin/products" element={<AdminProductsPage />} />
          <Route path="/admin/products/new" element={<AdminProductFormPage />} />
          <Route path="/admin/products/:id/edit" element={<AdminProductFormPage />} />
          <Route path="/admin/orders" element={<AdminOrdersPage />} />
          <Route path="/admin/orders/:order_id" element={<AdminOrderDetailPage />} />
          <Route path="/admin/customers" element={<AdminCustomersPage />} />
          <Route path="/admin/sellers" element={<AdminSellersPage />} />
          <Route path="/admin/banners" element={<AdminBannersPage />} />
          <Route path="/admin/videos" element={<AdminVideosPage />} />
          <Route path="/admin/marketing" element={<AdminMarketingPage />} />
          <Route path="/admin/settings" element={<AdminSettingsPage />} />
          <Route path="/admin/financial" element={<AdminFinancialPage />} />
          <Route path="/admin/payouts" element={<AdminPayoutPage />} />
        </Route>

        {/* 404 Not Found Route */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
};

export default AppRoutes;
