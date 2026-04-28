# Directivas Completas: Arquitecto v2 de SODA

## Contexto para Claude Code

Este documento es una especificación completa y autocontenida para implementar el Arquitecto v2 de SODA, junto con todos sus componentes de soporte.

**Antes de implementar cualquier cosa:**
1. Leé este documento completo
2. Revisá el estado actual del proyecto (qué ya existe, qué falta)
3. Identificá puntos de integración con código existente
4. Proponé un plan de implementación al usuario
5. Esperá aprobación antes de codear

**Regla fundamental:** no asumas. Si algo no está claro, preguntá.

---

## 1. Visión del Sistema

El Arquitecto v2 es el componente responsable de diseñar la arquitectura completa de cualquier proyecto que SODA vaya a construir. Funciona como un arquitecto senior humano: recibe requerimientos, analiza complejidad, y produce un contrato maestro exhaustivo que todos los agentes subsiguientes deben respetar.

### El flujo completo

```
Usuario aprueba blueprint del proyecto
    ↓
ProjectComplexityClassifier analiza el blueprint
    ↓ determina complejidad (simple, medium, complex)
    ↓
Architect genera Contrato Maestro usando el modelo correspondiente
    ↓ (Haiku/Sonnet/Opus según complejidad)
    ↓
ContractAuditor valida el contrato en Python puro
    ↓
¿Pasó la auditoría?
    ├─ Sí → Contrato aprobado → Siguiente fase
    └─ No → ContractRefinementLoop devuelve feedback al Architect
              ↓ (máximo 3 intentos)
              Architect refina el contrato
              ↓
              (vuelve a auditoría)
    ↓
Si después de 3 intentos no se aprueba → Escalado al usuario
```

### Componentes a implementar

1. **ProjectComplexityClassifier** (Python puro) - Clasifica el proyecto
2. **MasterContract** (Pydantic schemas) - Estructura del contrato
3. **Architect** (usa Claude según complejidad) - Genera el contrato
4. **ContractAuditor** (Python puro) - Valida el contrato
5. **ContractRefinementLoop** (Python puro) - Orquesta el ciclo

---

## 2. Principios de Implementación

Estos principios guían todas las decisiones de diseño:

**P1. Contrato como ley.** Una vez aprobado, el contrato es inmutable durante la fase de construcción.

**P2. Auditoría determinística.** El auditor es Python puro, sin IA. Reglas explícitas y reproducibles.

**P3. Escalado por complejidad.** Usar el modelo más barato que resuelva bien. Haiku para simple, Sonnet para medio, Opus para complejo.

**P4. Feedback accionable.** Cuando el auditor encuentra problemas, el feedback al Arquitecto debe ser específico y corregible.

**P5. Extensibilidad por diseño.** El contrato siempre incluye puntos de extensión para evolución futura.

**P6. Trazabilidad total.** Cada módulo mapea a nodos del árbol de objetivos.

**P7. Iteración acotada.** Máximo 3 intentos antes de escalar al usuario.

---

## 3. Configuración de Modelos

### Asignación por complejidad

```python
MODEL_ASSIGNMENT_BY_COMPLEXITY = {
    "simple": "claude-haiku-4-5-20251001",
    "medium": "claude-sonnet-4-5-20250929",
    "complex": "claude-opus-4-7",
}
```

### Costos estimados por contrato

Para un proyecto típico con un contrato de ~5000 tokens input y ~4000 tokens output:

- **Haiku 4.5:** ~$0.03 por intento
- **Sonnet 4.5:** ~$0.08 por intento
- **Opus 4.7:** ~$0.40 por intento

Con hasta 3 intentos en el loop:
- Simple: $0.03 - $0.10 por proyecto
- Medio: $0.08 - $0.25 por proyecto
- Complejo: $0.40 - $1.20 por proyecto

### Configuración de llamada por modelo

```python
MODEL_CALL_CONFIG = {
    "claude-haiku-4-5-20251001": {
        "temperature": 0.2,
        "max_tokens": 6000,
    },
    "claude-sonnet-4-5-20250929": {
        "temperature": 0.2,
        "max_tokens": 8000,
    },
    "claude-opus-4-7": {
        "temperature": 0.2,
        "max_tokens": 12000,
    },
}
```

---

## 4. Componente 1: ProjectComplexityClassifier

### 4.1 Ubicación

**Archivo:** `kernel/intelligence/complexity_classifier.py`

### 4.2 Responsabilidad

Analizar el blueprint del proyecto y determinar su nivel de complejidad: `simple`, `medium` o `complex`.

**No usa IA.** Es Python puro con reglas heurísticas.

### 4.3 Señales de análisis

El clasificador analiza estas señales del blueprint:

**Señales de tamaño:**
- Número de funcionalidades mencionadas
- Número estimado de módulos
- Líneas de código estimadas
- Número de entidades de datos distintas

**Señales de complejidad técnica:**
- Número de stacks tecnológicos (solo backend vs full-stack vs multi-stack)
- Requisitos de tiempo real
- Requisitos de multi-tenancy
- Requisitos de escalabilidad
- Necesidad de arquitectura distribuida

**Señales de integraciones:**
- Número de servicios externos (pagos, email, APIs)
- Integraciones con compliance (GDPR, HIPAA, etc.)
- Autenticación compleja (OAuth, SSO, MFA)

**Señales de dominio:**
- Industria regulada (salud, finanzas, legal)
- Datos sensibles
- Workflows complejos de negocio

### 4.4 Esquema de datos

```python
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum

class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"

class ComplexitySignals(BaseModel):
    """Señales extraídas del blueprint."""
    estimated_modules: int = Field(default=0, ge=0)
    estimated_loc: int = Field(default=0, ge=0)
    stack_count: int = Field(default=1, ge=1)
    external_integrations: list[str] = Field(default_factory=list)
    requires_realtime: bool = False
    requires_multi_tenant: bool = False
    requires_compliance: list[str] = Field(default_factory=list)
    auth_complexity: Literal["simple", "moderate", "complex"] = "simple"
    estimated_users: int = Field(default=0, ge=0)
    regulated_industry: bool = False
    handles_sensitive_data: bool = False
    complex_workflows: bool = False

class ComplexityAssessment(BaseModel):
    """Resultado de la evaluación."""
    level: ComplexityLevel
    score: int
    signals: ComplexitySignals
    reasoning: str
    override_available: bool = True
```

### 4.5 Algoritmo de clasificación

