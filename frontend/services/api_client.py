import os

import requests

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


class ApiError(Exception):
    pass


def _check(r: requests.Response):
    if r.ok:
        return r.json()
    try:
        detail = r.json().get("detail", r.text)
    except Exception:
        detail = r.text
    raise ApiError(f"{detail}" if isinstance(detail, str) else str(detail))


def _call(method: str, path: str, **kw):
    try:
        return _check(requests.request(method, BASE_URL + path, timeout=kw.pop("timeout", 300), **kw))
    except requests.ConnectionError as e:
        raise ApiError(f"Cannot reach the backend at {BASE_URL}. Is it running?") from e


def health() -> dict:
    return _call("GET", "/api/health", timeout=10)


def languages() -> list[dict]:
    return _call("GET", "/api/languages", timeout=10)


def upload(name: str, data: bytes, content_type: str) -> dict:
    return _call("POST", "/api/reports/upload", files={"file": (name, data, content_type)})


def extract(report_id: str) -> dict:
    return _call("POST", "/api/reports/extract", json={"report_id": report_id})


def simplify(report_id: str, language: str, measurements: list[dict] | None = None) -> dict:
    body = {"report_id": report_id, "language": language}
    if measurements is not None:
        body["measurements"] = measurements
    return _call("POST", "/api/reports/simplify", json=body)
