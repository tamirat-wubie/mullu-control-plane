use mind_core::PLATFORM_SCHEMA_VERSION;
use mind_store_sqlite::SqliteEventStore;

#[test]
fn sqlite_schema_advances_to_platform_schema() {
    let store = SqliteEventStore::in_memory().unwrap();
    let report = store.schema_report().unwrap();
    assert_eq!(PLATFORM_SCHEMA_VERSION, 25);
    assert_eq!(report.current_version_after, PLATFORM_SCHEMA_VERSION);
    assert_eq!(report.target_version, PLATFORM_SCHEMA_VERSION);
}
