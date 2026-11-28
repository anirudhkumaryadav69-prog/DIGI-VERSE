"""Stage A.1 Reliability & Security Hardening offline unit & regression tests.

These tests verify all Stage A.1 fixes deterministically using mocked DB/HTTP boundaries
without requiring a live PostgreSQL server or external cloud APIs.
"""
from __future__ import annotations

import importlib.util
import io
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import HTTPException, UploadFile

from app.api.routes import auth as auth_routes
from app.api.routes import seller as seller_routes
from app.core.config import settings
from app.core.rate_limit import rate_limit_customer, rate_limiter
from app.models.enums import (
    AccountStatus,
    CampaignStatus,
    DeliveryStatus,
    MessageChannel,
    ProductApprovalStatus,
    SellerApplicationStatus,
)
from app.schemas.auth import CustomerPhoneUpdateRequest
from app.services import campaign_worker, commerce_service, customer_auth_service, operations_service
from app.services.sms_service import SMSDeliveryResult
from app.services.whatsapp_service import (
    DevelopmentWhatsAppProvider,
    MetaWhatsAppCloudProvider,
    WhatsAppDeliveryError,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
PNG_MAGIC_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ---------------------------------------------------------------------------
# TASK 1 — WHATSAPP PHONE-CHANGE OTP FAILURE & ROLLBACK
# ---------------------------------------------------------------------------


class _FakeSavepointDB:
    """Lightweight session stub tracking savepoint rollbacks and commits."""

    def __init__(self, customer):
        self.customer = customer
        self.flushed = 0
        self.committed = 0
        self.rolled_back = 0
        self.savepoints_entered = 0
        self.savepoints_rolled_back = 0

    def scalar(self, _stmt):
        return None

    def flush(self):
        self.flushed += 1

    def commit(self):
        self.committed += 1

    def refresh(self, _obj):
        return None

    def rollback(self):
        self.rolled_back += 1

    @contextmanager
    def begin_nested(self):
        self.savepoints_entered += 1
        snapshot_pending = self.customer.pending_phone_number
        try:
            yield
        except Exception:
            self.savepoints_rolled_back += 1
            self.customer.pending_phone_number = snapshot_pending
            raise


def test_phone_change_delivery_failure_rolls_back_and_returns_502(monkeypatch):
    customer = SimpleNamespace(
        id=uuid.uuid4(),
        phone_number="+919800000001",
        pending_phone_number=None,
        is_phone_verified=True,
    )
    fake_db = _FakeSavepointDB(customer)

    class _ActiveProvider:
        pass

    monkeypatch.setattr(customer_auth_service, "get_sms_provider", lambda: _ActiveProvider())
    monkeypatch.setattr(
        customer_auth_service,
        "issue_phone_otp_challenge",
        lambda db, cust, phone, purpose: (
            SimpleNamespace(id=uuid.uuid4()),
            SMSDeliveryResult(
                status="failed",
                provider="whatsapp",
                safe_detail="WhatsApp OTP request was rejected.",
            ),
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_routes.request_phone_number_change(
            payload=CustomerPhoneUpdateRequest(phone_number="+919876543210"),
            customer=customer,
            db=fake_db,
        )

    assert exc_info.value.status_code == 502
    assert "rejected" in exc_info.value.detail.lower()
    assert customer.pending_phone_number is None
    assert fake_db.committed == 0
    assert fake_db.savepoints_rolled_back == 1
    assert fake_db.rolled_back == 1


def test_phone_change_delivery_disabled_rolls_back_and_returns_503(monkeypatch):
    customer = SimpleNamespace(
        id=uuid.uuid4(),
        phone_number="+919800000001",
        pending_phone_number="+919811111111",
        is_phone_verified=False,
    )
    fake_db = _FakeSavepointDB(customer)

    class _ActiveProvider:
        pass

    monkeypatch.setattr(customer_auth_service, "get_sms_provider", lambda: _ActiveProvider())
    monkeypatch.setattr(
        customer_auth_service,
        "issue_phone_otp_challenge",
        lambda db, cust, phone, purpose: (
            None,
            SMSDeliveryResult(
                status="disabled",
                provider="whatsapp",
                safe_detail="WhatsApp OTP delivery is disabled.",
            ),
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_routes.request_phone_number_change(
            payload=CustomerPhoneUpdateRequest(phone_number="+919876543210"),
            customer=customer,
            db=fake_db,
        )

    assert exc_info.value.status_code == 503
    assert customer.pending_phone_number == "+919811111111"
    assert fake_db.committed == 0
    assert fake_db.savepoints_rolled_back == 1
    assert fake_db.rolled_back == 1


def test_phone_change_delivery_accepted_commits_pending_phone(monkeypatch):
    now = datetime.now(timezone.utc)
    customer = SimpleNamespace(
        id=uuid.uuid4(),
        full_name="Test Buyer",
        email="buyer@example.test",
        phone_number="+919800000001",
        pending_phone_number=None,
        is_email_verified=False,
        is_phone_verified=True,
        account_status=AccountStatus.ACTIVE,
        email_marketing_consent=False,
        whatsapp_marketing_consent=False,
        role="CUSTOMER",
        is_seller=False,
        seller_status=None,
        seller_store_slug=None,
        last_login_at=now,
        created_at=now,
        updated_at=now,
    )
    fake_db = _FakeSavepointDB(customer)

    class _ActiveProvider:
        pass

    monkeypatch.setattr(customer_auth_service, "get_sms_provider", lambda: _ActiveProvider())
    monkeypatch.setattr(
        customer_auth_service,
        "issue_phone_otp_challenge",
        lambda db, cust, phone, purpose: (
            SimpleNamespace(id=uuid.uuid4()),
            SMSDeliveryResult(
                status="accepted",
                provider="whatsapp",
                provider_message_id="wamid.phonechange.1",
            ),
        ),
    )

    res = auth_routes.request_phone_number_change(
        payload=CustomerPhoneUpdateRequest(phone_number="+919876543210"),
        customer=customer,
        db=fake_db,
    )

    assert res.pending_phone_number == "+919876543210"
    assert fake_db.committed == 1
    assert fake_db.rolled_back == 0


# ---------------------------------------------------------------------------
# TASK 2 — WHATSAPP MARKETING TEMPLATE PAYLOAD
# ---------------------------------------------------------------------------


def test_whatsapp_marketing_template_payload_parameters_and_language(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "live_meta_token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "9988776655")
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE_LANGUAGE", "hi_IN")
    monkeypatch.setattr(settings, "WHATSAPP_GRAPH_API_VERSION", "v20.0")

    captured_requests: list[dict] = []
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(
            {
                "url": str(request.url),
                "auth": request.headers.get("Authorization"),
                "body": json.loads(request.content.decode("utf-8")),
            }
        )
        return httpx.Response(200, json={"messages": [{"id": "wamid.tpl.1"}]})

    monkeypatch.setattr(
        "app.services.whatsapp_service.httpx.Client",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )

    provider = MetaWhatsAppCloudProvider()

    # 1. Default configured language + content mapped as body parameter
    msg_id1 = provider.send_template_message(
        "+919876543210",
        "flash_drop_v1",
        "40% off all Figma kits today!",
    )
    assert msg_id1 == "wamid.tpl.1"
    body1 = captured_requests[0]["body"]
    assert captured_requests[0]["url"].endswith("/v20.0/9988776655/messages")
    assert body1 == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "919876543210",
        "type": "template",
        "template": {
            "name": "flash_drop_v1",
            "language": {"code": "hi_IN"},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": "40% off all Figma kits today!"}],
                }
            ],
        },
    }

    # 2. Explicit template_language + multi-parameter metadata override
    provider.send_template_message(
        "+919876543210",
        "creator_promo_v2",
        "Fallback body",
        metadata={"template_parameters": ["Aarav", "DIGI25"]},
        template_language="en_GB",
    )
    body2 = captured_requests[1]["body"]
    assert body2["template"] == {
        "name": "creator_promo_v2",
        "language": {"code": "en_GB"},
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "Aarav"},
                    {"type": "text", "text": "DIGI25"},
                ],
            }
        ],
    }

    # 3. Metadata language fallback + empty content omits components cleanly
    provider.send_template_message(
        "+919876543210",
        "static_notice_v1",
        "   ",
        metadata={"template_language": "fr_FR"},
    )
    body3 = captured_requests[2]["body"]
    assert body3["template"] == {
        "name": "static_notice_v1",
        "language": {"code": "fr_FR"},
    }