```python
class ProjectComplexityClassifier:
    """Clasifica proyectos por complejidad para asignación de modelos."""
    
    def __init__(self):
        self.weights = self._load_weights()
    
    def classify(self, blueprint: dict) -> ComplexityAssessment:
        """
        Punto de entrada principal.
        
        Args:
            blueprint: el blueprint aprobado del proyecto (estructura JSON)
        
        Returns:
            ComplexityAssessment con nivel y justificación
        """
        signals = self._extract_signals(blueprint)
        scores = self._calculate_scores(signals)
        level = self._determine_level(scores)
        reasoning = self._build_reasoning(signals, scores, level)
        
        return ComplexityAssessment(
            level=level,
            score=scores[level.value],
            signals=signals,
            reasoning=reasoning,
        )
    
    def _extract_signals(self, blueprint: dict) -> ComplexitySignals:
        """Extrae señales del blueprint."""
        # Implementar parsing del blueprint
        # Cada señal tiene su lógica específica de extracción
        pass
    
    def _calculate_scores(self, signals: ComplexitySignals) -> dict[str, int]:
        """Calcula score para cada nivel de complejidad."""
        simple_score = 0
        medium_score = 0
        complex_score = 0
        
        # Reglas para SIMPLE
        if signals.estimated_modules <= 3:
            simple_score += 3
        if signals.estimated_loc < 2000:
            simple_score += 2
        if signals.stack_count == 1:
            simple_score += 2
        if len(signals.external_integrations) == 0:
            simple_score += 2
        if not signals.requires_realtime:
            simple_score += 1
        if signals.auth_complexity == "simple":
            simple_score += 1
        if signals.estimated_users < 100:
            simple_score += 1
        
        # Reglas para MEDIUM
        if 4 <= signals.estimated_modules <= 8:
            medium_score += 3
        if 2000 <= signals.estimated_loc <= 10000:
            medium_score += 2
        if signals.stack_count == 2:
            medium_score += 2
        if 1 <= len(signals.external_integrations) <= 3:
            medium_score += 2
        if signals.auth_complexity == "moderate":
            medium_score += 1
        if 100 <= signals.estimated_users < 10000:
            medium_score += 1
        
        # Reglas para COMPLEX
        if signals.estimated_modules > 8:
            complex_score += 3
        if signals.estimated_loc > 10000:
            complex_score += 3
        if signals.stack_count > 2:
            complex_score += 2
        if len(signals.external_integrations) > 3:
            complex_score += 2
        if signals.requires_realtime:
            complex_score += 2
        if signals.requires_multi_tenant:
            complex_score += 2
        if len(signals.requires_compliance) > 0:
            complex_score += 3
        if signals.auth_complexity == "complex":
            complex_score += 2
        if signals.estimated_users >= 10000:
            complex_score += 2
        if signals.regulated_industry:
            complex_score += 2
        if signals.handles_sensitive_data:
            complex_score += 1
        if signals.complex_workflows:
            complex_score += 1
        
        return {
            "simple": simple_score,
            "medium": medium_score,
            "complex": complex_score,
        }
    
    def _determine_level(self, scores: dict[str, int]) -> ComplexityLevel:
        """Determina el nivel final con regla de desempate."""
        # Si complex tiene score alto, es complex (nunca se subestima complejidad)
        if scores["complex"] >= 6:
            return ComplexityLevel.COMPLEX
        
        # Si medium supera a simple por margen, es medium
        if scores["medium"] > scores["simple"] + 2:
            return ComplexityLevel.MEDIUM
        
        # Si los scores están parejos entre medium y complex, elegir complex (conservador)
        if abs(scores["medium"] - scores["complex"]) <= 2 and scores["complex"] >= 4:
            return ComplexityLevel.COMPLEX
        
        # Default al más alto
        return ComplexityLevel(max(scores, key=scores.get))
    
    def _build_reasoning(
        self,
        signals: ComplexitySignals,
        scores: dict[str, int],
        level: ComplexityLevel,
    ) -> str:
        """Genera explicación del resultado."""
        reasons = []
        reasons.append(f"Proyecto clasificado como {level.value}")
        reasons.append(f"Scores: {scores}")
        
        if level == ComplexityLevel.SIMPLE:
            reasons.append("Factores principales:")
            reasons.append(f"- Módulos estimados: {signals.estimated_modules}")
            reasons.append(f"- Integraciones externas: {len(signals.external_integrations)}")
            reasons.append(f"- Sin requisitos especiales")
        
        elif level == ComplexityLevel.MEDIUM:
            reasons.append("Factores principales:")
            reasons.append(f"- Módulos estimados: {signals.estimated_modules}")
            reasons.append(f"- {len(signals.external_integrations)} integraciones externas")
            reasons.append(f"- Complejidad de autenticación: {signals.auth_complexity}")
        
        else:  # COMPLEX
            reasons.append("Factores principales:")
            if signals.requires_compliance:
                reasons.append(f"- Compliance requerido: {signals.requires_compliance}")
            if signals.requires_multi_tenant:
                reasons.append("- Multi-tenant")
            if signals.requires_realtime:
                reasons.append("- Tiempo real")
            reasons.append(f"- {signals.estimated_modules} módulos estimados")
        
        return "\n".join(reasons)
```

### 4.6 Override manual

El usuario puede forzar un nivel específico:

```python
def select_model_for_architect(
    complexity: ComplexityLevel,
    user_override: ComplexityLevel | None = None,
) -> str:
    """Selecciona el modelo a usar para el Arquitecto."""
    final_level = user_override if user_override else complexity
    return MODEL_ASSIGNMENT_BY_COMPLEXITY[final_level.value]
```

### 4.7 Tests requeridos

Archivo: `tests/intelligence/test_complexity_classifier.py`

Casos de prueba mínimos:

1. **Clasificación simple:** blueprint con CRUD básico → SIMPLE
2. **Clasificación media:** blueprint con backend + frontend + 2 integraciones → MEDIUM
3. **Clasificación compleja:** blueprint con compliance + multi-tenant → COMPLEX
4. **Casos límite:** scores empatados entre niveles
5. **Override manual:** user override funciona correctamente
6. **Señales vacías:** blueprint mínimo se clasifica como simple
7. **Industria regulada:** salud o finanzas fuerzan COMPLEX o MEDIUM
8. **Reasoning:** el texto de reasoning es descriptivo y útil

---

## 5. Componente 2: MasterContract (Schemas Pydantic)

### 5.1 Ubicación

**Archivo:** `kernel/intelligence/contract_schemas.py`

### 5.2 Schemas completos

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime

class DataType(BaseModel):
    """Tipo de dato compartido entre módulos."""
    name: str = Field(..., description="Nombre único del tipo, en PascalCase")
    kind: Literal["primitive", "object", "enum", "union", "list"]
    fields: Optional[dict[str, str]] = Field(None, description="Para objects: {nombre_campo: tipo}")
    values: Optional[list[str]] = Field(None, description="Para enums: valores posibles")
    item_type: Optional[str] = Field(None, description="Para lists: tipo de los items")
    description: str = Field(..., min_length=10)
    used_by_modules: list[str] = Field(default_factory=list)

class InterfaceMethod(BaseModel):
    """Método público expuesto por un módulo."""
    name: str = Field(..., description="Nombre del método en snake_case")
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Mapa de {nombre_param: tipo}"
    )
    returns: str = Field(..., description="Tipo de retorno")
    raises: list[str] = Field(default_factory=list, description="Tipos de excepciones posibles")
    description: str = Field(..., min_length=10)
    example_usage: str = Field(..., description="Ejemplo de uso del método")
    is_async: bool = False

class Interface(BaseModel):
    """Interfaz pública de un módulo."""
    name: str = Field(..., description="Nombre de la interfaz")
    description: str
    methods: list[InterfaceMethod] = Field(..., min_length=1)
    events_emitted: list[str] = Field(default_factory=list)
    events_consumed: list[str] = Field(default_factory=list)

class Module(BaseModel):
    """Módulo del sistema."""
    id: str = Field(..., description="ID único, snake_case")
    name: str = Field(..., description="Nombre descriptivo")
    purpose: str = Field(..., min_length=20)
    interfaces: list[Interface] = Field(..., min_length=1)
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs de otros módulos de los que depende"
    )
    data_types_used: list[str] = Field(default_factory=list)
    extension_points: list[str] = Field(default_factory=list)
    goal_ids: list[str] = Field(
        ...,
        min_length=1,
        description="IDs de nodos del árbol de objetivos que implementa"
    )
    layer: Literal["domain", "application", "infrastructure", "presentation"]
    
    @field_validator('id')
    @classmethod
    def validate_snake_case(cls, v: str) -> str:
        if not v.replace('_', '').isalnum():
            raise ValueError('Module ID must be snake_case alphanumeric')
        if v != v.lower():
            raise ValueError('Module ID must be lowercase')
        return v

class EventChannel(BaseModel):
    """Canal de eventos del sistema."""
    name: str = Field(..., description="Nombre en formato dotted, ej: 'user.created'")
    payload_schema: str = Field(..., description="Nombre del DataType que define el payload")
    publishers: list[str] = Field(default_factory=list, description="Module IDs que publican")
    subscribers: list[str] = Field(default_factory=list, description="Module IDs que consumen")
    description: str
    is_reserved: bool = Field(False, description="True si es un canal reservado para extensión")
    
    @field_validator('name')
    @classmethod
    def validate_dotted(cls, v: str) -> str:
        if '.' not in v:
            raise ValueError('Event name must use dotted notation, e.g., "user.created"')
        return v

class ExtensionPoint(BaseModel):
    """Punto de extensión para evolución futura."""
    id: str
    type: Literal[
        "middleware_slot",
        "event_channel",
        "metadata_field",
        "plugin",
        "hook",
        "filter"
    ]
    location: str = Field(..., description="Dónde se aplica este punto")
    contract: str = Field(..., description="Qué debe cumplir quien lo extienda")
    description: str
    example_use_case: str

class ErrorType(BaseModel):
    """Tipo de error estandarizado."""
    name: str = Field(..., description="Nombre en PascalCase, ej: 'UserNotFoundError'")
    code: str = Field(..., description="Código UPPER_SNAKE_CASE, ej: 'AUTH_USER_NOT_FOUND'")
    message_template: str = Field(..., description="Template del mensaje, puede tener {placeholders}")
    recoverable: bool
    retry_strategy: Optional[str] = Field(None, description="Estrategia de retry si aplica")
    http_status: Optional[int] = Field(None, ge=400, le=599)
    raised_by_modules: list[str] = Field(default_factory=list)

