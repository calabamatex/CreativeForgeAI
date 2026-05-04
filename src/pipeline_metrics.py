"""Metrics calculation helpers for the creative automation pipeline."""

import platform
from dataclasses import dataclass
from typing import List, Dict

from src.models import TechnicalMetrics

# Note: an earlier `compute_business_metrics()` helper and `BusinessMetrics`
# data model were removed from this module. Their values (ROI multiplier,
# cost-savings percentage, time-saved hours, dollar savings) were tautologies
# computed entirely from hard-coded constants. The removed code used a hard-coded
# 96-hour manual-production baseline and a hard-coded $2700 manual cost,
# combined with an 80%-plus-cache-bonus assumption returned as output, which
# made the reported "ROI multiplier" algebraically 0.80 / 0.20 = 4.0 by
# construction regardless of workload. To produce honest business metrics here
# the pipeline would need: real per-call API cost from each provider's billing,
# a measured manual-production baseline at the deploying organization, and a
# defined cost-of-time input. None of those is currently wired in.


@dataclass
class RawMetricData:
    """Raw data collected during pipeline execution for metrics computation."""
    backend: str
    total_api_calls: int
    cache_hits: int
    cache_misses: int
    retry_count: int
    retry_reasons: List[str]
    api_response_times: List[float]
    image_processing_total_ms: float
    localization_total_ms: float
    compliance_check_total_ms: float
    peak_memory_mb: float
    full_error_traces: List[Dict[str, str]]


def compute_technical_metrics(data: RawMetricData) -> TechnicalMetrics:
    """Compute technical metrics from raw pipeline data."""
    cache_hit_rate = (
        (data.cache_hits / (data.cache_hits + data.cache_misses) * 100)
        if (data.cache_hits + data.cache_misses) > 0
        else 0.0
    )
    avg_api_response_time = (
        sum(data.api_response_times) / len(data.api_response_times)
        if data.api_response_times
        else 0.0
    )
    min_api_response_time = min(data.api_response_times) if data.api_response_times else 0.0
    max_api_response_time = max(data.api_response_times) if data.api_response_times else 0.0

    system_info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
        "machine": platform.machine(),
    }

    return TechnicalMetrics(
        backend_used=data.backend,
        total_api_calls=data.total_api_calls,
        cache_hits=data.cache_hits,
        cache_misses=data.cache_misses,
        cache_hit_rate=cache_hit_rate,
        retry_count=data.retry_count,
        retry_reasons=data.retry_reasons,
        avg_api_response_time_ms=avg_api_response_time,
        min_api_response_time_ms=min_api_response_time,
        max_api_response_time_ms=max_api_response_time,
        image_processing_time_ms=data.image_processing_total_ms,
        localization_time_ms=data.localization_total_ms,
        compliance_check_time_ms=data.compliance_check_total_ms,
        peak_memory_mb=data.peak_memory_mb,
        system_info=system_info,
        full_error_traces=data.full_error_traces,
    )


