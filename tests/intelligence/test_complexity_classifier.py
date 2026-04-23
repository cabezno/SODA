"""Tests for ProjectComplexityClassifier (Arquitecto v2, Fase 1)."""
import pytest

from kernel.intelligence.complexity_classifier import (
    ComplexityLevel,
    MODEL_ASSIGNMENT_BY_COMPLEXITY,
    ProjectComplexityClassifier,
    select_model_for_architect,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clf():
    return ProjectComplexityClassifier()


def _simple_blueprint() -> dict:
    return {
        "nombre": "Todo App",
        "descripcion": "Aplicación CRUD simple para gestionar tareas personales.",
        "funcionalidades": ["crear tarea", "editar tarea", "eliminar tarea"],
        "stack_sugerido": {"backend": "FastAPI"},
    }


def _medium_blueprint() -> dict:
    return {
        "nombre": "E-Commerce Simple",
        "descripcion": "Tienda online con carrito, pagos con Stripe y envío de emails.",
        "funcionalidades": [
            "catálogo de productos", "carrito de compras", "checkout",
            "pagos con stripe", "envío de emails con sendgrid",
            "panel de administración", "historial de pedidos",
        ],
        "stack_sugerido": {
            "backend": "FastAPI",
            "frontend": "React",
        },
        "integraciones": ["stripe", "sendgrid"],
    }


def _complex_blueprint() -> dict:
    return {
        "nombre": "SaaS Fintech Multi-Tenant",
        "descripcion": (
            "Plataforma SaaS multi-tenant para gestión financiera con compliance GDPR "
            "y PCI-DSS. Requiere tiempo real para notificaciones y SSO para autenticación. "
            "Manejo de datos sensibles como tarjetas y contraseñas. "
            "Esperamos miles de usuarios organizados por tenant."
        ),
        "funcionalidades": [
            "dashboard financiero", "reportes", "transacciones", "alertas en tiempo real",
            "gestión de usuarios", "roles y permisos", "facturación", "exportación",
            "integración contable", "auditoría", "multi-tenant", "compliance",
        ],
        "stack_sugerido": {
            "backend": "FastAPI",
            "frontend": "React",
            "mobile": "React Native",
        },
        "integraciones": ["stripe", "sendgrid", "twilio", "aws", "slack"],
    }


# ---------------------------------------------------------------------------
# Test 1: Simple classification
# ---------------------------------------------------------------------------

def test_simple_blueprint_classified_as_simple(clf):
    result = clf.classify(_simple_blueprint())
    assert result.level == ComplexityLevel.SIMPLE


def test_simple_has_low_scores(clf):
    result = clf.classify(_simple_blueprint())
    assert result.signals.estimated_modules <= 3
    assert len(result.signals.external_integrations) == 0


# ---------------------------------------------------------------------------
# Test 2: Medium classification
# ---------------------------------------------------------------------------

def test_medium_blueprint_classified_as_medium(clf):
    result = clf.classify(_medium_blueprint())
    assert result.level == ComplexityLevel.MEDIUM


def test_medium_detects_integrations(clf):
    result = clf.classify(_medium_blueprint())
    assert len(result.signals.external_integrations) >= 1


def test_medium_has_multi_stack(clf):
    result = clf.classify(_medium_blueprint())
    assert result.signals.stack_count >= 2


# ---------------------------------------------------------------------------
# Test 3: Complex classification
# ---------------------------------------------------------------------------

def test_complex_blueprint_classified_as_complex(clf):
    result = clf.classify(_complex_blueprint())
    assert result.level == ComplexityLevel.COMPLEX


def test_complex_detects_compliance(clf):
    result = clf.classify(_complex_blueprint())
    assert len(result.signals.requires_compliance) > 0


def test_complex_detects_multi_tenant(clf):
    result = clf.classify(_complex_blueprint())
    assert result.signals.requires_multi_tenant is True


def test_complex_detects_realtime(clf):
    result = clf.classify(_complex_blueprint())
    assert result.signals.requires_realtime is True


def test_complex_detects_sensitive_data(clf):
    result = clf.classify(_complex_blueprint())
    assert result.signals.handles_sensitive_data is True


# ---------------------------------------------------------------------------
# Test 4: Edge cases — tied scores lean conservative
# ---------------------------------------------------------------------------

def test_tied_medium_complex_scores_lean_complex(clf):
    """When medium and complex scores are close and complex >= 4, choose complex."""
    blueprint = {
        "nombre": "API con roles",
        "descripcion": "API backend con JWT y RBAC, roles y permisos. Integración con AWS S3.",
        "funcionalidades": ["auth", "roles", "api", "upload", "admin"],
        "stack_sugerido": {"backend": "FastAPI"},
        "integraciones": ["aws"],
    }
    result = clf.classify(blueprint)
    scores = clf._calculate_scores(result.signals)
    # Conservative tie-breaking: if complex score >= 4 and gap <= 2, should be complex
    if abs(scores["medium"] - scores["complex"]) <= 2 and scores["complex"] >= 4:
        assert result.level == ComplexityLevel.COMPLEX


# ---------------------------------------------------------------------------
# Test 5: Manual override
# ---------------------------------------------------------------------------

def test_override_forces_given_level():
    result = select_model_for_architect(
        ComplexityLevel.SIMPLE,
        user_override=ComplexityLevel.COMPLEX,
    )
    assert result == MODEL_ASSIGNMENT_BY_COMPLEXITY["complex"]


def test_no_override_uses_detected_level():
    result = select_model_for_architect(ComplexityLevel.MEDIUM)
    assert result == MODEL_ASSIGNMENT_BY_COMPLEXITY["medium"]


# ---------------------------------------------------------------------------
# Test 6: Minimal blueprint classified as simple
# ---------------------------------------------------------------------------

def test_empty_blueprint_classified_as_simple(clf):
    result = clf.classify({})
    assert result.level == ComplexityLevel.SIMPLE


def test_minimal_blueprint_classified_as_simple(clf):
    result = clf.classify({"nombre": "Script de backups", "descripcion": "Script simple"})
    assert result.level == ComplexityLevel.SIMPLE


# ---------------------------------------------------------------------------
# Test 7: Regulated industry forces higher complexity
# ---------------------------------------------------------------------------

def test_health_industry_increases_complexity(clf):
    blueprint = {
        "nombre": "Sistema Médico",
        "descripcion": "Sistema para gestión de historiales médicos en clínica.",
        "funcionalidades": ["pacientes", "historiales", "citas"],
        "stack_sugerido": {"backend": "FastAPI"},
    }
    result = clf.classify(blueprint)
    assert result.signals.regulated_industry is True
    # Regulated industry scores complex — should not be SIMPLE
    assert result.level != ComplexityLevel.SIMPLE


def test_finance_industry_increases_complexity(clf):
    blueprint = {
        "nombre": "App Finanzas",
        "descripcion": "Sistema de gestión de finanzas para banco.",
        "funcionalidades": ["transacciones", "reportes", "cuentas"],
        "stack_sugerido": {"backend": "Django"},
    }
    result = clf.classify(blueprint)
    assert result.signals.regulated_industry is True


# ---------------------------------------------------------------------------
# Test 8: Reasoning text is descriptive
# ---------------------------------------------------------------------------

def test_reasoning_is_non_empty(clf):
    result = clf.classify(_simple_blueprint())
    assert len(result.reasoning) > 20


def test_reasoning_mentions_level(clf):
    result = clf.classify(_complex_blueprint())
    assert "complex" in result.reasoning.lower()


def test_reasoning_contains_scores(clf):
    result = clf.classify(_medium_blueprint())
    assert "Scores" in result.reasoning


# ---------------------------------------------------------------------------
# Test 9: Model IDs are valid strings
# ---------------------------------------------------------------------------

def test_model_assignment_keys_complete():
    assert set(MODEL_ASSIGNMENT_BY_COMPLEXITY.keys()) == {"simple", "medium", "complex"}


def test_model_assignment_values_non_empty():
    for level, model in MODEL_ASSIGNMENT_BY_COMPLEXITY.items():
        assert isinstance(model, str) and len(model) > 0, f"Empty model ID for {level}"


# ---------------------------------------------------------------------------
# Test 10: Auth complexity detection
# ---------------------------------------------------------------------------

def test_oauth_detected_as_complex_auth(clf):
    bp = {"descripcion": "Sistema con OAuth y SSO para empresas."}
    result = clf.classify(bp)
    assert result.signals.auth_complexity == "complex"


def test_jwt_detected_as_moderate_auth(clf):
    bp = {"descripcion": "API con autenticación JWT y roles RBAC."}
    result = clf.classify(bp)
    assert result.signals.auth_complexity == "moderate"


def test_no_auth_keywords_is_simple_auth(clf):
    bp = {"descripcion": "Script de procesamiento de archivos CSV."}
    result = clf.classify(bp)
    assert result.signals.auth_complexity == "simple"
