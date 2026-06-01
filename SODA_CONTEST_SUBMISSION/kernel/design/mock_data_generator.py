"""
MockDataGenerator — heuristic domain-specific mock data for UI seed content.

Provides realistic-looking data (no "Test User 1", "Item 1" placeholders) so that
generated UIs render with real-looking content in their initial state.

Called by UIDesignAgent.generate_spec() in heuristic mode (no AI available).
When AI mode is active, the AI-generated mock_data takes priority.
"""
from __future__ import annotations

from typing import Optional

# ─── Name / value pools ─────────────────────────────────────────────────────

_FIRST = [
    "Sarah", "Michael", "Emma", "James", "Olivia", "Noah", "Ava",
    "William", "Isabella", "Ethan", "Mia", "Lucas", "Charlotte",
    "Alexander", "Amelia", "Henry", "Sophie", "Daniel", "Harper", "Owen",
]
_LAST = [
    "Johnson", "Williams", "Chen", "Garcia", "Davis", "Rodriguez",
    "Wilson", "Anderson", "Taylor", "Martinez", "Thompson", "White",
    "Harris", "Lewis", "Clark", "Walker", "Hall", "Young", "Allen", "King",
]
_DOMAINS = ["acmecorp.com", "techventures.io", "innovatelab.net", "startup.dev", "enterprise.org"]
_COMPANIES = [
    "Acme Corp", "TechVentures", "InnovateLab", "DataStream Inc",
    "CloudPeak", "NexGen Solutions", "PixelForge", "ByteCraft",
    "Veridian Tech", "StellarSoft",
]


def _name(seed: int) -> str:
    return f"{_FIRST[seed % len(_FIRST)]} {_LAST[(seed * 7 + 3) % len(_LAST)]}"


def _email(name: str, seed: int) -> str:
    parts = name.lower().split()
    return f"{parts[0][0]}.{parts[1]}@{_DOMAINS[seed % len(_DOMAINS)]}"


def _company(seed: int) -> str:
    return _COMPANIES[seed % len(_COMPANIES)]


# ─── Domain generators ───────────────────────────────────────────────────────

def _dashboard_data() -> dict:
    users = []
    roles = ["Admin", "Editor", "Viewer", "Manager", "Analyst", "Developer"]
    statuses = ["Active", "Active", "Active", "Inactive", "Active", "Pending"]
    seen = ["just now", "2 min ago", "1 hour ago", "yesterday", "3 days ago", "1 week ago"]
    for i in range(6):
        n = _name(i)
        users.append({
            "id": i + 1,
            "name": n,
            "email": _email(n, i),
            "role": roles[i],
            "status": statuses[i],
            "lastSeen": seen[i],
            "avatar": f"https://api.dicebear.com/7.x/avataaars/svg?seed={n.replace(' ', '')}",
        })
    return {
        "kpi_metrics": [
            {"label": "Total Revenue", "value": "$124,580", "change": "+12.4%", "trend": "up", "period": "vs last month"},
            {"label": "Active Users", "value": "8,249", "change": "+3.2%", "trend": "up", "period": "vs last month"},
            {"label": "Conversion Rate", "value": "3.6%", "change": "-0.8%", "trend": "down", "period": "vs last month"},
            {"label": "Avg Session", "value": "4m 32s", "change": "+18s", "trend": "up", "period": "vs last month"},
        ],
        "users": users,
        "recent_activity": [
            {"id": 1, "user": _name(0), "action": "Created a new report", "timestamp": "2 minutes ago", "type": "create"},
            {"id": 2, "user": _name(1), "action": "Updated team settings", "timestamp": "15 minutes ago", "type": "update"},
            {"id": 3, "user": _name(2), "action": "Exported data to CSV", "timestamp": "1 hour ago", "type": "export"},
            {"id": 4, "user": _name(3), "action": "Invited 3 new team members", "timestamp": "3 hours ago", "type": "invite"},
            {"id": 5, "user": _name(4), "action": "Archived 12 old records", "timestamp": "Yesterday", "type": "archive"},
        ],
    }


