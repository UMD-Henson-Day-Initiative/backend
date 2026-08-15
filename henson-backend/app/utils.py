# -*- coding: utf-8 -*-
"""Shared helper utilities used across route modules."""
from math import atan2, cos, radians, sin, sqrt


def api_error_payload(exc) -> dict:
    """Best-effort message extraction from a postgrest APIError."""
    if exc.args and isinstance(exc.args[0], dict):
        return exc.args[0]
    return {"message": str(exc)}


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in meters."""
    r = 6371000
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))
