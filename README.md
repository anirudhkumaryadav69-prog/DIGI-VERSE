# DIGI-VERSE

A full-stack digital products e-commerce platform built with a premium minimal aesthetic (Charcoal, Off-White, Muted Blue, and Neutral Grey).

---

## Technology Stack

### Frontend
- **React 18** + **Vite** (JavaScript)
- **Tailwind CSS**
- **React Router v6**
- **Axios**
- **Lucide React**

### Backend
- **Python 3.12+** + **FastAPI**
- **SQLAlchemy 2.0** + **PostgreSQL**
- **Alembic** (Database Migrations)
- **Pydantic v2** & **Pydantic Settings**
- **JWT Authentication** (`python-jose`, `passlib[bcrypt]`)

### Planned Integrations
- Razorpay UPI Payments
- Supabase Storage
- Resend Email
- WhatsApp Business Cloud API
- Google Drive Digital Product Delivery

---

## Project Architecture

```text
DIGI-VERSE/
├── frontend/                # React + Vite application
│   ├── public/
│   └── src/
│       ├── assets/          # images, icons, fonts
│       ├── components/      # common, products, cart, dashboard
│       ├── pages/           # customer, auth, customer-dashboard, admin
│       ├── layouts/
│       ├── services/        # Axios API client
│       ├── context/         # AuthContext & state providers
│       ├── hooks/
│       ├── routes/          # AppRoutes, ProtectedRoute, AdminRoute
│       └── styles/          # Tailwind & global CSS
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/             # Main router & endpoint routes
│   │   ├── core/            # config, database, security, permissions
│   │   ├── middleware/
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic & third-party services
│   │   └── utils/
│   ├── migrations/          # Alembic migration environment & versions
│   ├── scripts/             # Utility & dev runner scripts
│   └── tests/               # Pytest test suite
├── docs/                    # Architecture & API documentation
├── docker-compose.yml       # Local PostgreSQL container setup
└── .gitignore
```

---

## Getting Started

### 1. Database Setup (Optional via Docker)

Start the local PostgreSQL instance using Docker Compose:

```bash
docker compose up -d
```

---

### 2. Backend Setup & Execution

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python3.12 -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # macOS / Linux:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Update `.env` with your PostgreSQL connection string and secret keys.

5. Run database migrations (once PostgreSQL is running):
   ```bash
   alembic upgrade head
   ```

6. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   - **API Base URL**: `http://localhost:8000`
   - **Health Check**: `http://localhost:8000/api/health`
   - **Interactive Docs (Swagger)**: `http://localhost:8000/docs`

---

### 3. Frontend Setup & Execution

1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

4. Start the Vite development server:
   ```bash
   npm run dev
   ```
   - **Frontend URL**: `http://localhost:5173`

---

## API Reference & Catalog Management Guide

### 1. Administrator Provisioning & Dashboard (`/admin`)
- Provision the initial administrator (`Aayan`) once via CLI after setting `INITIAL_ADMIN_PASSWORD` in `backend/.env`:
  ```bash
  cd backend
  .\.venv\Scripts\python.exe scripts/provision_admin.py
  ```
- Sign in at `/admin/login`. On first login, change the initial password at `/admin/change-password` to unlock administrative operations.
- **Dashboard Endpoint**: `GET /api/admin/dashboard/overview` returns real-time PostgreSQL aggregates (`total_customers`, `total_products`, `total_categories`, `active_products`, `inactive_products`, `total_orders`, `total_sales_revenue`, `pending_orders`, `recent_registrations`, `recent_orders`, `recent_products`, and `recent_audit_logs`).

### 2. Category Management (`/admin/categories`)
- `GET /api/admin/categories` — Paginated list with `search` and `is_active` filter.
- `GET /api/admin/categories/{category_id}` — Single category details.
- `POST /api/admin/categories` — Create category (auto-generates kebab-case slug if omitted).
- `PATCH /api/admin/categories/{category_id}` — Update category name, slug, description, image, or active status.
- `DELETE /api/admin/categories/{category_id}` — Delete category (blocked with `409 Conflict` if products reference it).

