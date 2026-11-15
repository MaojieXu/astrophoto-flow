"""The workbench controller package.

Public entry points stay in the CLI and the HTTP app; this module exports only
the identity helpers other components import.
"""

from .contracts.lifecycle import ProductIdentity, ReadyResult
from .core.workspace import load_product_identity

__all__ = ["ProductIdentity", "ReadyResult", "load_product_identity"]
