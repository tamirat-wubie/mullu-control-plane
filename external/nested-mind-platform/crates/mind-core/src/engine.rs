use crate::{
    hash_state, Commit, EditProposal, EventId, Identity, Judgment, Lawbook, LawbookMigration,
    LawbookTransition, Mind, MindError, MindResult, PatchOp, StatePatch, SymbolState, SymbolValue,
    TopologyEffect,
};
use time::OffsetDateTime;

pub struct EvolutionPlan {
    commit: Commit,
    next_state: SymbolState,
    next_lawbook: Option<Lawbook>,
}

impl EvolutionPlan {
    #[must_use]
    pub fn commit(&self) -> &Commit {
        &self.commit
    }

    #[must_use]
    pub fn commit_mut(&mut self) -> &mut Commit {
        &mut self.commit
    }
}

pub struct EvolutionEngine;

impl EvolutionEngine {
    pub fn evaluate(mind: &Mind, proposal: EditProposal) -> MindResult<EvolutionPlan> {
        Self::evaluate_with_effects(mind, proposal, Vec::new(), None)
    }

    pub fn evaluate_child_attachment(
        parent: &Mind,
        child_identity: Identity,
        actor: impl Into<String>,
        reason: impl Into<String>,
    ) -> MindResult<EvolutionPlan> {
        validate_child_attachment(parent, &child_identity)?;
        let patch = child_registry_patch(&child_identity);
        let proposal = EditProposal::new(parent.id(), actor, reason, patch);
        let topology = vec![TopologyEffect::AttachChild {
            identity: child_identity,
        }];
        Self::evaluate_with_effects(parent, proposal, topology, None)
    }

    pub fn evaluate_lawbook_migration(
        mind: &Mind,
        migration: LawbookMigration,
    ) -> MindResult<EvolutionPlan> {
        let transition = mind.lawbook().apply_migration(migration)?;
        let patch = lawbook_metadata_patch(&transition.after)?;
        let proposal = EditProposal::new(
            mind.id(),
            transition.migration.actor.clone(),
            transition.migration.reason.clone(),
            patch,
        );
        Self::evaluate_with_effects(mind, proposal, Vec::new(), Some(transition))
    }

    pub fn apply_plan(mind: &mut Mind, plan: EvolutionPlan) -> MindResult<Commit> {
        if plan.commit.mind_id != mind.id() {
            return Err(MindError::CommitTargetMismatch {
                commit_id: plan.commit.id,
                expected: mind.id(),
                actual: plan.commit.mind_id,
            });
        }
        if plan.commit.parent_commit != mind.latest_commit_id() {
            return Err(MindError::CommitParentMismatch {
                commit_id: plan.commit.id,
                expected: mind.latest_commit_id(),
                actual: plan.commit.parent_commit,
            });
        }
        validate_topology_effects(mind, &plan.commit.topology)?;

        let commit = plan.commit;
        mind.replace_state(plan.next_state);
        if let Some(next_lawbook) = plan.next_lawbook {
            mind.replace_lawbook(next_lawbook);
        }
        apply_topology_effects(mind, &commit.topology)?;
        mind.push_commit(commit.clone());
        Ok(commit)
    }

    pub fn evolve(mind: &mut Mind, proposal: EditProposal) -> MindResult<Commit> {
        let plan = Self::evaluate(mind, proposal)?;
        Self::apply_plan(mind, plan)
    }

