use crate::{EventId, MindError, MindId, MindResult, SnapshotRecord, SnapshotStore};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SnapshotCompactionPolicy {
    pub keep_latest: usize,
    pub min_events_between_snapshots: u64,
}

impl SnapshotCompactionPolicy {
    #[must_use]
    pub fn new(keep_latest: usize, min_events_between_snapshots: u64) -> Self {
        Self {
            keep_latest,
            min_events_between_snapshots,
        }
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.keep_latest == 0 {
            return Err(MindError::SnapshotCompactionPolicyInvalid(
                "keep_latest must be at least 1".to_owned(),
            ));
        }
        Ok(())
    }

    pub fn evaluate(
        &self,
        mind_id: MindId,
        latest_event_sequence: u64,
        snapshots: &[SnapshotRecord],
    ) -> MindResult<SnapshotCompactionDecision> {
        self.validate()?;
        for snapshot in snapshots {
            snapshot.verify()?;
        }

        let mut ordered: Vec<SnapshotRecord> = snapshots
            .iter()
            .filter(|snapshot| snapshot.mind_id == mind_id)
            .cloned()
            .collect();
        ordered.sort_by_key(|snapshot| (snapshot.after_sequence, snapshot.snapshot_id));

        let newest_snapshot_sequence = ordered.last().map(|snapshot| snapshot.after_sequence);
        let should_create_snapshot = newest_snapshot_sequence.map_or(
            latest_event_sequence >= self.min_events_between_snapshots,
            |sequence| {
                latest_event_sequence.saturating_sub(sequence) >= self.min_events_between_snapshots
            },
        );

        let keep_count = self.keep_latest.min(ordered.len());
        let keep_snapshot_ids: BTreeSet<EventId> = ordered
            .iter()
            .rev()
            .take(keep_count)
            .map(|snapshot| snapshot.snapshot_id)
            .collect();
        let remove_snapshot_ids: Vec<EventId> = ordered
            .iter()
            .filter(|snapshot| !keep_snapshot_ids.contains(&snapshot.snapshot_id))
            .map(|snapshot| snapshot.snapshot_id)
            .collect();
        let keep_snapshot_ids = keep_snapshot_ids.into_iter().collect::<Vec<_>>();

        let mut reasons = Vec::new();
        reasons.push(format!("keep_latest={}", self.keep_latest));
        reasons.push(format!(
            "min_events_between_snapshots={}",
            self.min_events_between_snapshots
        ));
        if should_create_snapshot {
            reasons.push("snapshot_due=true".to_owned());
        } else {
            reasons.push("snapshot_due=false".to_owned());
        }
        if !remove_snapshot_ids.is_empty() {
            reasons.push(format!(
                "remove_older_snapshots={}",
                remove_snapshot_ids.len()
            ));
        }

        Ok(SnapshotCompactionDecision {
            mind_id,
            latest_event_sequence,
            newest_snapshot_sequence,
            should_create_snapshot,
            keep_snapshot_ids,
            remove_snapshot_ids,
            reasons,
        })
    }
}

impl Default for SnapshotCompactionPolicy {
    fn default() -> Self {
        Self {
            keep_latest: 3,
            min_events_between_snapshots: 25,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SnapshotCompactionDecision {
    pub mind_id: MindId,
    pub latest_event_sequence: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub newest_snapshot_sequence: Option<u64>,
    pub should_create_snapshot: bool,
    #[serde(default)]
    pub keep_snapshot_ids: Vec<EventId>,
    #[serde(default)]
    pub remove_snapshot_ids: Vec<EventId>,
    #[serde(default)]
    pub reasons: Vec<String>,
}

pub trait CompactingSnapshotStore: SnapshotStore {
    fn delete_snapshot(&mut self, mind_id: MindId, snapshot_id: EventId) -> MindResult<bool>;

    fn compact_snapshots(
        &mut self,
        mind_id: MindId,
        policy: &SnapshotCompactionPolicy,
        latest_event_sequence: u64,
    ) -> MindResult<SnapshotCompactionDecision> {
        let snapshots = self.snapshots_for_mind(mind_id)?;
        let decision = policy.evaluate(mind_id, latest_event_sequence, &snapshots)?;
        for snapshot_id in &decision.remove_snapshot_ids {
            self.delete_snapshot(mind_id, *snapshot_id)?;
        }
        Ok(decision)
    }
}

impl CompactingSnapshotStore for crate::InMemorySnapshotStore {
    fn delete_snapshot(&mut self, mind_id: MindId, snapshot_id: EventId) -> MindResult<bool> {
        let before = self.snapshots.len();
        self.snapshots.retain(|snapshot| {
            !(snapshot.mind_id == mind_id && snapshot.snapshot_id == snapshot_id)
        });
        Ok(before != self.snapshots.len())
    }
}

impl CompactingSnapshotStore for crate::JsonlSnapshotStore {
    fn delete_snapshot(&mut self, mind_id: MindId, snapshot_id: EventId) -> MindResult<bool> {
        let mut snapshots = self.read_all_snapshots()?;
        let before = snapshots.len();
        snapshots.retain(|snapshot| {
            !(snapshot.mind_id == mind_id && snapshot.snapshot_id == snapshot_id)
        });
        let removed = before != snapshots.len();
        if removed {
            self.rewrite_all_snapshots(&snapshots)?;
        }
        Ok(removed)
    }
}
