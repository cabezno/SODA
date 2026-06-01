import graphlib
from typing import Dict
from kernel.core.models_v2 import SodaContract

class TopologyValidator:
    @staticmethod
    def validate_dag(contracts: Dict[str, SodaContract]) -> None:
        """
        Builds a directed graph from contract dependencies and uses 
        graphlib.TopologicalSorter to detect any cycles.
        """
        graph = {cid: set(contract.dependencies) for cid, contract in contracts.items()}
        sorter = graphlib.TopologicalSorter(graph)
        try:
            # static_order resolves the graph and throws CycleError if a cycle exists.
            list(sorter.static_order())
        except graphlib.CycleError as e:
            raise ValueError(f"Error de topología: Se detectó un ciclo circular en las dependencias. Detalles: {e}")