class ArchitecturalDecision(BaseModel):
    """Decisión arquitectónica tomada con su justificación."""
    id: str
    title: str
    context: str = Field(..., description="Situación que llevó a esta decisión")
    decision: str = Field(..., description="Qué se decidió")
    consequences: list[str] = Field(..., description="Implicaciones positivas y negativas")
    alternatives_considered: list[str] = Field(default_factory=list)

class Constant(BaseModel):
    """Constante del sistema."""
    name: str = Field(..., description="UPPER_SNAKE_CASE")
    value: str
    type: str
    description: str
    used_in_modules: list[str] = Field(default_factory=list)

class MasterContract(BaseModel):
    """Contrato Maestro completo del proyecto."""
    project_id: str
    project_name: str
    version: str = Field("1.0.0", description="Semver del contrato")
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    complexity_level: Literal["simple", "medium", "complex"]
    model_used: str
    
    # Componentes del sistema
    modules: list[Module] = Field(..., min_length=1)
    data_types: list[DataType] = Field(default_factory=list)
    event_channels: list[EventChannel] = Field(default_factory=list)
    extension_points: list[ExtensionPoint] = Field(..., min_length=3)
    error_types: list[ErrorType] = Field(..., min_length=3)
    constants: list[Constant] = Field(default_factory=list)
    
    # Decisiones y documentación
    architectural_decisions: list[ArchitecturalDecision] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    
    # Metadata
    metadata: dict = Field(default_factory=dict)
```

### 5.3 Validaciones a nivel de schema

Los validadores de Pydantic capturan muchos errores automáticamente:
- Nombres obligatorios en formatos correctos (snake_case, PascalCase, etc.)
- Mínimos de elementos (al menos 1 módulo, al menos 3 extension_points, etc.)
- Campos requeridos vs opcionales
- Tipos literales controlados (kind, layer, type)

Los validadores más complejos (cross-reference, circularity, etc.) los implementa el ContractAuditor.

---

## 6. Componente 3: Architect

### 6.1 Ubicación

**Archivos:**
- `kernel/intelligence/architect.py` - Clase principal
- `prompts/claude/architect_simple.md` - Prompt para Haiku
- `prompts/claude/architect_medium.md` - Prompt para Sonnet
- `prompts/claude/architect_complex.md` - Prompt para Opus

### 6.2 Interfaz del Architect

```python
from kernel.drivers.claude_driver import ClaudeDriver
from kernel.context.context_builder import ContextBuilder
from kernel.intelligence.complexity_classifier import ComplexityLevel
from kernel.intelligence.contract_schemas import MasterContract
import json

class Architect:
    """Genera y refina contratos maestros de proyectos."""
    
    def __init__(
        self,
        claude_driver: ClaudeDriver,
        context_builder: ContextBuilder,
    ):
        self.driver = claude_driver
        self.context_builder = context_builder
    
    async def generate_master_contract(
        self,
        blueprint: dict,
        complexity: ComplexityLevel,
        active_skills: list,
        active_profile: dict,
        goal_tree: dict,
    ) -> MasterContract:
        """Genera el contrato maestro inicial."""
        
        model = MODEL_ASSIGNMENT_BY_COMPLEXITY[complexity.value]
        system_prompt = self._load_prompt_for_complexity(complexity)
        
        user_message = self._build_generation_prompt(
            blueprint=blueprint,
            skills=active_skills,
            profile=active_profile,
            goal_tree=goal_tree,
        )
        
        response = await self.driver.call(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            **MODEL_CALL_CONFIG[model],
            response_format="json",
        )
        
        contract_data = json.loads(response.content)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = model
        
        return MasterContract(**contract_data)
    
    async def refine_contract(
        self,
        current_contract: MasterContract,
        audit_feedback: "AuditReport",
        complexity: ComplexityLevel,
    ) -> MasterContract:
        """Refina un contrato basándose en feedback del auditor."""
        
        model = MODEL_ASSIGNMENT_BY_COMPLEXITY[complexity.value]
        system_prompt = self._load_refinement_prompt()
        
        feedback_text = audit_feedback.to_architect_feedback()
        
        user_message = self._build_refinement_prompt(
            current_contract=current_contract,
            feedback=feedback_text,
        )
        
        response = await self.driver.call(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            **MODEL_CALL_CONFIG[model],
            response_format="json",
        )
        
        contract_data = json.loads(response.content)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = model
        
        return MasterContract(**contract_data)
    
    def _load_prompt_for_complexity(self, complexity: ComplexityLevel) -> str:
        """Carga el prompt apropiado según complejidad."""
        path_map = {
            ComplexityLevel.SIMPLE: "prompts/claude/architect_simple.md",
            ComplexityLevel.MEDIUM: "prompts/claude/architect_medium.md",
            ComplexityLevel.COMPLEX: "prompts/claude/architect_complex.md",
        }
        path = path_map[complexity]
        with open(path) as f:
            return f.read()
    
    def _load_refinement_prompt(self) -> str:
        with open("prompts/claude/architect_refinement.md") as f:
            return f.read()
    
    def _build_generation_prompt(
        self,
        blueprint: dict,
        skills: list,
        profile: dict,
        goal_tree: dict,
    ) -> str:
        """Construye el prompt de generación."""
        return f"""Generá el contrato maestro para este proyecto.

## Blueprint del proyecto
```json
{json.dumps(blueprint, indent=2, ensure_ascii=False)}
```

## Árbol de objetivos
```json
{json.dumps(goal_tree, indent=2, ensure_ascii=False)}
```

## Skills activas
{self._format_skills(skills)}

## Perfil activo
{self._format_profile(profile)}

## Instrucciones
Generá un contrato maestro siguiendo el schema proporcionado.
Asegurate de incluir:
- Al menos 3 puntos de extensión
- Al menos 3 tipos de error estandarizados
- Todos los módulos mapean a al menos un goal_id del árbol
- Convenciones de nombres consistentes
- Documentación clara en cada elemento

Respondé solo con el JSON del contrato, sin explicaciones adicionales.
"""
    
    def _build_refinement_prompt(
        self,
        current_contract: MasterContract,
        feedback: str,
    ) -> str:
        """Construye el prompt de refinamiento."""
        return f"""Refiná el siguiente contrato basándote en el feedback del auditor.

## Contrato actual
```json
{current_contract.model_dump_json(indent=2)}
```

## Feedback del auditor
{feedback}

## Instrucciones
Corregí los errores críticos identificados.
Preservá todo lo que está correcto.
Mantené el mismo schema de output.

Respondé solo con el JSON del contrato corregido.
"""
    
    def _format_skills(self, skills: list) -> str:
        if not skills:
            return "Ninguna skill activa"
        return "\n".join(f"- {s.get('name')}: {s.get('description', '')}" for s in skills)
    
    def _format_profile(self, profile: dict) -> str:
        if not profile:
            return "Sin perfil específico"
        return f"""
Perfil: {profile.get('name')}
Experiencia: {profile.get('description', '')}
Preferencias de stack: {profile.get('preferred_stacks', [])}
"""
```

### 6.3 Prompt Base para Haiku (proyectos simples)

**Archivo:** `prompts/claude/architect_simple.md`

```markdown
# Arquitecto de Software - Proyectos Simples

Sos un arquitecto de software experimentado. Tu tarea es generar contratos maestros para proyectos de software simples: CRUDs básicos, APIs simples, scripts, utilidades.

## Tu output

Un contrato maestro en formato JSON que cumpla con el schema MasterContract.

El contrato debe incluir:
- Definición de todos los módulos necesarios (típicamente 1-3 módulos)
- Interfaces públicas con métodos, tipos de entrada y salida
- Tipos de datos compartidos
- Eventos (si aplica)
- Al menos 3 puntos de extensión
- Al menos 3 tipos de error estandarizados
- Constantes del sistema
- Decisiones arquitectónicas relevantes

## Principios a seguir

**Simplicidad sobre complejidad.** Para proyectos simples, evitar sobre-ingeniería. No crear abstracciones innecesarias.

**Convenciones consistentes:**
- Module IDs: snake_case
- Data types: PascalCase
- Método names: snake_case
- Constantes: UPPER_SNAKE_CASE
- Event names: dotted notation (ej: "user.created")
- Error codes: UPPER_SNAKE_CASE con prefijo (ej: "AUTH_FAILED")

**Trazabilidad obligatoria:** cada módulo debe mapear a al menos un goal_id del árbol de objetivos.

**Puntos de extensión:** incluir al menos:
- Un middleware_slot
- Un metadata_field reservado
- Un event_channel reservado o custom