### 3. Product, Image & Discount Management (`/admin/products`)
- `GET /api/admin/products` — Paginated admin product list with search, `category_id`, and `is_active` filter.
- `GET /api/admin/products/{product_id}` — Complete admin product details (includes confidential `private_download_url`, images, and sales history).
- `POST /api/admin/products` — Create digital product.
- `PATCH /api/admin/products/{product_id}` — Edit product details, category, price, metadata, or private download URL.
- `PATCH /api/admin/products/{product_id}/status` — Activate/deactivate product.
- `DELETE /api/admin/products/{product_id}` — Delete product (blocked with `409 Conflict` if referenced by historical orders or download records).
- **Image Uploads** (`UPLOAD_DIR=uploads/images`, `MAX_IMAGE_UPLOAD_BYTES=5242880`):
  - `POST /api/admin/products/{product_id}/images` — Multipart upload validated by extension (`.png`, `.jpg`, `.jpeg`, `.webp`), `Content-Type`, and binary magic-byte signatures; stored with server-generated UUID filenames.
  - `PATCH /api/admin/products/{product_id}/images/{image_id}` — Reorder or promote primary image.
  - `PUT /api/admin/products/{product_id}/images/{image_id}` — Replace image file.
  - `DELETE /api/admin/products/{product_id}/images/{image_id}` — Delete image.
- **Sales & Discounts**:
  - `POST /api/admin/products/{product_id}/sales` — Schedule or activate a product discount (`discounted_price < original_price`, at most one active sale per product).
  - `PATCH /api/admin/products/{product_id}/sales/{sale_id}` — Edit or toggle active status on a discount.

### 4. Public Customer Catalog (`/products`, `/categories`)
- `GET /api/products` — Public catalog supporting `page`, `page_size`, `search`, `category` (slug), `category_id`, `min_price`, `max_price`, and `sort_by` (`newest`, `price_asc`, `price_desc`, `popularity`). Exposes only active products in active categories and never serializes `private_download_url`.
- `GET /api/products/{slug}` — Public product detail with gallery images and backend-computed `effective_price` / `active_discount`.
- `GET /api/categories` & `GET /api/categories/{slug}` — Public active categories and active product counts.

### 5. Wishlist, Persistent Cart, Checkout, Payments, Orders & Digital Delivery
- **Wishlist (`/wishlist`)**: `GET /api/wishlist`, `POST /api/wishlist/{product_id}`, `DELETE /api/wishlist/{product_id}`, `DELETE /api/wishlist`.
- **Persistent Shopping Cart (`/cart`)**: `GET /api/cart`, `POST /api/cart/items`, `PATCH /api/cart/items/{item_id}`, `DELETE /api/cart/items/{item_id}`, `DELETE /api/cart`.
- **Checkout & Payments (`/checkout`)**:
  - `POST /api/checkout` — Server-side cart validation, price/discount recalculation, idempotency key deduplication, immutable `order_items` snapshots, and payment gateway initialization (`RazorpayPaymentProvider` when `RAZORPAY_KEY_ID` & `RAZORPAY_KEY_SECRET` are set).
  - `POST /api/payments/verify` — Cryptographic HMAC-SHA256 signature verification before capturing payment, fulfilling order, and clearing cart.
  - `POST /api/payments/webhook` — Raw-body HMAC-verified webhook handler with `payment_webhook_events` idempotency and out-of-order failure protection.
- **Customer & Admin Orders (`/orders`, `/admin/orders`)**:
  - Customer: `GET /api/orders`, `GET /api/orders/{order_id}`, `GET /api/orders/{order_id}/invoice`.
  - Admin: `GET /api/admin/orders`, `GET /api/admin/orders/statistics`, `GET /api/admin/orders/{order_id}`, `PATCH /api/admin/orders/{order_id}/status`.