# ---------------------------------------------------------------------------
# TASK 3 — WISHLIST PRODUCT VISIBILITY & EAGER LOADING
# ---------------------------------------------------------------------------


def test_wishlist_uses_public_visibility_and_eager_loads_seller(monkeypatch):
    now = datetime.now(timezone.utc)
    active_category = SimpleNamespace(id=uuid.uuid4(), name="UI Kits", is_active=True)

    def _make_product(name: str, approval: ProductApprovalStatus, seller_status: SellerApplicationStatus, seller_acct: AccountStatus):
        return SimpleNamespace(
            id=uuid.uuid4(),
            name=name,
            slug=name.lower().replace(" ", "-"),
            category=active_category,
            seller_id=uuid.uuid4(),
            seller=SimpleNamespace(
                application_status=seller_status,
                customer=SimpleNamespace(account_status=seller_acct),
            ),
            images=[],
            sales=[],
            image_url=None,
            original_price=Decimal("499.00"),
            is_active=True,
            approval_status=approval,
        )

    p_approved = _make_product(
        "Approved Pack", ProductApprovalStatus.PUBLISHED, SellerApplicationStatus.APPROVED, AccountStatus.ACTIVE
    )
    p_pending = _make_product(
        "Pending Pack", ProductApprovalStatus.PENDING_REVIEW, SellerApplicationStatus.APPROVED, AccountStatus.ACTIVE
    )
    p_suspended = _make_product(
        "Suspended Seller Pack", ProductApprovalStatus.PUBLISHED, SellerApplicationStatus.SUSPENDED, AccountStatus.ACTIVE
    )

    wishlist_rows = [
        SimpleNamespace(id=uuid.uuid4(), product=p_approved, created_at=now),
        SimpleNamespace(id=uuid.uuid4(), product=p_pending, created_at=now),
        SimpleNamespace(id=uuid.uuid4(), product=p_suspended, created_at=now),
    ]

    captured_stmt = {}

    class _FakeWishlistDB:
        def scalars(self, stmt):
            captured_stmt["stmt"] = stmt
            return SimpleNamespace(all=lambda: wishlist_rows)

    res = commerce_service.get_customer_wishlist(
        _FakeWishlistDB(),
        SimpleNamespace(id=uuid.uuid4()),
    )

    by_name = {item.product_name: item.is_available for item in res.items}
    assert by_name["Approved Pack"] is True
    assert by_name["Pending Pack"] is False
    assert by_name["Suspended Seller Pack"] is False

    # Verify eager-loading options cover Product.seller -> SellerProfile.customer (prevents N+1)
    option_str = " | ".join(repr(opt.path) for opt in captured_stmt["stmt"]._with_options)
    assert "; Wishlist>" in option_str
    assert "; product>" in option_str
    assert "; seller>" in option_str
    assert "; SellerProfile>" in option_str
    assert "; customer>" in option_str