## Formato de output

Respondé solo con JSON válido que cumpla el schema MasterContract.
No incluyas texto antes o después del JSON.
No uses markdown code fences.
```

### 6.4 Prompt Base para Sonnet (proyectos medios)

**Archivo:** `prompts/claude/architect_medium.md`

```markdown
# Arquitecto de Software - Proyectos Medios

Sos un arquitecto de software senior. Tu tarea es generar contratos maestros para proyectos de software de complejidad media: aplicaciones full-stack, SaaS simples, sistemas con múltiples módulos e integraciones.

## Tu output

Un contrato maestro en formato JSON que cumpla con el schema MasterContract.

## Consideraciones específicas para complejidad media

**Arquitectura por capas:** usar explícitamente las capas domain, application, infrastructure, presentation. Cada módulo se asigna a una capa.

**Separación de responsabilidades:** aplicar SRP rigurosamente. Un módulo hace una cosa bien.

**Dependencias unidireccionales:** módulos de capas superiores dependen de inferiores, nunca al revés.

**Puntos de extensión abundantes:** mínimo 5 puntos, anticipando necesidades futuras:
- Middleware slots para autenticación, logging, rate limiting
- Metadata fields en entidades principales
- Event channels para integraciones futuras
- Hook points en workflows críticos

**Manejo de errores completo:** al menos 8-10 tipos de error cubriendo:
- Errores de autenticación/autorización
- Errores de validación
- Errores de integraciones externas
- Errores de negocio específicos
- Errores técnicos (timeout, connection)

**Decisiones arquitectónicas documentadas:** explicar decisiones importantes como:
- Por qué elegiste X tecnología
- Por qué separaste o no separaste módulos
- Cómo manejás concurrencia si aplica
- Trade-offs asumidos

## Convenciones (igual que proyectos simples)

- Module IDs: snake_case
- Data types: PascalCase
- Método names: snake_case
- Constantes: UPPER_SNAKE_CASE
- Event names: dotted notation
- Error codes: UPPER_SNAKE_CASE con prefijo de módulo

## Trazabilidad

Cada módulo debe mapear a múltiples goal_ids cuando aplique. Los goal_ids cubren todo el árbol de objetivos sin dejar goals huérfanos.

## Formato de output

Respondé solo con JSON válido que cumpla el schema MasterContract.
No incluyas texto antes o después del JSON.
```

### 6.5 Prompt Base para Opus (proyectos complejos)

**Archivo:** `prompts/claude/architect_complex.md`

```markdown
# Arquitecto de Software Senior - Proyectos Complejos

Sos un arquitecto de software senior con experiencia en sistemas complejos, distribuidos, multi-tenant, y regulados. Tu tarea es generar contratos maestros para proyectos de alta complejidad.

## Tu output

Un contrato maestro en formato JSON que cumpla con el schema MasterContract.

## Consideraciones específicas para complejidad alta

**Arquitectura por capas explícita con Domain-Driven Design:**
- Bounded contexts claramente delimitados
- Agregados, entidades, value objects identificados
- Servicios de dominio separados de servicios de aplicación

**Patrones de arquitectura avanzados cuando aplique:**
- CQRS si hay asimetría entre reads y writes
- Event Sourcing si la auditabilidad es crítica
- Saga pattern para transacciones distribuidas
- Outbox pattern para consistencia eventual
- Circuit Breakers para integraciones externas

**Preocupaciones transversales (cross-cutting concerns):**
- Autenticación y autorización en todas las capas
- Logging estructurado con correlation IDs
- Observabilidad (tracing, metrics, logs)
- Rate limiting y throttling
- Idempotencia en operaciones críticas
- Caching strategy explícita

**Compliance y seguridad:**
- Si hay compliance (GDPR, HIPAA, PCI-DSS), implicaciones en todos los módulos afectados
- Encryption at rest y in transit donde corresponda
- Data retention policies
- Audit logs separados

**Multi-tenancy si aplica:**
- Estrategia de aislamiento (DB per tenant, schema per tenant, shared)
- Tenant context en todos los requests
- Cross-tenant operations (si existen) controladas

**Escalabilidad considerada:**
- Módulos stateless cuando posible
- Puntos de caching identificados
- Queues para procesamiento async
- Read replicas si aplica

**Puntos de extensión extensivos (mínimo 10):**
- Plugins para funcionalidad opcional
- Hooks en lifecycle events
- Middlewares en pipelines HTTP y de eventos
- Metadata extensible en todas las entidades principales
- Event channels para integraciones futuras

**Manejo de errores sofisticado:**
- Jerarquía de errores clara
- Retry strategies con exponential backoff
- Dead letter queues para mensajes no procesables
- Circuit breakers para integraciones externas
- Graceful degradation paths

**Decisiones arquitectónicas exhaustivamente documentadas:**
- Cada decisión con contexto, opciones consideradas, rationale
- Trade-offs explicitados
- Implicaciones a largo plazo
- Assumptions documentadas

## Convenciones

Mismas que los otros niveles. Consistencia es crítica en proyectos grandes.

## Trazabilidad

Cada módulo debe estar atado a múltiples goal_ids. Ningún goal debe quedar sin implementación. El contrato completo debe cubrir el árbol de objetivos sin gaps.

## Formato de output

Respondé solo con JSON válido que cumpla el schema MasterContract.
No incluyas texto antes o después del JSON.
Dada la complejidad, el contrato puede ser extenso. Asegurate de usar max_tokens apropiado.
```

### 6.6 Prompt de Refinamiento

**Archivo:** `prompts/claude/architect_refinement.md`

```markdown
# Arquitecto - Modo Refinamiento

Estás refinando un contrato maestro existente basándote en feedback específico del auditor.

## Instrucciones

**Preservá lo que está correcto.** No reescribas todo. Solo modificá lo necesario para corregir los issues reportados.

**Corregí errores críticos primero.** Los issues marcados como "error" son bloqueantes y deben resolverse.

**Considerá los warnings.** Los issues marcados como "warning" no son bloqueantes pero deberías corregirlos si no afecta otras partes del contrato.

**Ignorá los info por ahora.** Los issues marcados como "info" son sugerencias, no requieren acción inmediata.

**Mantené el schema.** El output sigue siendo MasterContract completo en JSON.

**Coherencia interna:** si corregís algo, verificá que no rompas otras partes. Por ejemplo, si renombrás un tipo, actualizá todas las referencias.

## Formato de output

JSON completo del contrato refinado. Todo el contrato, no solo las partes cambiadas.
No incluyas texto explicativo antes o después.
```

### 6.7 Tests requeridos

**Archivo:** `tests/intelligence/test_architect.py`

Casos mínimos:

1. Generar contrato para proyecto simple (CRUD)
2. Generar contrato para proyecto medio (e-commerce simple)
3. Generar contrato para proyecto complejo (platform multi-tenant)
4. Refinar contrato con feedback de auditor
5. El output cumple schema MasterContract en todos los casos
6. El modelo usado corresponde a la complejidad
7. El contrato incluye mínimo requerido de extension_points y error_types

---

## 7. Componente 4: ContractAuditor

### 7.1 Ubicación

**Archivos:**
- `kernel/integrity/contract_auditor.py` - Auditor principal
- `kernel/integrity/validators/base_validator.py` - Clase base
- `kernel/integrity/validators/consistency.py`
- `kernel/integrity/validators/completeness.py`
- `kernel/integrity/validators/dependency.py`
- `kernel/integrity/validators/naming.py`
- `kernel/integrity/validators/extensibility.py`
- `kernel/integrity/validators/traceability.py`

### 7.2 Schemas de Auditoría

**Archivo:** `kernel/integrity/audit_schemas.py`

```python
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

class Issue(BaseModel):
    """Problema detectado en el contrato."""
    severity: Literal["error", "warning", "info"]
    rule: str = Field(..., description="Nombre de la regla violada")
    location: str = Field(..., description="Path dentro del contrato")
    description: str
    suggestion: str

class ValidatorResult(BaseModel):
    """Resultado de un validador específico."""
    validator_name: str
    status: Literal["passed", "passed_with_warnings", "failed"]
    issues: list[Issue] = Field(default_factory=list)
    execution_time_ms: int = 0
    
    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)
    
    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

