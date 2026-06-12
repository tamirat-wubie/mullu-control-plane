//! Purpose: API error response mapping boundary for the Nested Mind API.
//! Governance scope: causal MindError to HTTP status and JSON error response projection.
//! Dependencies: Axum response primitives, serde JSON response construction, and mind-core error taxonomy.
//! Invariants: every mapped error remains explicit; response body preserves the causal error string.

use super::*;

pub(super) struct ApiError(pub(super) MindError);
impl From<MindError> for ApiError {
    fn from(value: MindError) -> Self {
        Self(value)
    }
}
impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let status = match &self.0 {
            MindError::Unauthorized { .. }
            | MindError::MissingCredentials
            | MindError::InvalidCredentials
            | MindError::Identity(_)
            | MindError::IdentityEvidenceRejected { .. }
            | MindError::IdentityRejected { .. }
            | MindError::IdentityAssertionInvalid { .. }
            | MindError::IdentityTokenExpired { .. }
            | MindError::MtlsSubjectRequired => StatusCode::UNAUTHORIZED,
            MindError::RateLimitExceeded { .. } => StatusCode::TOO_MANY_REQUESTS,
            MindError::RequestBodyTooLarge { .. } => StatusCode::PAYLOAD_TOO_LARGE,
            MindError::Store(_)
            | MindError::Io(_)
            | MindError::Serialization(_)
            | MindError::Observability(_)
            | MindError::Signing(_)
            | MindError::ObjectStore(_) => StatusCode::INTERNAL_SERVER_ERROR,
            _ => StatusCode::BAD_REQUEST,
        };
        (status, Json(json!({"error": self.0.to_string()}))).into_response()
    }
}
