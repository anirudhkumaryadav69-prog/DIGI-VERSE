import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_ROOT = path.resolve(__dirname, '..');
const SRC_DIR = path.join(FRONTEND_ROOT, 'src');
const DIST_DIR = path.join(FRONTEND_ROOT, 'dist');

function readSrc(relPath) {
  return fs.readFileSync(path.join(SRC_DIR, relPath), 'utf8');
}

test('1. Storefront Design System exports all required reusable primitives', () => {
  const ds = readSrc('components/common/StorefrontDesignSystem.jsx');
  const requiredExports = [
    'export const formatINR',
    'export const useDocumentMeta',
    'export const Button',
    'export const Input',
    'export const Badge',
    'export const SectionHeading',
    'export const LoadingState',
    'export const ProductCardSkeleton',
    'export const EmptyState',
    'export const ErrorAlert',
    'export const ToastBanner',
    'export const ConfirmDialog',
    'export const Pagination',
  ];
  for (const exp of requiredExports) {
    assert.ok(ds.includes(exp), `Missing export in StorefrontDesignSystem.jsx: ${exp}`);
  }
});

test('2. ProductCard & CategoryCard enforce lazy loading, accessibility, and link integrity', () => {
  const productCard = readSrc('components/products/ProductCard.jsx');
  assert.ok(productCard.includes('loading="lazy"'), 'ProductCard must lazy-load product images');
  assert.ok(
    productCard.includes('to={`/products/${product.slug}`}'),
    'ProductCard must link to /products/:slug'
  );
  assert.ok(
    productCard.includes('aria-label={`Add ${product.name} to cart`}'),
    'ProductCard must provide accessible button labels'
  );

  const categoryCard = readSrc('components/products/CategoryCard.jsx');
  assert.ok(
    categoryCard.includes('to={`/categories/${category.slug}`}'),
    'CategoryCard must link to /categories/:slug'
  );
});

test('3. Responsive StorefrontHeader, StorefrontFooter & StorefrontLayout prevent overflow', () => {
  const header = readSrc('components/common/StorefrontHeader.jsx');
  assert.ok(
    header.includes('aria-label="Toggle navigation menu"'),
    'StorefrontHeader must include accessible mobile menu toggle'
  );
  assert.ok(
    header.includes('aria-label="Primary Navigation"'),
    'StorefrontHeader must label primary navigation'
  );

  const layout = readSrc('components/common/StorefrontLayout.jsx');
  assert.ok(
    layout.includes('overflow-x-hidden'),
    'StorefrontLayout must guard against horizontal overflow'
  );
});

test('4. Homepage, Catalog, Detail, Cart, Wishlist, Checkout, Orders, Downloads & 404 routes are wired and code-split', () => {
  const routes = readSrc('routes/AppRoutes.jsx');
  assert.ok(routes.includes('<Route path="/" element={<HomePage />} />'));
  assert.ok(routes.includes('<Route path="/products" element={<ProductsCatalogPage />} />'));
  assert.ok(routes.includes('<Route path="/products/:slug" element={<ProductDetailPage />} />'));
  assert.ok(routes.includes('<Route path="/categories" element={<CategoriesPage />} />'));
  assert.ok(routes.includes('<Route path="/categories/:slug" element={<CategoryDetailPage />} />'));
  assert.ok(routes.includes('<Route path="/wishlist" element={<WishlistPage />} />'));
  assert.ok(routes.includes('<Route path="/cart" element={<CartPage />} />'));
  assert.ok(routes.includes('<Route path="/checkout" element={<CheckoutPage />} />'));
  assert.ok(routes.includes('<Route path="/orders" element={<CustomerOrdersPage />} />'));
  assert.ok(routes.includes('<Route path="/orders/:order_id" element={<CustomerOrderDetailPage />} />'));
  assert.ok(routes.includes('<Route path="/downloads" element={<CustomerDownloadsPage />} />'));
  assert.ok(routes.includes('<Route path="*" element={<NotFoundPage />} />'));
  assert.ok(
    routes.includes("lazy(() => import('../pages/admin/AdminDashboardPage'))"),
    'Admin routes must be lazy-loaded for code splitting'
  );
});

test('5. Product Catalog supports debounced search, on_sale filter, price filter, sorting, and stale-request protection', () => {
  const catalog = readSrc('pages/customer/ProductsCatalogPage.jsx');
  assert.ok(catalog.includes('latestRequestIdRef'), 'Catalog must guard against stale async responses');
  assert.ok(catalog.includes('setDebouncedSearch'), 'Catalog must debounce search input');
  assert.ok(catalog.includes('on_sale'), 'Catalog must support discounted product filtering');
  assert.ok(catalog.includes('handleClearFilters'), 'Catalog must support Clear All Filters');
});

test('6. Checkout enforces 6-stage flow, backend signature verification, and retry support', () => {
  const checkout = readSrc('pages/customer/CheckoutPage.jsx');
  assert.ok(checkout.includes('1. Review Order'));
  assert.ok(checkout.includes('2. Billing Details'));
  assert.ok(checkout.includes('3. Initialize Payment'));
  assert.ok(checkout.includes('4. Complete Payment'));
  assert.ok(checkout.includes('5. Server Verification'));
  assert.ok(checkout.includes('6. Final Result'));
  assert.ok(checkout.includes('commerceApi.verifyPayment'));
  assert.ok(checkout.includes('commerceApi.retryOrderPayment'));
});