class AuditReport(BaseModel):
    """Reporte completo de auditoría."""
    contract_id: str
    audited_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    results: list[ValidatorResult]
    overall_status: Literal["passed", "passed_with_warnings", "failed"]
    
    @property
    def all_errors(self) -> list[Issue]:
        return [i for r in self.results for i in r.issues if i.severity == "error"]
    
    @property
    def all_warnings(self) -> list[Issue]:
        return [i for r in self.results for i in r.issues if i.severity == "warning"]
    
    def to_architect_feedback(self) -> str:
        """Formatea el reporte para el Arquitecto."""
        lines = []
        lines.append("# Feedback del Auditor del Contrato\n")
        
        errors = self.all_errors
        warnings = self.all_warnings
        
        if errors:
            lines.append(f"## Errores críticos ({len(errors)})\n")
            for issue in errors:
                lines.append(f"**{issue.rule}** en `{issue.location}`")
                lines.append(f"- Problema: {issue.description}")
                lines.append(f"- Corrección sugerida: {issue.suggestion}\n")
        
        if warnings:
            lines.append(f"\n## Warnings ({len(warnings)})\n")
            for issue in warnings:
                lines.append(f"**{issue.rule}** en `{issue.location}`")
                lines.append(f"- Observación: {issue.description}\n")
        
        lines.append("\n## Instrucciones\n")
        lines.append("Corregí los errores críticos listados arriba.")
        lines.append("Preservá todo lo que está correcto en el contrato actual.")
        lines.append("Los warnings pueden corregirse pero no son bloqueantes.")
        
        return "\n".join(lines)
```

### 7.3 Clase Base del Validador

**Archivo:** `kernel/integrity/validators/base_validator.py`

```python
from abc import ABC, abstractmethod
from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import ValidatorResult, Issue
import time

class BaseValidator(ABC):
    """Clase base para validadores de contrato."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre único del validador."""
        pass
    
    @abstractmethod
    async def _validate(self, contract: MasterContract) -> list[Issue]:
        """Lógica específica del validador. Retorna lista de issues."""
        pass
    
    async def validate(self, contract: MasterContract) -> ValidatorResult:
        """Ejecuta la validación y mide tiempo."""
        start = time.time()
        
        try:
            issues = await self._validate(contract)
        except Exception as e:
            issues = [Issue(
                severity="error",
                rule=f"{self.name}_exception",
                location="validator",
                description=f"El validador falló con excepción: {str(e)}",
                suggestion="Revisar el contrato por problemas graves de estructura",
            )]
        
        elapsed_ms = int((time.time() - start) * 1000)
        
        if any(i.severity == "error" for i in issues):
            status = "failed"
        elif any(i.severity == "warning" for i in issues):
            status = "passed_with_warnings"
        else:
            status = "passed"
        
        return ValidatorResult(
            validator_name=self.name,
            status=status,
            issues=issues,
            execution_time_ms=elapsed_ms,
        )
```

### 7.4 Validador de Consistencia

**Archivo:** `kernel/integrity/validators/consistency.py`

```python
from kernel.integrity.validators.base_validator import BaseValidator
from kernel.integrity.audit_schemas import Issue
from kernel.intelligence.contract_schemas import MasterContract

class ConsistencyValidator(BaseValidator):
    """Verifica consistencia interna del contrato."""
    
    @property
    def name(self) -> str:
        return "consistency_validator"
    
    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues = []
        
        # IDs únicos de módulos
        issues.extend(self._check_unique_module_ids(contract))
        
        # Tipos referenciados existen
        issues.extend(self._check_data_types_exist(contract))
        
        # Módulos referenciados en depends_on existen
        issues.extend(self._check_dependencies_exist(contract))
        
        # Eventos emitidos/consumidos existen como canales
        issues.extend(self._check_events_exist(contract))
        
        # Error codes únicos
        issues.extend(self._check_unique_error_codes(contract))
        
        # Extension point IDs únicos
        issues.extend(self._check_unique_extension_ids(contract))
        
        return issues
    
    def _check_unique_module_ids(self, contract: MasterContract) -> list[Issue]:
        seen = set()
        duplicates = []
        for module in contract.modules:
            if module.id in seen:
                duplicates.append(module.id)
            seen.add(module.id)
        
        return [
            Issue(
                severity="error",
                rule="unique_module_ids",
                location=f"modules[id={dup}]",
                description=f"ID de módulo duplicado: {dup}",
                suggestion="Cada módulo debe tener un ID único"
            )
            for dup in duplicates
        ]
    
    def _check_data_types_exist(self, contract: MasterContract) -> list[Issue]:
        defined_types = {dt.name for dt in contract.data_types}
        primitive_types = {"str", "int", "float", "bool", "None", "datetime", "bytes", "Any", "dict", "list"}
        all_valid_types = defined_types | primitive_types
        
        issues = []
        
        for module in contract.modules:
            for interface in module.interfaces:
                for method in interface.methods:
                    # Check return type
                    if not self._is_valid_type(method.returns, all_valid_types):
                        issues.append(Issue(
                            severity="error",
                            rule="data_types_exist",
                            location=f"modules[{module.id}].interfaces[{interface.name}].methods[{method.name}].returns",
                            description=f"Tipo de retorno '{method.returns}' no está definido",
                            suggestion=f"Definir el tipo '{method.returns}' en data_types o usar un tipo primitivo"
                        ))
                    
                    # Check parameter types
                    for param_name, param_type in method.parameters.items():
                        if not self._is_valid_type(param_type, all_valid_types):
                            issues.append(Issue(
                                severity="error",
                                rule="data_types_exist",
                                location=f"modules[{module.id}].interfaces[{interface.name}].methods[{method.name}].parameters.{param_name}",
                                description=f"Tipo de parámetro '{param_type}' no está definido",
                                suggestion=f"Definir el tipo '{param_type}' en data_types o usar un tipo primitivo"
                            ))
        
        return issues
    
    def _is_valid_type(self, type_str: str, valid_types: set[str]) -> bool:
        """Verifica si un string de tipo es válido, considerando genéricos."""
        # Limpiar el tipo de envoltorios como Optional, list[], etc.
        clean = type_str.strip()
        
        # Remover Optional[]
        if clean.startswith("Optional[") and clean.endswith("]"):
            clean = clean[9:-1]
        
        # Remover list[], dict[], etc.
        for container in ["list[", "List[", "dict[", "Dict[", "set[", "Set[", "tuple[", "Tuple["]:
            if clean.startswith(container) and clean.endswith("]"):
                # Simplificación: asumir válido si el contenedor lo es
                return True
        
        return clean in valid_types
    
    def _check_dependencies_exist(self, contract: MasterContract) -> list[Issue]:
        module_ids = {m.id for m in contract.modules}
        issues = []
        
        for module in contract.modules:
            for dep in module.depends_on:
                if dep not in module_ids:
                    issues.append(Issue(
                        severity="error",
                        rule="dependencies_exist",
                        location=f"modules[{module.id}].depends_on",
                        description=f"Dependencia '{dep}' no es un módulo definido",
                        suggestion=f"Remover la dependencia o agregar el módulo '{dep}'"
                    ))
        
        return issues
    
    def _check_events_exist(self, contract: MasterContract) -> list[Issue]:
        channel_names = {ec.name for ec in contract.event_channels}
        issues = []
        
        for module in contract.modules:
            for interface in module.interfaces:
                for event in interface.events_emitted:
                    if event not in channel_names:
                        issues.append(Issue(
                            severity="error",
                            rule="events_exist",
                            location=f"modules[{module.id}].interfaces[{interface.name}].events_emitted",
                            description=f"Evento '{event}' emitido pero no definido como channel",
                            suggestion=f"Agregar el evento '{event}' a event_channels"
                        ))
                
                for event in interface.events_consumed:
                    if event not in channel_names:
                        issues.append(Issue(
                            severity="error",
                            rule="events_exist",
                            location=f"modules[{module.id}].interfaces[{interface.name}].events_consumed",
                            description=f"Evento '{event}' consumido pero no definido como channel",
                            suggestion=f"Agregar el evento '{event}' a event_channels"
                        ))
        
        return issues
    
    def _check_unique_error_codes(self, contract: MasterContract) -> list[Issue]:
        seen = set()
        duplicates = []
        for error in contract.error_types:
            if error.code in seen:
                duplicates.append(error.code)
            seen.add(error.code)
        
        return [
            Issue(
                severity="error",
                rule="unique_error_codes",
                location=f"error_types[code={dup}]",
                description=f"Error code duplicado: {dup}",
                suggestion="Cada error type debe tener un code único"
            )
            for dup in duplicates
        ]
    
    def _check_unique_extension_ids(self, contract: MasterContract) -> list[Issue]:
        seen = set()
        duplicates = []
        for ext in contract.extension_points:
            if ext.id in seen:
                duplicates.append(ext.id)
            seen.add(ext.id)
        
        return [
            Issue(
                severity="error",
                rule="unique_extension_ids",
                location=f"extension_points[id={dup}]",
                description=f"Extension point ID duplicado: {dup}",
                suggestion="Cada extension point debe tener un ID único"
            )
            for dup in duplicates
        ]
