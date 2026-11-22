from decimal import Decimal

import httpx

from app.core.config import settings
from app.services.sms_service import (
    DevelopmentSMSProvider,
    WhatsAppCloudSMSProvider,
    get_sms_provider,
)


class _FakeResponse:
    status_code = 200

    def json(self):
        return {"messages": [{"id": "wamid.test123"}]}


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.payload = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        self.payload = {"url": url, "headers": headers, "json": json}
        return _FakeResponse()


def test_development_provider_is_explicit_and_terminal_only(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "ENABLE_DEV_OTP", True)
    provider = DevelopmentSMSProvider()
    result = provider.send_otp("+919876543210", "123456", 5)
    captured = capsys.readouterr()

    assert result.status == "development_only"
    assert provider.get_last_otp("+919876543210") == "123456"
    assert "[LOCAL DEVELOPMENT OTP]" in captured.out
    assert "123456" in captured.out
    assert "+919876543210" not in captured.out


def test_whatsapp_provider_builds_authentication_template_and_accepts(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_OTP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "test_access_token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE_NAME", "verification_code")
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE_LANGUAGE", "en_US")
    monkeypatch.setattr(settings, "WHATSAPP_GRAPH_API_VERSION", "v27.0")

    captured = {}

    class _RecordingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr("app.services.sms_service.httpx.Client", _RecordingClient)
    provider = WhatsAppCloudSMSProvider()
    result = provider.send_otp("+919876543210", "123456", 5)

    assert result.status == "accepted"
    assert result.provider == "whatsapp"
    assert result.provider_message_id == "wamid.test123"
    assert captured["url"].endswith("/123456789/messages")
    assert captured["headers"]["Authorization"] == "Bearer test_access_token"
    template = captured["json"]["template"]
    assert template["name"] == "verification_code"
    assert template["language"]["code"] == "en_US"
    assert template["components"][0]["parameters"][0]["text"] == "123456"
    assert template["components"][1]["parameters"][0]["text"] == "123456"
    assert captured["json"]["to"] == "919876543210"


def test_whatsapp_provider_missing_config_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_OTP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    provider = WhatsAppCloudSMSProvider()
    result = provider.send_otp("+919876543210", "123456", 5)
    assert result.status == "failed"
    assert "not configured" in (result.safe_detail or "").lower()


def test_whatsapp_provider_handles_provider_failure(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_OTP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "test_access_token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE_NAME", "verification_code")
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE_LANGUAGE", "en_US")

    class _FailureClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def post(self, *args, **kwargs):
            response = httpx.Response(
                401,
                json={"error": {"message": "invalid token", "code": 190}},
                request=httpx.Request("POST", "https://graph.facebook.com/v27.0/test/messages"),
            )
            return response

    monkeypatch.setattr("app.services.sms_service.httpx.Client", _FailureClient)
    result = WhatsAppCloudSMSProvider().send_otp("+919876543210", "123456", 5)
    assert result.status == "failed"
    assert result.provider == "whatsapp"
    assert "authentication" in (result.safe_detail or "").lower()


def test_provider_selection_fails_closed_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "OTP_DELIVERY_PROVIDER", "development")
    monkeypatch.setattr(settings, "ENABLE_DEV_OTP", False)
    monkeypatch.setattr(settings, "WHATSAPP_OTP_ENABLED", False)
    try:
        get_sms_provider()
        assert False, "Production development fallback should fail closed"
    except RuntimeError:
        pass
