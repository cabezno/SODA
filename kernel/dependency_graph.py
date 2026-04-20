from dataclasses import dataclass, field
from typing import List, Dict, Set
from collections import deque


@dataclass
class ExecutionPlan:
    levels: List[List[str]]   # cada nivel es un grupo ejecutable en paralelo
    order: List[str]          # orden plano (topológico)
    parallelizable: bool      # True si algún nivel tiene >1 módulo


class DependencyGraph:
    """
    Construye un DAG de módulos desde la arquitectura y calcula
    el orden de ejecución óptimo (secuencial o paralelo por niveles).
    Python puro — sin IA.
    """

    def __init__(self, modulos: List[dict]):
        # nombre → lista de dependencias
        self.graph: Dict[str, List[str]] = {}
        # nombre → set de módulos que dependen de él (grafo inverso)
        self.reverse: Dict[str, Set[str]] = {}

        for m in modulos:
            nombre = m["nombre"]
            deps = [d for d in m.get("dependencias", []) if d in {x["nombre"] for x in modulos}]
            self.graph[nombre] = deps
            if nombre not in self.reverse:
                self.reverse[nombre] = set()
            for dep in deps:
                if dep not in self.reverse:
                    self.reverse[dep] = set()
                self.reverse[dep].add(nombre)

    def detect_cycles(self) -> List[str]:
        """Devuelve lista de nodos en ciclo, vacía si no hay ciclos."""
        visited: Set[str] = set()
        in_stack: Set[str] = set()
        cycle_nodes: List[str] = []

        def dfs(node: str) -> bool:
            visited.add(node)
            in_stack.add(node)
            for neighbor in self.graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in in_stack:
                    cycle_nodes.append(neighbor)
                    return True
            in_stack.discard(node)
            return False

        for node in self.graph:
            if node not in visited:
                dfs(node)

        return cycle_nodes

    def build_execution_plan(self) -> ExecutionPlan:
        """
        Algoritmo de Kahn con agrupación por niveles.
        Módulos del mismo nivel no tienen dependencias entre sí → paralelizables.
        """
        cycles = self.detect_cycles()
        if cycles:
            raise ValueError(f"Ciclo detectado en el grafo de dependencias: {cycles}")

        # In-degree por nodo
        in_degree: Dict[str, int] = {node: len(deps) for node, deps in self.graph.items()}
        queue = deque([n for n, d in in_degree.items() if d == 0])
        levels: List[List[str]] = []
        order: List[str] = []

        while queue:
            # Todos los nodos con in_degree=0 en este momento forman un nivel paralelo
            level = list(queue)
            queue.clear()
            levels.append(level)
            order.extend(level)

            for node in level:
                for dependent in self.reverse.get(node, set()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(order) != len(self.graph):
            raise ValueError("El grafo tiene ciclos no detectados por DFS (verificar consistencia).")

        return ExecutionPlan(
            levels=levels,
            order=order,
            parallelizable=any(len(lvl) > 1 for lvl in levels),
        )

    def summary(self) -> str:
        plan = self.build_execution_plan()
        lines = ["Plan de ejecución:"]
        for i, level in enumerate(plan.levels):
            tag = f"[paralelo x{len(level)}]" if len(level) > 1 else "[secuencial]"
            lines.append(f"  Nivel {i}: {tag} {' | '.join(level)}")
        return "\n".join(lines)
