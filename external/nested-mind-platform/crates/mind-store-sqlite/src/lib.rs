use mind_core::{
    validate_commit_for_append, verify_record_tail_with_signatures, ActionPromotionGateReport,
    AppendOnlyEventStore, AppliedSchemaMigration, AuditEvent, BackupManifest, BackupObjectReceipt,
    BranchProtectionEvaluationReport, BranchProtectionPolicy, BranchProtectionReconcilePlan,
    BranchProtectionReconcileReceipt, BranchProtectionWorkerPlan, BranchProtectionWorkerReport,
    ChaosExecutionRun, ChaosRehearsalPlan, CloudObjectBackupPlan, CloudSignedUrlReceipt,
    CloudUploadReceipt, Commit, CompactingSnapshotStore, ConnectorOrchestrationPlan,
    ConnectorOrchestrationReport, ConnectorWorkerExecutionReceipt, ConnectorWorkerJobPlan,
    ConsensusApplyIdempotencyDecision, ConsensusApplyReport, ConsensusChangeJudgment,
    ConsensusCommitCertificate, ConsensusLogCompactionDecision, ConsensusMembership,
    ConsensusPhysicalCompactionPlan, ConsensusPhysicalCompactionReport,
    ConsensusRetentionApprovalCertificate, ConsensusRetentionApprovalProposal,
    ConsensusRetentionApprovalVote, ConsensusRetentionEnforcementPlan,
    ConsensusRetentionEnforcementReport, CreativeEngineeringReport, DistributedLeaseAdapterReport,
    DistributedLeaseClaimReceipt, DistributedLeaseExecutionReceipt, DomainJobExecutionReport,
    EngineeringImplementationJobPlan, EventId, EventRecord, GitHubActionExecutionPlan,
    GitHubActionExecutionReceipt, GitHubAppInstallationTokenPlan,
    GitHubAppInstallationTokenReceipt, GitHubAppJwtPlan, GitHubAppJwtReceipt,
    GitHubCheckRunWritePlan, GitHubCheckRunWriteReceipt, GitHubReadinessEvidenceBundle,
    GitHubTokenExchangeWorkerPlan, GitHubTokenExchangeWorkerReceipt,
    ImplementationEvidenceAutomationPlan, ImplementationJobEvidenceBundle,
    InvariantFuzzExecutionReport, InvariantFuzzRunReport, JobExecutionReceipt,
    KubernetesAdmissionAuditReceipt, KubernetesAdmissionAuditReport,
    KubernetesAdmissionAuditRequest, KubernetesAuditLogCollectorPlan,
    KubernetesAuditLogCollectorReport, KubernetesAuditSourceAdapterPlan,
    KubernetesAuditSourceAdapterReceipt, KubernetesDryRunExecutionReceipt,
    KubernetesDryRunExecutionRequest, KubernetesStagingChaosPlan, KubernetesStagingChaosReceipt,
    LiveDomainJobExecutionReport, LiveOidcRefreshReport, LiveSecretConnectorPlan,
    LiveSecretConnectorReceipt, LiveStagingChaosAdapterPlan, LiveStagingChaosAdapterReceipt,
    ManagedSigningRequest, MandatoryCiGateReport, MindError, MindId, MindResult,
    MultiOperatorWaiverCertificate, NativeProviderAdapterReport, NativeProviderExecutionReceipt,
    NotificationDeliveryClientPlan, NotificationDeliveryClientReceipt,
    NotificationProviderDeliveryPlan, NotificationProviderDeliveryReceipt, ObservabilityEvent,
    ObservabilitySink, OidcJwksCacheEntry, ProductionReadinessGateReport, ProviderExecutionReceipt,
    ProviderSdkExecutionReport, ProviderSdkFeatureMatrix, ProviderSdkReceipt,
    ReadinessWaiverApplicationReport, ReadinessWaiverCertificate, ReadinessWaiverProposal,
    ReadinessWaiverVote, ReplicatedEventStore, ReplicationAck, ReplicationBatch,
    ReplicationDeliveryReceipt, ReplicationEnvelope, ScheduledJob, ScheduledJobStatus,
    SchedulerLeaseClaimReport, SchedulerLeasePolicy, SchedulerLeaseRecord, SchemaMigration,
    SchemaMigrationReport, SecretAccessPlan, SecretAccessReceipt, SignatureRequirement,
    SnapshotRecord, SnapshotStore, StagingChaosRunReport, VendorSigningReceipt,
    WaiverEscalationCertificate, WaiverNotificationAdapterPlan, WaiverNotificationAdapterReceipt,
    WaiverNotificationPlan, WaiverNotificationReceipt, WaiverReviewCertificate,
    WaiverReviewerAssignmentPlan, WorkerDaemonTickReport, WorkerRunReport, PLATFORM_SCHEMA_VERSION,
};
use rusqlite::{params, Connection, OptionalExtension};
use std::path::Path;

pub struct SqliteEventStore {
    connection: Connection,
    signature_requirement: SignatureRequirement,
}

impl SqliteEventStore {
    pub fn open(path: impl AsRef<Path>) -> MindResult<Self> {
        let connection = Connection::open(path).map_err(sqlite_error)?;
        let mut store = Self {
            connection,
            signature_requirement: SignatureRequirement::Required,
        };
        store.initialize_schema()?;
        Ok(store)
    }

    pub fn in_memory() -> MindResult<Self> {
        let connection = Connection::open_in_memory().map_err(sqlite_error)?;
        let mut store = Self {
            connection,
            signature_requirement: SignatureRequirement::Required,
        };
        store.initialize_schema()?;
        Ok(store)
    }

    #[must_use]
    pub fn with_signature_requirement(mut self, requirement: SignatureRequirement) -> Self {
        self.signature_requirement = requirement;
        self
    }

    fn initialize_schema(&mut self) -> MindResult<()> {
        self.connection
            .execute_batch(
                r#"
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = FULL;
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        "#,
            )
            .map_err(sqlite_error)?;
        self.run_pending_schema_migrations().map(|_| ())
    }

    pub fn run_pending_schema_migrations(&mut self) -> MindResult<SchemaMigrationReport> {
        let before = self.current_schema_version()?;
        let migrations = sqlite_schema_migrations()?;
        let target = migrations
            .last()
            .map_or(before, |migration| migration.version);
        let mut current = before;
        let mut applied = Vec::new();

        for migration in migrations {
            migration.verify_checksum()?;
            if let Some(applied_checksum) = self.applied_checksum_for_version(migration.version)? {
                if applied_checksum != migration.checksum {
                    return Err(MindError::SchemaMigrationConflict {
                        version: migration.version,
                        applied_checksum,
                        expected_checksum: migration.checksum,
                    });
                }
                current = current.max(migration.version);
                continue;
            }
            if migration.version != current + 1 {
                return Err(MindError::SchemaMigrationGap {
                    expected: current + 1,
                    actual: migration.version,
                });
            }

            let tx = self.connection.transaction().map_err(sqlite_error)?;
            for statement in &migration.statements {
                tx.execute_batch(statement).map_err(sqlite_error)?;
            }
            tx.execute(
                "INSERT INTO schema_migrations (version, name, checksum) VALUES (?1, ?2, ?3)",
                params![
                    migration.version as i64,
                    &migration.name,
                    &migration.checksum
                ],
            )
            .map_err(sqlite_error)?;
            tx.commit().map_err(sqlite_error)?;
            applied.push(AppliedSchemaMigration::from_migration(&migration));
            current = migration.version;
        }

        Ok(SchemaMigrationReport::new(before, current, target, applied))
    }

    pub fn schema_report(&self) -> MindResult<SchemaMigrationReport> {
        let current = self.current_schema_version()?;
        Ok(SchemaMigrationReport::new(
            current,
            current,
            PLATFORM_SCHEMA_VERSION,
            Vec::new(),
        ))
    }

    pub fn current_schema_version(&self) -> MindResult<u64> {
        let version: Option<i64> = self
            .connection
            .query_row("SELECT MAX(version) FROM schema_migrations", [], |row| {
                row.get::<_, Option<i64>>(0)
            })
            .map_err(sqlite_error)?;
        Ok(version.map_or(0, |value| value as u64))
    }

    fn applied_checksum_for_version(&self, version: u64) -> MindResult<Option<String>> {
        self.connection
            .query_row(
                "SELECT checksum FROM schema_migrations WHERE version = ?1",
                params![version as i64],
                |row| row.get::<_, String>(0),
            )
            .optional()
            .map_err(sqlite_error)
    }

