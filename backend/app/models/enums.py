"""Enumerations shared by ORM models. Stored as VARCHAR + CHECK constraints."""
import enum


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class AuthSubjectType(str, enum.Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class OTPPurpose(str, enum.Enum):
    PHONE_VERIFY = "phone_verify"
    PHONE_CHANGE = "phone_change"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"


class OrderPaymentStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class DownloadStatus(str, enum.Enum):
    GRANTED = "granted"
    COMPLETED = "completed"
    FAILED = "failed"
    REVOKED = "revoked"


class ActivityType(str, enum.Enum):
    PRODUCT_VIEW = "product_view"
    CATEGORY_VIEW = "category_view"
    SEARCH = "search"
    WISHLIST_ADD = "wishlist_add"
    WISHLIST_REMOVE = "wishlist_remove"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    CHECKOUT_START = "checkout_start"
    PURCHASE = "purchase"
    DOWNLOAD = "download"
    PROFILE_UPDATE = "profile_update"
    CONSENT_UPDATE = "consent_update"


class LoginStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    LOCKED = "locked"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    SENDING = "sending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class MessageChannel(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class DeliveryStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRYING = "retrying"
    ACCEPTED = "accepted"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    BOUNCED = "bounced"
    FAILED = "failed"
    SUPPRESSED = "suppressed"
    SKIPPED = "skipped"
    UNRESOLVED = "unresolved"


class AdDisplayPosition(str, enum.Enum):
    HOME_HERO = "home_hero"
    HOME_SECTION = "home_section"
    CATEGORY_PAGE = "category_page"
    PRODUCT_PAGE = "product_page"
    SIDEBAR = "sidebar"


class SellerApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class ProductApprovalStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"