# ---------------------------------------------------------------------------
# TASK 4 — CAMPAIGN STATUS COUNTING
# ---------------------------------------------------------------------------


def test_active_promotional_campaigns_counts_only_active_statuses():
    email_statuses = [
        CampaignStatus.DRAFT,
        CampaignStatus.SCHEDULED,
        CampaignStatus.QUEUED,
        CampaignStatus.SENDING,
        CampaignStatus.PROCESSING,
        CampaignStatus.COMPLETED,
        CampaignStatus.PARTIALLY_COMPLETED,
        CampaignStatus.CANCELLED,
        CampaignStatus.FAILED,
    ]
    wa_statuses = [
        CampaignStatus.SCHEDULED,
        CampaignStatus.QUEUED,
        CampaignStatus.SENDING,
        CampaignStatus.PROCESSING,
        CampaignStatus.COMPLETED,
        CampaignStatus.FAILED,
    ]

    # Build a minimal mock DB that evaluates the SQLAlchemy WHERE clause against each status list
    def _eval_campaign_count(model_cls, statuses, stmt):
        where_clauses = list(stmt._where_criteria)
        in_values = None
        for clause in where_clauses:
            right = getattr(clause, "right", None)
            if right is not None and hasattr(right, "value"):
                in_values = set(right.value)
        assert in_values is not None
        return sum(1 for st in statuses if st in in_values or st.value in in_values)

    class _FakeOpsDB:
        def __init__(self):
            self.scalar_calls = 0

        def execute(self, _stmt):
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return SimpleNamespace(one=lambda: SimpleNamespace(total_customers=0, new_customers=0))
            if self.scalar_calls == 2:
                return SimpleNamespace(one=lambda: SimpleNamespace(total_products=0, active_products=0))
            if self.scalar_calls == 3:
                return SimpleNamespace(
                    one=lambda: SimpleNamespace(
                        total_orders=0,
                        pending_orders=0,
                        paid_orders=0,
                        revenue_raw=Decimal("0.00"),
                    )
                )
            return SimpleNamespace(
                one=lambda: SimpleNamespace(
                    captured_raw=Decimal("0.00"),
                    pending_payments=0,
                    failed_payments=0,
                    refunded_payments=0,
                )
            )

        def scalar(self, stmt):
            sql_text = str(stmt)
            if "FROM email_campaigns" in sql_text:
                return _eval_campaign_count("email", email_statuses, stmt)
            if "FROM whatsapp_campaigns" in sql_text:
                return _eval_campaign_count("wa", wa_statuses, stmt)
            return 0

        def scalars(self, _stmt):
            return SimpleNamespace(all=lambda: [])

    overview = operations_service.get_advanced_dashboard_overview(
        _FakeOpsDB(),
        SimpleNamespace(username="Aayan"),
    )
    # 4 active email campaigns (SCHEDULED, QUEUED, SENDING, PROCESSING) +
    # 4 active WhatsApp campaigns (SCHEDULED, QUEUED, SENDING, PROCESSING) = 8
    assert overview["metrics"]["active_promotional_campaigns"] == 8


