from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from src.common.config import REPORTS_DIR

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("DASHBOARD_PORT", "8008"))


def _read_json_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def _as_float(value: object, digits: int = 4) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _metric(source: dict | None, *keys: str, digits: int = 4) -> float | None:
    if not source:
        return None
    for key in keys:
        if key in source:
            return _as_float(source.get(key), digits=digits)
    return None


def _summary_payload(latest_batch: dict | None) -> dict:
    latest_batch = latest_batch or {}
    return {
        "batch_id": _as_int(latest_batch.get("batch_id") or latest_batch.get("ma_lo")),
        "rows": _as_int(latest_batch.get("rows") or latest_batch.get("so_dong")),
        "alerts": _as_int(latest_batch.get("alerts") or latest_batch.get("so_canh_bao")),
        "latency_ms": _as_int(latest_batch.get("latency_ms") or latest_batch.get("thoi_gian_ms")),
    }


def _training_payload(training_metrics: dict | None) -> dict:
    return {
        "auc_roc": _metric(training_metrics, "auc_roc"),
        "auc_pr": _metric(training_metrics, "auc_pr"),
        "accuracy": _metric(training_metrics, "accuracy", "do_chinh_xac"),
        "precision": _metric(training_metrics, "precision"),
        "recall": _metric(training_metrics, "recall"),
        "f1": _metric(training_metrics, "f1"),
    }


def _evaluation_payload(rows: list[dict]) -> list[dict]:
    payload: list[dict] = []
    for row in rows:
        payload.append(
            {
                "model": row.get("model") or row.get("mo_hinh") or "Chưa rõ",
                "precision": _as_float(row.get("precision")),
                "recall": _as_float(row.get("recall")),
                "f1": _as_float(row.get("f1")),
            }
        )
    return payload


def _top_risk_payload(rows: list[dict]) -> list[dict]:
    payload: list[dict] = []
    for row in rows[:20]:
        payload.append(
            {
                "account": row.get("account") or row.get("nameorig") or row.get("account_id") or "N/A",
                "alert_count": _as_int(row.get("alert_count")),
                "total_amount": _as_float(row.get("total_amount"), digits=2),
                "avg_score": _as_float(row.get("avg_score")),
            }
        )
    return payload


def build_dashboard_payload() -> dict:
    latest_batch_path = REPORTS_DIR / "latest_gold_batch.json"
    training_metrics_path = REPORTS_DIR / "training_metrics.json"
    evaluation_path = REPORTS_DIR / "evaluation_summary.csv"
    top_risk_path = REPORTS_DIR / "top_risk_accounts.csv"
    dashboard_image_path = REPORTS_DIR / "dashboard.png"

    latest_batch = _read_json_file(latest_batch_path)
    training_metrics = _read_json_file(training_metrics_path)
    evaluation_rows = _read_csv_rows(evaluation_path)
    top_risk_rows = _read_csv_rows(top_risk_path)

    status = {
        "has_latest_batch": latest_batch is not None,
        "has_training_metrics": training_metrics is not None,
        "has_evaluation": bool(evaluation_rows),
        "has_top_risk_accounts": bool(top_risk_rows),
        "has_dashboard_image": dashboard_image_path.exists(),
    }

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "summary": _summary_payload(latest_batch),
        "training": _training_payload(training_metrics),
        "evaluation": _evaluation_payload(evaluation_rows),
        "top_risk_accounts": _top_risk_payload(top_risk_rows),
        "assets": {
            "dashboard_image_url": "/reports/dashboard.png" if dashboard_image_path.exists() else None,
        },
        "status": status,
    }


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, reports_dir: str | None = None, **kwargs):
        self.reports_dir = Path(reports_dir or REPORTS_DIR).resolve()
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)

        if path == "/api/dashboard":
            self._serve_dashboard_api()
            return

        if path.startswith("/reports/"):
            self._serve_report_asset(path)
            return

        if path == "/":
            self.path = "/index.html"
        else:
            self.path = path
        super().do_GET()

    def log_message(self, format: str, *args) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[dashboard {timestamp}] {format % args}")

    def _serve_dashboard_api(self) -> None:
        payload = build_dashboard_payload()
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_report_asset(self, request_path: str) -> None:
        relative_path = request_path.removeprefix("/reports/")
        candidate = (self.reports_dir / relative_path).resolve()

        if self.reports_dir not in candidate.parents and candidate != self.reports_dir:
            self.send_error(HTTPStatus.FORBIDDEN, "Đường dẫn không hợp lệ.")
            return

        if not candidate.exists() or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Không tìm thấy file báo cáo.")
            return

        mime_type, _ = mimetypes.guess_type(candidate.as_posix())
        try:
            with candidate.open("rb") as fh:
                content = fh.read()
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Không thể đọc file báo cáo.")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chạy dashboard demo cho đồ án Big Data.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host phục vụ dashboard. Mặc định: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port phục vụ dashboard. Mặc định: {DEFAULT_PORT}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    handler = partial(
        DashboardRequestHandler,
        directory=STATIC_DIR.as_posix(),
        reports_dir=REPORTS_DIR.as_posix(),
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Dashboard đang chạy tại http://{args.host}:{args.port}")
    print("Nhấn Ctrl+C để dừng server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng dashboard server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