test('7. Customer Authentication pages use StorefrontLayout, SEO metadata, and accessible form labels', () => {
  const authPages = [
    'pages/auth/LoginPage.jsx',
    'pages/auth/RegisterPage.jsx',
    'pages/auth/VerifyPhonePage.jsx',
    'pages/auth/ForgotPasswordPage.jsx',
    'pages/auth/ResetPasswordPage.jsx',
  ];
  for (const rel of authPages) {
    const src = readSrc(rel);
    assert.ok(src.includes('StorefrontLayout'), `${rel} must use StorefrontLayout`);
    assert.ok(src.includes('useDocumentMeta'), `${rel} must set SEO title & description`);
    assert.ok(src.includes('htmlFor='), `${rel} must provide accessible form labels`);
  }
});

test('8. Security review: no localStorage JWT tokens, no payment secrets, no private_download_url in storefront or bundle', () => {
  const apiSource = readSrc('services/api.js');
  assert.ok(!apiSource.includes('localStorage.setItem'), 'api.js must never store tokens in localStorage');
  assert.ok(apiSource.includes('X-CSRF-Token'), 'api.js must attach X-CSRF-Token on state-changing requests');
  assert.ok(apiSource.includes('digiverse:session-expired'), 'api.js must emit session-expired event on 401');

  const customerPagesDir = path.join(SRC_DIR, 'pages', 'customer');
  for (const file of fs.readdirSync(customerPagesDir)) {
    const content = fs.readFileSync(path.join(customerPagesDir, file), 'utf8');
    assert.ok(
      !content.includes('private_download_url'),
      `Customer page ${file} must never reference private_download_url`
    );
    assert.ok(
      !content.includes('localStorage.setItem'),
      `Customer page ${file} must never store tokens or signed URLs in localStorage`
    );
  }

  if (fs.existsSync(DIST_DIR)) {
    const assetsDir = path.join(DIST_DIR, 'assets');
    for (const asset of fs.readdirSync(assetsDir)) {
      if (asset.endsWith('.js')) {
        const bundleText = fs.readFileSync(path.join(assetsDir, asset), 'utf8');
        assert.ok(
          !bundleText.includes('digiverse_mock_gateway_hmac_secret_test_only'),
          'Production bundle must not contain mock payment HMAC secret'
        );
        assert.ok(
          !bundleText.includes('RAZORPAY_KEY_SECRET'),
          'Production bundle must not contain Razorpay secret key'
        );
      }
    }
  }
});

test('9. Phase 8.1 Admin private asset upload & Customer binary download integration checks', () => {
  const apiSource = readSrc('services/api.js');
  assert.ok(apiSource.includes('uploadProductAsset'), 'api.js must expose uploadProductAsset');
  assert.ok(apiSource.includes('deleteProductAsset'), 'api.js must expose deleteProductAsset');
  assert.ok(apiSource.includes('downloadAssetFile'), 'api.js must expose downloadAssetFile');

  const adminForm = readSrc('pages/admin/AdminProductFormPage.jsx');
  assert.ok(
    adminForm.includes('adminCatalogApi.uploadProductAsset'),
    'AdminProductFormPage must upload digital assets via adminCatalogApi.uploadProductAsset'
  );
  assert.ok(
    adminForm.includes('adminCatalogApi.deleteProductAsset'),
    'AdminProductFormPage must support deleting unpurchased digital assets'
  );

  const downloadsPage = readSrc('pages/customer/CustomerDownloadsPage.jsx');
  assert.ok(
    downloadsPage.includes('commerceApi.downloadAssetFile'),
    'CustomerDownloadsPage must download binary assets via commerceApi.downloadAssetFile'
  );
  assert.ok(
    !downloadsPage.includes('private_download_url'),
    'CustomerDownloadsPage must never reference private_download_url'
  );
});

test('10. Phase 9 Multi-vendor Seller Studio, Public Storefronts & Admin Governance checks', () => {
  const routes = readSrc('routes/AppRoutes.jsx');
  assert.ok(routes.includes('<Route path="/stores" element={<StoresDirectoryPage />} />'));
  assert.ok(routes.includes('<Route path="/store/:storeSlug" element={<SellerStorefrontPage />} />'));
  assert.ok(routes.includes('<Route path="/seller/apply" element={<SellerOnboardingPage />} />'));
  assert.ok(routes.includes('<Route element={<SellerRoute />}>'));
  assert.ok(routes.includes('<Route path="/seller" element={<SellerOverviewPage />} />'));
  assert.ok(routes.includes('<Route path="/seller/products" element={<SellerProductsPage />} />'));
  assert.ok(routes.includes('<Route path="/seller/orders" element={<SellerOrdersPage />} />'));
  assert.ok(routes.includes('<Route path="/admin/sellers" element={<AdminSellersPage />} />'));

  const sellerOverview = readSrc('pages/seller/SellerOverviewPage.jsx');
  assert.ok(
    sellerOverview.includes('Gross Product Sales'),
    'SellerOverviewPage must clearly label Gross Product Sales'
  );
  assert.ok(
    !sellerOverview.includes('Available Payout Balance'),
    'Phase 9 SellerOverviewPage must not show Phase 10 net payouts'
  );

  const sellerLayout = readSrc('layouts/SellerLayout.jsx');
  for (const label of [
    'Overview',
    'My Products',
    'Add Product',
    'Orders',
    'Store Profile',
    'Sales Analytics',
    'Account Settings',
  ]) {
    assert.ok(sellerLayout.includes(label), `SellerLayout must include ${label}`);
  }

  const productCard = readSrc('components/products/ProductCard.jsx');
  assert.ok(
    productCard.includes('/store/${product.seller.store_slug}'),
    'ProductCard must link seller attribution to /store/:storeSlug'
  );
});
