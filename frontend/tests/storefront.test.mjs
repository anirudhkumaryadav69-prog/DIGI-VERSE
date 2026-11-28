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

test('11. Phase 10.1 Seller Financial Dashboard is routed and uses backend financial APIs', () => {
  const routes = readSrc('routes/AppRoutes.jsx');
  const layout = readSrc('layouts/SellerLayout.jsx');
  const api = readSrc('services/api.js');
  const page = readSrc('pages/seller/SellerFinancialPage.jsx');

  assert.ok(routes.includes('<Route path="/seller/financial" element={<SellerFinancialPage />} />'));
  assert.ok(layout.includes("to: '/seller/financial'"));
  for (const method of [
    'getFinancialSummary',
    'getFinancialTransactions',
    'getFinancialOrders',
    'getFinancialOrderItems',
  ]) {
    assert.ok(api.includes(method), `Seller API must expose ${method}`);
  }
  assert.ok(page.includes('/api/seller/financial') === false);
  assert.ok(page.includes('Gross sales'));
  assert.ok(page.includes('Pending earnings'));
  assert.ok(page.includes('Available earnings'));
  assert.ok(page.includes('Settled amount'));
  assert.ok(page.includes('LoadingState'));
  assert.ok(page.includes('Pagination'));
});

test('16. OTP verification UI distinguishes development, WhatsApp, and resend states', () => {
  const verifyPage = readSrc('pages/auth/VerifyPhonePage.jsx');
  const authApi = readSrc('services/api.js');

  assert.ok(verifyPage.includes('Development mode'));
  assert.ok(verifyPage.includes('WhatsApp'));
  assert.ok(verifyPage.includes('otpDeliveryStatus'));
  assert.ok(authApi.includes("verifyOtp"));
  assert.ok(authApi.includes("sendOtp"));
});

test('15. Phase 10.2 Stage 6.3 Payout operations includes verification and reconciliation interfaces', () => {
  const api = readSrc('services/api.js');
  const page = readSrc('pages/admin/AdminPayoutPage.jsx');

  for (const method of [
    'listVerification',
    'getAccount',
    'approveAccount',
    'rejectAccount',
    'getHistory',
  ]) {
    assert.ok(api.includes(method), `Payout account verification API must expose ${method}`);
  }
  assert.ok(page.includes("id: 'overview'"));
  assert.ok(page.includes("id: 'requests'"));
  assert.ok(page.includes("id: 'reconciliation'"));
  assert.ok(page.includes("id: 'verification'"));
  assert.ok(page.includes("id: 'reports'"));
  assert.ok(page.includes('Record reconciliation resolution'));
  assert.ok(page.includes('Mandatory reason'));
  assert.ok(page.includes('No real money was transferred'));
  assert.ok(page.includes('Payout account verification'));
});

test('12. Phase 10.1 Admin Financial Management is guarded and integrates all financial endpoints', () => {
  const routes = readSrc('routes/AppRoutes.jsx');
  const layout = readSrc('layouts/AdminLayout.jsx');
  const api = readSrc('services/api.js');
  const page = readSrc('pages/admin/AdminFinancialPage.jsx');

  assert.ok(routes.includes('<Route path="/admin/financial" element={<AdminFinancialPage />} />'));
  assert.ok(layout.includes("to: '/admin/financial'"));
  for (const method of [
    'getCommission',
    'updateCommission',
    'listSellerCommissions',
    'getSellerCommission',
    'updateSellerCommission',
    'removeSellerCommission',
    'getLedger',
    'getCommissionReport',
  ]) {
    assert.ok(api.includes(method), `Admin financial API must expose ${method}`);
  }
  assert.ok(page.includes('Global commission'));
  assert.ok(page.includes('Seller commission overrides'));
  assert.ok(page.includes('Financial ledger'));
  assert.ok(page.includes('Commission report'));
  assert.ok(page.includes('Commission history'));
  assert.ok(page.includes('aria-label="Seller filter"'));
});

