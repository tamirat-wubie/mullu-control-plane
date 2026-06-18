"""Adapters from existing Mullu runtimes into CDG-RCCM components."""

from .snet import (
    SNET_COMPONENT_PREFIX,
    SNET_SYMBOL_PROJECTION,
    SNetDependencyGatedComponent,
    SNetDependencyGatedComponentFactory,
    run_dependency_gated_snet,
)
from .universal_action import UniversalActionClosureAdapter

__all__ = [
    "SNET_COMPONENT_PREFIX",
    "SNET_SYMBOL_PROJECTION",
    "SNetDependencyGatedComponent",
    "SNetDependencyGatedComponentFactory",
    "UniversalActionClosureAdapter",
    "run_dependency_gated_snet",
]
