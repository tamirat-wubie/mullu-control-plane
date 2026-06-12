use crate::{MindError, MindResult};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::{Duration, OffsetDateTime};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct RequestSafetyConfig {
    pub max_body_bytes: usize,
    pub max_requests_per_window: u32,
    pub window_seconds: u64,
}

impl RequestSafetyConfig {
    #[must_use]
    pub fn new(max_body_bytes: usize, max_requests_per_window: u32, window_seconds: u64) -> Self {
        Self {
            max_body_bytes,
            max_requests_per_window,
            window_seconds,
        }
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.max_body_bytes == 0 {
            return Err(MindError::RequestSafetyPolicyInvalid(
                "max_body_bytes must be greater than zero".to_owned(),
            ));
        }
        if self.max_requests_per_window == 0 {
            return Err(MindError::RequestSafetyPolicyInvalid(
                "max_requests_per_window must be greater than zero".to_owned(),
            ));
        }
        if self.window_seconds == 0 {
            return Err(MindError::RequestSafetyPolicyInvalid(
                "window_seconds must be greater than zero".to_owned(),
            ));
        }
        Ok(())
    }
}

impl Default for RequestSafetyConfig {
    fn default() -> Self {
        Self {
            max_body_bytes: 64 * 1024,
            max_requests_per_window: 60,
            window_seconds: 60,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct RateLimitDecision {
    pub key: String,
    pub allowed: bool,
    pub remaining: u32,
    pub limit: u32,
    pub reset_at: OffsetDateTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
struct RateLimitBucket {
    window_started_at: OffsetDateTime,
    count: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct InMemoryRateLimiter {
    config: RequestSafetyConfig,
    buckets: BTreeMap<String, RateLimitBucket>,
}

impl InMemoryRateLimiter {
    pub fn new(config: RequestSafetyConfig) -> MindResult<Self> {
        config.validate()?;
        Ok(Self {
            config,
            buckets: BTreeMap::new(),
        })
    }

    #[must_use]
    pub fn config(&self) -> &RequestSafetyConfig {
        &self.config
    }

    pub fn check(&mut self, key: impl Into<String>) -> MindResult<RateLimitDecision> {
        self.check_at(key, OffsetDateTime::now_utc())
    }

    pub fn check_at(
        &mut self,
        key: impl Into<String>,
        now: OffsetDateTime,
    ) -> MindResult<RateLimitDecision> {
        let key = key.into();
        let window = Duration::seconds(self.config.window_seconds as i64);
        let bucket = self.buckets.entry(key.clone()).or_insert(RateLimitBucket {
            window_started_at: now,
            count: 0,
        });
        if now - bucket.window_started_at >= window {
            bucket.window_started_at = now;
            bucket.count = 0;
        }
        let reset_at = bucket.window_started_at + window;
        if bucket.count >= self.config.max_requests_per_window {
            return Ok(RateLimitDecision {
                key,
                allowed: false,
                remaining: 0,
                limit: self.config.max_requests_per_window,
                reset_at,
            });
        }
        bucket.count += 1;
        let remaining = self
            .config
            .max_requests_per_window
            .saturating_sub(bucket.count);
        Ok(RateLimitDecision {
            key,
            allowed: true,
            remaining,
            limit: self.config.max_requests_per_window,
            reset_at,
        })
    }

    pub fn reject_if_body_too_large(&self, content_length: Option<u64>) -> MindResult<()> {
        if let Some(length) = content_length {
            if length > self.config.max_body_bytes as u64 {
                return Err(MindError::RequestBodyTooLarge {
                    max: self.config.max_body_bytes as u64,
                    actual: length,
                });
            }
        }
        Ok(())
    }

    pub fn prune_expired(&mut self, now: OffsetDateTime) {
        let window = Duration::seconds(self.config.window_seconds as i64);
        self.buckets
            .retain(|_, bucket| now - bucket.window_started_at < window);
    }
}
