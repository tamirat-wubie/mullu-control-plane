use mind_core::{
    AuditEvent, AuditEventKind, BackupManifest, EventId, ObservabilitySink, SignatureRequirement,
};
use mind_store_sqlite::SqliteEventStore;
use time::OffsetDateTime;

#[test]
fn sqlite_observability_sink_persists_audit_events() {
    let mut store = SqliteEventStore::in_memory()
        .unwrap()
        .with_signature_requirement(SignatureRequirement::Optional);
    store
        .record_audit(AuditEvent::new(AuditEventKind::BackupVerified, "verified"))
        .unwrap();
    let events = store.audit_events().unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].kind, AuditEventKind::BackupVerified);
}

#[test]
fn sqlite_store_records_backup_manifests() {
    let mut store = SqliteEventStore::in_memory()
        .unwrap()
        .with_signature_requirement(SignatureRequirement::Optional);
    let manifest = BackupManifest {
        backup_id: EventId::new(),
        mind_id: None,
        created_at: OffsetDateTime::now_utc(),
        platform_schema_version: mind_core::PLATFORM_SCHEMA_VERSION,
        event_count: 0,
        snapshot_count: 0,
        trace_count: 0,
        audit_count: 0,
        latest_event_sequence: None,
        latest_event_hash: None,
        latest_snapshot_hash: None,
        backup_hash: "hash-placeholder".to_owned(),
    };
    store.record_backup_manifest(&manifest).unwrap();
    let manifests = store.backup_manifests().unwrap();
    assert_eq!(manifests.len(), 1);
    assert_eq!(manifests[0].backup_hash, "hash-placeholder");
}

#[test]
fn sqlite_store_records_backup_object_receipts() {
    let mut store = SqliteEventStore::in_memory()
        .unwrap()
        .with_signature_requirement(SignatureRequirement::Optional);
    let backup_id = EventId::new();
    let receipt = mind_core::BackupObjectReceipt {
        receipt_id: EventId::new(),
        backup_id,
        mind_id: None,
        manifest_hash: "manifest-hash".to_owned(),
        location: mind_core::RawObjectStorageLocation {
            backend: mind_core::ObjectStorageBackend::LocalFilesystem,
            bucket: "mind-backups".to_owned(),
            key: "root/backup.json".to_owned(),
            uri: "file://object-store/mind-backups/root/backup.json".to_owned(),
            bytes: 128,
            sha256_hex: "content-hash".to_owned(),
            etag: None,
            written_at: OffsetDateTime::now_utc(),
        },
        verification: mind_core::BackupVerificationReport {
            backup_id,
            mind_id: None,
            valid: true,
            event_count: 0,
            snapshot_count: 0,
            trace_count: 0,
            audit_count: 0,
            latest_event_sequence: None,
            latest_event_hash: None,
            backup_hash: "backup-hash".to_owned(),
        },
    };
    store.record_backup_object_receipt(&receipt).unwrap();
    let receipts = store.backup_object_receipts().unwrap();
    assert_eq!(receipts.len(), 1);
    assert_eq!(receipts[0].backup_id, backup_id);
}
