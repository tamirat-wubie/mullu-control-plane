//! Purpose: request safety middleware boundary for the Nested Mind API.
//! Governance scope: request body limits, authentication admission, rate-limit admission, and rejection audit emission.
//! Dependencies: Axum middleware primitives, shared API state, auth configuration, and observability sink adapters.
//! Invariants: request rejection decisions remain explicit; successful requests retain rate-limit response headers.

use super::*;

pub(super) async fn enforce_request_safety(
    State(state): State<AppState>,
    request: Request<Body>,
    next: Next,
) -> Response {
    let content_length = request
        .headers()
        .get(CONTENT_LENGTH)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.parse::<u64>().ok());
    if let Err(error) = state
        .safety
        .read()
        .await
        .reject_if_body_too_large(content_length)
    {
        let _ = state
            .observability
            .write()
            .await
            .record_audit(AuditEvent::new(
                AuditEventKind::RequestRejected,
                "request body rejected by size policy",
            ));
        return ApiError(error).into_response();
    }

    let principal = match state.authn.authenticate(request.headers()) {
        Ok(principal) => principal,
        Err(error) => return ApiError(error).into_response(),
    };
    let key = principal.as_ref().map_or_else(
        || format!("anonymous:{}", request.uri().path()),
        |principal| format!("principal:{}", principal.id),
    );
    let decision = match state.safety.write().await.check(key.clone()) {
        Ok(decision) => decision,
        Err(error) => return ApiError(error).into_response(),
    };
    if !decision.allowed {
        let _ = state.observability.write().await.record_audit(
            AuditEvent::new(
                AuditEventKind::RequestRejected,
                "request rejected by rate limit",
            )
            .with_attribute("key", key)
            .with_attribute("limit", decision.limit.to_string()),
        );
        return ApiError(MindError::RateLimitExceeded {
            key: decision.key,
            limit: decision.limit,
        })
        .into_response();
    }

    let mut response = next.run(request).await;
    if let Ok(value) = HeaderValue::from_str(&decision.remaining.to_string()) {
        response
            .headers_mut()
            .insert("x-ratelimit-remaining", value);
    }
    if let Ok(value) = HeaderValue::from_str(&decision.limit.to_string()) {
        response.headers_mut().insert("x-ratelimit-limit", value);
    }
    if let Ok(value) = HeaderValue::from_str(&decision.reset_at.unix_timestamp().to_string()) {
        response.headers_mut().insert("x-ratelimit-reset", value);
    }
    response
}