# ---------------------------------------------------------------------------
# TASK 5 — ALEMBIC MIGRATION CHAIN & DOWNGRADE CORRECTION
# ---------------------------------------------------------------------------


def test_alembic_single_head_and_h7c8d9e0f205_downgrade_restores_constraint(monkeypatch):
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script_dir = ScriptDirectory.from_config(cfg)

    heads = script_dir.get_heads()
    assert heads == ["h7c8d9e0f205"]

    revisions = list(script_dir.walk_revisions(base="base", head="heads"))
    assert len(revisions) == 13
    assert revisions[0].revision == "h7c8d9e0f205"
    assert revisions[-1].revision == "3b9aa73cb927"

    mig_path = BACKEND_DIR / "migrations" / "versions" / "20261122_h7c8d9e0f205_phase10_2_payout_reconciliation.py"
    spec = importlib.util.spec_from_file_location("mig_h7c8d9e0f205", mig_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    recorded_constraints: list[tuple[str, str, str, str]] = []
    fake_op = MagicMock()
    fake_op.create_check_constraint.side_effect = lambda name, table, cond: recorded_constraints.append(
        ("create", name, table, cond)
    )
    monkeypatch.setattr(mod, "op", fake_op)

    mod.upgrade()
    upgrade_tx_cond = next(
        cond for action, name, _tbl, cond in recorded_constraints
        if action == "create" and name == "financial_transaction_type_valid"
    )
    assert "'payout_settlement'" in upgrade_tx_cond

    recorded_constraints.clear()
    mod.downgrade()
    downgrade_tx_cond = next(
        cond for action, name, _tbl, cond in recorded_constraints
        if action == "create" and name == "financial_transaction_type_valid"
    )
    assert "'payout_settlement'" not in downgrade_tx_cond
    assert "'payment_capture'" in downgrade_tx_cond
    assert "'refund_reversal'" in downgrade_tx_cond
    assert "'payment_reversal'" in downgrade_tx_cond
    assert "'financial_correction'" in downgrade_tx_cond


# ---------------------------------------------------------------------------
# TASK 7 — SELLER BRANDING UPLOAD PER-CUSTOMER RATE LIMITING
# ---------------------------------------------------------------------------


def test_seller_branding_upload_per_customer_rate_limit_and_size_preserved(monkeypatch, tmp_path):
    rate_limiter.reset()
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "RATE_LIMIT_USE_DB", False)
    monkeypatch.setattr(settings, "IMAGE_STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    # Inspect route dependency wiring on POST /api/seller/branding-image
    branding_route = next(
        r for r in seller_routes.router.routes if getattr(r, "path", "").endswith("/branding-image")
    )
    assert len(branding_route.dependencies) == 1

    dep_fn = branding_route.dependencies[0].dependency
    cust_a = SimpleNamespace(id=uuid.uuid4())
    cust_b = SimpleNamespace(id=uuid.uuid4())

    # 10 uploads succeed for Customer A; 11th triggers HTTP 429
    for _ in range(10):
        dep_fn(customer=cust_a, db=None)

    with pytest.raises(HTTPException) as exc_429:
        dep_fn(customer=cust_a, db=None)
    assert exc_429.value.status_code == 429
    assert "Retry-After" in exc_429.value.headers

    # Independent Customer B is NOT blocked by Customer A's quota (strictly per-customer key)
    dep_fn(customer=cust_b, db=None)

    # Verify image size limit & upload still works cleanly
    ok_upload = UploadFile(
        filename="logo.png",
        file=io.BytesIO(PNG_MAGIC_BYTES),
        headers={"content-type": "image/png"},
    )
    res = seller_routes.seller_upload_branding_image(file=ok_upload, customer=cust_b)
    assert res["image_url"].startswith("/api/uploads/images/")

    oversized = UploadFile(
        filename="huge.png",
        file=io.BytesIO(PNG_MAGIC_BYTES + (b"\x00" * (settings.MAX_IMAGE_UPLOAD_BYTES + 10))),
        headers={"content-type": "image/png"},
    )
    with pytest.raises(HTTPException) as exc_413:
        seller_routes.seller_upload_branding_image(file=oversized, customer=cust_b)
    assert exc_413.value.status_code == 413

    rate_limiter.reset()


# ---------------------------------------------------------------------------
# STAGE A.3 — WHATSAPP CAMPAIGN WORKER TEMPLATE PARAMETERS & VALIDATION
# ---------------------------------------------------------------------------


def _build_mock_meta_client(monkeypatch, captured_requests: list[dict], *, msg_prefix: str = "wamid.a3"):
    real_client = httpx.Client
    counter = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        counter["n"] += 1
        captured_requests.append(
            {
                "url": str(request.url),
                "body": json.loads(request.content.decode("utf-8")),
            }
        )
        return httpx.Response(200, json={"messages": [{"id": f"{msg_prefix}.{counter['n']}"}]})

    monkeypatch.setattr(
        "app.services.whatsapp_service.httpx.Client",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )


class _FakeWorkerClaimDB:
    """In-memory Session stub for testing campaign_worker.claim_recipient_batch()."""

    def __init__(self, recipients: list[SimpleNamespace], campaigns_by_id: dict[uuid.UUID, SimpleNamespace]):
        self._recipients = recipients
        self._campaigns = campaigns_by_id
        self.flushed = 0

    def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: self._recipients)

    def get(self, _model, entity_id):
        return self._campaigns.get(entity_id)

    def flush(self):
        self.flushed += 1


