use mind_core::{
    AppendOnlyEventStore, AuditEvent, AuditEventKind, EditProposal, EvolutionEngine,
    InMemoryEventStore, InMemoryRateLimiter, JsonBackupStore, Mind, MindBackup,
    RequestSafetyConfig, SignatureRequirement, SnapshotRecord, StatePatch, SymbolValue,
    TelemetryExportFormat, TelemetryExporter, TraceContext, PLATFORM_SCHEMA_VERSION,
};
use time::OffsetDateTime;

#[test]
fn backup_capture_and_verify_preserves_event_chain() {
    let mut mind = Mind::new_root("root");
    let mut store = InMemoryEventStore::new();
    let proposal = EditProposal::new(
        mind.id(),
        "test",
        "set goal",
        StatePatch::new().set("goal", SymbolValue::from("nested minds")),
    );
    let plan = EvolutionEngine::evaluate(&mind, proposal).unwrap();
    let record = store.append(plan.commit().clone()).unwrap();
    EvolutionEngine::apply_plan(&mut mind, plan).unwrap();
    let snapshot = SnapshotRecord::capture(&mind, Some(&record)).unwrap();
    let backup = MindBackup::capture(
        Some(mind.id()),
        store.records_for_mind(mind.id()).unwrap(),
        vec![snapshot],
        Vec::new(),
        vec![AuditEvent::new(AuditEventKind::BackupCreated, "created")],
        PLATFORM_SCHEMA_VERSION,
    )
    .unwrap();

    let report = backup.verify(SignatureRequirement::Optional).unwrap();
    assert!(report.valid);
    assert_eq!(report.event_count, 1);
    assert_eq!(report.snapshot_count, 1);
}

#[test]
fn json_backup_store_restores_to_new_jsonl_files() {
    let mut mind = Mind::new_root("root");
    let mut store = InMemoryEventStore::new();
    let proposal = EditProposal::new(
        mind.id(),
        "test",
        "set key",
        StatePatch::new().set("k", SymbolValue::from("v")),
    );
    let plan = EvolutionEngine::evaluate(&mind, proposal).unwrap();
    store.append(plan.commit().clone()).unwrap();
    EvolutionEngine::apply_plan(&mut mind, plan).unwrap();
    let backup = MindBackup::capture(
        Some(mind.id()),
        store.records_for_mind(mind.id()).unwrap(),
        Vec::new(),
        Vec::new(),
        Vec::new(),
        PLATFORM_SCHEMA_VERSION,
    )
    .unwrap();

    let base = std::env::temp_dir().join(format!("mind-backup-{}", mind_core::EventId::new()));
    let backup_path = base.with_extension("json");
    let events_path = base.with_extension("events.jsonl");
    let snapshots_path = base.with_extension("snapshots.jsonl");
    let backup_store = JsonBackupStore::new(backup_path.clone()).unwrap();
    backup_store.save(&backup).unwrap();
    let report = backup_store
        .restore_to_jsonl(
            &events_path,
            &snapshots_path,
            Option::<&std::path::Path>::None,
            SignatureRequirement::Optional,
            mind_core::BackupRestoreMode::NewFilesOnly,
        )
        .unwrap();

    assert!(report.valid);
    assert!(events_path.exists());
    assert!(snapshots_path.exists());
    std::fs::remove_file(backup_path).ok();
    std::fs::remove_file(events_path).ok();
    std::fs::remove_file(snapshots_path).ok();
}

#[test]
fn rate_limiter_rejects_after_configured_window_capacity() {
    let config = RequestSafetyConfig::new(1024, 2, 60);
    let mut limiter = InMemoryRateLimiter::new(config).unwrap();
    let now = OffsetDateTime::now_utc();
    assert!(limiter.check_at("actor", now).unwrap().allowed);
    assert!(limiter.check_at("actor", now).unwrap().allowed);
    assert!(!limiter.check_at("actor", now).unwrap().allowed);
    assert!(limiter.reject_if_body_too_large(Some(2048)).is_err());
}

#[test]
fn telemetry_exporter_emits_internal_and_otlp_shaped_payloads() {
    let trace = TraceContext::root("test.operation").finish_success();
    let audit = AuditEvent::new(AuditEventKind::TelemetryExported, "exported");
    let internal = TelemetryExporter::export(
        TelemetryExportFormat::InternalJson,
        vec![trace.clone()],
        vec![audit.clone()],
    )
    .unwrap();
    let otlp = TelemetryExporter::export(TelemetryExportFormat::OtlpJson, vec![trace], vec![audit])
        .unwrap();

    assert_eq!(internal.trace_count, 1);
    assert_eq!(internal.audit_count, 1);
    assert!(internal.payload.get("traces").is_some());
    assert!(otlp.payload.get("resourceSpans").is_some());
    assert!(otlp.payload.get("resourceLogs").is_some());
}
