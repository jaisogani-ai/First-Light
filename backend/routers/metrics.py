"""Lightweight Prometheus metrics — counters/histograms updated from real verify calls."""

import psutil
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter(tags=["metrics"])

COMMANDS_VERIFIED = Counter("first_light_commands_verified_total", "Commands accepted by the verifier")
COMMANDS_REJECTED = Counter("first_light_commands_rejected_total", "Commands rejected by the verifier", ["reason"])
VERIFIER_LATENCY = Histogram("first_light_verifier_latency_ms", "Verifier wall-clock latency (ms)")
PRODUCER_LATENCY = Histogram("first_light_producer_latency_ms", "Producer pipeline wall-clock latency (ms)")
PROCESS_CPU_PCT = Gauge("first_light_process_cpu_percent", "Backend process CPU percent")
PROCESS_MEM_MB = Gauge("first_light_process_memory_mb", "Backend process RSS memory (MB)")


@router.get("/metrics")
def metrics():
    proc = psutil.Process()
    PROCESS_CPU_PCT.set(proc.cpu_percent(interval=0.05))
    PROCESS_MEM_MB.set(proc.memory_info().rss / (1024 * 1024))
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