    fn evaluate_with_effects(
        mind: &Mind,
        proposal: EditProposal,
        topology: Vec<TopologyEffect>,
        lawbook_transition: Option<LawbookTransition>,
    ) -> MindResult<EvolutionPlan> {
        if proposal.mind_id != mind.id() {
            return Err(MindError::WrongTarget {
                proposal: proposal.mind_id,
                mind: mind.id(),
            });
        }
        validate_topology_effects(mind, &topology)?;
        if let Some(transition) = &lawbook_transition {
            transition.verify_against(mind.lawbook())?;
        }

        let EditProposal {
            id: proposal_id,
            mind_id: _,
            actor,
            reason,
            patch,
            evidence: _,
        } = proposal;
        mind.invariants().validate_patch(mind.state(), &patch)?;

        let before_hash = hash_state(mind.state())?;
        let mut next_state = mind.state().clone();
        next_state.apply(&patch)?;
        let effective_lawbook = lawbook_transition
            .as_ref()
            .map(|transition| transition.after.clone())
            .unwrap_or_else(|| mind.lawbook().clone());
        effective_lawbook.validate_state(&next_state)?;
        let after_hash = hash_state(&next_state)?;

        let mut constructive_delta: Vec<String> = patch.ops().iter().map(render_op).collect();
        constructive_delta.extend(topology.iter().map(render_topology_effect));
        if let Some(transition) = &lawbook_transition {
            constructive_delta.push(format!(
                "migrate_lawbook {} -> {}",
                transition.migration.from_version, transition.migration.to_version
            ));
        }

        let judgment = Judgment {
            accepted: true,
            rationale:
                "Patch satisfied invariants, lawbook, topology rules, and governance effects."
                    .to_owned(),
            constructive_delta,
            fracture_delta: Vec::new(),
            law_trace: effective_lawbook.trace(),
        };

        let commit = Commit {
            id: EventId::new(),
            proposal_id,
            mind_id: mind.id(),
            parent_commit: mind.latest_commit_id(),
            actor,
            reason,
            at: OffsetDateTime::now_utc(),
            patch,
            topology,
            lawbook_transition: lawbook_transition.clone(),
            before_hash,
            after_hash,
            judgment,
            signature: None,
        };

        Ok(EvolutionPlan {
            commit,
            next_state,
            next_lawbook: lawbook_transition.map(|transition| transition.after),
        })
    }
}

fn lawbook_metadata_patch(lawbook: &Lawbook) -> MindResult<StatePatch> {
    Ok(StatePatch::new()
        .set("lawbook.id", SymbolValue::Text(lawbook.id().to_string()))
        .set(
            "lawbook.version",
            SymbolValue::Number(lawbook.version() as f64),
        )
        .set("lawbook.hash", SymbolValue::Text(lawbook.hash()?)))
}

fn child_registry_patch(identity: &Identity) -> StatePatch {
    let base = format!("children.{}", identity.id);
    StatePatch::new()
        .set(
            format!("{base}.id"),
            SymbolValue::Text(identity.id.to_string()),
        )
        .set(
            format!("{base}.kind"),
            SymbolValue::Text(identity.kind.clone()),
        )
        .set(
            format!("{base}.parent_id"),
            identity
                .parent_id
                .map(|id| SymbolValue::Text(id.to_string()))
                .unwrap_or(SymbolValue::Null),
        )
        .set(
            format!("{base}.version"),
            SymbolValue::Number(identity.version as f64),
        )
}

fn validate_topology_effects(mind: &Mind, effects: &[TopologyEffect]) -> MindResult<()> {
    let mut projected_child_count = mind.children().len();
    let mut seen_child_ids = std::collections::BTreeSet::new();
    for effect in effects {
        match effect {
            TopologyEffect::AttachChild { identity } => {
                validate_child_identity(mind, identity)?;
                if mind.children().contains_key(&identity.id) || !seen_child_ids.insert(identity.id)
                {
                    return Err(MindError::DuplicateChild(identity.id));
                }
                projected_child_count += 1;
                if projected_child_count > mind.invariants().max_children() {
                    return Err(MindError::MaxChildren {
                        max_children: mind.invariants().max_children(),
                    });
                }
            }
        }
    }
    Ok(())
}

fn validate_child_attachment(parent: &Mind, child_identity: &Identity) -> MindResult<()> {
    validate_topology_effects(
        parent,
        &[TopologyEffect::AttachChild {
            identity: child_identity.clone(),
        }],
    )
}

fn validate_child_identity(parent: &Mind, child_identity: &Identity) -> MindResult<()> {
    if child_identity.parent_id != Some(parent.id()) {
        return Err(MindError::WrongParent {
            child_parent: child_identity.parent_id,
            target_parent: parent.id(),
        });
    }
    Ok(())
}

fn apply_topology_effects(mind: &mut Mind, effects: &[TopologyEffect]) -> MindResult<()> {
    for effect in effects {
        match effect {
            TopologyEffect::AttachChild { identity } => {
                mind.add_child(Mind::from_identity(identity.clone()))?
            }
        }
    }
    Ok(())
}

fn render_op(op: &PatchOp) -> String {
    match op {
        PatchOp::Set { key, .. } => format!("set {key}"),
        PatchOp::Remove { key } => format!("remove {key}"),
    }
}

fn render_topology_effect(effect: &TopologyEffect) -> String {
    match effect {
        TopologyEffect::AttachChild { identity } => {
            format!("attach_child {} kind={}", identity.id, identity.kind)
        }
    }
}
