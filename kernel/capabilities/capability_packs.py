from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CapabilityPack:
    key: str
    name: str
    description: str
    domains: tuple[str, ...]
    includes: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["domains"] = list(self.domains)
        data["includes"] = list(self.includes)
        return data


class CapabilityPackRegistry:
    """Closed catalog of reusable higher-level capability packs."""

    def __init__(self):
        self._packs = {
            pack.key: pack
            for pack in (
                CapabilityPack(
                    key="auth_complete",
                    name="Auth Complete",
                    description="End-to-end authentication and authorization foundations.",
                    domains=("backend", "security", "web"),
                    includes=("login", "registration", "roles", "permissions", "session_or_jwt"),
                ),
                CapabilityPack(
                    key="payment_processing",
                    name="Payment Processing",
                    description="Payment flows via Stripe or MercadoPago: checkout sessions, webhooks, refunds, and transaction state handling.",
                    domains=("backend", "commerce", "integrations"),
                    includes=("stripe_checkout", "mercadopago_checkout", "webhooks", "refunds", "transaction_status"),
                ),
                CapabilityPack(
                    key="email_notifications",
                    name="Email Notifications",
                    description="Transactional email flows, templates, and delivery triggers.",
                    domains=("backend", "communication"),
                    includes=("templates", "delivery", "events", "retry_policy"),
                ),
            )
        }

    def list_packs(self, domain: str | None = None) -> list[dict]:
        packs = list(self._packs.values())
        if domain:
            normalized = domain.strip().lower()
            packs = [
                pack for pack in packs
                if any(item.lower() == normalized for item in pack.domains)
            ]
        return [pack.to_dict() for pack in sorted(packs, key=lambda item: item.key)]

    def get_pack(self, key: str) -> dict:
        normalized = (key or "").strip().lower()
        if normalized not in self._packs:
            raise KeyError(f"Unknown capability pack: {key}")
        return self._packs[normalized].to_dict()

    def recommend(self, text: str) -> list[str]:
        normalized = (text or "").strip().lower()
        if not normalized:
            return []

        keyword_map = {
            "auth_complete": (
                "auth",
                "authentication",
                "authorization",
                "login",
                "register",
                "signup",
                "role",
                "permission",
                "jwt",
                "oauth",
            ),
            "payment_processing": (
                "payment",
                "checkout",
                "stripe",
                "paypal",
                "billing",
                "invoice",
                "refund",
                "webhook",
            ),
            "email_notifications": (
                "email",
                "mail",
                "notification",
                "newsletter",
                "smtp",
                "template",
            ),
        }

        recommended = []
        for pack_key, keywords in keyword_map.items():
            if any(keyword in normalized for keyword in keywords):
                recommended.append(pack_key)
        return recommended