test('13. Phase 10.2 Seller Payout Dashboard exposes backend balances and masked account management', () => {
  const routes = readSrc('routes/AppRoutes.jsx');
  const layout = readSrc('layouts/SellerLayout.jsx');
  const api = readSrc('services/api.js');
  const page = readSrc('pages/seller/SellerPayoutPage.jsx');

  assert.ok(routes.includes('<Route path="/seller/payouts" element={<SellerPayoutPage />} />'));
  assert.ok(layout.includes("to: '/seller/payouts'"));
  for (const method of [
    'getBalance',
    'listAccounts',
    'createAccount',
    'updateAccount',
    'setDefaultAccount',
    'deactivateAccount',
    'createRequest',
    'listRequests',
    'getRequest',
    'cancelRequest',
    'getAttempts',
  ]) {
    assert.ok(api.includes(method), `Seller payout API must expose ${method}`);
  }
  assert.ok(page.includes('Signed payable'));
  assert.ok(page.includes('Outstanding debt'));
  assert.ok(page.includes('Reserved payout'));
  assert.ok(page.includes('Available withdrawal'));
  assert.ok(page.includes('Settled payout'));
  assert.ok(page.includes('No money has been transferred'));
  assert.ok(page.includes('Payout request history'));
  assert.ok(page.includes('Execution timeline'));
  assert.ok(page.includes('Simulated execution'));
  assert.ok(page.includes('Edit masked payout account') || page.includes('>Edit<'));
  assert.ok(page.includes('LoadingState'));
});

test('14. Phase 10.2 Admin Payout Dashboard exposes review, approval, rejection and reporting', () => {
  const routes = readSrc('routes/AppRoutes.jsx');
  const layout = readSrc('layouts/AdminLayout.jsx');
  const api = readSrc('services/api.js');
  const page = readSrc('pages/admin/AdminPayoutPage.jsx');

  assert.ok(routes.includes('<Route path="/admin/payouts" element={<AdminPayoutPage />} />'));
  assert.ok(layout.includes("to: '/admin/payouts'"));
  for (const method of [
    'listRequests',
    'getRequest',
    'reviewRequest',
    'approveRequest',
    'rejectRequest',
    'getReport',
    'getDetail',
    'executeRequest',
    'retryRequest',
    'listAttempts',
    'listReconciliation',
    'getReconciliationSummary',
    'getReconciliationDetail',
    'resolveReconciliation',
  ]) {
    assert.ok(api.includes(method), `Admin payout API must expose ${method}`);
  }
  assert.ok(page.includes('Payout Management'));
  assert.ok(page.includes('Mandatory rejection reason'));
  assert.ok(page.includes('does not execute or confirm a money transfer'));
  assert.ok(page.includes('Apply filters'));
  assert.ok(page.includes('LoadingState'));
  assert.ok(page.includes('Pagination'));
});