```

### 7.5 Validador de Completitud

**Archivo:** `kernel/integrity/validators/completeness.py`

```python
from kernel.integrity.validators.base_validator import BaseValidator
from kernel.integrity.audit_schemas import Issue
from kernel.intelligence.contract_schemas import MasterContract

class CompletenessValidator(BaseValidator):
    """Verifica que el contrato esté completo."""
    
    MIN_EXTENSION_POINTS = 3
    MIN_ERROR_TYPES = 3
    
    @property
    def name(self) -> str:
        return "completeness_validator"
    
    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues = []
        
        # Mínimo de módulos
        if len(contract.modules) < 1:
            issues.append(Issue(
                severity="error",
                rule="minimum_modules",
                location="modules",
                description="El contrato debe tener al menos 1 módulo",
                suggestion="Definir los módulos del sistema"
            ))
        
        # Mínimo de extension points
        if len(contract.extension_points) < self.MIN_EXTENSION_POINTS:
            issues.append(Issue(
                severity="error",
                rule="minimum_extension_points",
                location="extension_points",
                description=f"Debe haber al menos {self.MIN_EXTENSION_POINTS} puntos de extensión, hay {len(contract.extension_points)}",
                suggestion=f"Agregar al menos {self.MIN_EXTENSION_POINTS - len(contract.extension_points)} puntos de extensión más"
            ))
        
        # Mínimo de error types
        if len(contract.error_types) < self.MIN_ERROR_TYPES:
            issues.append(Issue(
                severity="error",
                rule="minimum_error_types",
                location="error_types",
                description=f"Debe haber al menos {self.MIN_ERROR_TYPES} tipos de error, hay {len(contract.error_types)}",
                suggestion="Definir tipos de error adicionales para diferentes situaciones"
            ))
        
        # Cada módulo tiene al menos una interfaz
        for module in contract.modules:
            if not module.interfaces:
                issues.append(Issue(
                    severity="error",
                    rule="module_has_interfaces",
                    location=f"modules[{module.id}].interfaces",
                    description=f"Módulo '{module.id}' no tiene interfaces definidas",
                    suggestion="Todo módulo debe exponer al menos una interfaz"
                ))
            
            for interface in module.interfaces:
                if not interface.methods:
                    issues.append(Issue(
                        severity="error",
                        rule="interface_has_methods",
                        location=f"modules[{module.id}].interfaces[{interface.name}].methods",
                        description=f"Interfaz '{interface.name}' no tiene métodos definidos",
                        suggestion="Toda interfaz debe tener al menos un método"
                    ))
                
                for method in interface.methods:
                    if len(method.description) < 10:
                        issues.append(Issue(
                            severity="warning",
                            rule="method_description_too_short",
                            location=f"modules[{module.id}].interfaces[{interface.name}].methods[{method.name}].description",
                            description=f"Descripción del método '{method.name}' es muy corta",
                            suggestion="Agregar descripción más detallada"
                        ))
        
        # Data types tienen descripción
        for dt in contract.data_types:
            if len(dt.description) < 10:
                issues.append(Issue(
                    severity="warning",
                    rule="data_type_description_too_short",
                    location=f"data_types[{dt.name}].description",
                    description=f"Descripción del tipo '{dt.name}' es muy corta",
                    suggestion="Agregar descripción más detallada"
                ))
        
        return issues
```

### 7.6 Validador de Dependencias

**Archivo:** `kernel/integrity/validators/dependency.py`

```python
from kernel.integrity.validators.base_validator import BaseValidator
from kernel.integrity.audit_schemas import Issue
from kernel.intelligence.contract_schemas import MasterContract

