"""Adapters that wire intent_substrate primitives to specific mcoi engines.

Each adapter exposes a thin, opinionated mapping from substrate
abstractions (StateView, IntentClosure) to a particular state-bearing
engine. Add a new adapter here when you want substrate predicates to
observe (or substrate closures to act on) a new engine without
modifying that engine's source.

Available:
  service_catalog
    ServiceCatalogStateView — exposes ServiceCatalogEngine tasks and
    requests as queryable entities for predicate evaluation (observation).
    RequestStatusClosureAdapter — opt-in IntentClosure that drives a
    ServiceCatalogEngine request to FULFILLED on success / CANCELLED on
    precondition failure (action).
"""