def _fake_recipient_row(campaign_id: uuid.UUID, customer_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        channel=MessageChannel.WHATSAPP,
        email_campaign_id=None,
        whatsapp_campaign_id=campaign_id,
        customer_id=customer_id,
        delivery_status=DeliveryStatus.QUEUED,
        idempotency_key=None,
        attempt_count=0,
        max_attempts=5,
        locked_by=None,
        locked_at=None,
        next_retry_at=None,
        failure_reason=None,
    )


def test_worker_forwards_string_and_dict_template_parameters_without_leakage(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "live_meta_token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "9988776655")
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE_LANGUAGE", "en_US")
    monkeypatch.setattr(settings, "WHATSAPP_GRAPH_API_VERSION", "v20.0")

    captured_requests: list[dict] = []
    _build_mock_meta_client(monkeypatch, captured_requests)
    provider = MetaWhatsAppCloudProvider()
    monkeypatch.setattr(campaign_worker, "get_whatsapp_provider", lambda: provider)

    camp_strings_id = uuid.uuid4()
    camp_dicts_id = uuid.uuid4()
    camp_fallback_id = uuid.uuid4()

    camp_strings = SimpleNamespace(
        id=camp_strings_id,
        name="Multi String Camp",
        content="Unused fallback body",
        approved_template_name="promo_multi_v1",
        status=CampaignStatus.QUEUED,
        audience_criteria={
            "template_language": "hi_IN",
            "template_parameters": ["Aarav", "DIGI40", "24h"],
        },
    )
    camp_dicts = SimpleNamespace(
        id=camp_dicts_id,
        name="Dict Param Camp",
        content="Unused fallback body 2",
        approved_template_name="invoice_notice_v2",
        status=CampaignStatus.QUEUED,
        audience_criteria={
            "language_code": "pt_BR",
            "template_parameters": [
                {"type": "text", "text": "Maya"},
                {"type": "currency", "currency": {"fallback_value": "$19.00", "code": "USD", "amount_1000": 19000}},
                {"type": "date_time", "date_time": {"fallback_value": "December 1, 2026"}},
            ],
        },
    )
    camp_fallback = SimpleNamespace(
        id=camp_fallback_id,
        name="Default Body Fallback Camp",
        content="Standard fallback promotional text",
        approved_template_name="plain_promo_v1",
        status=CampaignStatus.QUEUED,
        audience_criteria={"verified_phone_only": True},
    )

    cust_1 = SimpleNamespace(id=uuid.uuid4(), phone_number="+919876543210")
    cust_2 = SimpleNamespace(id=uuid.uuid4(), phone_number="+5511999998888")
    cust_3 = SimpleNamespace(id=uuid.uuid4(), phone_number="+14155550123")

    fake_db = _FakeWorkerClaimDB(
        recipients=[
            _fake_recipient_row(camp_strings_id, cust_1.id),
            _fake_recipient_row(camp_dicts_id, cust_2.id),
            _fake_recipient_row(camp_fallback_id, cust_3.id),
        ],
        campaigns_by_id={
            camp_strings_id: camp_strings,
            camp_dicts_id: camp_dicts,
            camp_fallback_id: camp_fallback,
        },
    )

    jobs = campaign_worker.claim_recipient_batch(fake_db, worker_id="worker-a3-1", batch_size=10)
    assert len(jobs) == 3

    # Mutate campaign criteria lists after claim to prove job snapshots are isolated.
    camp_strings.audience_criteria["template_parameters"].append("LEAKED")
    camp_dicts.audience_criteria["template_parameters"][0]["text"] = "MUTATED"

    res_1 = campaign_worker._execute_provider_send(jobs[0], cust_1)
    res_2 = campaign_worker._execute_provider_send(jobs[1], cust_2)
    res_3 = campaign_worker._execute_provider_send(jobs[2], cust_3)

    assert res_1["outcome"] == "accepted"
    assert res_2["outcome"] == "accepted"
    assert res_3["outcome"] == "accepted"

    # Job 1: multi-string parameters + custom template_language
    assert captured_requests[0]["body"]["to"] == "919876543210"
    assert captured_requests[0]["body"]["template"] == {
        "name": "promo_multi_v1",
        "language": {"code": "hi_IN"},
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "Aarav"},
                    {"type": "text", "text": "DIGI40"},
                    {"type": "text", "text": "24h"},
                ],
            }
        ],
    }

    # Job 2: dictionary parameters + language_code fallback + zero leakage from Job 1 or post-claim mutation
    assert captured_requests[1]["body"]["to"] == "5511999998888"
    assert captured_requests[1]["body"]["template"] == {
        "name": "invoice_notice_v2",
        "language": {"code": "pt_BR"},
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "Maya"},
                    {"type": "currency", "currency": {"fallback_value": "$19.00", "code": "USD", "amount_1000": 19000}},
                    {"type": "date_time", "date_time": {"fallback_value": "December 1, 2026"}},
                ],
            }
        ],
    }

    # Job 3: no template_parameters -> retains content fallback + settings default language
    assert captured_requests[2]["body"]["to"] == "14155550123"
    assert captured_requests[2]["body"]["template"] == {
        "name": "plain_promo_v1",
        "language": {"code": "en_US"},
        "components": [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": "Standard fallback promotional text"}],
            }
        ],
    }