class DependencyValidator(BaseValidator):
    """Verifica integridad del grafo de dependencias."""
    
    MAX_DEPTH = 5
    MAX_DIRECT_DEPENDENCIES = 8
    
    @property
    def name(self) -> str:
        return "dependency_validator"
    
    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues = []
        
        # Construir grafo de dependencias
        graph = {m.id: m.depends_on for m in contract.modules}
        
        # Detectar ciclos
        cycles = self._detect_cycles(graph)
        for cycle in cycles:
            issues.append(Issue(
                severity="error",
                rule="no_circular_dependencies",
                location=f"modules[{','.join(cycle)}]",
                description=f"Dependencia circular detectada: {' -> '.join(cycle)} -> {cycle[0]}",
                suggestion="Reestructurar las dependencias para eliminar el ciclo, posiblemente usando inversión de dependencias"
            ))
        
        # Verificar profundidad máxima
        depths = self._calculate_depths(graph)
        for module_id, depth in depths.items():
            if depth > self.MAX_DEPTH:
                issues.append(Issue(
                    severity="warning",
                    rule="max_dependency_depth",
                    location=f"modules[{module_id}]",
                    description=f"Profundidad de dependencias excesiva: {depth} (máximo recomendado: {self.MAX_DEPTH})",
                    suggestion="Considerar aplanar la jerarquía de dependencias"
                ))
        
        # Verificar dependencias directas excesivas
        for module_id, deps in graph.items():
            if len(deps) > self.MAX_DIRECT_DEPENDENCIES:
                issues.append(Issue(
                    severity="warning",
                    rule="max_direct_dependencies",
                    location=f"modules[{module_id}].depends_on",
                    description=f"Módulo '{module_id}' tiene muchas dependencias directas: {len(deps)} (máximo recomendado: {self.MAX_DIRECT_DEPENDENCIES})",
                    suggestion="Considerar refactorizar el módulo para reducir sus dependencias"
                ))
        
        return issues
    
    def _detect_cycles(self, graph: dict[str, list[str]]) -> list[list[str]]:
        """Detecta ciclos usando DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        colors = {node: WHITE for node in graph}
        cycles = []
        
        def dfs(node: str, path: list[str]) -> None:
            if colors[node] == GRAY:
                # Encontramos ciclo
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:])
                return
            if colors[node] == BLACK:
                return
            
            colors[node] = GRAY
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor in graph:
                    dfs(neighbor, path.copy())
            
            colors[node] = BLACK
        
        for node in graph:
            if colors[node] == WHITE:
                dfs(node, [])
        
        return cycles
    
    def _calculate_depths(self, graph: dict[str, list[str]]) -> dict[str, int]:
        """Calcula la profundidad máxima de dependencias de cada nodo."""
        depths = {}
        
        def depth(node: str, visited: set[str]) -> int:
            if node in visited:
                return 0  # Ciclo detectado, no profundizar
            if node in depths:
                return depths[node]
            if node not in graph:
                return 0
            
            visited.add(node)
            deps = graph.get(node, [])
            
            if not deps:
                depths[node] = 0
                return 0
            
            max_dep_depth = max(
                (depth(dep, visited.copy()) for dep in deps if dep in graph),
                default=0
            )
            
            depths[node] = max_dep_depth + 1
            return depths[node]
        
        for node in graph:
            if node not in depths:
                depth(node, set())
        
        return depths
```

### 7.7 Validador de Nombres

**Archivo:** `kernel/integrity/validators/naming.py`

```python
import re
from kernel.integrity.validators.base_validator import BaseValidator
from kernel.integrity.audit_schemas import Issue
from kernel.intelligence.contract_schemas import MasterContract

class NamingValidator(BaseValidator):
    """Verifica convenciones de nombres."""
    
    SNAKE_CASE_REGEX = re.compile(r'^[a-z][a-z0-9_]*$')
    PASCAL_CASE_REGEX = re.compile(r'^[A-Z][a-zA-Z0-9]*$')
    UPPER_SNAKE_CASE_REGEX = re.compile(r'^[A-Z][A-Z0-9_]*$')
    DOTTED_EVENT_REGEX = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')
    
    @property
    def name(self) -> str:
        return "naming_validator"
    
    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues = []
        
        # Module IDs: snake_case
        for module in contract.modules:
            if not self.SNAKE_CASE_REGEX.match(module.id):
                issues.append(Issue(
                    severity="error",
                    rule="module_id_snake_case",
                    location=f"modules[{module.id}].id",
                    description=f"ID de módulo '{module.id}' no es snake_case",
                    suggestion="Usar snake_case: solo minúsculas, números y underscores"
                ))
        
        # Data types: PascalCase
        for dt in contract.data_types:
            if not self.PASCAL_CASE_REGEX.match(dt.name):
                issues.append(Issue(
                    severity="error",
                    rule="data_type_pascal_case",
                    location=f"data_types[{dt.name}].name",
                    description=f"Nombre de tipo '{dt.name}' no es PascalCase",
                    suggestion="Usar PascalCase: empezar con mayúscula, sin underscores"
                ))
        
        # Método names: snake_case
        for module in contract.modules:
            for interface in module.interfaces:
                for method in interface.methods:
                    if not self.SNAKE_CASE_REGEX.match(method.name):
                        issues.append(Issue(
                            severity="error",
                            rule="method_name_snake_case",
                            location=f"modules[{module.id}].interfaces[{interface.name}].methods[{method.name}].name",
                            description=f"Nombre de método '{method.name}' no es snake_case",
                            suggestion="Usar snake_case para nombres de métodos"
                        ))
        
        # Constants: UPPER_SNAKE_CASE
        for const in contract.constants:
            if not self.UPPER_SNAKE_CASE_REGEX.match(const.name):
                issues.append(Issue(
                    severity="error",
                    rule="constant_upper_snake_case",
                    location=f"constants[{const.name}].name",
                    description=f"Nombre de constante '{const.name}' no es UPPER_SNAKE_CASE",
                    suggestion="Usar UPPER_SNAKE_CASE para constantes"
                ))
        
        # Event names: dotted notation
        for event in contract.event_channels:
            if not self.DOTTED_EVENT_REGEX.match(event.name):
                issues.append(Issue(
                    severity="error",
                    rule="event_dotted_notation",
                    location=f"event_channels[{event.name}].name",
                    description=f"Nombre de evento '{event.name}' no usa notación con puntos",
                    suggestion="Usar notación con puntos: 'entidad.accion' (ej: 'user.created')"
                ))
        
        # Error codes: UPPER_SNAKE_CASE
        for error in contract.error_types:
            if not self.UPPER_SNAKE_CASE_REGEX.match(error.code):
                issues.append(Issue(
                    severity="error",
                    rule="error_code_upper_snake_case",
                    location=f"error_types[{error.code}].code",
                    description=f"Error code '{error.code}' no es UPPER_SNAKE_CASE",
                    suggestion="Usar UPPER_SNAKE_CASE para error codes"
                ))
        
        return issues
```

### 7.8 Validador de Extensibilidad

**Archivo:** `kernel/integrity/validators/extensibility.py`

```python
from kernel.integrity.validators.base_validator import BaseValidator
from kernel.integrity.audit_schemas import Issue
from kernel.intelligence.contract_schemas import MasterContract

class ExtensibilityValidator(BaseValidator):
    """Verifica que haya suficientes puntos de extensión."""
    
    REQUIRED_TYPES = {"middleware_slot", "metadata_field", "event_channel"}
    MIN_TOTAL = 3
    
    @property
    def name(self) -> str:
        return "extensibility_validator"
    
    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues = []
        
        # Cantidad mínima
        if len(contract.extension_points) < self.MIN_TOTAL:
            issues.append(Issue(
                severity="error",
                rule="minimum_extension_points",
                location="extension_points",
                description=f"Debe haber al menos {self.MIN_TOTAL} puntos de extensión",
                suggestion="Agregar más puntos de extensión para permitir evolución futura"
            ))
        
        # Tipos diversos
        present_types = {ext.type for ext in contract.extension_points}
        missing_types = self.REQUIRED_TYPES - present_types
        
        for missing in missing_types:
            issues.append(Issue(
                severity="warning",
                rule="missing_extension_type",
                location="extension_points",
                description=f"No hay puntos de extensión de tipo '{missing}'",
                suggestion=f"Considerar agregar al menos un '{missing}' para extensibilidad balanceada"
            ))
        
        # Cada extension point está bien documentado
        for ext in contract.extension_points:
            if len(ext.contract) < 20:
                issues.append(Issue(
                    severity="warning",
                    rule="extension_point_contract_unclear",
                    location=f"extension_points[{ext.id}].contract",
                    description=f"Extension point '{ext.id}' tiene contrato poco claro",
                    suggestion="Documentar claramente qué debe cumplir quien use este extension point"
                ))
            
            if not ext.example_use_case:
                issues.append(Issue(
                    severity="info",
                    rule="extension_point_no_example",
                    location=f"extension_points[{ext.id}].example_use_case",
                    description=f"Extension point '{ext.id}' no tiene ejemplo de uso",
                    suggestion="Agregar un ejemplo de uso facilita la adopción futura"
                ))
        
        return issues
```

### 7.9 Validador de Trazabilidad

**Archivo:** `kernel/integrity/validators/traceability.py`

```python
from kernel.integrity.validators.base_validator import BaseValidator
from kernel.integrity.audit_schemas import Issue
from kernel.intelligence.contract_schemas import MasterContract

class TraceabilityValidator(BaseValidator):
    """Verifica trazabilidad con el árbol de objetivos."""
    
    def __init__(self, goal_tree: dict):
        self.goal_tree = goal_tree
        self.all_goal_ids = self._extract_all_goal_ids(goal_tree)
    
    @property
    def name(self) -> str:
        return "traceability_validator"
    
    async def _validate(self, contract: MasterContract) -> list[Issue]:
        issues = []
        
        # Todo módulo referencia al menos un goal_id válido
        for module in contract.modules:
            if not module.goal_ids:
                issues.append(Issue(
                    severity="error",
                    rule="module_has_goals",
                    location=f"modules[{module.id}].goal_ids",
                    description=f"Módulo '{module.id}' no referencia ningún goal",
                    suggestion="Todo módulo debe mapear a al menos un objetivo del árbol"
                ))
                continue
            
            for goal_id in module.goal_ids:
                if goal_id not in self.all_goal_ids:
                    issues.append(Issue(
                        severity="error",
                        rule="goal_ids_valid",
                        location=f"modules[{module.id}].goal_ids",
                        description=f"Goal ID '{goal_id}' no existe en el árbol de objetivos",
                        suggestion="Verificar que el goal_id corresponda a un nodo existente"
                    ))
        
        # Todos los goals del árbol tienen al menos un módulo que los implementa
        implemented_goals = set()
        for module in contract.modules:
            implemented_goals.update(module.goal_ids)
        
        unimplemented = self.all_goal_ids - implemented_goals
        for goal_id in unimplemented:
            issues.append(Issue(
                severity="warning",
                rule="goal_has_implementation",
                location=f"goal_tree[{goal_id}]",
                description=f"Goal '{goal_id}' no está implementado por ningún módulo",
                suggestion="Asignar el goal a un módulo, o verificar si es necesario"
            ))
        
        return issues
    
    def _extract_all_goal_ids(self, tree: dict) -> set[str]:
        """Extrae todos los goal IDs del árbol."""
        ids = set()
        
        def traverse(node):
            if isinstance(node, dict):
                if "id" in node:
                    ids.add(node["id"])
                for value in node.values():
                    traverse(value)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)
        
        traverse(tree)
        return ids
```

### 7.10 Orquestador del Auditor

**Archivo:** `kernel/integrity/contract_auditor.py`

```python
import asyncio
from kernel.integrity.audit_schemas import AuditReport
from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.validators.consistency import ConsistencyValidator
from kernel.integrity.validators.completeness import CompletenessValidator
from kernel.integrity.validators.dependency import DependencyValidator
from kernel.integrity.validators.naming import NamingValidator
from kernel.integrity.validators.extensibility import ExtensibilityValidator
from kernel.integrity.validators.traceability import TraceabilityValidator

class ContractAuditor:
    """Audita contratos maestros ejecutando todos los validadores."""
    
    def __init__(self, goal_tree: dict):
        self.goal_tree = goal_tree
        self.validators = [
            ConsistencyValidator(),
            CompletenessValidator(),
            DependencyValidator(),
            NamingValidator(),
            ExtensibilityValidator(),
            TraceabilityValidator(goal_tree=goal_tree),
        ]
    
    async def audit(self, contract: MasterContract) -> AuditReport:
        """Ejecuta todos los validadores y consolida el reporte."""
        results = await asyncio.gather(
            *(validator.validate(contract) for validator in self.validators)
        )
        
        has_errors = any(r.has_errors for r in results)
        has_warnings = any(r.has_warnings for r in results)
        
        if has_errors:
            overall = "failed"
        elif has_warnings:
            overall = "passed_with_warnings"
        else:
            overall = "passed"
        
        return AuditReport(
            contract_id=contract.project_id,
            results=list(results),
            overall_status=overall,
        )
```

---

## 8. Componente 5: ContractRefinementLoop

### 8.1 Ubicación

**Archivo:** `kernel/orchestration/contract_refinement_loop.py`

### 8.2 Implementación

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal
from kernel.intelligence.architect import Architect
from kernel.integrity.contract_auditor import ContractAuditor
from kernel.intelligence.contract_schemas import MasterContract
from kernel.integrity.audit_schemas import AuditReport
from kernel.intelligence.complexity_classifier import ComplexityLevel

class RefinementAttempt(BaseModel):
    attempt_number: int
    contract: MasterContract
    audit_report: AuditReport
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ContractResult(BaseModel):
    status: Literal["approved", "approved_with_warnings", "requires_user_intervention"]
    contract: MasterContract | None
    attempts: list[RefinementAttempt]
    final_issues: AuditReport | None = None
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0

class ContractRefinementLoop:
    """Orquesta el ciclo Arquitecto ↔ Auditor."""
    
    def __init__(
        self,
        architect: Architect,
        auditor: ContractAuditor,
        max_attempts: int = 3,
    ):
        self.architect = architect
        self.auditor = auditor
        self.max_attempts = max_attempts
    
    async def execute(
        self,
        blueprint: dict,
        complexity: ComplexityLevel,
        active_skills: list,
        active_profile: dict,
        goal_tree: dict,
    ) -> ContractResult:
        """Ejecuta el ciclo completo."""
        attempts = []
        current_contract = None
        
        for attempt_num in range(self.max_attempts):
            # Generar o refinar contrato
            if attempt_num == 0:
                current_contract = await self.architect.generate_master_contract(
                    blueprint=blueprint,
                    complexity=complexity,
                    active_skills=active_skills,
                    active_profile=active_profile,
                    goal_tree=goal_tree,
                )
            else:
                current_contract = await self.architect.refine_contract(
                    current_contract=current_contract,
                    audit_feedback=attempts[-1].audit_report,
                    complexity=complexity,
                )
            
            # Auditar
            audit_report = await self.auditor.audit(current_contract)
            
            attempts.append(RefinementAttempt(
                attempt_number=attempt_num + 1,
                contract=current_contract,
                audit_report=audit_report,
            ))
            
            # Evaluar si continuar
            if audit_report.overall_status == "passed":
                return ContractResult(
                    status="approved",
                    contract=current_contract,
                    attempts=attempts,
                )
            
            if audit_report.overall_status == "passed_with_warnings":
                return ContractResult(
                    status="approved_with_warnings",
                    contract=current_contract,
                    attempts=attempts,
                )
        
        # Agotamos intentos sin aprobación
        return ContractResult(
            status="requires_user_intervention",
            contract=current_contract,
            attempts=attempts,
            final_issues=attempts[-1].audit_report,
        )
```

---

## 9. Integración con el Orchestrator Principal

### 9.1 Modificaciones al Orchestrator

El Orchestrator principal debe invocar estos componentes en la fase de arquitectura:

```python
# En el Orchestrator principal
async def execute_architecture_phase(self, project):
    # 1. Clasificar complejidad
    classifier = ProjectComplexityClassifier()
    complexity_assessment = classifier.classify(project.blueprint)
    
    # Notificar al usuario la clasificación
    await self.ui.notify(
        project.id,
        f"Proyecto clasificado como {complexity_assessment.level.value}",
        complexity_assessment.reasoning
    )
    
    # 2. Preparar inputs
    active_skills = await self.skill_matcher.get_for_project(project)
    active_profile = await self.profile_matcher.get_for_project(project)
    goal_tree = project.goal_tree
    
    # 3. Ejecutar refinement loop
    loop = ContractRefinementLoop(
        architect=self.architect,
        auditor=ContractAuditor(goal_tree=goal_tree.to_dict()),
        max_attempts=3,
    )
    
    result = await loop.execute(
        blueprint=project.blueprint,
        complexity=complexity_assessment.level,
        active_skills=active_skills,
        active_profile=active_profile,
        goal_tree=goal_tree.to_dict(),
    )
    
    # 4. Manejar resultado
    if result.status == "approved":
        project.master_contract = result.contract
        await self.advance_to_skeleton_generation(project)
    
    elif result.status == "approved_with_warnings":
        project.master_contract = result.contract
        await self.ui.show_warnings(
            project.id,
            result.attempts[-1].audit_report
        )
        await self.advance_to_skeleton_generation(project)
    
    elif result.status == "requires_user_intervention":
        await self.escalate_to_user(
            project,
            result.final_issues,
            result.attempts
        )
```

### 9.2 Persistencia del Contrato

Cuando el contrato es aprobado, se guarda en el proyecto:

- **Ubicación:** `projects/{project_id}/master_contract.json`
- **Versionado:** commitear en git con mensaje `"feat: master contract approved (complexity: {level}, attempts: {n})"`
- **Inmutabilidad:** una vez aprobado, el contrato no se modifica durante desarrollo

---

## 10. Testing Completo Requerido

### 10.1 Tests por componente

**test_complexity_classifier.py:** 8 casos mínimos (ver sección 4.7)

**test_contract_schemas.py:** validar que los schemas Pydantic rechazan inputs inválidos y aceptan válidos

**test_architect.py:** 
- Generación para cada nivel de complejidad
- Refinamiento con feedback
- Output cumple schema

**test_validators.py:** un archivo por validador, con casos positivos y negativos para cada regla

**test_contract_auditor.py:** integración de todos los validadores

**test_contract_refinement_loop.py:**
- Loop exitoso en primer intento
- Loop que refina y aprueba
- Loop que agota intentos
- Manejo de errores

### 10.2 Tests de integración

**test_architect_audit_integration.py:** flujo end-to-end desde blueprint hasta contrato aprobado

---

## 11. Primera Acción Esperada

Al terminar de leer este documento, tu primera respuesta debe ser:

1. Confirmar que leíste y entendiste el alcance completo
2. Inventario del código existente relevante (Drivers, ContextBuilder, modelos Pydantic ya definidos, Orchestrator actual)
3. Plan de implementación con:
   - Orden específico de componentes a crear
   - Modificaciones a componentes existentes
   - Archivos nuevos que se crearán
   - Tests que implementarás
   - Estimación de tiempo por fase
4. Preguntas sobre ambigüedades o decisiones de integración
5. Riesgos identificados

**No empieces a codear hasta que el usuario apruebe tu plan.**

---

## 12. Criterios de Éxito

La implementación es exitosa cuando:

1. ProjectComplexityClassifier clasifica correctamente proyectos de prueba en cada nivel
2. Architect genera contratos válidos según schema en los 3 niveles de complejidad
3. ContractAuditor detecta todos los tipos de issues esperados en casos de prueba
4. Refinement loop converge en menos de 3 intentos para 90%+ de casos
5. Costos promedio se mantienen en los rangos estimados
6. Tests pasan con cobertura mínima del 80%
7. Integración con Orchestrator no rompe funcionalidad existente
8. El contrato persistido es consultable y auditable

---

## 13. Notas Finales

### Sobre el manejo de tokens y costos

El UsageMonitor existente (si ya está implementado) debe capturar cada llamada al Architect con metadata:
- Modelo usado
- Tokens input/output
- Costo
- Nivel de complejidad
- Attempt number

Esto permite análisis posterior de eficiencia.

### Sobre iteración y mejora

Después de los primeros 10-20 proyectos reales, hay que analizar:
- Frecuencia de cada tipo de error detectado por el auditor
- Tipos de errores que el Arquitecto comete más seguido
- Casos donde el refinement loop converge vs escala a usuario

Esta telemetría guía mejoras a los prompts del Arquitecto.

### Sobre extensiones futuras (fuera de este scope)

Cosas que NO implementamos ahora pero preparamos el terreno:
- Caché de contratos similares para proyectos parecidos
- Templates de contratos por tipo de proyecto común
- Aprendizaje del Arquitecto de contratos aprobados (retroalimentación positiva)
- Versionado de contratos y migración entre versiones

Esto viene después, cuando el sistema base esté estable.

---

**Cierre:** este sistema es la pieza más crítica de SODA. Su calidad determina la calidad de todo lo subsecuente. Invertí el tiempo necesario en hacerlo bien, especialmente los validadores que son Python puro y tienen que ser determinísticos y confiables.
