"""Governed Financial Operations Layer.

Domain pack with its own invariants, permissions, providers,
state machines, and proofs. Every financial action flows through:
classification → RBAC → spend budget → policy → approval →
idempotency → state machine → provider → settlement → ledger → proof.
"""
