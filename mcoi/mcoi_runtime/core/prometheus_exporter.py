"""Phase 226B — Prometheus Metrics Exporter.

Purpose: Export platform metrics in Prometheus text exposition format.
    Supports counters, gauges, histograms with labels.
Dependencies: None (stdlib only).
Invariants:
  - Output conforms to Prometheus exposition format v0.0.4.
  - Metric names follow Prometheus naming conventions (snake_case, prefixed).
  - All metrics include HELP and TYPE annotations.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any


@unique
class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class MetricSample:
    """A single metric sample with optional labels."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float | None = None

    def to_prometheus(self) -> str:
        label_str = ""
        if self.labels:
            pairs = ",".join(f'{k}="{v}"' for k, v in sorted(self.labels.items()))
            label_str = f"{{{pairs}}}"
        ts = f" {int(self.timestamp * 1000)}" if self.timestamp else ""
        return f"{self.name}{label_str} {self.value}{ts}"


@dataclass
class MetricFamily:
    """A metric family with type, help, and samples."""
    name: str
    metric_type: MetricType
    help_text: str
    samples: list[MetricSample] = field(default_factory=list)

    def to_prometheus(self) -> str:
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} {self.metric_type.value}",
        ]
        for sample in self.samples:
            lines.append(sample.to_prometheus())
        return "\n".join(lines)


class PrometheusExporter:
    """Collects and exports metrics in Prometheus format."""

    def __init__(self, prefix: str = "mullu"):
        self._prefix = prefix
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._help: dict[str, str] = {}
        self._labels: dict[str, dict[str, str]] = {}

    def register_counter(self, name: str, help_text: str) -> None:
        full_name = f"{self._prefix}_{name}"
        self._counters[full_name] = 0.0
        self._help[full_name] = help_text

    def register_gauge(self, name: str, help_text: str) -> None:
        full_name = f"{self._prefix}_{name}"
        self._gauges[full_name] = 0.0
        self._help[full_name] = help_text

    def inc_counter(self, name: str, value: float = 1.0, **labels: str) -> None:
        full_name = f"{self._prefix}_{name}"
        if labels:
            key = f"{full_name}|" + "|".join(f"{k}={v}" for k, v in sorted(labels.items()))
            self._counters[key] = self._counters.get(key, 0.0) + value
            self._labels[key] = labels
            if full_name not in self._help:
                self._help[full_name] = name
        else:
            self._counters[full_name] = self._counters.get(full_name, 0.0) + value

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        full_name = f"{self._prefix}_{name}"
        if labels:
            key = f"{full_name}|" + "|".join(f"{k}={v}" for k, v in sorted(labels.items()))
            self._gauges[key] = value
            self._labels[key] = labels
            if full_name not in self._help:
                self._help[full_name] = name
        else:
            self._gauges[full_name] = value

    def export(self) -> str:
        """Export all metrics in Prometheus text format."""
        families: dict[str, MetricFamily] = {}

        # Counters
        for key, value in sorted(self._counters.items()):
            base_name = key.split("|")[0]
            if base_name not in families:
                families[base_name] = MetricFamily(
                    name=base_name,
                    metric_type=MetricType.COUNTER,
                    help_text=self._help.get(base_name, base_name),
                )
            labels = self._labels.get(key, {})
            families[base_name].samples.append(
                MetricSample(name=base_name, value=value, labels=labels)
            )

        # Gauges
        for key, value in sorted(self._gauges.items()):
            base_name = key.split("|")[0]
            if base_name not in families:
                families[base_name] = MetricFamily(
                    name=base_name,
                    metric_type=MetricType.GAUGE,
                    help_text=self._help.get(base_name, base_name),
                )
            labels = self._labels.get(key, {})
            families[base_name].samples.append(
                MetricSample(name=base_name, value=value, labels=labels)
            )

        return "\n\n".join(f.to_prometheus() for f in families.values()) + "\n"

    @property
    def metric_count(self) -> int:
        return len(set(k.split("|")[0] for k in self._counters)) + \
               len(set(k.split("|")[0] for k in self._gauges))

    def summary(self) -> dict[str, Any]:
        return {
            "prefix": self._prefix,
            "counters": len(self._counters),
            "gauges": len(self._gauges),
            "metric_families": self.metric_count,
        }