def _ecommerce_data() -> dict:
    products = [
        {"id": "PRD-001", "name": "Wireless Noise-Canceling Headphones", "price": 279.99,
         "originalPrice": 349.99, "category": "Electronics", "stock": 45, "rating": 4.8,
         "reviews": 1243, "badge": "Best Seller"},
        {"id": "PRD-002", "name": "Ergonomic Standing Desk Converter", "price": 189.00,
         "originalPrice": None, "category": "Office", "stock": 12, "rating": 4.6,
         "reviews": 387, "badge": "Low Stock"},
        {"id": "PRD-003", "name": "Premium Leather Laptop Sleeve 15\"", "price": 49.99,
         "originalPrice": 69.99, "category": "Accessories", "stock": 89, "rating": 4.7,
         "reviews": 2156, "badge": "Sale"},
        {"id": "PRD-004", "name": "Mechanical Keyboard — Tactile Brown", "price": 129.00,
         "originalPrice": None, "category": "Electronics", "stock": 34, "rating": 4.9,
         "reviews": 891, "badge": None},
        {"id": "PRD-005", "name": "USB-C Hub 7-in-1 Adapter", "price": 39.99,
         "originalPrice": 54.99, "category": "Electronics", "stock": 156, "rating": 4.5,
         "reviews": 3421, "badge": "Sale"},
        {"id": "PRD-006", "name": "Bamboo Wireless Charging Pad", "price": 29.00,
         "originalPrice": None, "category": "Accessories", "stock": 67, "rating": 4.3,
         "reviews": 612, "badge": "New"},
    ]
    orders = [
        {"id": "#ORD-7891", "customer": _name(0), "date": "Jan 15, 2025", "total": "$329.98", "status": "Delivered", "items": 2},
        {"id": "#ORD-7890", "customer": _name(1), "date": "Jan 14, 2025", "total": "$189.00", "status": "Shipped", "items": 1},
        {"id": "#ORD-7889", "customer": _name(2), "date": "Jan 14, 2025", "total": "$79.98", "status": "Processing", "items": 3},
        {"id": "#ORD-7888", "customer": _name(3), "date": "Jan 13, 2025", "total": "$649.97", "status": "Delivered", "items": 4},
        {"id": "#ORD-7887", "customer": _name(4), "date": "Jan 12, 2025", "total": "$29.00", "status": "Cancelled", "items": 1},
    ]
    return {
        "products": products,
        "orders": orders,
        "categories": ["Electronics", "Office", "Accessories", "Books", "Sports", "Home"],
    }


def _social_data() -> dict:
    posts = [
        {
            "id": 1, "author": _name(0), "handle": "@sarah_j",
            "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=sarah",
            "content": "Just launched my new open-source project! Three months of work finally paying off. The community response has been incredible — 400 GitHub stars in 48 hours.",
            "timestamp": "5 minutes ago", "likes": 142, "comments": 23, "shares": 18, "liked": False,
        },
        {
            "id": 2, "author": _name(1), "handle": "@mike_w",
            "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=mike",
            "content": "The best productivity tip I've learned this year: time-block your calendar ruthlessly. Nothing changed my output more than protecting 3-hour deep work blocks every morning.",
            "timestamp": "2 hours ago", "likes": 387, "comments": 56, "shares": 94, "liked": True,
        },
        {
            "id": 3, "author": _name(2), "handle": "@emma_chen",
            "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=emma",
            "content": "Hot take: the most underrated skill in software engineering is writing. Clear documentation and well-named variables save more time than any clever algorithm.",
            "timestamp": "4 hours ago", "likes": 891, "comments": 134, "shares": 267, "liked": False,
        },
    ]
    return {
        "posts": posts,
        "trending_topics": ["#WebDev", "#TypeScript", "#OpenSource", "#Productivity", "#AI"],
        "suggested_users": [
            {"name": _name(5), "handle": "@lucas_k", "bio": "Product designer @ Figma | Design systems", "followers": "12.4K"},
            {"name": _name(6), "handle": "@charlotte_t", "bio": "Staff engineer @ Stripe | Open source", "followers": "8.7K"},
        ],
    }