def test_whatsapp_template_parameters_rejects_malformed_values_safely(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "live_meta_token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "9988776655")
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE_LANGUAGE", "en_US")
    monkeypatch.setattr(settings, "WHATSAPP_GRAPH_API_VERSION", "v20.0")

    captured_requests: list[dict] = []
    _build_mock_meta_client(monkeypatch, captured_requests)
    provider = MetaWhatsAppCloudProvider()
    monkeypatch.setattr(campaign_worker, "get_whatsapp_provider", lambda: provider)

    malformed_cases = [
        "not-a-list",
        12345,
        {"type": "text", "text": "bare-dict"},
        [None],
        [True],
        ["   "],
        [{}],
        [{"type": "text"}],
        [{"type": "text", "text": "   "}],
        [{"type": "unsupported_kind", "value": "x"}],
    ]

    for bad_params in malformed_cases:
        with pytest.raises(WhatsAppDeliveryError) as exc_info:
            provider.send_template_message(
                "+919876543210",
                "flash_drop_v1",
                "Fallback content",
                metadata={"template_parameters": bad_params},
            )
        assert exc_info.value.code == "invalid_template_parameters"
        assert exc_info.value.retryable is False

    # Worker execution must convert invalid campaign template_parameters into a clean non-retryable error outcome
    bad_camp_id = uuid.uuid4()
    bad_camp = SimpleNamespace(
        id=bad_camp_id,
        name="Malformed Camp",
        content="Fallback",
        approved_template_name="bad_tpl_v1",
        status=CampaignStatus.QUEUED,
        audience_criteria={"template_parameters": [{"type": "text"}]},
    )
    cust = SimpleNamespace(id=uuid.uuid4(), phone_number="+919876543210")
    fake_db = _FakeWorkerClaimDB(
        recipients=[_fake_recipient_row(bad_camp_id, cust.id)],
        campaigns_by_id={bad_camp_id: bad_camp},
    )
    jobs = campaign_worker.claim_recipient_batch(fake_db, worker_id="worker-a3-bad", batch_size=5)
    result = campaign_worker._execute_provider_send(jobs[0], cust)
    assert result["outcome"] == "error"
    assert result["error_code"] == "invalid_template_parameters"
    assert result["retryable"] is False
    assert captured_requests == []


def test_whatsapp_provider_positional_compatibility_and_dev_provider(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE_LANGUAGE", "en_US")
    dev_provider = DevelopmentWhatsAppProvider()

    # Positional call with original 3..6 arguments must remain compatible
    msg_id = dev_provider.send_template_message(
        "+919876543210",
        "legacy_tpl_v1",
        "Positional body message",
        {"template_parameters": ["One", "Two"]},
        "idem-pos-1",
        "de_DE",
    )
    assert msg_id.startswith("wamid_dev_")
    assert dev_provider.sent_messages[-1]["template_language"] == "de_DE"
    assert dev_provider.sent_messages[-1]["template_parameters"] == [
        {"type": "text", "text": "One"},
        {"type": "text", "text": "Two"},
    ]

    with pytest.raises(WhatsAppDeliveryError) as exc_info:
        dev_provider.send_template_message(
            "+919876543210",
            "legacy_tpl_v1",
            "Fallback",
            {"template_parameters": "corrupt"},
        )
    assert exc_info.value.code == "invalid_template_parameters"