    fn read_records(
        &self,
        sql: &str,
        args: &[&dyn rusqlite::ToSql],
    ) -> MindResult<Vec<EventRecord>> {
        let mut statement = self.connection.prepare(sql).map_err(sqlite_error)?;
        let rows = statement
            .query_map(args, |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut records = Vec::new();
        for row in rows {
            records.push(serde_json::from_str::<EventRecord>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(records)
    }

    fn read_snapshots(
        &self,
        sql: &str,
        args: &[&dyn rusqlite::ToSql],
    ) -> MindResult<Vec<SnapshotRecord>> {
        let mut statement = self.connection.prepare(sql).map_err(sqlite_error)?;
        let rows = statement
            .query_map(args, |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut snapshots = Vec::new();
        for row in rows {
            let snapshot = serde_json::from_str::<SnapshotRecord>(&row.map_err(sqlite_error)?)?;
            snapshot.verify()?;
            snapshots.push(snapshot);
        }
        Ok(snapshots)
    }

    pub fn record_backup_manifest(&mut self, manifest: &BackupManifest) -> MindResult<()> {
        let mind_id = manifest.mind_id.map(|id| id.to_string());
        let manifest_json = serde_json::to_string(manifest)?;
        self.connection
            .execute(
                r#"
            INSERT OR REPLACE INTO backup_manifests (backup_id, mind_id, backup_hash, manifest_json)
            VALUES (?1, ?2, ?3, ?4)
        "#,
                params![
                    manifest.backup_id.to_string(),
                    mind_id.as_deref(),
                    &manifest.backup_hash,
                    &manifest_json,
                ],
            )
            .map_err(sqlite_error)?;
        Ok(())
    }

    pub fn backup_manifests(&self) -> MindResult<Vec<BackupManifest>> {
        let mut statement = self
            .connection
            .prepare("SELECT manifest_json FROM backup_manifests ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut manifests = Vec::new();
        for row in rows {
            manifests.push(serde_json::from_str::<BackupManifest>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(manifests)
    }

    pub fn record_backup_object_receipt(
        &mut self,
        receipt: &BackupObjectReceipt,
    ) -> MindResult<()> {
        let target_id = format!("{}/{}", receipt.location.bucket, receipt.location.key);
        let receipt_json = serde_json::to_string(receipt)?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO backup_object_receipts (receipt_id, backup_id, target_id, backup_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            receipt.receipt_id.to_string(),
            receipt.backup_id.to_string(),
            target_id,
            &receipt.verification.backup_hash,
            &receipt_json,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn backup_object_receipts(&self) -> MindResult<Vec<BackupObjectReceipt>> {
        let mut statement = self
            .connection
            .prepare("SELECT receipt_json FROM backup_object_receipts ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<BackupObjectReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_managed_signing_request(
        &mut self,
        request: &ManagedSigningRequest,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO managed_signing_requests (request_id, commit_id, provider, key_id, payload_hash, request_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            request.request_id.to_string(),
            request.commit_id.to_string(),
            format!("{:?}", request.key.provider),
            &request.key.key_id,
            &request.payload_hash,
            serde_json::to_string(request)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn managed_signing_requests(&self) -> MindResult<Vec<ManagedSigningRequest>> {
        let mut statement = self
            .connection
            .prepare("SELECT request_json FROM managed_signing_requests ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut requests = Vec::new();
        for row in rows {
            requests.push(serde_json::from_str::<ManagedSigningRequest>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(requests)
    }

    pub fn record_cloud_object_backup_plan(
        &mut self,
        plan: &CloudObjectBackupPlan,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO cloud_object_backup_plans (plan_id, backup_id, provider, bucket, object_key, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            plan.put_request.request_id.to_string(),
            plan.backup_id.to_string(),
            format!("{:?}", plan.target.provider),
            &plan.target.bucket,
            &plan.put_request.key,
            serde_json::to_string(plan)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn cloud_object_backup_plans(&self) -> MindResult<Vec<CloudObjectBackupPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM cloud_object_backup_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            plans.push(serde_json::from_str::<CloudObjectBackupPlan>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(plans)
    }

    pub fn record_replication_batch(&mut self, batch: &ReplicationBatch) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO replication_batches (batch_id, leader_id, mind_id, from_sequence, batch_hash, batch_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            batch.batch_id.to_string(),
            &batch.term.leader_id,
            batch.mind_id.to_string(),
            batch.from_sequence as i64,
            &batch.batch_hash,
            serde_json::to_string(batch)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn replication_batches(&self) -> MindResult<Vec<ReplicationBatch>> {
        let mut statement = self
            .connection
            .prepare("SELECT batch_json FROM replication_batches ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut batches = Vec::new();
        for row in rows {
            batches.push(serde_json::from_str::<ReplicationBatch>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(batches)
    }

    pub fn record_replication_ack(&mut self, ack: &ReplicationAck) -> MindResult<()> {
        self.connection
            .execute(
                r#"
            INSERT INTO replication_acks (ack_id, batch_id, follower_id, accepted, ack_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#,
                params![
                    EventId::new().to_string(),
                    ack.batch_id.to_string(),
                    &ack.follower_id,
                    if ack.accepted { 1_i64 } else { 0_i64 },
                    serde_json::to_string(ack)?,
                ],
            )
            .map_err(sqlite_error)?;
        Ok(())
    }

    pub fn replication_acks(&self) -> MindResult<Vec<ReplicationAck>> {
        let mut statement = self
            .connection
            .prepare("SELECT ack_json FROM replication_acks ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut acks = Vec::new();
        for row in rows {
            acks.push(serde_json::from_str::<ReplicationAck>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(acks)
    }

    pub fn record_oidc_jwks_cache(&mut self, cache: &OidcJwksCacheEntry) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO oidc_jwks_cache (issuer, jwks_uri, jwks_hash, key_count, cache_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            &cache.issuer,
            &cache.jwks_uri,
            &cache.jwks_hash,
            cache.key_count as i64,
            serde_json::to_string(cache)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn oidc_jwks_caches(&self) -> MindResult<Vec<OidcJwksCacheEntry>> {
        let mut statement = self
            .connection
            .prepare("SELECT cache_json FROM oidc_jwks_cache ORDER BY cached_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut entries = Vec::new();
        for row in rows {
            entries.push(serde_json::from_str::<OidcJwksCacheEntry>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(entries)
    }

    pub fn record_live_oidc_refresh(&mut self, report: &LiveOidcRefreshReport) -> MindResult<()> {
        self.connection
            .execute(
                r#"
            INSERT OR REPLACE INTO live_oidc_refreshes (refresh_id, issuer, jwks_hash, report_json)
            VALUES (?1, ?2, ?3, ?4)
        "#,
                params![
                    report.refresh_id.to_string(),
                    &report.request.issuer,
                    &report.jwks_hash,
                    serde_json::to_string(report)?,
                ],
            )
            .map_err(sqlite_error)?;
        Ok(())
    }

    pub fn live_oidc_refreshes(&self) -> MindResult<Vec<LiveOidcRefreshReport>> {
        let mut statement = self
            .connection
            .prepare("SELECT report_json FROM live_oidc_refreshes ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<LiveOidcRefreshReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_vendor_signing_receipt(
        &mut self,
        receipt: &VendorSigningReceipt,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO signing_execution_receipts (receipt_id, request_id, provider, key_id, payload_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            receipt.execution_id.to_string(),
            receipt.request_id.to_string(),
            format!("{:?}", receipt.provider),
            &receipt.key_id,
            &receipt.payload_hash,
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn vendor_signing_receipts(&self) -> MindResult<Vec<VendorSigningReceipt>> {
        let mut statement = self
            .connection
            .prepare("SELECT receipt_json FROM signing_execution_receipts ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<VendorSigningReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_cloud_upload_receipt(&mut self, receipt: &CloudUploadReceipt) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO cloud_transfer_receipts (receipt_id, provider, bucket, object_key, body_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            receipt.receipt_id.to_string(),
            format!("{:?}", receipt.provider),
            &receipt.bucket,
            &receipt.key,
            &receipt.body_sha256_hex,
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn cloud_upload_receipts(&self) -> MindResult<Vec<CloudUploadReceipt>> {
        let mut statement = self
            .connection
            .prepare("SELECT receipt_json FROM cloud_transfer_receipts ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<CloudUploadReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_cloud_signed_url_receipt(
        &mut self,
        receipt: &CloudSignedUrlReceipt,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO cloud_signed_url_receipts (receipt_id, provider, bucket, object_key, body_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            receipt.receipt_id.to_string(),
            format!("{:?}", receipt.provider),
            &receipt.bucket,
            &receipt.key,
            &receipt.observed_body_sha256_hex,
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn cloud_signed_url_receipts(&self) -> MindResult<Vec<CloudSignedUrlReceipt>> {
        let mut statement = self
            .connection
            .prepare("SELECT receipt_json FROM cloud_signed_url_receipts ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<CloudSignedUrlReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_replication_envelope(
        &mut self,
        envelope: &ReplicationEnvelope,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO replication_inbox (envelope_id, batch_id, mind_id, from_sequence, body_hash, envelope_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            envelope.envelope_id.to_string(),
            envelope.batch.batch_id.to_string(),
            envelope.batch.mind_id.to_string(),
            envelope.batch.from_sequence as i64,
            &envelope.body_hash,
            serde_json::to_string(envelope)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn replication_envelopes(&self) -> MindResult<Vec<ReplicationEnvelope>> {
        let mut statement = self
            .connection
            .prepare("SELECT envelope_json FROM replication_inbox ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut envelopes = Vec::new();
        for row in rows {
            let envelope =
                serde_json::from_str::<ReplicationEnvelope>(&row.map_err(sqlite_error)?)?;
            envelope.verify()?;
            envelopes.push(envelope);
        }
        Ok(envelopes)
    }

    pub fn record_replication_delivery_receipt(
        &mut self,
        receipt: &ReplicationDeliveryReceipt,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO replication_delivery_receipts (delivery_id, envelope_id, endpoint_node_id, status, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            receipt.delivery_id.to_string(),
            receipt.envelope_id.to_string(),
            &receipt.endpoint_node_id,
            format!("{:?}", receipt.status),
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn replication_delivery_receipts(&self) -> MindResult<Vec<ReplicationDeliveryReceipt>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT receipt_json FROM replication_delivery_receipts ORDER BY created_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<ReplicationDeliveryReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_consensus_membership(
        &mut self,
        membership: &ConsensusMembership,
    ) -> MindResult<()> {
        membership.validate()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_memberships (configuration_id, cluster_id, term, leader_id, membership_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            membership.configuration_id.to_string(),
            &membership.cluster_id,
            membership.term as i64,
            membership.leader_id.as_deref(),
            serde_json::to_string(membership)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn record_consensus_change_judgment(
        &mut self,
        judgment: &ConsensusChangeJudgment,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_change_judgments (proposal_id, cluster_id, accepted, before_configuration_id, after_configuration_id, judgment_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            judgment.proposal_id.to_string(),
            &judgment.cluster_id,
            if judgment.accepted { 1_i64 } else { 0_i64 },
            judgment.before_configuration_id.to_string(),
            judgment.after_configuration_id.to_string(),
            serde_json::to_string(judgment)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn consensus_change_judgments(&self) -> MindResult<Vec<ConsensusChangeJudgment>> {
        let mut statement = self
            .connection
            .prepare("SELECT judgment_json FROM consensus_change_judgments ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut judgments = Vec::new();
        for row in rows {
            judgments.push(serde_json::from_str::<ConsensusChangeJudgment>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(judgments)
    }

    pub fn record_scheduled_job(&mut self, job: &ScheduledJob) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO scheduled_jobs (job_id, kind, target, status, due_at, not_before, attempt_count, idempotency_key, payload_hash, job_json, updated_at)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, datetime('now'))
        "#, params![
            job.job_id.to_string(),
            format!("{:?}", job.kind),
            &job.target,
            format!("{:?}", job.status),
            job.due_at.to_string(),
            job.not_before.to_string(),
            job.attempt_count as i64,
            &job.idempotency_key,
            &job.payload_hash,
            serde_json::to_string(job)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn scheduled_jobs(&self) -> MindResult<Vec<ScheduledJob>> {
        let mut statement = self
            .connection
            .prepare("SELECT job_json FROM scheduled_jobs ORDER BY due_at ASC, created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut jobs = Vec::new();
        for row in rows {
            jobs.push(serde_json::from_str::<ScheduledJob>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(jobs)
    }

    pub fn record_provider_execution_receipt(
        &mut self,
        receipt: &ProviderExecutionReceipt,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO provider_execution_receipts (receipt_id, execution_id, adapter, command_kind, target, status, payload_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![
            receipt.receipt_id.to_string(),
            receipt.execution_id.to_string(),
            format!("{:?}", receipt.adapter),
            format!("{:?}", receipt.command_kind),
            &receipt.target,
            format!("{:?}", receipt.status),
            &receipt.expected_payload_hash,
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn provider_execution_receipts(&self) -> MindResult<Vec<ProviderExecutionReceipt>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT receipt_json FROM provider_execution_receipts ORDER BY completed_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<ProviderExecutionReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_consensus_commit_certificate(
        &mut self,
        certificate: &ConsensusCommitCertificate,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_commit_certificates (certificate_id, entry_id, cluster_id, term, committed, entry_hash, certificate_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            certificate.certificate_id.to_string(),
            certificate.entry.entry_id.to_string(),
            &certificate.entry.cluster_id,
            certificate.entry.term as i64,
            if certificate.committed { 1_i64 } else { 0_i64 },
            &certificate.entry.entry_hash,
            serde_json::to_string(certificate)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn consensus_commit_certificates(&self) -> MindResult<Vec<ConsensusCommitCertificate>> {
        let mut statement = self.connection.prepare("SELECT certificate_json FROM consensus_commit_certificates ORDER BY certified_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut certificates = Vec::new();
        for row in rows {
            certificates.push(serde_json::from_str::<ConsensusCommitCertificate>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(certificates)
    }

    pub fn record_scheduler_lease(&mut self, lease: &SchedulerLeaseRecord) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO scheduler_leases (lease_id, job_id, worker_id, status, lease_expires_at, lease_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            lease.lease_id.to_string(),
            lease.job_id.to_string(),
            &lease.worker_id,
            format!("{:?}", lease.status),
            lease.lease_expires_at.to_string(),
            serde_json::to_string(lease)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn scheduler_leases(&self) -> MindResult<Vec<SchedulerLeaseRecord>> {
        let mut statement = self
            .connection
            .prepare("SELECT lease_json FROM scheduler_leases ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut leases = Vec::new();
        for row in rows {
            leases.push(serde_json::from_str::<SchedulerLeaseRecord>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(leases)
    }

    pub fn record_worker_run_report(&mut self, report: &WorkerRunReport) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO worker_run_reports (run_id, worker_id, claimed_count, succeeded_count, failed_count, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            report.run_id.to_string(),
            &report.worker_id,
            report.claimed_count as i64,
            report.succeeded_count as i64,
            report.failed_count as i64,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn worker_run_reports(&self) -> MindResult<Vec<WorkerRunReport>> {
        let mut statement = self
            .connection
            .prepare("SELECT report_json FROM worker_run_reports ORDER BY started_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<WorkerRunReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_provider_sdk_receipt(&mut self, receipt: &ProviderSdkReceipt) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO provider_sdk_receipts (receipt_id, invocation_id, sdk, command_kind, target, status, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            receipt.receipt_id.to_string(),
            receipt.invocation_id.to_string(),
            format!("{:?}", receipt.sdk),
            format!("{:?}", receipt.command_kind),
            &receipt.target,
            format!("{:?}", receipt.status),
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn provider_sdk_receipts(&self) -> MindResult<Vec<ProviderSdkReceipt>> {
        let mut statement = self
            .connection
            .prepare("SELECT receipt_json FROM provider_sdk_receipts ORDER BY completed_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<ProviderSdkReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_consensus_apply_report(
        &mut self,
        report: &ConsensusApplyReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_apply_reports (apply_id, certificate_id, entry_id, cluster_id, operation_kind, status, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            report.apply_id.to_string(),
            report.certificate_id.to_string(),
            report.entry_id.to_string(),
            &report.cluster_id,
            &report.operation_kind,
            format!("{:?}", report.status),
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn consensus_apply_reports(&self) -> MindResult<Vec<ConsensusApplyReport>> {
        let mut statement = self
            .connection
            .prepare("SELECT report_json FROM consensus_apply_reports ORDER BY applied_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<ConsensusApplyReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn claim_due_jobs_for_worker(
        &mut self,
        worker_id: impl Into<String>,
        policy: &SchedulerLeasePolicy,
        limit: usize,
        now: time::OffsetDateTime,
    ) -> MindResult<SchedulerLeaseClaimReport> {
        policy.validate()?;
        let worker_id = worker_id.into();
        if worker_id.trim().is_empty() {
            return Err(MindError::Store(
                "scheduler worker id is required".to_owned(),
            ));
        }
        let requested_limit = limit.max(1).min(policy.max_claims_per_poll.max(1));
        let candidates = self
            .scheduled_jobs()?
            .into_iter()
            .filter(|job| job.is_due_at(now))
            .take(requested_limit)
            .collect::<Vec<_>>();
        let tx = self.connection.transaction().map_err(sqlite_error)?;
        let mut leases = Vec::new();
        let mut updated_jobs = Vec::new();
        for job in candidates {
            let prior_attempt = job.attempt_count;
            let (claimed_job, claim) = job.claim(worker_id.clone(), policy, now)?;
            let lease = SchedulerLeaseRecord::from_claim(&claimed_job, &claim)?;
            let changed = tx
                .execute(
                    r#"
                UPDATE scheduled_jobs
                SET status = ?2,
                    due_at = ?3,
                    not_before = ?4,
                    attempt_count = ?5,
                    idempotency_key = ?6,
                    payload_hash = ?7,
                    job_json = ?8,
                    updated_at = datetime('now')
                WHERE job_id = ?1
                  AND status = 'Pending'
                  AND attempt_count = ?9
                  AND payload_hash = ?10
            "#,
                    params![
                        claimed_job.job_id.to_string(),
                        format!("{:?}", ScheduledJobStatus::Claimed),
                        claimed_job.due_at.to_string(),
                        claimed_job.not_before.to_string(),
                        claimed_job.attempt_count as i64,
                        &claimed_job.idempotency_key,
                        &claimed_job.payload_hash,
                        serde_json::to_string(&claimed_job)?,
                        prior_attempt as i64,
                        &job.payload_hash,
                    ],
                )
                .map_err(sqlite_error)?;
            if changed == 1 {
                tx.execute(r#"
                    INSERT OR REPLACE INTO scheduler_leases (lease_id, job_id, worker_id, status, lease_expires_at, lease_json)
                    VALUES (?1, ?2, ?3, ?4, ?5, ?6)
                "#, params![
                    lease.lease_id.to_string(),
                    lease.job_id.to_string(),
                    &lease.worker_id,
                    format!("{:?}", lease.status),
                    lease.lease_expires_at.to_string(),
                    serde_json::to_string(&lease)?,
                ]).map_err(sqlite_error)?;
                leases.push(lease);
                updated_jobs.push(claimed_job);
            }
        }
        tx.commit().map_err(sqlite_error)?;
        Ok(SchedulerLeaseClaimReport {
            report_id: EventId::new(),
            worker_id,
            requested_limit,
            claimed_count: leases.len(),
            leases,
            updated_jobs,
            claimed_at: now,
        })
    }

    pub fn record_worker_daemon_tick(&mut self, report: &WorkerDaemonTickReport) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO worker_daemon_ticks (tick_id, worker_id, tick_index, claimed_count, succeeded_count, failed_count, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            report.tick_id.to_string(),
            &report.worker_id,
            report.tick_index as i64,
            report.claimed_count as i64,
            report.succeeded_count as i64,
            report.failed_count as i64,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn worker_daemon_ticks(&self) -> MindResult<Vec<WorkerDaemonTickReport>> {
        let mut statement = self
            .connection
            .prepare("SELECT report_json FROM worker_daemon_ticks ORDER BY started_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<WorkerDaemonTickReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_provider_sdk_feature_matrix(
        &mut self,
        matrix: &ProviderSdkFeatureMatrix,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO provider_sdk_feature_matrices (matrix_id, enabled_count, native_count, matrix_json)
            VALUES (?1, ?2, ?3, ?4)
        "#, params![
            matrix.matrix_id.to_string(),
            matrix.enabled_features().len() as i64,
            matrix.native_features().len() as i64,
            serde_json::to_string(matrix)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn provider_sdk_feature_matrices(&self) -> MindResult<Vec<ProviderSdkFeatureMatrix>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT matrix_json FROM provider_sdk_feature_matrices ORDER BY generated_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut matrices = Vec::new();
        for row in rows {
            matrices.push(serde_json::from_str::<ProviderSdkFeatureMatrix>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(matrices)
    }

    pub fn record_consensus_apply_idempotency_decision(
        &mut self,
        decision: &ConsensusApplyIdempotencyDecision,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_apply_idempotency (decision_id, certificate_id, entry_id, status, decision_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            decision.decision_id.to_string(),
            decision.certificate_id.to_string(),
            decision.entry_id.to_string(),
            format!("{:?}", decision.status),
            serde_json::to_string(decision)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn consensus_apply_idempotency_decisions(
        &self,
    ) -> MindResult<Vec<ConsensusApplyIdempotencyDecision>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT decision_json FROM consensus_apply_idempotency ORDER BY checked_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut decisions = Vec::new();
        for row in rows {
            decisions.push(serde_json::from_str::<ConsensusApplyIdempotencyDecision>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(decisions)
    }

    pub fn record_consensus_log_compaction_decision(
        &mut self,
        decision: &ConsensusLogCompactionDecision,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_log_compactions (compaction_id, cluster_id, compacted_count, decision_json)
            VALUES (?1, ?2, ?3, ?4)
        "#, params![
            decision.compaction_id.to_string(),
            &decision.cluster_id,
            decision.compact_certificate_ids.len() as i64,
            serde_json::to_string(decision)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn consensus_log_compaction_decisions(
        &self,
    ) -> MindResult<Vec<ConsensusLogCompactionDecision>> {
        let mut statement = self
            .connection
            .prepare("SELECT decision_json FROM consensus_log_compactions ORDER BY decided_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut decisions = Vec::new();
        for row in rows {
            decisions.push(serde_json::from_str::<ConsensusLogCompactionDecision>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(decisions)
    }

    pub fn record_job_execution_receipt(
        &mut self,
        receipt: &JobExecutionReceipt,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO job_execution_receipts (receipt_id, job_id, worker_id, kind, status, payload_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            receipt.receipt_id.to_string(),
            receipt.job_id.to_string(),
            &receipt.worker_id,
            format!("{:?}", receipt.kind),
            format!("{:?}", receipt.status),
            &receipt.expected_payload_hash,
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn job_execution_receipts(&self) -> MindResult<Vec<JobExecutionReceipt>> {
        let mut statement = self
            .connection
            .prepare("SELECT receipt_json FROM job_execution_receipts ORDER BY completed_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<JobExecutionReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_native_provider_adapter_report(
        &mut self,
        report: &NativeProviderAdapterReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO native_provider_adapter_reports (report_id, invocation_id, sdk, command_kind, accepted, request_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            report.report_id.to_string(),
            report.invocation_id.to_string(),
            format!("{:?}", report.sdk),
            format!("{:?}", report.command_kind),
            if report.accepted { 1_i64 } else { 0_i64 },
            &report.request_hash,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn native_provider_adapter_reports(&self) -> MindResult<Vec<NativeProviderAdapterReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM native_provider_adapter_reports ORDER BY evaluated_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<NativeProviderAdapterReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_distributed_lease_claim_receipt(
        &mut self,
        receipt: &DistributedLeaseClaimReceipt,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO distributed_lease_claim_receipts (receipt_id, request_id, backend, job_id, worker_id, status, payload_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![
            receipt.receipt_id.to_string(),
            receipt.request_id.to_string(),
            format!("{:?}", receipt.backend),
            receipt.job_id.to_string(),
            &receipt.worker_id,
            format!("{:?}", receipt.status),
            &receipt.expected_payload_hash,
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn distributed_lease_claim_receipts(
        &self,
    ) -> MindResult<Vec<DistributedLeaseClaimReceipt>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT receipt_json FROM distributed_lease_claim_receipts ORDER BY issued_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<DistributedLeaseClaimReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_consensus_physical_compaction_report(
        &mut self,
        report: &ConsensusPhysicalCompactionReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_physical_compactions (report_id, plan_id, decision_id, cluster_id, status, deleted_certificate_count, backup_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![
            report.report_id.to_string(),
            report.plan_id.to_string(),
            report.decision_id.to_string(),
            &report.cluster_id,
            format!("{:?}", report.status),
            report.deleted_certificate_count as i64,
            &report.backup_guard.backup_hash,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn consensus_physical_compaction_reports(
        &self,
    ) -> MindResult<Vec<ConsensusPhysicalCompactionReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM consensus_physical_compactions ORDER BY compacted_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<ConsensusPhysicalCompactionReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_domain_job_execution_report(
        &mut self,
        report: &DomainJobExecutionReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO domain_job_execution_reports (report_id, plan_id, job_id, worker_id, kind, status, payload_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![
            report.report_id.to_string(),
            report.plan_id.to_string(),
            report.job_id.to_string(),
            &report.worker_id,
            format!("{:?}", report.kind),
            format!("{:?}", report.status),
            &report.receipt.expected_payload_hash,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn domain_job_execution_reports(&self) -> MindResult<Vec<DomainJobExecutionReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM domain_job_execution_reports ORDER BY executed_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<DomainJobExecutionReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_distributed_lease_adapter_report(
        &mut self,
        report: &DistributedLeaseAdapterReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO distributed_lease_adapter_reports (report_id, request_id, backend, mode, job_id, worker_id, accepted, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![
            report.report_id.to_string(),
            report.request_id.to_string(),
            format!("{:?}", report.backend),
            format!("{:?}", report.mode),
            report.job_id.to_string(),
            &report.worker_id,
            if report.accepted { 1_i64 } else { 0_i64 },
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn distributed_lease_adapter_reports(
        &self,
    ) -> MindResult<Vec<DistributedLeaseAdapterReport>> {
        let mut statement = self.connection.prepare("SELECT report_json FROM distributed_lease_adapter_reports ORDER BY evaluated_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<DistributedLeaseAdapterReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_native_provider_execution_receipt(
        &mut self,
        receipt: &NativeProviderExecutionReceipt,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO native_provider_execution_receipts (receipt_id, execution_id, sdk, command_kind, status, request_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            receipt.receipt_id.to_string(),
            receipt.execution_id.to_string(),
            format!("{:?}", receipt.sdk_invocation.sdk),
            format!("{:?}", receipt.sdk_invocation.command_kind),
            format!("{:?}", receipt.status),
            &receipt.sdk_invocation.request_hash,
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn native_provider_execution_receipts(
        &self,
    ) -> MindResult<Vec<NativeProviderExecutionReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM native_provider_execution_receipts ORDER BY executed_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<NativeProviderExecutionReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_consensus_retention_enforcement_report(
        &mut self,
        report: &ConsensusRetentionEnforcementReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_retention_enforcements (report_id, plan_id, decision_id, cluster_id, status, deleted_certificate_count, deleted_apply_report_count, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![
            report.report_id.to_string(),
            report.plan_id.to_string(),
            report.decision_id.to_string(),
            &report.cluster_id,
            format!("{:?}", report.status),
            report.deleted_certificate_count as i64,
            report.deleted_apply_report_count as i64,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn consensus_retention_enforcement_reports(
        &self,
    ) -> MindResult<Vec<ConsensusRetentionEnforcementReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM consensus_retention_enforcements ORDER BY enforced_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<ConsensusRetentionEnforcementReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_live_domain_job_execution_report(
        &mut self,
        report: &LiveDomainJobExecutionReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO live_domain_job_execution_reports (report_id, domain_report_id, job_id, worker_id, kind, status, evidence_count, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![
            report.report_id.to_string(),
            report.domain_report.report_id.to_string(),
            report.job_id.to_string(),
            &report.worker_id,
            format!("{:?}", report.kind),
            format!("{:?}", report.status),
            report.evidence.len() as i64,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn live_domain_job_execution_reports(
        &self,
    ) -> MindResult<Vec<LiveDomainJobExecutionReport>> {
        let mut statement = self.connection.prepare("SELECT report_json FROM live_domain_job_execution_reports ORDER BY executed_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<LiveDomainJobExecutionReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_distributed_lease_execution_receipt(
        &mut self,
        receipt: &DistributedLeaseExecutionReceipt,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO distributed_lease_execution_receipts (receipt_id, plan_id, backend, job_id, worker_id, accepted, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            receipt.receipt_id.to_string(),
            receipt.plan.plan_id.to_string(),
            format!("{:?}", receipt.plan.backend),
            receipt.plan.job_id.to_string(),
            &receipt.plan.worker_id,
            if receipt.accepted { 1_i64 } else { 0_i64 },
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn distributed_lease_execution_receipts(
        &self,
    ) -> MindResult<Vec<DistributedLeaseExecutionReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM distributed_lease_execution_receipts ORDER BY executed_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            receipts.push(serde_json::from_str::<DistributedLeaseExecutionReceipt>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(receipts)
    }

    pub fn record_provider_sdk_execution_report(
        &mut self,
        report: &ProviderSdkExecutionReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO provider_sdk_execution_reports (report_id, plan_id, execution_id, sdk, accepted, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            report.report_id.to_string(),
            report.plan.plan_id.to_string(),
            report.plan.execution_id.to_string(),
            format!("{:?}", report.plan.sdk),
            if report.accepted { 1_i64 } else { 0_i64 },
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn provider_sdk_execution_reports(&self) -> MindResult<Vec<ProviderSdkExecutionReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM provider_sdk_execution_reports ORDER BY executed_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<ProviderSdkExecutionReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_consensus_retention_approval_proposal(
        &mut self,
        proposal: &ConsensusRetentionApprovalProposal,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_retention_approval_proposals (proposal_id, plan_id, decision_id, cluster_id, proposal_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            proposal.proposal_id.to_string(),
            proposal.plan_id.to_string(),
            proposal.decision_id.to_string(),
            &proposal.cluster_id,
            serde_json::to_string(proposal)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn record_consensus_retention_approval_vote(
        &mut self,
        vote: &ConsensusRetentionApprovalVote,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_retention_approval_votes (vote_id, proposal_id, voter_id, decision, vote_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            vote.vote_id.to_string(),
            vote.proposal_id.to_string(),
            &vote.voter_id,
            format!("{:?}", vote.decision),
            serde_json::to_string(vote)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn record_consensus_retention_approval_certificate(
        &mut self,
        certificate: &ConsensusRetentionApprovalCertificate,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO consensus_retention_approval_certificates (certificate_id, proposal_id, plan_id, cluster_id, status, approvals, rejections, certificate_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![
            certificate.certificate_id.to_string(),
            certificate.proposal_id.to_string(),
            certificate.plan_id.to_string(),
            &certificate.cluster_id,
            format!("{:?}", certificate.status),
            certificate.approvals as i64,
            certificate.rejections as i64,
            serde_json::to_string(certificate)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn consensus_retention_approval_certificates(
        &self,
    ) -> MindResult<Vec<ConsensusRetentionApprovalCertificate>> {
        let mut statement = self.connection.prepare("SELECT certificate_json FROM consensus_retention_approval_certificates ORDER BY certified_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut certificates = Vec::new();
        for row in rows {
            certificates.push(
                serde_json::from_str::<ConsensusRetentionApprovalCertificate>(
                    &row.map_err(sqlite_error)?,
                )?,
            );
        }
        Ok(certificates)
    }

    pub fn apply_consensus_retention_enforcement(
        &mut self,
        plan: &ConsensusRetentionEnforcementPlan,
    ) -> MindResult<ConsensusRetentionEnforcementReport> {
        let tx = self.connection.transaction().map_err(sqlite_error)?;
        let mut deleted_certificates = 0_usize;
        let mut deleted_apply_reports = 0_usize;
        for certificate_id in &plan.certificate_ids_to_delete {
            deleted_certificates += tx
                .execute(
                    "DELETE FROM consensus_commit_certificates WHERE certificate_id = ?1",
                    params![certificate_id.to_string()],
                )
                .map_err(sqlite_error)?;
        }
        for apply_id in &plan.apply_report_ids_to_delete {
            deleted_apply_reports += tx
                .execute(
                    "DELETE FROM consensus_apply_reports WHERE apply_id = ?1",
                    params![apply_id.to_string()],
                )
                .map_err(sqlite_error)?;
        }
        tx.commit().map_err(sqlite_error)?;
        let report = mind_core::report_consensus_retention_enforcement_applied(
            plan,
            deleted_certificates,
            deleted_apply_reports,
        );
        self.record_consensus_retention_enforcement_report(&report)?;
        Ok(report)
    }

    pub fn apply_consensus_physical_compaction(
        &mut self,
        plan: &ConsensusPhysicalCompactionPlan,
    ) -> MindResult<ConsensusPhysicalCompactionReport> {
        let tx = self.connection.transaction().map_err(sqlite_error)?;
        let mut deleted = 0_usize;
        for certificate_id in &plan.certificate_ids_to_delete {
            deleted += tx
                .execute(
                    "DELETE FROM consensus_commit_certificates WHERE certificate_id = ?1",
                    params![certificate_id.to_string()],
                )
                .map_err(sqlite_error)?;
        }
        tx.commit().map_err(sqlite_error)?;
        let report = ConsensusPhysicalCompactionReport::applied(plan, deleted, 0);
        self.record_consensus_physical_compaction_report(&report)?;
        Ok(report)
    }

    pub fn record_creative_engineering_report(
        &mut self,
        report: &CreativeEngineeringReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO creative_engineering_reports (report_id, report_hash, schema_version, suggestion_count, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            report.report_id.to_string(),
            &report.report_hash,
            report.platform_schema_version as i64,
            report.suggestions.len() as i64,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn creative_engineering_reports(&self) -> MindResult<Vec<CreativeEngineeringReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM creative_engineering_reports ORDER BY generated_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<CreativeEngineeringReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_chaos_rehearsal_plan(&mut self, plan: &ChaosRehearsalPlan) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO chaos_rehearsal_plans (plan_id, rehearsal_hash, mind_id, experiment_count, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            plan.plan_id.to_string(),
            &plan.rehearsal_hash,
            plan.mind_id.map(|id| id.to_string()),
            plan.experiments.len() as i64,
            serde_json::to_string(plan)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn chaos_rehearsal_plans(&self) -> MindResult<Vec<ChaosRehearsalPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM chaos_rehearsal_plans ORDER BY generated_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            plans.push(serde_json::from_str::<ChaosRehearsalPlan>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(plans)
    }

    pub fn record_invariant_fuzz_run_report(
        &mut self,
        report: &InvariantFuzzRunReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO invariant_fuzz_runs (run_id, target_mind_id, case_bank_hash, case_count, expected_reject_count, run_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            report.run_id.to_string(),
            report.target_mind_id.to_string(),
            &report.case_bank_hash,
            report.cases.len() as i64,
            report.expected_reject_count as i64,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn invariant_fuzz_run_reports(&self) -> MindResult<Vec<InvariantFuzzRunReport>> {
        let mut statement = self
            .connection
            .prepare("SELECT run_json FROM invariant_fuzz_runs ORDER BY generated_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<InvariantFuzzRunReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_production_readiness_gate_report(
        &mut self,
        report: &ProductionReadinessGateReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO production_readiness_gates (gate_id, creative_report_id, status, gate_hash, blocker_count, gate_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            report.gate_id.to_string(),
            report.creative_report_id.to_string(),
            format!("{:?}", report.status),
            &report.gate_hash,
            report.blockers.len() as i64,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn production_readiness_gate_reports(
        &self,
    ) -> MindResult<Vec<ProductionReadinessGateReport>> {
        let mut statement = self
            .connection
            .prepare("SELECT gate_json FROM production_readiness_gates ORDER BY evaluated_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<ProductionReadinessGateReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_chaos_execution_run(&mut self, run: &ChaosExecutionRun) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO chaos_execution_runs (run_id, plan_id, status, result_count, run_hash, run_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            run.run_id.to_string(),
            run.plan_id.to_string(),
            format!("{:?}", run.status),
            run.results.len() as i64,
            &run.run_hash,
            serde_json::to_string(run)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn chaos_execution_runs(&self) -> MindResult<Vec<ChaosExecutionRun>> {
        let mut statement = self
            .connection
            .prepare("SELECT run_json FROM chaos_execution_runs ORDER BY executed_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut runs = Vec::new();
        for row in rows {
            runs.push(serde_json::from_str::<ChaosExecutionRun>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(runs)
    }

    pub fn record_invariant_fuzz_execution_report(
        &mut self,
        report: &InvariantFuzzExecutionReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO invariant_fuzz_execution_reports (execution_id, run_id, target_mind_id, passed_count, failed_count, execution_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            report.execution_id.to_string(),
            report.run_id.to_string(),
            report.target_mind_id.to_string(),
            report.passed_count as i64,
            report.failed_count as i64,
            &report.execution_hash,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn invariant_fuzz_execution_reports(
        &self,
    ) -> MindResult<Vec<InvariantFuzzExecutionReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM invariant_fuzz_execution_reports ORDER BY executed_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<InvariantFuzzExecutionReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_readiness_waiver_proposal(
        &mut self,
        proposal: &ReadinessWaiverProposal,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO readiness_waiver_proposals (proposal_id, gate_id, risk_owner, proposal_hash, proposal_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            proposal.proposal_id.to_string(),
            proposal.gate_id.to_string(),
            &proposal.risk_owner,
            &proposal.proposal_hash,
            serde_json::to_string(proposal)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn readiness_waiver_proposals(&self) -> MindResult<Vec<ReadinessWaiverProposal>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT proposal_json FROM readiness_waiver_proposals ORDER BY proposed_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut proposals = Vec::new();
        for row in rows {
            proposals.push(serde_json::from_str::<ReadinessWaiverProposal>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(proposals)
    }

    pub fn record_readiness_waiver_vote(&mut self, vote: &ReadinessWaiverVote) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO readiness_waiver_votes (vote_id, proposal_id, voter, decision, vote_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            vote.vote_id.to_string(),
            vote.proposal_id.to_string(),
            &vote.voter,
            format!("{:?}", vote.decision),
            serde_json::to_string(vote)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn readiness_waiver_votes(&self) -> MindResult<Vec<ReadinessWaiverVote>> {
        let mut statement = self
            .connection
            .prepare("SELECT vote_json FROM readiness_waiver_votes ORDER BY voted_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut votes = Vec::new();
        for row in rows {
            votes.push(serde_json::from_str::<ReadinessWaiverVote>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(votes)
    }

    pub fn record_readiness_waiver_certificate(
        &mut self,
        certificate: &ReadinessWaiverCertificate,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO readiness_waiver_certificates (certificate_id, proposal_id, gate_id, status, certificate_hash, certificate_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            certificate.certificate_id.to_string(),
            certificate.proposal.proposal_id.to_string(),
            certificate.proposal.gate_id.to_string(),
            format!("{:?}", certificate.status),
            &certificate.certificate_hash,
            serde_json::to_string(certificate)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn readiness_waiver_certificates(&self) -> MindResult<Vec<ReadinessWaiverCertificate>> {
        let mut statement = self.connection.prepare("SELECT certificate_json FROM readiness_waiver_certificates ORDER BY certified_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut certificates = Vec::new();
        for row in rows {
            certificates.push(serde_json::from_str::<ReadinessWaiverCertificate>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(certificates)
    }

    pub fn record_readiness_waiver_application_report(
        &mut self,
        report: &ReadinessWaiverApplicationReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO readiness_waiver_application_reports (report_id, gate_id, effective_status, report_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            report.report_id.to_string(),
            report.gate_id.to_string(),
            format!("{:?}", report.effective_status),
            &report.report_hash,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn readiness_waiver_application_reports(
        &self,
    ) -> MindResult<Vec<ReadinessWaiverApplicationReport>> {
        let mut statement = self.connection.prepare("SELECT report_json FROM readiness_waiver_application_reports ORDER BY evaluated_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<ReadinessWaiverApplicationReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_engineering_implementation_job_plan(
        &mut self,
        plan: &EngineeringImplementationJobPlan,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO engineering_implementation_job_plans (plan_id, source_report_id, job_count, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            plan.plan_id.to_string(),
            plan.source_report_id.to_string(),
            plan.jobs.len() as i64,
            &plan.plan_hash,
            serde_json::to_string(plan)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn engineering_implementation_job_plans(
        &self,
    ) -> MindResult<Vec<EngineeringImplementationJobPlan>> {
        let mut statement = self.connection.prepare("SELECT plan_json FROM engineering_implementation_job_plans ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            plans.push(serde_json::from_str::<EngineeringImplementationJobPlan>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(plans)
    }

    pub fn record_staging_chaos_run_report(
        &mut self,
        report: &StagingChaosRunReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO staging_chaos_run_reports (staging_run_id, plan_id, environment_name, status, report_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            report.staging_run_id.to_string(),
            report.plan_id.to_string(),
            &report.environment.environment_name,
            format!("{:?}", report.status),
            &report.report_hash,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn staging_chaos_run_reports(&self) -> MindResult<Vec<StagingChaosRunReport>> {
        let mut statement = self
            .connection
            .prepare("SELECT report_json FROM staging_chaos_run_reports ORDER BY executed_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<StagingChaosRunReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_mandatory_ci_gate_report(
        &mut self,
        report: &MandatoryCiGateReport,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO mandatory_ci_gate_reports (ci_gate_id, status, report_hash, report_json)
            VALUES (?1, ?2, ?3, ?4)
        "#, params![
            report.ci_gate_id.to_string(),
            format!("{:?}", report.status),
            &report.report_hash,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn mandatory_ci_gate_reports(&self) -> MindResult<Vec<MandatoryCiGateReport>> {
        let mut statement = self
            .connection
            .prepare("SELECT report_json FROM mandatory_ci_gate_reports ORDER BY evaluated_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            reports.push(serde_json::from_str::<MandatoryCiGateReport>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(reports)
    }

    pub fn record_multi_operator_waiver_certificate(
        &mut self,
        certificate: &MultiOperatorWaiverCertificate,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO multi_operator_waiver_certificates (certificate_id, proposal_id, gate_id, status, certificate_hash, certificate_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            certificate.certificate_id.to_string(),
            certificate.proposal.proposal_id.to_string(),
            certificate.gate_id.to_string(),
            format!("{:?}", certificate.status),
            &certificate.certificate_hash,
            serde_json::to_string(certificate)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn multi_operator_waiver_certificates(
        &self,
    ) -> MindResult<Vec<MultiOperatorWaiverCertificate>> {
        let mut statement = self.connection.prepare("SELECT certificate_json FROM multi_operator_waiver_certificates ORDER BY certified_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut certificates = Vec::new();
        for row in rows {
            certificates.push(serde_json::from_str::<MultiOperatorWaiverCertificate>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(certificates)
    }

    pub fn record_implementation_job_evidence_bundle(
        &mut self,
        bundle: &ImplementationJobEvidenceBundle,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO implementation_job_evidence_bundles (bundle_id, implementation_job_id, scheduled_job_id, status, bundle_hash, bundle_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            bundle.bundle_id.to_string(),
            bundle.implementation_job_id.to_string(),
            bundle.scheduled_job_id.to_string(),
            format!("{:?}", bundle.status),
            &bundle.bundle_hash,
            serde_json::to_string(bundle)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn implementation_job_evidence_bundles(
        &self,
    ) -> MindResult<Vec<ImplementationJobEvidenceBundle>> {
        let mut statement = self.connection.prepare("SELECT bundle_json FROM implementation_job_evidence_bundles ORDER BY evaluated_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut bundles = Vec::new();
        for row in rows {
            bundles.push(serde_json::from_str::<ImplementationJobEvidenceBundle>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(bundles)
    }

    pub fn record_implementation_evidence_automation_plan(
        &mut self,
        plan: &ImplementationEvidenceAutomationPlan,
    ) -> MindResult<()> {
        self.connection.execute(r#"
            INSERT OR REPLACE INTO implementation_evidence_automation_plans (automation_plan_id, implementation_plan_id, repository, target_count, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            plan.automation_plan_id.to_string(),
            plan.implementation_plan_id.to_string(),
            &plan.repository,
            plan.targets.len() as i64,
            &plan.plan_hash,
            serde_json::to_string(plan)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn implementation_evidence_automation_plans(
        &self,
    ) -> MindResult<Vec<ImplementationEvidenceAutomationPlan>> {
        let mut statement = self.connection.prepare("SELECT plan_json FROM implementation_evidence_automation_plans ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            plans.push(
                serde_json::from_str::<ImplementationEvidenceAutomationPlan>(
                    &row.map_err(sqlite_error)?,
                )?,
            );
        }
        Ok(plans)
    }

    pub fn record_github_readiness_evidence_bundle(
        &mut self,
        bundle: &GitHubReadinessEvidenceBundle,
    ) -> MindResult<()> {
        bundle.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_readiness_evidence_bundles (bundle_id, repository, pull_request_number, head_sha, status, bundle_hash, bundle_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            bundle.bundle_id.to_string(),
            &bundle.repository,
            bundle.pull_request.pull_request_number as i64,
            &bundle.pull_request.head_sha,
            format!("{:?}", bundle.status),
            &bundle.bundle_hash,
            serde_json::to_string(bundle)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_readiness_evidence_bundles(
        &self,
    ) -> MindResult<Vec<GitHubReadinessEvidenceBundle>> {
        let mut statement = self.connection.prepare("SELECT bundle_json FROM github_readiness_evidence_bundles ORDER BY collected_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut bundles = Vec::new();
        for row in rows {
            let bundle =
                serde_json::from_str::<GitHubReadinessEvidenceBundle>(&row.map_err(sqlite_error)?)?;
            bundle.verify()?;
            bundles.push(bundle);
        }
        Ok(bundles)
    }

    pub fn record_branch_protection_policy(
        &mut self,
        policy: &BranchProtectionPolicy,
    ) -> MindResult<()> {
        policy.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO branch_protection_policies (policy_id, repository, branch, policy_hash, policy_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![
            policy.policy_id.to_string(),
            &policy.repository,
            &policy.branch,
            &policy.policy_hash,
            serde_json::to_string(policy)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn branch_protection_policies(&self) -> MindResult<Vec<BranchProtectionPolicy>> {
        let mut statement = self
            .connection
            .prepare("SELECT policy_json FROM branch_protection_policies ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut policies = Vec::new();
        for row in rows {
            let policy =
                serde_json::from_str::<BranchProtectionPolicy>(&row.map_err(sqlite_error)?)?;
            policy.verify()?;
            policies.push(policy);
        }
        Ok(policies)
    }

    pub fn record_branch_protection_evaluation_report(
        &mut self,
        report: &BranchProtectionEvaluationReport,
    ) -> MindResult<()> {
        report.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO branch_protection_evaluation_reports (report_id, policy_id, repository, branch, compliant, report_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            report.report_id.to_string(),
            report.policy_id.to_string(),
            &report.repository,
            &report.branch,
            if report.compliant { 1_i64 } else { 0_i64 },
            &report.report_hash,
            serde_json::to_string(report)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn branch_protection_evaluation_reports(
        &self,
    ) -> MindResult<Vec<BranchProtectionEvaluationReport>> {
        let mut statement = self.connection.prepare("SELECT report_json FROM branch_protection_evaluation_reports ORDER BY evaluated_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            let report = serde_json::from_str::<BranchProtectionEvaluationReport>(
                &row.map_err(sqlite_error)?,
            )?;
            report.verify()?;
            reports.push(report);
        }
        Ok(reports)
    }

    pub fn record_live_staging_chaos_adapter_plan(
        &mut self,
        plan: &LiveStagingChaosAdapterPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO live_staging_chaos_adapter_plans (adapter_plan_id, rehearsal_plan_id, backend, mode, namespace, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            plan.adapter_plan_id.to_string(),
            plan.rehearsal_plan_id.to_string(),
            format!("{:?}", plan.backend),
            format!("{:?}", plan.mode),
            &plan.namespace,
            &plan.plan_hash,
            serde_json::to_string(plan)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn live_staging_chaos_adapter_plans(&self) -> MindResult<Vec<LiveStagingChaosAdapterPlan>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT plan_json FROM live_staging_chaos_adapter_plans ORDER BY created_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            let plan =
                serde_json::from_str::<LiveStagingChaosAdapterPlan>(&row.map_err(sqlite_error)?)?;
            plan.verify()?;
            plans.push(plan);
        }
        Ok(plans)
    }

    pub fn record_live_staging_chaos_adapter_receipt(
        &mut self,
        receipt: &LiveStagingChaosAdapterReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO live_staging_chaos_adapter_receipts (receipt_id, adapter_plan_id, backend, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            receipt.receipt_id.to_string(),
            receipt.adapter_plan_id.to_string(),
            format!("{:?}", receipt.backend),
            format!("{:?}", receipt.status),
            &receipt.receipt_hash,
            serde_json::to_string(receipt)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn live_staging_chaos_adapter_receipts(
        &self,
    ) -> MindResult<Vec<LiveStagingChaosAdapterReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM live_staging_chaos_adapter_receipts ORDER BY executed_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            let receipt = serde_json::from_str::<LiveStagingChaosAdapterReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            receipt.verify()?;
            receipts.push(receipt);
        }
        Ok(receipts)
    }

    pub fn record_waiver_review_certificate(
        &mut self,
        certificate: &WaiverReviewCertificate,
    ) -> MindResult<()> {
        certificate.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO waiver_review_certificates (certificate_id, review_id, proposal_id, status, certificate_hash, certificate_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![
            certificate.certificate_id.to_string(),
            certificate.review_id.to_string(),
            certificate.proposal_id.to_string(),
            format!("{:?}", certificate.status),
            &certificate.certificate_hash,
            serde_json::to_string(certificate)?,
        ]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn waiver_review_certificates(&self) -> MindResult<Vec<WaiverReviewCertificate>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT certificate_json FROM waiver_review_certificates ORDER BY certified_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut certificates = Vec::new();
        for row in rows {
            let certificate =
                serde_json::from_str::<WaiverReviewCertificate>(&row.map_err(sqlite_error)?)?;
            certificate.verify()?;
            certificates.push(certificate);
        }
        Ok(certificates)
    }

    pub fn record_github_check_run_write_plan(
        &mut self,
        plan: &GitHubCheckRunWritePlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_check_run_write_plans (plan_id, repository, head_sha, name, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![plan.plan_id.to_string(), &plan.request.repository, &plan.request.head_sha, &plan.request.name, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_check_run_write_plans(&self) -> MindResult<Vec<GitHubCheckRunWritePlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM github_check_run_write_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            let plan =
                serde_json::from_str::<GitHubCheckRunWritePlan>(&row.map_err(sqlite_error)?)?;
            plan.verify()?;
            plans.push(plan);
        }
        Ok(plans)
    }

    pub fn record_github_check_run_write_receipt(
        &mut self,
        receipt: &GitHubCheckRunWriteReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_check_run_write_receipts (receipt_id, plan_id, repository, head_sha, name, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![receipt.receipt_id.to_string(), receipt.plan_id.to_string(), &receipt.repository, &receipt.head_sha, &receipt.name, format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_check_run_write_receipts(&self) -> MindResult<Vec<GitHubCheckRunWriteReceipt>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT receipt_json FROM github_check_run_write_receipts ORDER BY written_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            let receipt =
                serde_json::from_str::<GitHubCheckRunWriteReceipt>(&row.map_err(sqlite_error)?)?;
            receipt.verify()?;
            receipts.push(receipt);
        }
        Ok(receipts)
    }

    pub fn record_branch_protection_reconcile_plan(
        &mut self,
        plan: &BranchProtectionReconcilePlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO branch_protection_reconcile_plans (reconcile_id, repository, branch, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![plan.reconcile_id.to_string(), &plan.policy.repository, &plan.policy.branch, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn branch_protection_reconcile_plans(
        &self,
    ) -> MindResult<Vec<BranchProtectionReconcilePlan>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT plan_json FROM branch_protection_reconcile_plans ORDER BY created_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            let plan =
                serde_json::from_str::<BranchProtectionReconcilePlan>(&row.map_err(sqlite_error)?)?;
            plan.verify()?;
            plans.push(plan);
        }
        Ok(plans)
    }

    pub fn record_branch_protection_reconcile_receipt(
        &mut self,
        receipt: &BranchProtectionReconcileReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO branch_protection_reconcile_receipts (receipt_id, reconcile_id, repository, branch, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![receipt.receipt_id.to_string(), receipt.reconcile_id.to_string(), &receipt.repository, &receipt.branch, format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn branch_protection_reconcile_receipts(
        &self,
    ) -> MindResult<Vec<BranchProtectionReconcileReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM branch_protection_reconcile_receipts ORDER BY reconciled_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            let receipt = serde_json::from_str::<BranchProtectionReconcileReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            receipt.verify()?;
            receipts.push(receipt);
        }
        Ok(receipts)
    }

    pub fn record_kubernetes_staging_chaos_plan(
        &mut self,
        plan: &KubernetesStagingChaosPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_staging_chaos_plans (plan_id, rehearsal_plan_id, namespace, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![plan.plan_id.to_string(), plan.rehearsal_plan_id.to_string(), &plan.namespace, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_staging_chaos_plans(&self) -> MindResult<Vec<KubernetesStagingChaosPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM kubernetes_staging_chaos_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            let plan =
                serde_json::from_str::<KubernetesStagingChaosPlan>(&row.map_err(sqlite_error)?)?;
            plan.verify()?;
            plans.push(plan);
        }
        Ok(plans)
    }

    pub fn record_kubernetes_staging_chaos_receipt(
        &mut self,
        receipt: &KubernetesStagingChaosReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_staging_chaos_receipts (receipt_id, plan_id, rehearsal_plan_id, namespace, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![receipt.receipt_id.to_string(), receipt.plan_id.to_string(), receipt.rehearsal_plan_id.to_string(), &receipt.namespace, format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_staging_chaos_receipts(
        &self,
    ) -> MindResult<Vec<KubernetesStagingChaosReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM kubernetes_staging_chaos_receipts ORDER BY executed_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            let receipt =
                serde_json::from_str::<KubernetesStagingChaosReceipt>(&row.map_err(sqlite_error)?)?;
            receipt.verify()?;
            receipts.push(receipt);
        }
        Ok(receipts)
    }

    pub fn record_waiver_reviewer_assignment_plan(
        &mut self,
        plan: &WaiverReviewerAssignmentPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO waiver_reviewer_assignment_plans (assignment_plan_id, review_id, proposal_id, status, assignment_hash, assignment_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![plan.assignment_plan_id.to_string(), plan.review_id.to_string(), plan.proposal_id.to_string(), format!("{:?}", plan.status), &plan.assignment_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn waiver_reviewer_assignment_plans(
        &self,
    ) -> MindResult<Vec<WaiverReviewerAssignmentPlan>> {
        let mut statement = self.connection.prepare("SELECT assignment_json FROM waiver_reviewer_assignment_plans ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            let plan =
                serde_json::from_str::<WaiverReviewerAssignmentPlan>(&row.map_err(sqlite_error)?)?;
            plan.verify()?;
            plans.push(plan);
        }
        Ok(plans)
    }

    pub fn record_waiver_escalation_certificate(
        &mut self,
        certificate: &WaiverEscalationCertificate,
    ) -> MindResult<()> {
        certificate.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO waiver_escalation_certificates (certificate_id, assignment_plan_id, review_id, proposal_id, status, certificate_hash, certificate_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![certificate.certificate_id.to_string(), certificate.assignment_plan_id.to_string(), certificate.review_id.to_string(), certificate.proposal_id.to_string(), format!("{:?}", certificate.status), &certificate.certificate_hash, serde_json::to_string(certificate)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn waiver_escalation_certificates(&self) -> MindResult<Vec<WaiverEscalationCertificate>> {
        let mut statement = self.connection.prepare("SELECT certificate_json FROM waiver_escalation_certificates ORDER BY escalated_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut certificates = Vec::new();
        for row in rows {
            let certificate =
                serde_json::from_str::<WaiverEscalationCertificate>(&row.map_err(sqlite_error)?)?;
            certificate.verify()?;
            certificates.push(certificate);
        }
        Ok(certificates)
    }

    pub fn record_secret_access_plan(&mut self, plan: &SecretAccessPlan) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO secret_access_plans (plan_id, backend, key_id, purpose, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![plan.plan_id.to_string(), format!("{:?}", plan.reference.backend), &plan.reference.key_id, &plan.purpose, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn secret_access_plans(&self) -> MindResult<Vec<SecretAccessPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM secret_access_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<SecretAccessPlan>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_secret_access_receipt(
        &mut self,
        receipt: &SecretAccessReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO secret_access_receipts (receipt_id, plan_id, backend, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![receipt.receipt_id.to_string(), receipt.plan_id.to_string(), format!("{:?}", receipt.backend), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn secret_access_receipts(&self) -> MindResult<Vec<SecretAccessReceipt>> {
        let mut statement = self
            .connection
            .prepare("SELECT receipt_json FROM secret_access_receipts ORDER BY resolved_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<SecretAccessReceipt>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_github_app_jwt_plan(&mut self, plan: &GitHubAppJwtPlan) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_app_jwt_plans (jwt_plan_id, app_id, installation_id, key_id, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![plan.jwt_plan_id.to_string(), plan.app_id.to_string(), plan.installation_id.to_string(), &plan.key_id, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_app_jwt_plans(&self) -> MindResult<Vec<GitHubAppJwtPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM github_app_jwt_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<GitHubAppJwtPlan>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_github_app_jwt_receipt(
        &mut self,
        receipt: &GitHubAppJwtReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_app_jwt_receipts (receipt_id, jwt_plan_id, secret_receipt_id, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![receipt.receipt_id.to_string(), receipt.jwt_plan_id.to_string(), receipt.secret_receipt_id.to_string(), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_app_jwt_receipts(&self) -> MindResult<Vec<GitHubAppJwtReceipt>> {
        let mut statement = self
            .connection
            .prepare("SELECT receipt_json FROM github_app_jwt_receipts ORDER BY signed_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<GitHubAppJwtReceipt>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_connector_worker_job_plan(
        &mut self,
        plan: &ConnectorWorkerJobPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO connector_worker_job_plans (connector_plan_id, worker_id, action_kind, target, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![plan.connector_plan_id.to_string(), &plan.worker_id, format!("{:?}", plan.action_kind), &plan.target, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn connector_worker_job_plans(&self) -> MindResult<Vec<ConnectorWorkerJobPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM connector_worker_job_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value =
                serde_json::from_str::<ConnectorWorkerJobPlan>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_connector_worker_execution_receipt(
        &mut self,
        receipt: &ConnectorWorkerExecutionReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO connector_worker_execution_receipts (receipt_id, connector_plan_id, action_kind, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![receipt.receipt_id.to_string(), receipt.connector_plan_id.to_string(), format!("{:?}", receipt.action_kind), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn connector_worker_execution_receipts(
        &self,
    ) -> MindResult<Vec<ConnectorWorkerExecutionReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM connector_worker_execution_receipts ORDER BY executed_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<ConnectorWorkerExecutionReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_kubernetes_admission_audit_request(
        &mut self,
        request: &KubernetesAdmissionAuditRequest,
    ) -> MindResult<()> {
        request.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_admission_audit_requests (audit_request_id, dry_run_request_id, namespace, operation, request_hash, request_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![request.audit_request_id.to_string(), request.dry_run_request_id.to_string(), &request.namespace, format!("{:?}", request.operation), &request.request_hash, serde_json::to_string(request)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_admission_audit_requests(
        &self,
    ) -> MindResult<Vec<KubernetesAdmissionAuditRequest>> {
        let mut statement = self.connection.prepare("SELECT request_json FROM kubernetes_admission_audit_requests ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<KubernetesAdmissionAuditRequest>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_kubernetes_admission_audit_receipt(
        &mut self,
        receipt: &KubernetesAdmissionAuditReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_admission_audit_receipts (audit_receipt_id, audit_request_id, dry_run_receipt_id, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![receipt.audit_receipt_id.to_string(), receipt.audit_request_id.to_string(), receipt.dry_run_receipt_id.to_string(), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_admission_audit_receipts(
        &self,
    ) -> MindResult<Vec<KubernetesAdmissionAuditReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM kubernetes_admission_audit_receipts ORDER BY captured_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<KubernetesAdmissionAuditReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_kubernetes_admission_audit_report(
        &mut self,
        report: &KubernetesAdmissionAuditReport,
    ) -> MindResult<()> {
        report.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_admission_audit_reports (report_id, audit_request_id, audit_receipt_id, status, report_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![report.report_id.to_string(), report.audit_request_id.to_string(), report.audit_receipt_id.to_string(), format!("{:?}", report.status), &report.report_hash, serde_json::to_string(report)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_admission_audit_reports(
        &self,
    ) -> MindResult<Vec<KubernetesAdmissionAuditReport>> {
        let mut statement = self.connection.prepare("SELECT report_json FROM kubernetes_admission_audit_reports ORDER BY evaluated_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<KubernetesAdmissionAuditReport>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_waiver_notification_adapter_plan(
        &mut self,
        plan: &WaiverNotificationAdapterPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO waiver_notification_adapter_plans (adapter_plan_id, notification_plan_id, adapter_kind, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![plan.adapter_plan_id.to_string(), plan.notification_plan_id.to_string(), format!("{:?}", plan.adapter_kind), format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn waiver_notification_adapter_plans(
        &self,
    ) -> MindResult<Vec<WaiverNotificationAdapterPlan>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT plan_json FROM waiver_notification_adapter_plans ORDER BY created_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value =
                serde_json::from_str::<WaiverNotificationAdapterPlan>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_waiver_notification_adapter_receipt(
        &mut self,
        receipt: &WaiverNotificationAdapterReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO waiver_notification_adapter_receipts (receipt_id, adapter_plan_id, adapter_kind, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![receipt.receipt_id.to_string(), receipt.adapter_plan_id.to_string(), format!("{:?}", receipt.adapter_kind), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn waiver_notification_adapter_receipts(
        &self,
    ) -> MindResult<Vec<WaiverNotificationAdapterReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM waiver_notification_adapter_receipts ORDER BY delivered_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<WaiverNotificationAdapterReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_live_secret_connector_plan(
        &mut self,
        plan: &LiveSecretConnectorPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO live_secret_connector_plans (connector_plan_id, access_plan_id, backend, locator_fingerprint, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![plan.connector_plan_id.to_string(), plan.access_plan_id.to_string(), format!("{:?}", plan.backend), &plan.locator_fingerprint, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn live_secret_connector_plans(&self) -> MindResult<Vec<LiveSecretConnectorPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM live_secret_connector_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value =
                serde_json::from_str::<LiveSecretConnectorPlan>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_live_secret_connector_receipt(
        &mut self,
        receipt: &LiveSecretConnectorReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO live_secret_connector_receipts (connector_receipt_id, connector_plan_id, access_receipt_id, backend, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![receipt.connector_receipt_id.to_string(), receipt.connector_plan_id.to_string(), receipt.access_receipt_id.to_string(), format!("{:?}", receipt.backend), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn live_secret_connector_receipts(&self) -> MindResult<Vec<LiveSecretConnectorReceipt>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT receipt_json FROM live_secret_connector_receipts ORDER BY completed_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value =
                serde_json::from_str::<LiveSecretConnectorReceipt>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_github_token_exchange_worker_plan(
        &mut self,
        plan: &GitHubTokenExchangeWorkerPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_token_exchange_worker_plans (exchange_plan_id, repository, installation_id, jwt_receipt_id, secret_connector_receipt_id, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![plan.exchange_plan_id.to_string(), &plan.repository, plan.installation_id.to_string(), plan.jwt_receipt_id.to_string(), plan.secret_connector_receipt_id.to_string(), format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_token_exchange_worker_plans(
        &self,
    ) -> MindResult<Vec<GitHubTokenExchangeWorkerPlan>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT plan_json FROM github_token_exchange_worker_plans ORDER BY created_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value =
                serde_json::from_str::<GitHubTokenExchangeWorkerPlan>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_github_token_exchange_worker_receipt(
        &mut self,
        receipt: &GitHubTokenExchangeWorkerReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_token_exchange_worker_receipts (exchange_receipt_id, exchange_plan_id, token_receipt_id, installation_id, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![receipt.exchange_receipt_id.to_string(), receipt.exchange_plan_id.to_string(), receipt.token_receipt_id.to_string(), receipt.installation_id.to_string(), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_token_exchange_worker_receipts(
        &self,
    ) -> MindResult<Vec<GitHubTokenExchangeWorkerReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM github_token_exchange_worker_receipts ORDER BY exchanged_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<GitHubTokenExchangeWorkerReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_kubernetes_audit_log_collector_plan(
        &mut self,
        plan: &KubernetesAuditLogCollectorPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_audit_log_collector_plans (collector_plan_id, audit_report_id, namespace, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![plan.collector_plan_id.to_string(), plan.audit_report_id.to_string(), &plan.namespace, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_audit_log_collector_plans(
        &self,
    ) -> MindResult<Vec<KubernetesAuditLogCollectorPlan>> {
        let mut statement = self.connection.prepare("SELECT plan_json FROM kubernetes_audit_log_collector_plans ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<KubernetesAuditLogCollectorPlan>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_kubernetes_audit_log_collector_report(
        &mut self,
        report: &KubernetesAuditLogCollectorReport,
    ) -> MindResult<()> {
        report.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_audit_log_collector_reports (collector_report_id, collector_plan_id, audit_receipt_id, status, report_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![report.collector_report_id.to_string(), report.collector_plan_id.to_string(), report.audit_receipt_id.to_string(), format!("{:?}", report.status), &report.report_hash, serde_json::to_string(report)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_audit_log_collector_reports(
        &self,
    ) -> MindResult<Vec<KubernetesAuditLogCollectorReport>> {
        let mut statement = self.connection.prepare("SELECT report_json FROM kubernetes_audit_log_collector_reports ORDER BY collected_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<KubernetesAuditLogCollectorReport>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_notification_delivery_client_plan(
        &mut self,
        plan: &NotificationDeliveryClientPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO notification_delivery_client_plans (client_plan_id, adapter_plan_id, adapter_kind, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![plan.client_plan_id.to_string(), plan.adapter_plan_id.to_string(), format!("{:?}", plan.adapter_kind), format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn notification_delivery_client_plans(
        &self,
    ) -> MindResult<Vec<NotificationDeliveryClientPlan>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT plan_json FROM notification_delivery_client_plans ORDER BY created_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<NotificationDeliveryClientPlan>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_notification_delivery_client_receipt(
        &mut self,
        receipt: &NotificationDeliveryClientReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO notification_delivery_client_receipts (client_receipt_id, client_plan_id, adapter_receipt_id, adapter_kind, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![receipt.client_receipt_id.to_string(), receipt.client_plan_id.to_string(), receipt.adapter_receipt_id.to_string(), format!("{:?}", receipt.adapter_kind), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn notification_delivery_client_receipts(
        &self,
    ) -> MindResult<Vec<NotificationDeliveryClientReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM notification_delivery_client_receipts ORDER BY delivered_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<NotificationDeliveryClientReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_connector_orchestration_plan(
        &mut self,
        plan: &ConnectorOrchestrationPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO connector_orchestration_plans (orchestration_plan_id, worker_id, purpose, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![plan.orchestration_plan_id.to_string(), &plan.worker_id, &plan.purpose, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn connector_orchestration_plans(&self) -> MindResult<Vec<ConnectorOrchestrationPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM connector_orchestration_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value =
                serde_json::from_str::<ConnectorOrchestrationPlan>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_connector_orchestration_report(
        &mut self,
        report: &ConnectorOrchestrationReport,
    ) -> MindResult<()> {
        report.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO connector_orchestration_reports (orchestration_report_id, orchestration_plan_id, status, report_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5)
        "#, params![report.orchestration_report_id.to_string(), report.orchestration_plan_id.to_string(), format!("{:?}", report.status), &report.report_hash, serde_json::to_string(report)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn connector_orchestration_reports(&self) -> MindResult<Vec<ConnectorOrchestrationReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM connector_orchestration_reports ORDER BY evaluated_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value =
                serde_json::from_str::<ConnectorOrchestrationReport>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_kubernetes_audit_source_adapter_plan(
        &mut self,
        plan: &KubernetesAuditSourceAdapterPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_audit_source_adapter_plans (source_plan_id, collector_plan_id, kind, namespace, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![plan.source_plan_id.to_string(), plan.collector_plan_id.to_string(), format!("{:?}", plan.kind), &plan.namespace, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_audit_source_adapter_plans(
        &self,
    ) -> MindResult<Vec<KubernetesAuditSourceAdapterPlan>> {
        let mut statement = self.connection.prepare("SELECT plan_json FROM kubernetes_audit_source_adapter_plans ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<KubernetesAuditSourceAdapterPlan>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_kubernetes_audit_source_adapter_receipt(
        &mut self,
        receipt: &KubernetesAuditSourceAdapterReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_audit_source_adapter_receipts (source_receipt_id, source_plan_id, collector_report_id, kind, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![receipt.source_receipt_id.to_string(), receipt.source_plan_id.to_string(), receipt.collector_report_id.to_string(), format!("{:?}", receipt.kind), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_audit_source_adapter_receipts(
        &self,
    ) -> MindResult<Vec<KubernetesAuditSourceAdapterReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM kubernetes_audit_source_adapter_receipts ORDER BY collected_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<KubernetesAuditSourceAdapterReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_notification_provider_delivery_plan(
        &mut self,
        plan: &NotificationProviderDeliveryPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO notification_provider_delivery_plans (provider_plan_id, client_plan_id, provider_kind, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![plan.provider_plan_id.to_string(), plan.client_plan_id.to_string(), format!("{:?}", plan.provider_kind), format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn notification_provider_delivery_plans(
        &self,
    ) -> MindResult<Vec<NotificationProviderDeliveryPlan>> {
        let mut statement = self.connection.prepare("SELECT plan_json FROM notification_provider_delivery_plans ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<NotificationProviderDeliveryPlan>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_notification_provider_delivery_receipt(
        &mut self,
        receipt: &NotificationProviderDeliveryReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO notification_provider_delivery_receipts (provider_receipt_id, provider_plan_id, client_receipt_id, provider_kind, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![receipt.provider_receipt_id.to_string(), receipt.provider_plan_id.to_string(), receipt.client_receipt_id.to_string(), format!("{:?}", receipt.provider_kind), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn notification_provider_delivery_receipts(
        &self,
    ) -> MindResult<Vec<NotificationProviderDeliveryReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM notification_provider_delivery_receipts ORDER BY delivered_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value = serde_json::from_str::<NotificationProviderDeliveryReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_action_promotion_gate_report(
        &mut self,
        report: &ActionPromotionGateReport,
    ) -> MindResult<()> {
        report.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO action_promotion_gate_reports (gate_report_id, status, report_hash, report_json)
            VALUES (?1, ?2, ?3, ?4)
        "#, params![report.gate_report_id.to_string(), format!("{:?}", report.status), &report.report_hash, serde_json::to_string(report)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn action_promotion_gate_reports(&self) -> MindResult<Vec<ActionPromotionGateReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM action_promotion_gate_reports ORDER BY evaluated_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut values = Vec::new();
        for row in rows {
            let value =
                serde_json::from_str::<ActionPromotionGateReport>(&row.map_err(sqlite_error)?)?;
            value.verify()?;
            values.push(value);
        }
        Ok(values)
    }

    pub fn record_github_app_installation_token_plan(
        &mut self,
        plan: &GitHubAppInstallationTokenPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_app_installation_token_plans (plan_id, app_id, installation_id, repository, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![plan.plan_id.to_string(), plan.request.app_id.to_string(), plan.request.installation_id.to_string(), &plan.request.repository, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_app_installation_token_plans(
        &self,
    ) -> MindResult<Vec<GitHubAppInstallationTokenPlan>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT plan_json FROM github_app_installation_token_plans ORDER BY created_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            let plan = serde_json::from_str::<GitHubAppInstallationTokenPlan>(
                &row.map_err(sqlite_error)?,
            )?;
            plan.verify()?;
            plans.push(plan);
        }
        Ok(plans)
    }

    pub fn record_github_app_installation_token_receipt(
        &mut self,
        receipt: &GitHubAppInstallationTokenReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_app_installation_token_receipts (receipt_id, plan_id, installation_id, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![receipt.receipt_id.to_string(), receipt.plan_id.to_string(), receipt.installation_id.to_string(), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_app_installation_token_receipts(
        &self,
    ) -> MindResult<Vec<GitHubAppInstallationTokenReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM github_app_installation_token_receipts ORDER BY issued_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            let receipt = serde_json::from_str::<GitHubAppInstallationTokenReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            receipt.verify()?;
            receipts.push(receipt);
        }
        Ok(receipts)
    }

    pub fn record_github_action_execution_plan(
        &mut self,
        plan: &GitHubActionExecutionPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_action_execution_plans (execution_id, token_plan_id, repository, action_kind, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![plan.execution_id.to_string(), plan.token_plan_id.to_string(), &plan.repository, format!("{:?}", plan.action_kind), format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_action_execution_plans(&self) -> MindResult<Vec<GitHubActionExecutionPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM github_action_execution_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            let plan =
                serde_json::from_str::<GitHubActionExecutionPlan>(&row.map_err(sqlite_error)?)?;
            plan.verify()?;
            plans.push(plan);
        }
        Ok(plans)
    }

    pub fn record_github_action_execution_receipt(
        &mut self,
        receipt: &GitHubActionExecutionReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO github_action_execution_receipts (receipt_id, execution_id, token_receipt_id, repository, action_kind, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
        "#, params![receipt.receipt_id.to_string(), receipt.execution_id.to_string(), receipt.token_receipt_id.to_string(), &receipt.repository, format!("{:?}", receipt.action_kind), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn github_action_execution_receipts(
        &self,
    ) -> MindResult<Vec<GitHubActionExecutionReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM github_action_execution_receipts ORDER BY executed_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            let receipt =
                serde_json::from_str::<GitHubActionExecutionReceipt>(&row.map_err(sqlite_error)?)?;
            receipt.verify()?;
            receipts.push(receipt);
        }
        Ok(receipts)
    }

    pub fn record_branch_protection_worker_plan(
        &mut self,
        plan: &BranchProtectionWorkerPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO branch_protection_worker_plans (worker_plan_id, repository, branch, mode, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![plan.worker_plan_id.to_string(), &plan.repository, &plan.branch, format!("{:?}", plan.mode), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn branch_protection_worker_plans(&self) -> MindResult<Vec<BranchProtectionWorkerPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM branch_protection_worker_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            let plan =
                serde_json::from_str::<BranchProtectionWorkerPlan>(&row.map_err(sqlite_error)?)?;
            plan.verify()?;
            plans.push(plan);
        }
        Ok(plans)
    }

    pub fn record_branch_protection_worker_report(
        &mut self,
        report: &BranchProtectionWorkerReport,
    ) -> MindResult<()> {
        report.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO branch_protection_worker_reports (report_id, worker_plan_id, repository, branch, status, report_hash, report_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![report.report_id.to_string(), report.worker_plan_id.to_string(), &report.repository, &report.branch, format!("{:?}", report.status), &report.report_hash, serde_json::to_string(report)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn branch_protection_worker_reports(
        &self,
    ) -> MindResult<Vec<BranchProtectionWorkerReport>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT report_json FROM branch_protection_worker_reports ORDER BY executed_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut reports = Vec::new();
        for row in rows {
            let report =
                serde_json::from_str::<BranchProtectionWorkerReport>(&row.map_err(sqlite_error)?)?;
            report.verify()?;
            reports.push(report);
        }
        Ok(reports)
    }

    pub fn record_kubernetes_dry_run_execution_request(
        &mut self,
        request: &KubernetesDryRunExecutionRequest,
    ) -> MindResult<()> {
        request.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_dry_run_execution_requests (request_id, plan_id, namespace, context_name, request_hash, request_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![request.request_id.to_string(), request.plan_id.to_string(), &request.namespace, &request.context_name, &request.request_hash, serde_json::to_string(request)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_dry_run_execution_requests(
        &self,
    ) -> MindResult<Vec<KubernetesDryRunExecutionRequest>> {
        let mut statement = self.connection.prepare("SELECT request_json FROM kubernetes_dry_run_execution_requests ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut requests = Vec::new();
        for row in rows {
            let request = serde_json::from_str::<KubernetesDryRunExecutionRequest>(
                &row.map_err(sqlite_error)?,
            )?;
            request.verify()?;
            requests.push(request);
        }
        Ok(requests)
    }

    pub fn record_kubernetes_dry_run_execution_receipt(
        &mut self,
        receipt: &KubernetesDryRunExecutionReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO kubernetes_dry_run_execution_receipts (receipt_id, request_id, plan_id, namespace, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![receipt.receipt_id.to_string(), receipt.request_id.to_string(), receipt.plan_id.to_string(), &receipt.namespace, format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn kubernetes_dry_run_execution_receipts(
        &self,
    ) -> MindResult<Vec<KubernetesDryRunExecutionReceipt>> {
        let mut statement = self.connection.prepare("SELECT receipt_json FROM kubernetes_dry_run_execution_receipts ORDER BY executed_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            let receipt = serde_json::from_str::<KubernetesDryRunExecutionReceipt>(
                &row.map_err(sqlite_error)?,
            )?;
            receipt.verify()?;
            receipts.push(receipt);
        }
        Ok(receipts)
    }

    pub fn record_waiver_notification_plan(
        &mut self,
        plan: &WaiverNotificationPlan,
    ) -> MindResult<()> {
        plan.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO waiver_notification_plans (notification_plan_id, assignment_plan_id, review_id, proposal_id, channel, plan_hash, plan_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![plan.notification_plan_id.to_string(), plan.assignment_plan_id.to_string(), plan.review_id.to_string(), plan.proposal_id.to_string(), format!("{:?}", plan.channel), &plan.plan_hash, serde_json::to_string(plan)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn waiver_notification_plans(&self) -> MindResult<Vec<WaiverNotificationPlan>> {
        let mut statement = self
            .connection
            .prepare("SELECT plan_json FROM waiver_notification_plans ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut plans = Vec::new();
        for row in rows {
            let plan = serde_json::from_str::<WaiverNotificationPlan>(&row.map_err(sqlite_error)?)?;
            plan.verify()?;
            plans.push(plan);
        }
        Ok(plans)
    }

    pub fn record_waiver_notification_receipt(
        &mut self,
        receipt: &WaiverNotificationReceipt,
    ) -> MindResult<()> {
        receipt.verify()?;
        self.connection.execute(r#"
            INSERT OR REPLACE INTO waiver_notification_receipts (receipt_id, notification_plan_id, assignment_plan_id, channel, status, receipt_hash, receipt_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![receipt.receipt_id.to_string(), receipt.notification_plan_id.to_string(), receipt.assignment_plan_id.to_string(), format!("{:?}", receipt.channel), format!("{:?}", receipt.status), &receipt.receipt_hash, serde_json::to_string(receipt)?]).map_err(sqlite_error)?;
        Ok(())
    }

    pub fn waiver_notification_receipts(&self) -> MindResult<Vec<WaiverNotificationReceipt>> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT receipt_json FROM waiver_notification_receipts ORDER BY delivered_at ASC",
            )
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut receipts = Vec::new();
        for row in rows {
            let receipt =
                serde_json::from_str::<WaiverNotificationReceipt>(&row.map_err(sqlite_error)?)?;
            receipt.verify()?;
            receipts.push(receipt);
        }
        Ok(receipts)
    }

    pub fn consensus_memberships(&self) -> MindResult<Vec<ConsensusMembership>> {
        let mut statement = self
            .connection
            .prepare("SELECT membership_json FROM consensus_memberships ORDER BY created_at ASC")
            .map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut memberships = Vec::new();
        for row in rows {
            memberships.push(serde_json::from_str::<ConsensusMembership>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(memberships)
    }
}

impl AppendOnlyEventStore for SqliteEventStore {
    fn append(&mut self, commit: Commit) -> MindResult<EventRecord> {
        validate_commit_for_append(&commit, self.signature_requirement)?;
        let tx = self.connection.transaction().map_err(sqlite_error)?;
        let mind_id = commit.mind_id.to_string();
        let prior: Option<(i64, String)> = tx.query_row(
            "SELECT sequence, record_hash FROM mind_events WHERE mind_id = ?1 ORDER BY sequence DESC LIMIT 1",
            params![mind_id],
            |row| Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?)),
        ).optional().map_err(sqlite_error)?;
        let sequence = prior
            .as_ref()
            .map_or(1_u64, |(sequence, _)| (*sequence as u64) + 1);
        let previous_record_hash = prior.map(|(_, hash)| hash);
        let record = EventRecord::new(sequence, previous_record_hash, commit)?;
        let record_json = serde_json::to_string(&record)?;
        let previous_record_hash = record.previous_record_hash.as_deref();
        tx.execute(r#"
            INSERT INTO mind_events (mind_id, sequence, commit_id, previous_record_hash, record_hash, record_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
        "#, params![record.mind_id.to_string(), record.sequence as i64, record.commit_id.to_string(), previous_record_hash, &record.record_hash, &record_json]).map_err(sqlite_error)?;
        tx.commit().map_err(sqlite_error)?;
        Ok(record)
    }

    fn records_for_mind(&self, mind_id: MindId) -> MindResult<Vec<EventRecord>> {
        let mind_id = mind_id.to_string();
        let args: [&dyn rusqlite::ToSql; 1] = [&mind_id];
        self.read_records(
            "SELECT record_json FROM mind_events WHERE mind_id = ?1 ORDER BY sequence ASC",
            &args,
        )
    }

    fn all_records(&self) -> MindResult<Vec<EventRecord>> {
        let args: [&dyn rusqlite::ToSql; 0] = [];
        self.read_records(
            "SELECT record_json FROM mind_events ORDER BY mind_id ASC, sequence ASC",
            &args,
        )
    }

    fn signature_requirement(&self) -> SignatureRequirement {
        self.signature_requirement
    }
}

impl ReplicatedEventStore for SqliteEventStore {
    fn append_replicated_records(&mut self, records: Vec<EventRecord>) -> MindResult<usize> {
        if records.is_empty() {
            return Ok(0);
        }
        let mind_id = records[0].mind_id;
        if records.iter().any(|record| record.mind_id != mind_id) {
            return Err(MindError::DistributedAppendRejected {
                reason: "replicated records contain multiple mind ids".to_owned(),
            });
        }
        let prior_records = self.records_for_mind(mind_id)?;
        let expected_sequence = prior_records.last().map_or(1, |record| record.sequence + 1);
        let expected_previous_hash = prior_records
            .last()
            .map(|record| record.record_hash.clone());
        verify_record_tail_with_signatures(
            &records,
            expected_sequence,
            expected_previous_hash,
            self.signature_requirement,
        )?;
        let tx = self.connection.transaction().map_err(sqlite_error)?;
        for record in &records {
            let previous_record_hash = record.previous_record_hash.as_deref();
            let record_json = serde_json::to_string(record)?;
            tx.execute(r#"
                INSERT INTO mind_events (mind_id, sequence, commit_id, previous_record_hash, record_hash, record_json)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6)
            "#, params![
                record.mind_id.to_string(),
                record.sequence as i64,
                record.commit_id.to_string(),
                previous_record_hash,
                &record.record_hash,
                &record_json,
            ]).map_err(sqlite_error)?;
        }
        tx.commit().map_err(sqlite_error)?;
        Ok(records.len())
    }
}

impl SnapshotStore for SqliteEventStore {
    fn save_snapshot(&mut self, snapshot: SnapshotRecord) -> MindResult<SnapshotRecord> {
        snapshot.verify()?;
        let tx = self.connection.transaction().map_err(sqlite_error)?;
        let latest_commit_id = snapshot.latest_commit_id.map(|id| id.to_string());
        let snapshot_json = serde_json::to_string(&snapshot)?;
        tx.execute(r#"
            INSERT INTO mind_snapshots (mind_id, after_sequence, snapshot_id, latest_commit_id, after_record_hash, snapshot_hash, snapshot_json)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
        "#, params![
            snapshot.mind_id.to_string(),
            snapshot.after_sequence as i64,
            snapshot.snapshot_id.to_string(),
            latest_commit_id.as_deref(),
            snapshot.after_record_hash.as_deref(),
            &snapshot.snapshot_hash,
            &snapshot_json,
        ]).map_err(sqlite_error)?;
        tx.commit().map_err(sqlite_error)?;
        Ok(snapshot)
    }

    fn latest_snapshot_for_mind(&self, mind_id: MindId) -> MindResult<Option<SnapshotRecord>> {
        let mind_id = mind_id.to_string();
        let mut statement = self.connection.prepare(
            "SELECT snapshot_json FROM mind_snapshots WHERE mind_id = ?1 ORDER BY after_sequence DESC, created_at DESC LIMIT 1",
        ).map_err(sqlite_error)?;
        let snapshot_json: Option<String> = statement
            .query_row(params![mind_id], |row| row.get(0))
            .optional()
            .map_err(sqlite_error)?;
        match snapshot_json {
            Some(json) => {
                let snapshot = serde_json::from_str::<SnapshotRecord>(&json)?;
                snapshot.verify()?;
                Ok(Some(snapshot))
            }
            None => Ok(None),
        }
    }

    fn snapshots_for_mind(&self, mind_id: MindId) -> MindResult<Vec<SnapshotRecord>> {
        let mind_id = mind_id.to_string();
        let args: [&dyn rusqlite::ToSql; 1] = [&mind_id];
        self.read_snapshots("SELECT snapshot_json FROM mind_snapshots WHERE mind_id = ?1 ORDER BY after_sequence ASC, created_at ASC", &args)
    }
}

impl CompactingSnapshotStore for SqliteEventStore {
    fn delete_snapshot(&mut self, mind_id: MindId, snapshot_id: EventId) -> MindResult<bool> {
        let changed = self
            .connection
            .execute(
                "DELETE FROM mind_snapshots WHERE mind_id = ?1 AND snapshot_id = ?2",
                params![mind_id.to_string(), snapshot_id.to_string()],
            )
            .map_err(sqlite_error)?;
        Ok(changed > 0)
    }
}

impl ObservabilitySink for SqliteEventStore {
    fn record_trace(&mut self, event: ObservabilityEvent) -> MindResult<()> {
        self.connection
            .execute(
                r#"
            INSERT OR REPLACE INTO observability_events (event_id, event_kind, event_json)
            VALUES (?1, 'trace', ?2)
        "#,
                params![
                    event.trace.span_id.to_string(),
                    serde_json::to_string(&event)?
                ],
            )
            .map_err(sqlite_error)?;
        Ok(())
    }

    fn record_audit(&mut self, event: AuditEvent) -> MindResult<()> {
        self.connection
            .execute(
                r#"
            INSERT OR REPLACE INTO observability_events (event_id, event_kind, event_json)
            VALUES (?1, 'audit', ?2)
        "#,
                params![event.event_id.to_string(), serde_json::to_string(&event)?],
            )
            .map_err(sqlite_error)?;
        Ok(())
    }

    fn trace_events(&self) -> MindResult<Vec<ObservabilityEvent>> {
        let mut statement = self.connection.prepare("SELECT event_json FROM observability_events WHERE event_kind = 'trace' ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut events = Vec::new();
        for row in rows {
            events.push(serde_json::from_str::<ObservabilityEvent>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(events)
    }

    fn audit_events(&self) -> MindResult<Vec<AuditEvent>> {
        let mut statement = self.connection.prepare("SELECT event_json FROM observability_events WHERE event_kind = 'audit' ORDER BY created_at ASC").map_err(sqlite_error)?;
        let rows = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(sqlite_error)?;
        let mut events = Vec::new();
        for row in rows {
            events.push(serde_json::from_str::<AuditEvent>(
                &row.map_err(sqlite_error)?,
            )?);
        }
        Ok(events)
    }
}

fn sqlite_schema_migrations() -> MindResult<Vec<SchemaMigration>> {
    Ok(vec![
        SchemaMigration::new(1, "create_mind_events", vec![r#"
            CREATE TABLE IF NOT EXISTS mind_events (
                mind_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                commit_id TEXT NOT NULL,
                previous_record_hash TEXT,
                record_hash TEXT NOT NULL,
                record_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (mind_id, sequence),
                UNIQUE (mind_id, commit_id),
                UNIQUE (mind_id, record_hash)
            );
        "#.to_owned()])?,
        SchemaMigration::new(2, "index_mind_events", vec![r#"
            CREATE INDEX IF NOT EXISTS idx_mind_events_mind_id_sequence ON mind_events (mind_id, sequence);
        "#.to_owned()])?,
        SchemaMigration::new(3, "create_mind_snapshots", vec![r#"
            CREATE TABLE IF NOT EXISTS mind_snapshots (
                mind_id TEXT NOT NULL,
                after_sequence INTEGER NOT NULL,
                snapshot_id TEXT NOT NULL,
                latest_commit_id TEXT,
                after_record_hash TEXT,
                snapshot_hash TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (mind_id, after_sequence, snapshot_id),
                UNIQUE (mind_id, snapshot_id),
                UNIQUE (mind_id, snapshot_hash)
            );
        "#.to_owned()])?,
        SchemaMigration::new(4, "index_mind_snapshots", vec![r#"
            CREATE INDEX IF NOT EXISTS idx_mind_snapshots_mind_id_sequence ON mind_snapshots (mind_id, after_sequence);
        "#.to_owned()])?,
        SchemaMigration::new(5, "create_observability_events", vec![r#"
            CREATE TABLE IF NOT EXISTS observability_events (
                event_id TEXT PRIMARY KEY,
                event_kind TEXT NOT NULL,
                event_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_observability_events_kind ON observability_events (event_kind, created_at);
        "#.to_owned()])?,
        SchemaMigration::new(6, "create_backup_manifests", vec![r#"
            CREATE TABLE IF NOT EXISTS backup_manifests (
                backup_id TEXT PRIMARY KEY,
                mind_id TEXT,
                backup_hash TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_backup_manifests_mind_id_created ON backup_manifests (mind_id, created_at);
        "#.to_owned()])?,
        SchemaMigration::new(7, "create_identity_signing_object_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS identity_provider_bindings (
                binding_id TEXT PRIMARY KEY,
                source_kind TEXT NOT NULL,
                issuer TEXT,
                subject TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                binding_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_identity_provider_bindings_principal ON identity_provider_bindings (principal_id, created_at);
            CREATE TABLE IF NOT EXISTS signing_key_descriptors (
                key_id TEXT PRIMARY KEY,
                backend TEXT NOT NULL,
                state TEXT NOT NULL,
                descriptor_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS backup_object_receipts (
                receipt_id TEXT PRIMARY KEY,
                backup_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                backup_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_backup_object_receipts_backup_id ON backup_object_receipts (backup_id, created_at);
        "#.to_owned()])?,
        SchemaMigration::new(8, "create_direct_identity_managed_signing_cloud_replication_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS oidc_jwks_verifier_configs (
                issuer TEXT PRIMARY KEY,
                config_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS managed_signing_requests (
                request_id TEXT PRIMARY KEY,
                commit_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                key_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                request_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_managed_signing_requests_commit ON managed_signing_requests (commit_id, created_at);
            CREATE TABLE IF NOT EXISTS cloud_object_backup_plans (
                plan_id TEXT PRIMARY KEY,
                backup_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                bucket TEXT NOT NULL,
                object_key TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cloud_object_backup_plans_backup ON cloud_object_backup_plans (backup_id, created_at);
            CREATE TABLE IF NOT EXISTS replication_batches (
                batch_id TEXT PRIMARY KEY,
                leader_id TEXT NOT NULL,
                mind_id TEXT NOT NULL,
                from_sequence INTEGER NOT NULL,
                batch_hash TEXT NOT NULL,
                batch_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_replication_batches_mind_sequence ON replication_batches (mind_id, from_sequence);
            CREATE TABLE IF NOT EXISTS replication_acks (
                ack_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                follower_id TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                ack_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_replication_acks_batch ON replication_acks (batch_id, created_at);
        "#.to_owned()])?,
        SchemaMigration::new(9, "create_discovery_execution_transfer_replication_consensus_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS oidc_jwks_cache (
                issuer TEXT PRIMARY KEY,
                jwks_uri TEXT NOT NULL,
                jwks_hash TEXT NOT NULL,
                key_count INTEGER NOT NULL,
                cache_json TEXT NOT NULL,
                cached_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS signing_execution_receipts (
                receipt_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                key_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_signing_execution_receipts_request ON signing_execution_receipts (request_id, created_at);
            CREATE TABLE IF NOT EXISTS cloud_transfer_receipts (
                receipt_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                bucket TEXT NOT NULL,
                object_key TEXT NOT NULL,
                body_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cloud_transfer_receipts_target ON cloud_transfer_receipts (bucket, object_key);
            CREATE TABLE IF NOT EXISTS replication_inbox (
                envelope_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                mind_id TEXT NOT NULL,
                from_sequence INTEGER NOT NULL,
                body_hash TEXT NOT NULL,
                envelope_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_replication_inbox_mind_sequence ON replication_inbox (mind_id, from_sequence);
            CREATE TABLE IF NOT EXISTS consensus_memberships (
                configuration_id TEXT PRIMARY KEY,
                cluster_id TEXT NOT NULL,
                term INTEGER NOT NULL,
                leader_id TEXT,
                membership_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_memberships_cluster_term ON consensus_memberships (cluster_id, term);
        "#.to_owned()])?,
        SchemaMigration::new(10, "create_live_connector_and_governance_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS live_oidc_refreshes (
                refresh_id TEXT PRIMARY KEY,
                issuer TEXT NOT NULL,
                jwks_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_live_oidc_refreshes_issuer ON live_oidc_refreshes (issuer, created_at);
            CREATE TABLE IF NOT EXISTS cloud_signed_url_receipts (
                receipt_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                bucket TEXT NOT NULL,
                object_key TEXT NOT NULL,
                body_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cloud_signed_url_receipts_target ON cloud_signed_url_receipts (bucket, object_key);
            CREATE TABLE IF NOT EXISTS replication_delivery_receipts (
                delivery_id TEXT PRIMARY KEY,
                envelope_id TEXT NOT NULL,
                endpoint_node_id TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_replication_delivery_receipts_envelope ON replication_delivery_receipts (envelope_id, created_at);
            CREATE TABLE IF NOT EXISTS consensus_change_judgments (
                proposal_id TEXT PRIMARY KEY,
                cluster_id TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                before_configuration_id TEXT NOT NULL,
                after_configuration_id TEXT NOT NULL,
                judgment_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_change_judgments_cluster ON consensus_change_judgments (cluster_id, created_at);
        "#.to_owned()])?,
        SchemaMigration::new(11, "create_scheduler_provider_consensus_commit_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                job_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                due_at TEXT NOT NULL,
                not_before TEXT NOT NULL,
                attempt_count INTEGER NOT NULL,
                idempotency_key TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                job_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_status_due ON scheduled_jobs (status, due_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_scheduled_jobs_idempotency ON scheduled_jobs (idempotency_key);
            CREATE TABLE IF NOT EXISTS provider_execution_receipts (
                receipt_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                adapter TEXT NOT NULL,
                command_kind TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_provider_execution_receipts_execution ON provider_execution_receipts (execution_id, completed_at);
            CREATE TABLE IF NOT EXISTS consensus_commit_certificates (
                certificate_id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL,
                cluster_id TEXT NOT NULL,
                term INTEGER NOT NULL,
                committed INTEGER NOT NULL,
                entry_hash TEXT NOT NULL,
                certificate_json TEXT NOT NULL,
                certified_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_commit_certificates_cluster_term ON consensus_commit_certificates (cluster_id, term);
        "#.to_owned()])?,

        SchemaMigration::new(12, "create_worker_scheduler_provider_sdk_consensus_apply_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS scheduler_leases (
                lease_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                status TEXT NOT NULL,
                lease_expires_at TEXT NOT NULL,
                lease_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_scheduler_leases_job_worker ON scheduler_leases (job_id, worker_id, created_at);
            CREATE TABLE IF NOT EXISTS worker_run_reports (
                run_id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                claimed_count INTEGER NOT NULL,
                succeeded_count INTEGER NOT NULL,
                failed_count INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_worker_run_reports_worker ON worker_run_reports (worker_id, started_at);
            CREATE TABLE IF NOT EXISTS provider_sdk_receipts (
                receipt_id TEXT PRIMARY KEY,
                invocation_id TEXT NOT NULL,
                sdk TEXT NOT NULL,
                command_kind TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_provider_sdk_receipts_invocation ON provider_sdk_receipts (invocation_id, completed_at);
            CREATE TABLE IF NOT EXISTS consensus_apply_reports (
                apply_id TEXT PRIMARY KEY,
                certificate_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                cluster_id TEXT NOT NULL,
                operation_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                report_json TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_apply_reports_cluster ON consensus_apply_reports (cluster_id, applied_at);
        "#.to_owned()])?,
        SchemaMigration::new(13, "create_worker_daemon_provider_feature_consensus_idempotency_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS worker_daemon_ticks (
                tick_id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                tick_index INTEGER NOT NULL,
                claimed_count INTEGER NOT NULL,
                succeeded_count INTEGER NOT NULL,
                failed_count INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_worker_daemon_ticks_worker ON worker_daemon_ticks (worker_id, started_at);
            CREATE TABLE IF NOT EXISTS provider_sdk_feature_matrices (
                matrix_id TEXT PRIMARY KEY,
                enabled_count INTEGER NOT NULL,
                native_count INTEGER NOT NULL,
                matrix_json TEXT NOT NULL,
                generated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS consensus_apply_idempotency (
                decision_id TEXT PRIMARY KEY,
                certificate_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                status TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                checked_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_apply_idempotency_entry ON consensus_apply_idempotency (entry_id, checked_at);
            CREATE TABLE IF NOT EXISTS consensus_log_compactions (
                compaction_id TEXT PRIMARY KEY,
                cluster_id TEXT NOT NULL,
                compacted_count INTEGER NOT NULL,
                decision_json TEXT NOT NULL,
                decided_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_log_compactions_cluster ON consensus_log_compactions (cluster_id, decided_at);
        "#.to_owned()])?,
        SchemaMigration::new(14, "create_job_receipt_native_provider_physical_compaction_distributed_lease_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS job_execution_receipts (
                receipt_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_job_execution_receipts_job ON job_execution_receipts (job_id, completed_at);
            CREATE TABLE IF NOT EXISTS native_provider_adapter_reports (
                report_id TEXT PRIMARY KEY,
                invocation_id TEXT NOT NULL,
                sdk TEXT NOT NULL,
                command_kind TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                request_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_native_provider_adapter_reports_sdk ON native_provider_adapter_reports (sdk, evaluated_at);
            CREATE TABLE IF NOT EXISTS distributed_lease_claim_receipts (
                receipt_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                job_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                issued_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_distributed_lease_claim_receipts_job ON distributed_lease_claim_receipts (job_id, issued_at);
            CREATE TABLE IF NOT EXISTS consensus_physical_compactions (
                report_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                cluster_id TEXT NOT NULL,
                status TEXT NOT NULL,
                deleted_certificate_count INTEGER NOT NULL,
                backup_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                compacted_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_physical_compactions_cluster ON consensus_physical_compactions (cluster_id, compacted_at);
        "#.to_owned()])?,
        SchemaMigration::new(15, "create_domain_job_lease_native_retention_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS domain_job_execution_reports (
                report_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_domain_job_execution_reports_job ON domain_job_execution_reports (job_id, executed_at);
            CREATE TABLE IF NOT EXISTS distributed_lease_adapter_reports (
                report_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                mode TEXT NOT NULL,
                job_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_distributed_lease_adapter_reports_job ON distributed_lease_adapter_reports (job_id, evaluated_at);
            CREATE TABLE IF NOT EXISTS native_provider_execution_receipts (
                receipt_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                sdk TEXT NOT NULL,
                command_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_native_provider_execution_receipts_execution ON native_provider_execution_receipts (execution_id, executed_at);
            CREATE TABLE IF NOT EXISTS consensus_retention_enforcements (
                report_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                cluster_id TEXT NOT NULL,
                status TEXT NOT NULL,
                deleted_certificate_count INTEGER NOT NULL,
                deleted_apply_report_count INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                enforced_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_retention_enforcements_cluster ON consensus_retention_enforcements (cluster_id, enforced_at);
        "#.to_owned()])?,
        SchemaMigration::new(16, "create_live_executors_lease_provider_retention_approval_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS live_domain_job_execution_reports (
                report_id TEXT PRIMARY KEY,
                domain_report_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                evidence_count INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_live_domain_job_execution_reports_job ON live_domain_job_execution_reports (job_id, executed_at);
            CREATE TABLE IF NOT EXISTS distributed_lease_execution_receipts (
                receipt_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                job_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                receipt_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_distributed_lease_execution_receipts_job ON distributed_lease_execution_receipts (job_id, executed_at);
            CREATE TABLE IF NOT EXISTS provider_sdk_execution_reports (
                report_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                execution_id TEXT NOT NULL,
                sdk TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_provider_sdk_execution_reports_execution ON provider_sdk_execution_reports (execution_id, executed_at);
            CREATE TABLE IF NOT EXISTS consensus_retention_approval_proposals (
                proposal_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                cluster_id TEXT NOT NULL,
                proposal_json TEXT NOT NULL,
                proposed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_retention_approval_proposals_cluster ON consensus_retention_approval_proposals (cluster_id, proposed_at);
            CREATE TABLE IF NOT EXISTS consensus_retention_approval_votes (
                vote_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                voter_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                vote_json TEXT NOT NULL,
                voted_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_retention_approval_votes_proposal ON consensus_retention_approval_votes (proposal_id, voted_at);
            CREATE TABLE IF NOT EXISTS consensus_retention_approval_certificates (
                certificate_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                cluster_id TEXT NOT NULL,
                status TEXT NOT NULL,
                approvals INTEGER NOT NULL,
                rejections INTEGER NOT NULL,
                certificate_json TEXT NOT NULL,
                certified_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_consensus_retention_approval_certificates_cluster ON consensus_retention_approval_certificates (cluster_id, certified_at);
        "#.to_owned()])?,
        SchemaMigration::new(17, "create_creative_engineering_readiness_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS creative_engineering_reports (
                report_id TEXT PRIMARY KEY,
                report_hash TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                suggestion_count INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                generated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_creative_engineering_reports_generated ON creative_engineering_reports (generated_at);
            CREATE TABLE IF NOT EXISTS chaos_rehearsal_plans (
                plan_id TEXT PRIMARY KEY,
                rehearsal_hash TEXT NOT NULL,
                mind_id TEXT,
                experiment_count INTEGER NOT NULL,
                plan_json TEXT NOT NULL,
                generated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_chaos_rehearsal_plans_mind ON chaos_rehearsal_plans (mind_id, generated_at);
            CREATE TABLE IF NOT EXISTS invariant_fuzz_runs (
                run_id TEXT PRIMARY KEY,
                target_mind_id TEXT NOT NULL,
                case_bank_hash TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                expected_reject_count INTEGER NOT NULL,
                run_json TEXT NOT NULL,
                generated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_invariant_fuzz_runs_mind ON invariant_fuzz_runs (target_mind_id, generated_at);
            CREATE TABLE IF NOT EXISTS production_readiness_gates (
                gate_id TEXT PRIMARY KEY,
                creative_report_id TEXT NOT NULL,
                status TEXT NOT NULL,
                gate_hash TEXT NOT NULL,
                blocker_count INTEGER NOT NULL,
                gate_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_production_readiness_gates_status ON production_readiness_gates (status, evaluated_at);
        "#.to_owned()])?,
        SchemaMigration::new(18, "create_executable_readiness_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS chaos_execution_runs (
                run_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                status TEXT NOT NULL,
                result_count INTEGER NOT NULL,
                run_hash TEXT NOT NULL,
                run_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_chaos_execution_runs_plan ON chaos_execution_runs (plan_id, executed_at);
            CREATE TABLE IF NOT EXISTS invariant_fuzz_execution_reports (
                execution_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                target_mind_id TEXT NOT NULL,
                passed_count INTEGER NOT NULL,
                failed_count INTEGER NOT NULL,
                execution_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_invariant_fuzz_execution_reports_run ON invariant_fuzz_execution_reports (run_id, executed_at);
            CREATE TABLE IF NOT EXISTS readiness_waiver_proposals (
                proposal_id TEXT PRIMARY KEY,
                gate_id TEXT NOT NULL,
                risk_owner TEXT NOT NULL,
                proposal_hash TEXT NOT NULL,
                proposal_json TEXT NOT NULL,
                proposed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_readiness_waiver_proposals_gate ON readiness_waiver_proposals (gate_id, proposed_at);
            CREATE TABLE IF NOT EXISTS readiness_waiver_votes (
                vote_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                voter TEXT NOT NULL,
                decision TEXT NOT NULL,
                vote_json TEXT NOT NULL,
                voted_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_readiness_waiver_votes_proposal ON readiness_waiver_votes (proposal_id, voted_at);
            CREATE TABLE IF NOT EXISTS readiness_waiver_certificates (
                certificate_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                gate_id TEXT NOT NULL,
                status TEXT NOT NULL,
                certificate_hash TEXT NOT NULL,
                certificate_json TEXT NOT NULL,
                certified_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_readiness_waiver_certificates_gate ON readiness_waiver_certificates (gate_id, certified_at);
            CREATE TABLE IF NOT EXISTS readiness_waiver_application_reports (
                report_id TEXT PRIMARY KEY,
                gate_id TEXT NOT NULL,
                effective_status TEXT NOT NULL,
                report_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_readiness_waiver_application_reports_gate ON readiness_waiver_application_reports (gate_id, evaluated_at);
            CREATE TABLE IF NOT EXISTS engineering_implementation_job_plans (
                plan_id TEXT PRIMARY KEY,
                source_report_id TEXT NOT NULL,
                job_count INTEGER NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_engineering_implementation_job_plans_source ON engineering_implementation_job_plans (source_report_id, created_at);
        "#.to_owned()])?,

        SchemaMigration::new(19, "create_enforced_readiness_engineering_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS staging_chaos_run_reports (
                staging_run_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                environment_name TEXT NOT NULL,
                status TEXT NOT NULL,
                report_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_staging_chaos_run_reports_plan ON staging_chaos_run_reports (plan_id, executed_at);
            CREATE TABLE IF NOT EXISTS mandatory_ci_gate_reports (
                ci_gate_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                report_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_mandatory_ci_gate_reports_status ON mandatory_ci_gate_reports (status, evaluated_at);
            CREATE TABLE IF NOT EXISTS multi_operator_waiver_certificates (
                certificate_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                gate_id TEXT NOT NULL,
                status TEXT NOT NULL,
                certificate_hash TEXT NOT NULL,
                certificate_json TEXT NOT NULL,
                certified_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_multi_operator_waiver_certificates_gate ON multi_operator_waiver_certificates (gate_id, certified_at);
            CREATE TABLE IF NOT EXISTS implementation_job_evidence_bundles (
                bundle_id TEXT PRIMARY KEY,
                implementation_job_id TEXT NOT NULL,
                scheduled_job_id TEXT NOT NULL,
                status TEXT NOT NULL,
                bundle_hash TEXT NOT NULL,
                bundle_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_implementation_job_evidence_bundles_job ON implementation_job_evidence_bundles (implementation_job_id, evaluated_at);
            CREATE TABLE IF NOT EXISTS implementation_evidence_automation_plans (
                automation_plan_id TEXT PRIMARY KEY,
                implementation_plan_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                target_count INTEGER NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_implementation_evidence_automation_plans_impl ON implementation_evidence_automation_plans (implementation_plan_id, created_at);
        "#.to_owned()])?,
        SchemaMigration::new(20, "create_github_branch_chaos_waiver_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS github_readiness_evidence_bundles (
                bundle_id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                pull_request_number INTEGER NOT NULL,
                head_sha TEXT NOT NULL,
                status TEXT NOT NULL,
                bundle_hash TEXT NOT NULL,
                bundle_json TEXT NOT NULL,
                collected_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_github_readiness_evidence_repo_pr ON github_readiness_evidence_bundles (repository, pull_request_number, collected_at);
            CREATE TABLE IF NOT EXISTS branch_protection_policies (
                policy_id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL,
                policy_hash TEXT NOT NULL,
                policy_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_branch_protection_policies_repo_branch ON branch_protection_policies (repository, branch, created_at);
            CREATE TABLE IF NOT EXISTS branch_protection_evaluation_reports (
                report_id TEXT PRIMARY KEY,
                policy_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL,
                compliant INTEGER NOT NULL,
                report_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_branch_protection_eval_repo_branch ON branch_protection_evaluation_reports (repository, branch, evaluated_at);
            CREATE TABLE IF NOT EXISTS live_staging_chaos_adapter_plans (
                adapter_plan_id TEXT PRIMARY KEY,
                rehearsal_plan_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                mode TEXT NOT NULL,
                namespace TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_live_staging_chaos_adapter_plans_rehearsal ON live_staging_chaos_adapter_plans (rehearsal_plan_id, created_at);
            CREATE TABLE IF NOT EXISTS live_staging_chaos_adapter_receipts (
                receipt_id TEXT PRIMARY KEY,
                adapter_plan_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_live_staging_chaos_adapter_receipts_plan ON live_staging_chaos_adapter_receipts (adapter_plan_id, executed_at);
            CREATE TABLE IF NOT EXISTS waiver_review_certificates (
                certificate_id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL,
                proposal_id TEXT NOT NULL,
                status TEXT NOT NULL,
                certificate_hash TEXT NOT NULL,
                certificate_json TEXT NOT NULL,
                certified_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_waiver_review_certificates_proposal ON waiver_review_certificates (proposal_id, certified_at);
        "#.to_owned()])?,
        SchemaMigration::new(21, "create_github_kubernetes_reconcile_assignment_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS github_check_run_write_plans (
                plan_id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                head_sha TEXT NOT NULL,
                name TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_github_check_run_write_plans_repo_sha ON github_check_run_write_plans (repository, head_sha, created_at);
            CREATE TABLE IF NOT EXISTS github_check_run_write_receipts (
                receipt_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                head_sha TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                written_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_github_check_run_write_receipts_plan ON github_check_run_write_receipts (plan_id, written_at);
            CREATE TABLE IF NOT EXISTS branch_protection_reconcile_plans (
                reconcile_id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_branch_protection_reconcile_plans_repo_branch ON branch_protection_reconcile_plans (repository, branch, created_at);
            CREATE TABLE IF NOT EXISTS branch_protection_reconcile_receipts (
                receipt_id TEXT PRIMARY KEY,
                reconcile_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                reconciled_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_branch_protection_reconcile_receipts_plan ON branch_protection_reconcile_receipts (reconcile_id, reconciled_at);
            CREATE TABLE IF NOT EXISTS kubernetes_staging_chaos_plans (
                plan_id TEXT PRIMARY KEY,
                rehearsal_plan_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_kubernetes_staging_chaos_plans_rehearsal ON kubernetes_staging_chaos_plans (rehearsal_plan_id, created_at);
            CREATE TABLE IF NOT EXISTS kubernetes_staging_chaos_receipts (
                receipt_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                rehearsal_plan_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_kubernetes_staging_chaos_receipts_plan ON kubernetes_staging_chaos_receipts (plan_id, executed_at);
            CREATE TABLE IF NOT EXISTS waiver_reviewer_assignment_plans (
                assignment_plan_id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL,
                proposal_id TEXT NOT NULL,
                status TEXT NOT NULL,
                assignment_hash TEXT NOT NULL,
                assignment_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_waiver_reviewer_assignment_plans_review ON waiver_reviewer_assignment_plans (review_id, created_at);
            CREATE TABLE IF NOT EXISTS waiver_escalation_certificates (
                certificate_id TEXT PRIMARY KEY,
                assignment_plan_id TEXT NOT NULL,
                review_id TEXT NOT NULL,
                proposal_id TEXT NOT NULL,
                status TEXT NOT NULL,
                certificate_hash TEXT NOT NULL,
                certificate_json TEXT NOT NULL,
                escalated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_waiver_escalation_certificates_review ON waiver_escalation_certificates (review_id, escalated_at);
        "#.to_owned()])?,
        SchemaMigration::new(22, "create_live_action_execution_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS github_app_installation_token_plans (
                plan_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_github_app_installation_token_plans_repo ON github_app_installation_token_plans (repository, created_at);
            CREATE TABLE IF NOT EXISTS github_app_installation_token_receipts (
                receipt_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                issued_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_github_app_installation_token_receipts_plan ON github_app_installation_token_receipts (plan_id, issued_at);
            CREATE TABLE IF NOT EXISTS github_action_execution_plans (
                execution_id TEXT PRIMARY KEY,
                token_plan_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                action_kind TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_github_action_execution_plans_repo ON github_action_execution_plans (repository, created_at);
            CREATE TABLE IF NOT EXISTS github_action_execution_receipts (
                receipt_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                token_receipt_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                action_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_github_action_execution_receipts_execution ON github_action_execution_receipts (execution_id, executed_at);
            CREATE TABLE IF NOT EXISTS branch_protection_worker_plans (
                worker_plan_id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS branch_protection_worker_reports (
                report_id TEXT PRIMARY KEY,
                worker_plan_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL,
                status TEXT NOT NULL,
                report_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS kubernetes_dry_run_execution_requests (
                request_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                context_name TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                request_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS kubernetes_dry_run_execution_receipts (
                receipt_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS waiver_notification_plans (
                notification_plan_id TEXT PRIMARY KEY,
                assignment_plan_id TEXT NOT NULL,
                review_id TEXT NOT NULL,
                proposal_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS waiver_notification_receipts (
                receipt_id TEXT PRIMARY KEY,
                notification_plan_id TEXT NOT NULL,
                assignment_plan_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                delivered_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        "#.to_owned()])?,
        SchemaMigration::new(23, "create_secret_connector_admission_notification_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS secret_access_plans (
                plan_id TEXT PRIMARY KEY,
                backend TEXT NOT NULL,
                key_id TEXT NOT NULL,
                purpose TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_secret_access_plans_backend_key ON secret_access_plans (backend, key_id, created_at);
            CREATE TABLE IF NOT EXISTS secret_access_receipts (
                receipt_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                resolved_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_secret_access_receipts_plan ON secret_access_receipts (plan_id, resolved_at);
            CREATE TABLE IF NOT EXISTS github_app_jwt_plans (
                jwt_plan_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                key_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_github_app_jwt_plans_app ON github_app_jwt_plans (app_id, installation_id, created_at);
            CREATE TABLE IF NOT EXISTS github_app_jwt_receipts (
                receipt_id TEXT PRIMARY KEY,
                jwt_plan_id TEXT NOT NULL,
                secret_receipt_id TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                signed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_github_app_jwt_receipts_plan ON github_app_jwt_receipts (jwt_plan_id, signed_at);
            CREATE TABLE IF NOT EXISTS connector_worker_job_plans (
                connector_plan_id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                action_kind TEXT NOT NULL,
                target TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_connector_worker_job_plans_worker ON connector_worker_job_plans (worker_id, created_at);
            CREATE TABLE IF NOT EXISTS connector_worker_execution_receipts (
                receipt_id TEXT PRIMARY KEY,
                connector_plan_id TEXT NOT NULL,
                action_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_connector_worker_execution_receipts_plan ON connector_worker_execution_receipts (connector_plan_id, executed_at);
            CREATE TABLE IF NOT EXISTS kubernetes_admission_audit_requests (
                audit_request_id TEXT PRIMARY KEY,
                dry_run_request_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                operation TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                request_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS kubernetes_admission_audit_receipts (
                audit_receipt_id TEXT PRIMARY KEY,
                audit_request_id TEXT NOT NULL,
                dry_run_receipt_id TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                captured_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS kubernetes_admission_audit_reports (
                report_id TEXT PRIMARY KEY,
                audit_request_id TEXT NOT NULL,
                audit_receipt_id TEXT NOT NULL,
                status TEXT NOT NULL,
                report_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS waiver_notification_adapter_plans (
                adapter_plan_id TEXT PRIMARY KEY,
                notification_plan_id TEXT NOT NULL,
                adapter_kind TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS waiver_notification_adapter_receipts (
                receipt_id TEXT PRIMARY KEY,
                adapter_plan_id TEXT NOT NULL,
                adapter_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                delivered_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        "#.to_owned()])?,
        SchemaMigration::new(24, "create_live_secret_token_audit_notification_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS live_secret_connector_plans (
                connector_plan_id TEXT PRIMARY KEY,
                access_plan_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                locator_fingerprint TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS live_secret_connector_receipts (
                connector_receipt_id TEXT PRIMARY KEY,
                connector_plan_id TEXT NOT NULL,
                access_receipt_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS github_token_exchange_worker_plans (
                exchange_plan_id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                jwt_receipt_id TEXT NOT NULL,
                secret_connector_receipt_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS github_token_exchange_worker_receipts (
                exchange_receipt_id TEXT PRIMARY KEY,
                exchange_plan_id TEXT NOT NULL,
                token_receipt_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                exchanged_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS kubernetes_audit_log_collector_plans (
                collector_plan_id TEXT PRIMARY KEY,
                audit_report_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS kubernetes_audit_log_collector_reports (
                collector_report_id TEXT PRIMARY KEY,
                collector_plan_id TEXT NOT NULL,
                audit_receipt_id TEXT NOT NULL,
                status TEXT NOT NULL,
                report_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                collected_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS notification_delivery_client_plans (
                client_plan_id TEXT PRIMARY KEY,
                adapter_plan_id TEXT NOT NULL,
                adapter_kind TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS notification_delivery_client_receipts (
                client_receipt_id TEXT PRIMARY KEY,
                client_plan_id TEXT NOT NULL,
                adapter_receipt_id TEXT NOT NULL,
                adapter_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                delivered_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        "#.to_owned()])?,
        SchemaMigration::new(25, "create_connector_orchestration_audit_source_notification_provider_ledgers", vec![r#"
            CREATE TABLE IF NOT EXISTS connector_orchestration_plans (
                orchestration_plan_id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                purpose TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS connector_orchestration_reports (
                orchestration_report_id TEXT PRIMARY KEY,
                orchestration_plan_id TEXT NOT NULL,
                status TEXT NOT NULL,
                report_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS kubernetes_audit_source_adapter_plans (
                source_plan_id TEXT PRIMARY KEY,
                collector_plan_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                namespace TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS kubernetes_audit_source_adapter_receipts (
                source_receipt_id TEXT PRIMARY KEY,
                source_plan_id TEXT NOT NULL,
                collector_report_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                collected_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS notification_provider_delivery_plans (
                provider_plan_id TEXT PRIMARY KEY,
                client_plan_id TEXT NOT NULL,
                provider_kind TEXT NOT NULL,
                mode TEXT NOT NULL,
                plan_hash TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS notification_provider_delivery_receipts (
                provider_receipt_id TEXT PRIMARY KEY,
                provider_plan_id TEXT NOT NULL,
                client_receipt_id TEXT NOT NULL,
                provider_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                delivered_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS action_promotion_gate_reports (
                gate_report_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                report_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        "#.to_owned()])?,
    ])
}

fn sqlite_error(error: rusqlite::Error) -> MindError {
    MindError::Store(error.to_string())
}