def _fintech_data() -> dict:
    return {
        "account_summary": {
            "balance": "$24,891.50",
            "savings": "$8,340.00",
            "investments": "$15,200.00",
            "monthly_spend": "$3,847.20",
        },
        "transactions": [
            {"id": "TXN-001", "description": "Spotify Premium", "category": "Entertainment", "amount": -9.99, "date": "Jan 15", "status": "completed", "icon": "🎵"},
            {"id": "TXN-002", "description": "Salary Deposit — Acme Corp", "category": "Income", "amount": 5400.00, "date": "Jan 15", "status": "completed", "icon": "💼"},
            {"id": "TXN-003", "description": "Whole Foods Market", "category": "Groceries", "amount": -127.43, "date": "Jan 14", "status": "completed", "icon": "🛒"},
            {"id": "TXN-004", "description": "AWS Services", "category": "Software", "amount": -42.17, "date": "Jan 14", "status": "completed", "icon": "☁️"},
            {"id": "TXN-005", "description": "Netflix", "category": "Entertainment", "amount": -15.99, "date": "Jan 13", "status": "completed", "icon": "🎬"},
            {"id": "TXN-006", "description": "Freelance Invoice #142", "category": "Income", "amount": 1200.00, "date": "Jan 12", "status": "completed", "icon": "📋"},
        ],
        "spending_categories": [
            {"name": "Housing", "amount": 1800, "percentage": 47, "color": "#4f46e5"},
            {"name": "Groceries", "amount": 480, "percentage": 12, "color": "#10b981"},
            {"name": "Transport", "amount": 240, "percentage": 6, "color": "#f59e0b"},
            {"name": "Entertainment", "amount": 180, "percentage": 5, "color": "#ec4899"},
            {"name": "Other", "amount": 1147, "percentage": 30, "color": "#94a3b8"},
        ],
    }


def _healthcare_data() -> dict:
    return {
        "doctors": [
            {"id": "DR-001", "name": "Dr. Rebecca Torres", "specialty": "Cardiologist", "rating": 4.9, "patients": 847, "available": True, "nextSlot": "Today 3:00 PM"},
            {"id": "DR-002", "name": "Dr. James Nakamura", "specialty": "Neurologist", "rating": 4.7, "patients": 634, "available": False, "nextSlot": "Tomorrow 10:00 AM"},
            {"id": "DR-003", "name": "Dr. Maria Santos", "specialty": "General Practice", "rating": 4.8, "patients": 1203, "available": True, "nextSlot": "Today 4:30 PM"},
        ],
        "appointments": [
            {"id": "APT-001", "patient": _name(0), "doctor": "Dr. Rebecca Torres", "date": "Jan 16, 2025", "time": "10:00 AM", "type": "Follow-up", "status": "Confirmed"},
            {"id": "APT-002", "patient": _name(1), "doctor": "Dr. Maria Santos", "date": "Jan 16, 2025", "time": "2:30 PM", "type": "Check-up", "status": "Pending"},
            {"id": "APT-003", "patient": _name(2), "doctor": "Dr. James Nakamura", "date": "Jan 17, 2025", "time": "9:00 AM", "type": "Consultation", "status": "Confirmed"},
            {"id": "APT-004", "patient": _name(3), "doctor": "Dr. Maria Santos", "date": "Jan 17, 2025", "time": "11:00 AM", "type": "Check-up", "status": "Waitlisted"},
        ],
        "stats": {
            "total_patients": 2847,
            "appointments_today": 24,
            "avg_wait_time": "8 min",
            "satisfaction": "96%",
        },
    }


