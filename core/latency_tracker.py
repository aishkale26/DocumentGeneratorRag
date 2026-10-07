import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

@dataclass
class LatencyStage:
    name: str
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

class LatencyTracker:
    """
    High-precision Latency Profiler for RAG, Summarization, and Document Generation pipelines.
    Tracks time-to-first-token (TTFT), retrieval latency, embedding latency, and token throughput.
    """
    def __init__(self, operation_name: str = "RAG_Operation"):
        self.operation_name = operation_name
        self.start_time: float = time.perf_counter()
        self.end_time: Optional[float] = None
        self.stages: List[LatencyStage] = []
        self._current_stage_name: Optional[str] = None
        self._current_stage_start: Optional[float] = None
        self._current_stage_meta: Dict[str, Any] = {}
        self.ttft_ms: Optional[float] = None
        self.tokens_generated: int = 0

    def start_stage(self, stage_name: str, **metadata):
        if self._current_stage_name:
            self.end_stage()
        self._current_stage_name = stage_name
        self._current_stage_start = time.perf_counter()
        self._current_stage_meta = metadata

    def end_stage(self, **additional_meta):
        if self._current_stage_name and self._current_stage_start:
            duration_ms = (time.perf_counter() - self._current_stage_start) * 1000.0
            meta = {**self._current_stage_meta, **additional_meta}
            self.stages.append(LatencyStage(
                name=self._current_stage_name,
                duration_ms=round(duration_ms, 2),
                metadata=meta
            ))
            self._current_stage_name = None
            self._current_stage_start = None
            self._current_stage_meta = {}

    def record_ttft(self):
        """Record Time-To-First-Token in milliseconds since pipeline start."""
        if self.ttft_ms is None:
            self.ttft_ms = round((time.perf_counter() - self.start_time) * 1000.0, 2)

    def finish(self, tokens_generated: int = 0) -> "LatencyTracker":
        if self._current_stage_name:
            self.end_stage()
        self.end_time = time.perf_counter()
        self.tokens_generated = tokens_generated
        return self

    @property
    def total_latency_ms(self) -> float:
        if self.end_time:
            return round((self.end_time - self.start_time) * 1000.0, 2)
        return round((time.perf_counter() - self.start_time) * 1000.0, 2)

    @property
    def tokens_per_second(self) -> float:
        gen_stage = next((s for s in self.stages if "generate" in s.name.lower() or "llm" in s.name.lower() or "synthesis" in s.name.lower()), None)
        if gen_stage and gen_stage.duration_ms > 0 and self.tokens_generated > 0:
            return round((self.tokens_generated / (gen_stage.duration_ms / 1000.0)), 2)
        elif self.total_latency_ms > 0 and self.tokens_generated > 0:
            return round((self.tokens_generated / (self.total_latency_ms / 1000.0)), 2)
        return 0.0

    def get_breakdown(self) -> Dict[str, Any]:
        total = self.total_latency_ms
        stages_data = []
        for s in self.stages:
            pct = round((s.duration_ms / total * 100.0), 1) if total > 0 else 0
            stages_data.append({
                "stage": s.name,
                "duration_ms": s.duration_ms,
                "percentage": pct,
                "metadata": s.metadata
            })
        
        # Identify bottleneck
        bottleneck = max(self.stages, key=lambda s: s.duration_ms).name if self.stages else "None"

        return {
            "operation": self.operation_name,
            "total_latency_ms": total,
            "ttft_ms": self.ttft_ms,
            "tokens_generated": self.tokens_generated,
            "tokens_per_sec": self.tokens_per_second,
            "bottleneck_stage": bottleneck,
            "stages": stages_data
        }

    def to_markdown_table(self) -> str:
        data = self.get_breakdown()
        lines = [
            f"### ⚡ Latency Telemetry: {data['operation']}",
            f"**Total Duration:** `{data['total_latency_ms']} ms` | **TTFT:** `{data['ttft_ms'] or 'N/A'} ms` | **Throughput:** `{data['tokens_per_sec']} tokens/s` | **Bottleneck:** `{data['bottleneck_stage']}`",
            "",
            "| Execution Stage | Latency (ms) | % of Total | Stage Metadata |",
            "| :--- | :--- | :--- | :--- |"
        ]
        for s in data["stages"]:
            meta_str = ", ".join(f"{k}: {v}" for k, v in s["metadata"].items()) if s["metadata"] else "-"
            lines.append(f"| **{s['stage']}** | `{s['duration_ms']} ms` | `{s['percentage']}%` | {meta_str} |")
        return "\n".join(lines)
