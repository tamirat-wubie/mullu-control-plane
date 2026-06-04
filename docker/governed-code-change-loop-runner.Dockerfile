# Purpose: minimal no-network sandbox image for governed code-change loop probes.
# Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
# Dependencies: python:3.12-slim and Docker rootless/no-network runner contract.
# Invariants: the sandbox user is nonroot; /workspace is the governed workdir.

FROM python:3.12-slim

RUN useradd -m nonroot

USER nonroot
WORKDIR /workspace
