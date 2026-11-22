"""SQLAlchemy ORM models. Importing this package registers every table on Base.metadata."""
from app.core.database import Base
from app.models.admin import Admin, AuditLog
from app.models.auth import AuthSession, PasswordResetToken, PhoneOTPChallenge, RateLimitBucket
from app.models.campaign import (
    CampaignRecipient,
    EmailCampaign,
    MarketingWebhookEvent,
    MessageTemplate,
    WhatsAppCampaign,
    WorkerHeartbeat,
)
from app.models.catalog import Category, Product, ProductImage, Sale
from app.models.content import AdvertisementVideo, Banner
from app.models.customer import Customer, CustomerActivity, LoginHistory
from app.models.order import DownloadRecord, Order, OrderItem, Payment, PaymentWebhookEvent
from app.models.seller import SellerProfile
from app.models.settings import StoreSetting
from app.models.shopping import Cart, CartItem, Wishlist
from app.models.financial import (
    CommissionConfiguration,
    CommissionHistory,
    FinancialLedgerEntry,
    FinancialTransaction,
    RefundRecord,
    SellerCommissionOverride,
)

__all__ = [
    "Base",
    "Admin",
    "AuditLog",
    "AuthSession",
    "PhoneOTPChallenge",
    "PasswordResetToken",
    "RateLimitBucket",
    "Customer",
    "CustomerActivity",
    "LoginHistory",
    "SellerProfile",
    "Category",
    "Product",
    "ProductImage",
    "Sale",
    "Banner",
    "AdvertisementVideo",
    "Wishlist",
    "Cart",
    "CartItem",
    "Order",
    "OrderItem",
    "Payment",
    "PaymentWebhookEvent",
    "DownloadRecord",
    "EmailCampaign",
    "WhatsAppCampaign",
    "MessageTemplate",
    "CampaignRecipient",
    "MarketingWebhookEvent",
    "WorkerHeartbeat",
    "StoreSetting",
    "CommissionConfiguration",
    "SellerCommissionOverride",
    "CommissionHistory",
    "RefundRecord",
    "FinancialTransaction",
    "FinancialLedgerEntry",
]
