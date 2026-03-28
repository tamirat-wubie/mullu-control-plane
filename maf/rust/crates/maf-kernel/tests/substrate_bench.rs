//! Substrate benchmarks for maf-kernel.
//!
//! Run: cargo test -p maf-kernel --test substrate_bench -- --nocapture

use maf_kernel::*;
use std::time::Instant;

fn build_machine() -> StateMachineSpec {
    StateMachineSpec {
        machine_id: "bench-machine".into(),
        name: "Bench".into(),
        version: "1.0".into(),
        states: (0..100).map(|i| format!("s{}", i)).collect(),
        initial_state: "s0".into(),
        terminal_states: vec!["s99".into()],
        transitions: (0..99)
            .map(|i| TransitionRule {
                from_state: format!("s{}", i),
                to_state: format!("s{}", i + 1),
                action: format!("step_{}", i),
                guard_label: String::new(),
                emits: String::new(),
            })
            .collect(),
    }
}

#[test]
fn bench_is_legal_100_state_machine() {
    let m = build_machine();
    let start = Instant::now();
    let iterations = 10_000;
    for i in 0..iterations {
        let from = format!("s{}", i % 99);
        let to = format!("s{}", (i % 99) + 1);
        let action = format!("step_{}", i % 99);
        let _ = m.is_legal(&from, &to, &action);
    }
    let elapsed = start.elapsed();
    let per_op_ns = elapsed.as_nanos() / iterations as u128;
    eprintln!(
        "is_legal: {} ops in {:?} ({} ns/op)",
        iterations, elapsed, per_op_ns
    );
    assert!(per_op_ns < 100_000, "is_legal too slow: {} ns/op", per_op_ns);
}

#[test]
fn bench_certify_transition() {
    let m = build_machine();
    let guards = vec![GuardVerdict {
        guard_id: "g1".into(),
        passed: true,
        reason: "ok".into(),
    }];
    let start = Instant::now();
    let iterations = 10_000;
    for i in 0..iterations {
        let from = format!("s{}", i % 99);
        let to = format!("s{}", (i % 99) + 1);
        let action = format!("step_{}", i % 99);
        let _ = m.certify_transition(&CertifyParams {
            entity_id: "entity-1",
            from_state: &from,
            to_state: &to,
            action: &action,
            before_state_hash: "hash-before",
            after_state_hash: "hash-after",
            guards: &guards,
            actor_id: "actor",
            reason: "reason",
            causal_parent: "parent",
            timestamp: "2026-03-27T12:00:00Z",
        });
    }
    let elapsed = start.elapsed();
    let per_op_ns = elapsed.as_nanos() / iterations as u128;
    eprintln!(
        "certify_transition: {} ops in {:?} ({} ns/op)",
        iterations, elapsed, per_op_ns
    );
    assert!(
        per_op_ns < 200_000,
        "certify_transition too slow: {} ns/op",
        per_op_ns
    );
}

#[test]
fn bench_receipt_serialization() {
    let m = build_machine();
    let capsule = m
        .certify_transition(&CertifyParams {
            entity_id: "e1",
            from_state: "s0",
            to_state: "s1",
            action: "step_0",
            before_state_hash: "h1",
            after_state_hash: "h2",
            guards: &[],
            actor_id: "actor",
            reason: "reason",
            causal_parent: "parent",
            timestamp: "2026-03-27T12:00:00Z",
        })
        .unwrap();

    let start = Instant::now();
    let iterations = 10_000;
    for _ in 0..iterations {
        let json = serde_json::to_string(&capsule).unwrap();
        let _: ProofCapsule = serde_json::from_str(&json).unwrap();
    }
    let elapsed = start.elapsed();
    let per_op_ns = elapsed.as_nanos() / iterations as u128;
    eprintln!(
        "receipt round-trip: {} ops in {:?} ({} ns/op)",
        iterations, elapsed, per_op_ns
    );
    assert!(
        per_op_ns < 100_000,
        "receipt round-trip too slow: {} ns/op",
        per_op_ns
    );
}
