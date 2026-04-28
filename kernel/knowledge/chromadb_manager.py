from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ChromaDBManager:
    """Semantic memory layer using ChromaDB.

    Stores project blueprints/architectures as embeddings so future projects
    can query for similar past work. Gracefully degrades when ChromaDB is
    unavailable (import error or collection errors).
    """

    COLLECTION_PROJECTS = "soda_projects"
    COLLECTION_SKILLS = "soda_skills"
    COLLECTION_PROFILES = "soda_profiles"

    def __init__(self, persist_dir: str = "data/chroma"):
        self.persist_dir = str(Path(persist_dir).resolve())
        self._client = None
        self._collections: dict = {}
        self._is_active = False
        self._try_init()

    def _try_init(self) -> None:
        try:
            import chromadb
            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            for name in (self.COLLECTION_PROJECTS, self.COLLECTION_SKILLS, self.COLLECTION_PROFILES):
                self._collections[name] = self._client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )
            self._is_active = True
            logger.info("ChromaDB initialized at %s", self.persist_dir)
        except Exception as exc:
            logger.warning("ChromaDB unavailable — vector memory disabled: %s", exc)
            self._is_active = False

    def is_available(self) -> bool:
        return self._is_active

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def store_project_context(self, project_id: str, context_data: dict) -> bool:
        """Store project blueprint + architecture as a searchable document."""
        if not self._is_active:
            return False
        try:
            col = self._collections[self.COLLECTION_PROJECTS]
            doc = json.dumps(context_data, ensure_ascii=False)
            # Use project_id as stable document ID
            col.upsert(
                ids=[project_id],
                documents=[doc],
                metadatas=[{
                    "project_id": project_id,
                    "nombre": str(context_data.get("nombre_proyecto", project_id))[:512],
                    "stack": str(context_data.get("stack_sugerido", ""))[:256],
                }],
            )
            return True
        except Exception as exc:
            logger.warning("ChromaDB store_project_context error: %s", exc)
            return False

    def query_similar_projects(self, query: str, n_results: int = 2) -> List[Dict]:
        """Return past projects semantically similar to the query description."""
        if not self._is_active:
            return []
        try:
            col = self._collections[self.COLLECTION_PROJECTS]
            count = col.count()
            if count == 0:
                return []
            results = col.query(
                query_texts=[query],
                n_results=min(n_results, count),
                include=["documents", "metadatas", "distances"],
            )
            out = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                try:
                    parsed = json.loads(doc)
                except Exception:
                    parsed = {"raw": doc}
                out.append({
                    "project_id": meta.get("project_id", ""),
                    "similarity": round(1.0 - float(dist), 4),
                    "context": parsed,
                })
            return out
        except Exception as exc:
            logger.warning("ChromaDB query_similar_projects error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Skills / Profiles (lightweight metadata store)
    # ------------------------------------------------------------------

    def store_skill(self, skill_id: str, content: str, metadata: Optional[dict] = None) -> bool:
        if not self._is_active:
            return False
        try:
            col = self._collections[self.COLLECTION_SKILLS]
            col.upsert(
                ids=[skill_id],
                documents=[content],
                metadatas=[{**(metadata or {}), "skill_id": skill_id}],
            )
            return True
        except Exception as exc:
            logger.warning("ChromaDB store_skill error: %s", exc)
            return False

    def store_profile(self, profile_id: str, content: str, metadata: Optional[dict] = None) -> bool:
        if not self._is_active:
            return False
        try:
            col = self._collections[self.COLLECTION_PROFILES]
            col.upsert(
                ids=[profile_id],
                documents=[content],
                metadatas=[{**(metadata or {}), "profile_id": profile_id}],
            )
            return True
        except Exception as exc:
            logger.warning("ChromaDB store_profile error: %s", exc)
            return False


class KnowledgeOrchestrator:
    """Routes knowledge queries to the appropriate ChromaDB collection."""

    def __init__(self, chroma_mgr: ChromaDBManager):
        self.chroma = chroma_mgr

    def enrich_context_with_history(self, current_description: str) -> str:
        """Inject summaries of similar past projects into the current context."""
        similar = self.chroma.query_similar_projects(current_description)
        if not similar:
            return ""
        snippets = []
        for item in similar[:2]:
            ctx = item.get("context", {})
            name = ctx.get("nombre_proyecto", item.get("project_id", ""))
            score = item.get("similarity", 0)
            stack = ctx.get("stack_sugerido", "")
            snippets.append(f"- '{name}' (similitud {score:.0%}, stack: {stack})")
        return "Proyectos similares en memoria:\n" + "\n".join(snippets)

    def store_completed_project(self, project_id: str, blueprint: dict, architecture: dict) -> bool:
        """Persist a completed project's context for future retrieval."""
        context = {**blueprint, "architecture_modulos": len(architecture.get("modulos", []))}
        return self.chroma.store_project_context(project_id, context)

    def query(self, description: str, role: str = "code_generator", n: int = 2) -> str:
        """
        Return a formatted string with context from past similar projects.
        Injected into task prompts via ContextBuilder to enable RAG.

        role is used to decide what level of detail to include:
          - code_generator / reviewer: module names + files
          - global_architect: full module list + stack
          - others: brief summary only
        """
        similar = self.chroma.query_similar_projects(description, n_results=n)
        if not similar:
            return ""

        parts = []
        for item in similar:
            ctx = item.get("context", {})
            sim = item.get("similarity", 0)
            if sim < 0.30:
                continue
            name = ctx.get("nombre_proyecto", item.get("project_id", "?"))
            stack = ctx.get("stack_sugerido", "")
            n_modules = ctx.get("architecture_modulos", 0)

            if role in ("code_generator", "reviewer"):
                parts.append(
                    f"• '{name}' ({sim:.0%} similar) — stack: {stack}, {n_modules} módulos"
                )
            elif role == "global_architect":
                modulos = ctx.get("modulos", [])
                mod_names = ", ".join(m.get("nombre", "") for m in modulos[:6]) if modulos else "n/a"
                parts.append(
                    f"• '{name}' ({sim:.0%}) — stack: {stack} — módulos: {mod_names}"
                )
            else:
                parts.append(f"• '{name}' ({sim:.0%} similar)")

        if not parts:
            return ""
        return "## Proyectos similares completados (memoria SODA)\n" + "\n".join(parts)