test('17. Stage A: Razorpay Checkout SDK loads lazily, prevents duplicates, and handles load errors', async () => {
  const indexHtml = fs.readFileSync(path.join(FRONTEND_ROOT, 'index.html'), 'utf8');
  assert.ok(
    !indexHtml.includes('checkout.razorpay.com'),
    'index.html must not statically load Razorpay Checkout SDK globally'
  );

  const checkoutSrc = readSrc('pages/customer/CheckoutPage.jsx');
  assert.ok(checkoutSrc.includes('loadRazorpaySdk'), 'CheckoutPage must use lazy loadRazorpaySdk');
  assert.ok(checkoutSrc.includes('payment.failed'), 'CheckoutPage must handle Razorpay payment.failed events');

  const vercelJson = JSON.parse(fs.readFileSync(path.join(FRONTEND_ROOT, 'vercel.json'), 'utf8'));
  assert.ok(
    !JSON.stringify(vercelJson).includes('REPLACE-WITH-YOUR-STAGING-API-HOST'),
    'vercel.json must not contain placeholder backend hostnames'
  );
  assert.ok(
    vercelJson.rewrites?.some(
      (r) => r.source === '/((?!api(?:/|$)).*)' && r.destination === '/index.html'
    ),
    'vercel.json must preserve SPA fallback rewrite while excluding /api and /api/* routes'
  );

  const { loadRazorpaySdk, RAZORPAY_CHECKOUT_SCRIPT_URL, resetRazorpayLoaderForTests } = await import(
    '../src/utils/razorpay.js'
  );

  const createMockDom = () => {
    const scripts = [];
    const defaultView = {};
    const makeScript = () => {
      const listeners = {};
      const el = {
        src: '',
        async: false,
        dataset: {},
        addEventListener: (evt, fn) => {
          listeners[evt] = listeners[evt] || [];
          listeners[evt].push(fn);
        },
        removeEventListener: (evt, fn) => {
          listeners[evt] = (listeners[evt] || []).filter((f) => f !== fn);
        },
        dispatch: (evt) => {
          for (const fn of [...(listeners[evt] || [])]) fn();
        },
        remove: () => {
          const idx = scripts.indexOf(el);
          if (idx >= 0) scripts.splice(idx, 1);
        },
      };
      return el;
    };
    const doc = {
      defaultView,
      head: {
        appendChild: (el) => {
          scripts.push(el);
        },
      },
      createElement: (tag) => {
        assert.equal(tag, 'script');
        return makeScript();
      },
      querySelector: (sel) => {
        if (sel.includes(RAZORPAY_CHECKOUT_SCRIPT_URL)) {
          return scripts.find((s) => s.src === RAZORPAY_CHECKOUT_SCRIPT_URL) || null;
        }
        return null;
      },
    };
    return { doc, defaultView, scripts };
  };

  // 1. Concurrent calls inject only a single script tag
  resetRazorpayLoaderForTests();
  const dom1 = createMockDom();
  const p1 = loadRazorpaySdk({ doc: dom1.doc, timeoutMs: 2000 });
  const p2 = loadRazorpaySdk({ doc: dom1.doc, timeoutMs: 2000 });
  assert.equal(dom1.scripts.length, 1);
  assert.equal(dom1.scripts[0].src, RAZORPAY_CHECKOUT_SCRIPT_URL);
  function MockRazorpay() {}
  dom1.defaultView.Razorpay = MockRazorpay;
  dom1.scripts[0].dispatch('load');
  const [ctor1, ctor2] = await Promise.all([p1, p2]);
  assert.equal(ctor1, MockRazorpay);
  assert.equal(ctor2, MockRazorpay);

  // 2. Script load error rejects clearly and allows retry without duplicate lingering scripts
  resetRazorpayLoaderForTests();
  const dom2 = createMockDom();
  const errPromise = loadRazorpaySdk({ doc: dom2.doc, timeoutMs: 2000 });
  assert.equal(dom2.scripts.length, 1);
  dom2.scripts[0].dispatch('error');
  await assert.rejects(errPromise, /Unable to load the Razorpay payment gateway/);

  const retryPromise = loadRazorpaySdk({ doc: dom2.doc, timeoutMs: 2000 });
  assert.equal(dom2.scripts.length, 1);
  dom2.defaultView.Razorpay = MockRazorpay;
  dom2.scripts[0].dispatch('load');
  assert.equal(await retryPromise, MockRazorpay);

  // 3. Load event without window.Razorpay rejects cleanly
  resetRazorpayLoaderForTests();
  const dom3 = createMockDom();
  const missingCtorPromise = loadRazorpaySdk({ doc: dom3.doc, timeoutMs: 2000 });
  dom3.scripts[0].dispatch('load');
  await assert.rejects(missingCtorPromise, /window\.Razorpay is unavailable/);
});

