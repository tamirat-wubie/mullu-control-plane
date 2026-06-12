use crate::{
    hash_state, verify_record_chain, verify_record_chain_with_signatures,
    verify_record_tail_with_signatures, EventId, EventRecord, Identity, Mind, MindError, MindId,
    MindResult, SignatureRequirement, SnapshotRecord, TopologyEffect,
};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplayReport {
    pub mind_id: MindId,
    pub commit_count: usize,
    pub final_hash: String,
    pub latest_commit_id: Option<EventId>,
    pub child_count: usize,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub from_snapshot: Option<EventId>,
}

pub struct ReplayEngine;

impl ReplayEngine {
    pub fn replay(identity: Identity, records: &[EventRecord]) -> MindResult<(Mind, ReplayReport)> {
        Self::replay_with_signature_requirement(identity, records, SignatureRequirement::Optional)
    }

    pub fn replay_with_signature_requirement(
        identity: Identity,
        records: &[EventRecord],
        signature_requirement: SignatureRequirement,
    ) -> MindResult<(Mind, ReplayReport)> {
        if signature_requirement == SignatureRequirement::Optional {
            verify_record_chain(records)?;
        } else {
            verify_record_chain_with_signatures(records, signature_requirement)?;
        }

        let mut mind = Mind::from_identity(identity);
        apply_records(&mut mind, records, None)?;
        report_for(&mind, None)
    }

    pub fn replay_from_snapshot(
        snapshot: &SnapshotRecord,
        tail_records: &[EventRecord],
        signature_requirement: SignatureRequirement,
    ) -> MindResult<(Mind, ReplayReport)> {
        snapshot.verify()?;
        verify_record_tail_with_signatures(
            tail_records,
            snapshot.after_sequence + 1,
            snapshot.after_record_hash.clone(),
            signature_requirement,
        )?;

        let mut mind = snapshot.restore_mind()?;
        apply_records(&mut mind, tail_records, snapshot.latest_commit_id)?;
        report_for(&mind, Some(snapshot.snapshot_id))
    }
}

fn report_for(mind: &Mind, from_snapshot: Option<EventId>) -> MindResult<(Mind, ReplayReport)> {
    let report = ReplayReport {
        mind_id: mind.id(),
        commit_count: mind.history().len(),
        final_hash: hash_state(mind.state())?,
        latest_commit_id: mind.latest_commit_id(),
        child_count: mind.children().len(),
        from_snapshot,
    };
    Ok((mind.clone(), report))
}

fn apply_records(
    mind: &mut Mind,
    records: &[EventRecord],
    mut expected_parent_commit: Option<EventId>,
) -> MindResult<()> {
    for record in records {
        let commit = &record.commit;

        if commit.mind_id != mind.id() {
            return Err(MindError::CommitTargetMismatch {
                commit_id: commit.id,
                expected: mind.id(),
                actual: commit.mind_id,
            });
        }

        if commit.parent_commit != expected_parent_commit {
            return Err(MindError::CommitParentMismatch {
                commit_id: commit.id,
                expected: expected_parent_commit,
                actual: commit.parent_commit,
            });
        }

        let before_hash = hash_state(mind.state())?;
        if before_hash != commit.before_hash {
            return Err(MindError::CommitBeforeHashMismatch {
                commit_id: commit.id,
                expected: before_hash,
                actual: commit.before_hash.clone(),
            });
        }

        mind.invariants()
            .validate_patch(mind.state(), &commit.patch)?;
        validate_topology_effects(mind, &commit.topology)?;

        let effective_lawbook = if let Some(transition) = &commit.lawbook_transition {
            transition.verify_against(mind.lawbook())?;
            transition.after.clone()
        } else {
            mind.lawbook().clone()
        };

        let mut next_state = mind.state().clone();
        next_state.apply(&commit.patch)?;
        effective_lawbook.validate_state(&next_state)?;

        let after_hash = hash_state(&next_state)?;
        if after_hash != commit.after_hash {
            return Err(MindError::CommitAfterHashMismatch {
                commit_id: commit.id,
                expected: after_hash,
                actual: commit.after_hash.clone(),
            });
        }

        mind.replace_state(next_state);
        if commit.lawbook_transition.is_some() {
            mind.replace_lawbook(effective_lawbook);
        }
        apply_topology_effects(mind, &commit.topology)?;
        mind.push_commit(commit.clone());
        expected_parent_commit = Some(commit.id);
    }
    Ok(())
}

fn validate_topology_effects(mind: &Mind, effects: &[TopologyEffect]) -> MindResult<()> {
    let mut projected_child_count = mind.children().len();
    let mut seen_child_ids = std::collections::BTreeSet::new();

    for effect in effects {
        match effect {
            TopologyEffect::AttachChild { identity } => {
                if identity.parent_id != Some(mind.id()) {
                    return Err(MindError::WrongParent {
                        child_parent: identity.parent_id,
                        target_parent: mind.id(),
                    });
                }

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

fn apply_topology_effects(mind: &mut Mind, effects: &[TopologyEffect]) -> MindResult<()> {
    for effect in effects {
        match effect {
            TopologyEffect::AttachChild { identity } => {
                let child = Mind::from_identity(identity.clone());
                mind.add_child(child)?;
            }
        }
    }
    Ok(())
}
