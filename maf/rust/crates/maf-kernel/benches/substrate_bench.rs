//! Substrate benchmarks for maf-kernel.
//!
//! Run: cargo bench -p maf-kernel
//!
//! These benchmarks establish performance baselines for core substrate
//! operations. CI should flag regressions above 20%.

#![allow(unused)]

use maf_kernel::*;

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

#[cfg(test)]
mod bench_tests {
    use super::*;
    use std::time::Instant;

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
        // Regression gate: under 100μs in debug, under 10μs in release
        assert!(
            per_op_ns < 100_000,
            "is_legal too slow: {} ns/op",
            per_op_ns
        );
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
            let _ = m.certify_transition(
                "entity-1",
                &from,
                &to,
                &action,
                "hash-before",
                "hash-after",
                &guards,
                "actor",
                "reason",
                "parent",
                "2026-03-27T12:00:00Z",
            );
        }
        let elapsed = start.elapsed();
        let per_op_ns = elapsed.as_nanos() / iterations as u128;
        eprintln!(
            "certify_transition: {} ops in {:?} ({} ns/op)",
            iterations, elapsed, per_op_ns
        );
        // Regression gate: under 200μs in debug, under 50μs in release
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
            .certify_transition(
                "e1",
                "s0",
                "s1",
                "step_0",
                "h1",
                "h2",
                &[],
                "actor",
                "reason",
                "parent",
                "2026-03-27T12:00:00Z",
            )
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
        // Regression gate: under 100μs in debug, under 20μs in release
        assert!(
            per_op_ns < 100_000,
            "receipt round-trip too slow: {} ns/op",
            per_op_ns
        );
    }
}