test('18. Production stability: Vercel /api exclusion, HTML fallback guard, HomePage/AuthContext safety & ErrorBoundary', async () => {
  const vercelJson = JSON.parse(fs.readFileSync(path.join(FRONTEND_ROOT, 'vercel.json'), 'utf8'));
  const apiProxyRewrite = vercelJson.rewrites?.find(
    (r) => r.source === '/api/:path*' && /^https:\/\/.+\/api\/:path\*$/.test(r.destination || '')
  );
  assert.ok(apiProxyRewrite, 'vercel.json must preserve the /api/:path* backend reverse proxy');

  const spaRewrite = vercelJson.rewrites?.find((r) => r.destination === '/index.html');
  assert.ok(spaRewrite, 'vercel.json must include an /index.html SPA rewrite');
  assert.equal(spaRewrite.source, '/((?!api(?:/|$)).*)');
  const spaRegex = new RegExp(`^${spaRewrite.source}$`);
  assert.equal(spaRegex.test('/api'), false, 'bare /api must not match SPA rewrite');
  assert.equal(spaRegex.test('/api/health'), false, '/api/health must not match SPA rewrite');
  assert.equal(spaRegex.test('/api/auth/login'), false, '/api/auth/login must not match SPA rewrite');
  assert.equal(spaRegex.test('/api/banners'), false, '/api/banners must not match SPA rewrite');
  assert.equal(spaRegex.test('/api/auth/me'), false, '/api/auth/me must not match SPA rewrite');
  assert.equal(spaRegex.test('/'), true, '/ must match SPA rewrite');
  assert.equal(spaRegex.test('/products'), true, '/products must match SPA rewrite');
  assert.equal(spaRegex.test('/categories'), true, '/categories must match SPA rewrite');
  assert.equal(spaRegex.test('/admin/login'), true, '/admin/login must match SPA rewrite');
  assert.equal(spaRegex.test('/seller'), true, '/seller must match SPA rewrite');

  const {
    asArray,
    asPaginatedItems,
    asPlainObject,
    isHtmlPayload,
    isValidAdminProfile,
    isValidCustomerProfile,
    validateApiResponse,
  } = await import('../src/utils/apiValidation.js');

  const htmlDoc = '<!doctype html><html lang="en"><body><div id="root"></div></body></html>';
  const htmlTagOnly = '  <HTML><head></head><body>Fallback</body></html>';

  // 1. HTML detection & interceptor validation
  assert.equal(isHtmlPayload(htmlDoc), true);
  assert.equal(isHtmlPayload(htmlTagOnly), true);
  assert.equal(isHtmlPayload({ items: [] }), false);
  assert.equal(isHtmlPayload(null), false);

  assert.throws(
    () =>
      validateApiResponse({
        status: 200,
        headers: { 'content-type': 'text/html; charset=utf-8' },
        config: {},
        data: htmlDoc,
      }),
    (err) => err.code === 'API_HTML_RESPONSE' && typeof err.response?.data?.detail === 'string'
  );

  assert.throws(
    () =>
      validateApiResponse({
        status: 200,
        headers: { 'content-type': 'application/json' },
        config: {},
        data: htmlTagOnly,
      }),
    (err) => err.code === 'API_HTML_RESPONSE'
  );

  // 2. Preserve valid JSON, 204, and binary / explicit non-JSON responses
  const validJson = validateApiResponse({
    status: 200,
    headers: { 'content-type': 'application/json' },
    config: {},
    data: [{ id: 'banner-1' }],
  });
  assert.deepEqual(validJson.data, [{ id: 'banner-1' }]);

  const noContent = validateApiResponse({ status: 204, headers: {}, config: {}, data: '' });
  assert.equal(noContent.status, 204);

  const blobPayload = { size: 512, type: 'application/zip' };
  assert.equal(
    validateApiResponse({
      status: 200,
      headers: { 'content-type': 'application/octet-stream' },
      config: { responseType: 'blob' },
      data: blobPayload,
    }).data,
    blobPayload
  );
  assert.equal(
    validateApiResponse({
      status: 200,
      headers: { 'content-type': 'text/html' },
      config: { responseType: 'arraybuffer' },
      data: new ArrayBuffer(8),
    }).status,
    200
  );

  // 3. HomePage safe array & plain-object coercion
  for (const malformed of [htmlDoc, {}, null, undefined, 123, 'bad']) {
    assert.deepEqual(asArray(malformed), []);
    assert.deepEqual(asPaginatedItems(malformed), []);
  }
  assert.deepEqual(asArray([{ id: 'b1' }]), [{ id: 'b1' }]);
  assert.deepEqual(asPaginatedItems({ items: [{ id: 'p1' }], total: 1 }), [{ id: 'p1' }]);

  for (const malformedObj of [htmlDoc, [], null, undefined, 'bad']) {
    assert.deepEqual(asPlainObject(malformedObj), {});
  }
  assert.deepEqual(asPlainObject({ 'store.name': 'DIGI-VERSE' }), { 'store.name': 'DIGI-VERSE' });

  // 4. AuthContext profile validation rejects HTML/malformed values
  for (const invalidProfile of [htmlDoc, [], null, undefined, {}, { email: 'a@b.com' }]) {
    assert.equal(isValidCustomerProfile(invalidProfile), false);
  }
  assert.equal(
    isValidCustomerProfile({ id: 'cust-1', email: 'buyer@example.com', full_name: 'Buyer' }),
    true
  );

  for (const invalidAdmin of [htmlDoc, [], null, undefined, {}, { id: '1', role: 'CUSTOMER' }]) {
    assert.equal(isValidAdminProfile(invalidAdmin), false);
  }
  assert.equal(
    isValidAdminProfile({ id: 'adm-1', role: 'ADMIN', username: 'admin' }),
    true
  );

  // 5. Wiring checks across App, api.js, HomePage, AuthContext, and StorefrontLayout
  const appSrc = readSrc('App.jsx');
  assert.ok(appSrc.includes('AppErrorBoundary'), 'App.jsx must wrap routes with AppErrorBoundary');
  const apiSrc = readSrc('services/api.js');
  assert.ok(apiSrc.includes('validateApiResponse'), 'api.js must validate responses in interceptor');
  const homeSrc = readSrc('pages/customer/HomePage.jsx');
  assert.ok(homeSrc.includes('asArray(banners)'), 'HomePage must guard banners with asArray');
  assert.ok(homeSrc.includes('asArray(videos)'), 'HomePage must guard videos with asArray');
  assert.ok(homeSrc.includes('asPlainObject(storeSettings)'), 'HomePage must guard storeSettings');
  const authSrc = readSrc('context/AuthContext.jsx');
  assert.ok(authSrc.includes('isValidCustomerProfile'), 'AuthContext must validate customer profile');
  assert.ok(authSrc.includes('isValidAdminProfile'), 'AuthContext must validate admin profile');
  const layoutSrc = readSrc('components/common/StorefrontLayout.jsx');
  assert.ok(layoutSrc.includes('isPlainObject'), 'StorefrontLayout must validate public settings');
});