def _landing_data() -> dict:
    return {
        "hero": {
            "headline": "Build faster, ship smarter",
            "subheadline": "The all-in-one platform that helps your team collaborate, automate, and deliver results — 10x faster than before.",
            "cta_primary": "Start free trial",
            "cta_secondary": "Watch 2-min demo",
            "social_proof": "Trusted by 50,000+ teams at Google, Stripe, and Notion",
            "stats": [
                {"value": "50K+", "label": "Teams worldwide"},
                {"value": "99.9%", "label": "Uptime SLA"},
                {"value": "4.9/5", "label": "Customer rating"},
            ],
        },
        "features": [
            {"icon": "⚡", "title": "Blazing Fast", "description": "Built on edge infrastructure with sub-100ms response times globally. Your users never wait."},
            {"icon": "🔒", "title": "Enterprise Security", "description": "SOC 2 Type II compliant with end-to-end encryption, SSO, and granular role-based access."},
            {"icon": "🔧", "title": "Fully Customizable", "description": "Every workflow, every integration, every report — tailored exactly to how your team works."},
            {"icon": "📊", "title": "Real-time Analytics", "description": "Deep insights with beautiful dashboards that update the moment your data changes."},
        ],
        "testimonials": [
            {"name": "Alexandra Chen", "role": "CTO at Veritas Health", "content": "We reduced our deployment cycle from 2 weeks to 4 hours. The ROI was immediate and undeniable.", "avatar": "AC"},
            {"name": "Marcus Williams", "role": "VP Engineering at Flux", "content": "Finally a tool that actually delivers on its promises. Our entire team adopted it in under a week.", "avatar": "MW"},
            {"name": "Priya Sharma", "role": "Lead Developer at Orbit", "content": "The DX is exceptional. I've recommended it to every engineering team I know.", "avatar": "PS"},
        ],
        "pricing": [
            {"plan": "Starter", "price": "$0", "period": "forever", "features": ["5 projects", "10 GB storage", "Community support", "Basic analytics"]},
            {"plan": "Pro", "price": "$29", "period": "/month", "popular": True, "features": ["Unlimited projects", "100 GB storage", "Priority support", "Advanced analytics", "Custom domains"]},
            {"plan": "Enterprise", "price": "Custom", "period": "", "features": ["Everything in Pro", "SSO & SAML", "Custom contracts", "99.99% SLA", "Dedicated account manager"]},
        ],
    }


def _generic_data() -> dict:
    users = []
    for i in range(5):
        n = _name(i)
        users.append({"id": i + 1, "name": n, "email": _email(n, i), "status": "Active", "company": _company(i)})
    return {
        "users": users,
        "items": [
            {"id": 1, "title": "Q4 Performance Review", "description": "Annual performance metrics and team assessment report", "status": "Completed", "priority": "High"},
            {"id": 2, "title": "Product Roadmap 2025", "description": "Strategic planning for upcoming product features and milestones", "status": "In Progress", "priority": "High"},
            {"id": 3, "title": "Customer Feedback Analysis", "description": "Synthesizing 500+ survey responses into actionable insights", "status": "Pending", "priority": "Medium"},
            {"id": 4, "title": "Infrastructure Migration", "description": "Moving legacy services to cloud-native architecture", "status": "In Progress", "priority": "Critical"},
            {"id": 5, "title": "Security Audit", "description": "Quarterly vulnerability assessment and penetration testing", "status": "Scheduled", "priority": "High"},
        ],
        "notifications": [
            {"id": 1, "title": "New comment on your post", "time": "2 min ago", "read": False},
            {"id": 2, "title": "Meeting in 30 minutes: Design Review", "time": "28 min ago", "read": False},
            {"id": 3, "title": "Report exported successfully", "time": "1 hour ago", "read": True},
        ],
    }


# ─── Registry ────────────────────────────────────────────────────────────────

_GENERATORS = {
    "dashboard":      _dashboard_data,
    "ecommerce":      _ecommerce_data,
    "social":         _social_data,
    "fintech":        _fintech_data,
    "healthcare":     _healthcare_data,
    "landing":        _landing_data,
    "blog":           _landing_data,
    "developer_tool": _dashboard_data,
    "generic":        _generic_data,
}


class MockDataGenerator:
    """Generates domain-specific realistic mock data for UI seed content."""

    @staticmethod
    def generate(
        project_type: str,
        blueprint: Optional[dict] = None,
        architecture: Optional[dict] = None,
    ) -> dict:
        """
        Returns a dict of mock data keyed by entity type (e.g. 'users', 'products').
        Falls back to generic if project_type is unknown.
        """
        generator = _GENERATORS.get(project_type, _generic_data)
        return generator()