- **Digital Product Delivery (`/downloads`)**:
  - `GET /api/downloads`, `POST /api/downloads/{order_item_id}`, `GET /api/downloads/{download_id}/status`, and `GET /api/downloads/{download_id}/file?token=...` (short-lived signed JWT download delivery enforcing ownership, verified payment, and per-item download limits).

### 6. Advanced Admin Operations, SQL Analytics, Marketing Automation & Store Settings
- **SQL Analytics (`/admin`)**:
  - `GET /api/admin/dashboard/overview` & `GET /api/admin/dashboard/analytics` — Live PostgreSQL aggregations for `total_customers`, `new_customers`, `total_captured_revenue`, `average_order_value`, `total_downloads`, `active_promotional_campaigns`, `daily_sales`, `weekly_sales`, `monthly_sales`, `best_selling_products`, `top_categories`, `most_downloaded_products`, and `recent_customer_activity`.
- **Customer Management (`/admin/customers`)**:
  - `GET /api/admin/customers` — Paginated directory with search, status filters, order counts, and total spend.
  - `PATCH /api/admin/customers/{customer_id}/status` — Update account status (`active`, `suspended`, `deactivated`) with immediate active session revocation on suspension/deactivation.
- **Promotional Banners & Advertisement Videos (`/admin/banners`, `/admin/videos`)**:
  - Admin CRUD: `GET/POST/PATCH/DELETE /api/admin/banners` and `GET/POST/PATCH/DELETE /api/admin/videos`.
  - Public Endpoints: `GET /api/banners` (active & scheduled date window filtering) and `GET /api/videos?position=...` (`home_hero`, `home_section`, `category_page`, `product_page`, `sidebar`).
- **Marketing Automation & Consent Enforcement (`/admin/marketing`)**:
  - Reusable Message Templates: `GET/POST/PATCH/DELETE /api/admin/templates`.
  - Email Campaigns: `GET/POST /api/admin/campaigns/email`, `POST /api/admin/campaigns/email/{campaign_id}/launch`.
  - WhatsApp Campaigns: `GET/POST /api/admin/campaigns/whatsapp`, `POST /api/admin/campaigns/whatsapp/{campaign_id}/launch`.
  - Strictly targets only active customers who have opted in (`email_marketing_consent = true` / `whatsapp_marketing_consent = true`), backed by the PostgreSQL database trigger `trg_campaign_recipient_consent`.
- **Store Settings & Security Audit Logs (`/admin/settings`)**:
  - `GET/PUT /api/admin/settings`, `PATCH /api/admin/settings/batch`, and public `GET /api/settings/public` (exposing only non-sensitive `store.*` keys while rejecting secret-like keys and protecting `system.initial_admin_provisioned`).
  - `GET /api/admin/audit-logs` — Paginated administrative audit trail filterable by `action` and `entity_type`.

### 7. Storefront UX, Conversion Optimization & Customer Experience (Phase 6)
- **Design System**: Consistent minimal design system (`StorefrontDesignSystem.jsx`, `ProductCard.jsx`, `CategoryCard.jsx`, `StorefrontHeader.jsx`, `StorefrontFooter.jsx`, `StorefrontLayout.jsx`).
- **Catalog Filtering & Retry Payment**:
  - `GET /api/products` supports `on_sale=true` for currently active promotional discounts, effective-price `min_price` / `max_price` filtering, debounced search, stale-request protection, and sanitized public product `metadata`.
  - `POST /api/orders/{order_id}/retry-payment` re-initializes payment for an existing pending or failed order without creating duplicate orders.
- **Automated Testing**:
  - Backend (65 tests across `test_database.py`, `test_health.py`, `test_auth.py`, `test_catalog.py`, `test_commerce.py`, `test_operations.py`, and `test_storefront_journeys.py`):
    ```bash
    cd backend
    .\.venv\Scripts\python.exe -m pytest tests -v
    ```
  - Frontend (7 automated storefront & bundle security tests):
    ```bash
    npm --prefix frontend test
    ```




