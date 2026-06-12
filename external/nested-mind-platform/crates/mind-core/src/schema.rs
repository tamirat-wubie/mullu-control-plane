use crate::{hash_serializable, MindError, MindResult};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

pub const PLATFORM_SCHEMA_VERSION: u64 = 25;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SchemaMigration {
    pub version: u64,
    pub name: String,
    #[serde(default)]
    pub statements: Vec<String>,
    pub checksum: String,
}

impl SchemaMigration {
    pub fn new(version: u64, name: impl Into<String>, statements: Vec<String>) -> MindResult<Self> {
        let name = name.into();
        let checksum = Self::calculate_checksum(version, &name, &statements)?;
        Ok(Self {
            version,
            name,
            statements,
            checksum,
        })
    }

    pub fn calculate_checksum(
        version: u64,
        name: &str,
        statements: &[String],
    ) -> MindResult<String> {
        hash_serializable(&SchemaMigrationBody {
            version,
            name,
            statements,
        })
    }

    pub fn verify_checksum(&self) -> MindResult<()> {
        let expected = Self::calculate_checksum(self.version, &self.name, &self.statements)?;
        if expected != self.checksum {
            return Err(MindError::SchemaMigrationChecksumMismatch {
                version: self.version,
                expected,
                actual: self.checksum.clone(),
            });
        }
        Ok(())
    }
}

#[derive(Serialize)]
struct SchemaMigrationBody<'a> {
    version: u64,
    name: &'a str,
    statements: &'a [String],
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AppliedSchemaMigration {
    pub version: u64,
    pub name: String,
    pub checksum: String,
    pub applied_at: OffsetDateTime,
}

impl AppliedSchemaMigration {
    #[must_use]
    pub fn from_migration(migration: &SchemaMigration) -> Self {
        Self {
            version: migration.version,
            name: migration.name.clone(),
            checksum: migration.checksum.clone(),
            applied_at: OffsetDateTime::now_utc(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SchemaMigrationPlan {
    pub current_version: u64,
    pub target_version: u64,
    pub migrations: Vec<SchemaMigration>,
}

impl SchemaMigrationPlan {
    pub fn new(current_version: u64, migrations: Vec<SchemaMigration>) -> MindResult<Self> {
        let target_version = migrations
            .last()
            .map_or(current_version, |migration| migration.version);
        let plan = Self {
            current_version,
            target_version,
            migrations,
        };
        plan.verify()?;
        Ok(plan)
    }

    pub fn verify(&self) -> MindResult<()> {
        for (expected, migration) in (self.current_version + 1..).zip(self.migrations.iter()) {
            migration.verify_checksum()?;
            if migration.version < expected {
                return Err(MindError::SchemaMigrationDowngrade {
                    current: expected - 1,
                    attempted: migration.version,
                });
            }
            if migration.version != expected {
                return Err(MindError::SchemaMigrationGap {
                    expected,
                    actual: migration.version,
                });
            }
        }
        Ok(())
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.migrations.is_empty()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SchemaMigrationReport {
    pub current_version_before: u64,
    pub current_version_after: u64,
    pub target_version: u64,
    #[serde(default)]
    pub applied: Vec<AppliedSchemaMigration>,
    pub already_current: bool,
}

impl SchemaMigrationReport {
    #[must_use]
    pub fn new(
        current_version_before: u64,
        current_version_after: u64,
        target_version: u64,
        applied: Vec<AppliedSchemaMigration>,
    ) -> Self {
        Self {
            current_version_before,
            current_version_after,
            target_version,
            already_current: current_version_after >= target_version && applied.is_empty(),
            applied,
        }
    }

    #[must_use]
    pub fn already_current(version: u64) -> Self {
        Self {
            current_version_before: version,
            current_version_after: version,
            target_version: version,
            applied: Vec::new(),
            already_current: true,
        }
    }
}
