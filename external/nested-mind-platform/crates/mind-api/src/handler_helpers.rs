//! Purpose: handler-local helper boundary for the Nested Mind API.
//! Governance scope: handler support functions for bounded result tails, actor resolution, and governed plan signing.
//! Dependencies: mind-core principal, authorization, identity, signing, and evolution plan contracts.
//! Invariants: helper functions remain deterministic; privilege escalation for requested actors stays explicit.

use super::*;

pub(super) fn limit_tail<T>(values: Vec<T>, limit: Option<usize>) -> Vec<T> {
    let Some(limit) = limit else {
        return values;
    };
    if values.len() <= limit {
        return values;
    }
    let skip = values.len() - limit;
    values.into_iter().skip(skip).collect()
}

pub(super) fn sign_plan_if_configured(
    plan: &mut EvolutionPlan,
    signer: Option<&Arc<Ed25519CommitSigner>>,
) -> Result<(), MindError> {
    if let Some(signer) = signer {
        plan.commit_mut().sign_with(signer.as_ref())?;
    }
    Ok(())
}
pub(super) fn resolve_actor(
    principal: &Principal,
    requested_actor: Option<String>,
    authz: &AuthorizationPolicy,
    mind_id: MindId,
) -> Result<String, MindError> {
    let Some(actor) = requested_actor else {
        return Ok(principal.id.clone());
    };
    if actor == principal.id {
        return Ok(actor);
    }
    authz.require(Some(principal), mind_id, &MindAction::Administer)?;
    Ok(actor)
}
