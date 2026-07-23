"""Observability — structured logging, metrics, and event stream for the continuity loop.

Provides:
  - StructuredLogger: JSON-formatted structured logging
  - MetricsCollector: counters, histograms, gauges for continuity operations
  - EventStream: append-only event log for audit and monitoring
  - ContinuityObserver: integrates with the continuity loop to auto-emit events

All events are JSON-formatted and can be shipped to any log aggregator.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LogEvent:
    """A single structured log event."""
    timestamp: float
    level: str  # DEBUG, INFO, WARN, ERROR
    component: str
    event_type: str
    agent_id: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "component": self.component,
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "message": self.message,
            "data": self.data,
        }


class StructuredLogger:
    """JSON-formatted structured logger."""

    def __init__(self, component: str = "continuity", sink=None):
        self.component = component
        self.sink = sink or sys.stderr
        self._events: List[LogEvent] = []

    def _log(self, level: str, event_type: str, message: str,
             agent_id: str = "", **kwargs):
        event = LogEvent(
            timestamp=time.time(),
            level=level,
            component=self.component,
            event_type=event_type,
            agent_id=agent_id,
            message=message,
            data=kwargs,
        )
        self._events.append(event)
        line = json.dumps(event.to_dict())
        print(line, file=self.sink, flush=True)

    def debug(self, event_type: str, message: str, agent_id: str = "", **kw):
        self._log("DEBUG", event_type, message, agent_id, **kw)

    def info(self, event_type: str, message: str, agent_id: str = "", **kw):
        self._log("INFO", event_type, message, agent_id, **kw)

    def warn(self, event_type: str, message: str, agent_id: str = "", **kw):
        self._log("WARN", event_type, message, agent_id, **kw)

    def error(self, event_type: str, message: str, agent_id: str = "", **kw):
        self._log("ERROR", event_type, message, agent_id, **kw)

    def get_events(self) -> List[dict]:
        return [e.to_dict() for e in self._events]


class MetricsCollector:
    """Counters, histograms, and gauges for continuity operations."""

    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._gauges: Dict[str, float] = {}

    def increment(self, name: str, value: int = 1):
        self._counters[name] = self._counters.get(name, 0) + value

    def observe(self, name: str, value: float):
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

    def set_gauge(self, name: str, value: float):
        self._gauges[name] = value

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_histogram(self, name: str) -> dict:
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "mean": 0, "min": 0, "max": 0, "p50": 0, "p95": 0}
        sorted_vals = sorted(values)
        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "p50": sorted_vals[len(sorted_vals) // 2],
            "p95": sorted_vals[int(len(sorted_vals) * 0.95)] if len(values) > 1 else values[0],
        }

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0)

    def snapshot(self) -> dict:
        return {
            "counters": dict(self._counters),
            "histograms": {k: self.get_histogram(k) for k in self._histograms},
            "gauges": dict(self._gauges),
        }


class EventStream:
    """Append-only event log for audit and monitoring."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event_type: str, data: Dict[str, Any]):
        """Append an event to the stream."""
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            **data,
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def read(self, since: float = 0) -> List[dict]:
        """Read events since a timestamp."""
        if not self.path.exists():
            return []
        events = []
        with open(self.path) as f:
            for line in f:
                try:
                    event = json.loads(line)
                    if event.get("timestamp", 0) >= since:
                        events.append(event)
                except json.JSONDecodeError:
                    continue
        return events


class ContinuityObserver:
    """Integrates with the continuity loop to auto-emit events and metrics.

    Usage:
        observer = ContinuityObserver(logger, metrics, event_stream)
        loop = ContinuityLoop(..., observer=observer)
    """

    def __init__(
        self,
        logger: StructuredLogger,
        metrics: MetricsCollector,
        event_stream: Optional[EventStream] = None,
    ):
        self.logger = logger
        self.metrics = metrics
        self.event_stream = event_stream

    def on_seal(self, agent_id: str, epoch: int, capsule_hash: str, duration_ms: float):
        self.logger.info("capsule_sealed", f"sealed epoch {epoch}", agent_id,
                         epoch=epoch, capsule_hash=capsule_hash, duration_ms=duration_ms)
        self.metrics.increment("capsules_sealed")
        self.metrics.observe("seal_duration_ms", duration_ms)
        if self.event_stream:
            self.event_stream.emit("seal", {
                "agent_id": agent_id, "epoch": epoch, "capsule_hash": capsule_hash,
            })

    def on_destroy(self, agent_id: str, runtime_id: str, duration_ms: float):
        self.logger.info("runtime_destroyed", f"destroyed {runtime_id}", agent_id,
                         runtime_id=runtime_id, duration_ms=duration_ms)
        self.metrics.increment("runtimes_destroyed")
        if self.event_stream:
            self.event_stream.emit("destroy", {
                "agent_id": agent_id, "runtime_id": runtime_id,
            })

    def on_restore(self, agent_id: str, host_id: str, success: bool, duration_ms: float):
        level = "info" if success else "error"
        self.logger._log(level, "capsule_restored",
                         f"restore on {host_id}: {'ok' if success else 'failed'}",
                         agent_id, host_id=host_id, success=success, duration_ms=duration_ms)
        if success:
            self.metrics.increment("restores_succeeded")
        else:
            self.metrics.increment("restores_failed")
        self.metrics.observe("restore_duration_ms", duration_ms)
        if self.event_stream:
            self.event_stream.emit("restore", {
                "agent_id": agent_id, "host_id": host_id, "success": success,
            })

    def on_witness(self, agent_id: str, host_id: str, operations: int):
        self.logger.info("witness_signed", f"host {host_id} signed witness",
                         agent_id, host_id=host_id, operations=operations)
        self.metrics.increment("witnesses_signed")
        if self.event_stream:
            self.event_stream.emit("witness", {
                "agent_id": agent_id, "host_id": host_id, "operations": operations,
            })

    def on_reseal(self, agent_id: str, epoch: int, capsule_hash: str):
        self.logger.info("capsule_resealed", f"owner resealed epoch {epoch}",
                         agent_id, epoch=epoch, capsule_hash=capsule_hash)
        self.metrics.increment("capsules_resealed")
        if self.event_stream:
            self.event_stream.emit("reseal", {
                "agent_id": agent_id, "epoch": epoch, "capsule_hash": capsule_hash,
            })

    def on_verify(self, checks_passed: int, checks_failed: int, valid: bool):
        self.logger.info("offline_verified", f"chain verified: {checks_passed}p/{checks_failed}f",
                         valid=valid, checks_passed=checks_passed, checks_failed=checks_failed)
        self.metrics.increment("verifications_run")
        if not valid:
            self.metrics.increment("verifications_failed")

    def on_attack_detected(self, attack_type: str, detail: str):
        self.logger.warn("attack_detected", f"{attack_type}: {detail}",
                         attack_type=attack_type, detail=detail)
        self.metrics.increment("attacks_detected")
        if self.event_stream:
            self.event_stream.emit("attack_detected", {
                "attack_type": attack_type, "detail": detail,
            })