test('19. Stage 3.12 Admin Dashboard pending_review query & Payout production simulation guard', () => {
  const dashboardSrc = readSrc('pages/admin/AdminDashboardPage.jsx');
  assert.ok(
    dashboardSrc.includes("approval_status: 'pending_review'"),
    'AdminDashboardPage must query pending_review to match backend ProductApprovalStatus enum'
  );
  assert.ok(
    !dashboardSrc.includes("approval_status: 'submitted'"),
    'AdminDashboardPage must not send invalid approval_status submitted'
  );

  const payoutSrc = readSrc('pages/admin/AdminPayoutPage.jsx');
  assert.ok(
    payoutSrc.includes('isPayoutSimulationSupported') && payoutSrc.includes('checkBackendHealth'),
    'AdminPayoutPage must gate mock payout simulation by backend environment'
  );
  assert.ok(
    payoutSrc.includes('simulationSupported') &&
      payoutSrc.includes('Payout execution and simulation are unavailable in this environment'),
    'AdminPayoutPage must hide simulation buttons and explain unavailability in non-dev environments'
  );
  assert.ok(
    payoutSrc.includes('Simulate success') &&
      payoutSrc.includes('Simulate failure') &&
      payoutSrc.includes('Retry failed payout'),
    'AdminPayoutPage must preserve simulation and retry actions for isolated development/test environments'
  );
});
