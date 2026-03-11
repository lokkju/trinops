"""Web-based progress display."""

from __future__ import annotations

import dataclasses
import json
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TextIO

from trino_progress.stats import QueryStats


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Trino Query Progress</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; background: #fafafa; color: #222; }
  h1 { font-size: 1.4em; }
  .state { font-size: 1.2em; font-weight: bold; padding: 0.3em 0.6em; border-radius: 4px; display: inline-block; }
  .state-RUNNING { background: #dbeafe; color: #1e40af; }
  .state-FINISHED { background: #dcfce7; color: #166534; }
  .state-FAILED { background: #fee2e2; color: #991b1b; }
  .state-QUEUED, .state-PLANNING, .state-STARTING { background: #fef3c7; color: #92400e; }
  .progress-bar { width: 100%%; height: 24px; background: #e5e7eb; border-radius: 4px; overflow: hidden; margin: 1em 0; }
  .progress-fill { height: 100%%; background: #3b82f6; transition: width 0.3s; }
  table { border-collapse: collapse; width: 100%%; margin: 1em 0; }
  th, td { text-align: left; padding: 0.4em 0.8em; border-bottom: 1px solid #e5e7eb; }
  th { background: #f3f4f6; font-weight: 600; }
  .stages { margin-top: 1.5em; }
  .stage { padding: 0.3em 0; border-left: 3px solid #3b82f6; padding-left: 0.8em; margin: 0.5em 0; }
</style>
</head>
<body>
<h1>Trino Query Progress</h1>
<div id="content"><p>Waiting for stats...</p></div>
<script>
function fmt(bytes) {
  const units = ['B','KB','MB','GB','TB'];
  let i = 0;
  let n = bytes;
  while (Math.abs(n) >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return n.toFixed(1) + ' ' + units[i];
}
function fmtTime(ms) {
  const s = ms / 1000;
  if (s < 60) return s.toFixed(1) + 's';
  const m = s / 60;
  if (m < 60) return m.toFixed(1) + 'm';
  return (m / 60).toFixed(1) + 'h';
}
function renderStage(stage) {
  let html = '<div class="stage">';
  html += '<strong>Stage ' + stage.stage_id + '</strong> — ' + stage.state;
  html += ' | splits ' + stage.completed_splits + '/' + stage.total_splits;
  html += ' | ' + stage.processed_rows.toLocaleString() + ' rows';
  if (stage.sub_stages && stage.sub_stages.length > 0) {
    stage.sub_stages.forEach(function(s) { html += renderStage(s); });
  }
  html += '</div>';
  return html;
}
function update() {
  fetch('/stats').then(r => r.json()).then(s => {
    const pct = s.total_splits > 0 ? (s.completed_splits / s.total_splits * 100) : 0;
    let html = '<span class="state state-' + s.state + '">' + s.state + '</span>';
    html += '<div class="progress-bar"><div class="progress-fill" style="width:' + pct.toFixed(1) + '%%"></div></div>';
    html += '<table><tr><th>Metric</th><th>Value</th></tr>';
    html += '<tr><td>Splits</td><td>' + s.completed_splits + ' / ' + s.total_splits + ' (queued: ' + s.queued_splits + ', running: ' + s.running_splits + ')</td></tr>';
    html += '<tr><td>Rows</td><td>' + s.processed_rows.toLocaleString() + '</td></tr>';
    html += '<tr><td>Data</td><td>' + fmt(s.processed_bytes) + '</td></tr>';
    html += '<tr><td>Elapsed</td><td>' + fmtTime(s.elapsed_time_millis) + '</td></tr>';
    html += '<tr><td>CPU</td><td>' + fmtTime(s.cpu_time_millis) + '</td></tr>';
    html += '<tr><td>Peak Memory</td><td>' + fmt(s.peak_memory_bytes) + '</td></tr>';
    html += '<tr><td>Spilled</td><td>' + fmt(s.spilled_bytes) + '</td></tr>';
    html += '<tr><td>Nodes</td><td>' + s.nodes + '</td></tr>';
    html += '</table>';
    if (s.root_stage) {
      html += '<div class="stages"><h3>Stages</h3>' + renderStage(s.root_stage) + '</div>';
    }
    document.getElementById('content').innerHTML = html;
    if (s.state !== 'FINISHED' && s.state !== 'FAILED') {
      setTimeout(update, 1000);
    }
  }).catch(() => setTimeout(update, 2000));
}
update();
</script>
</body>
</html>
"""


def _stats_to_dict(stats: QueryStats) -> dict:
    """Convert QueryStats to a JSON-serializable dict."""
    return dataclasses.asdict(stats)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stats":
            self._json_response(
                _stats_to_dict(self.server.latest_stats) if self.server.latest_stats else {}
            )
        elif self.path == "/stats/history":
            self._json_response(
                [_stats_to_dict(s) for s in self.server.stats_history]
            )
        elif self.path == "/":
            self._html_response(_HTML_TEMPLATE)
        else:
            self.send_error(404)

    def _json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html_response(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class WebDisplay:
    def __init__(self, port: int = 0, file: TextIO | None = None) -> None:
        self._file = file or sys.stderr
        self._server = HTTPServer(("127.0.0.1", port), _Handler)
        self._server.latest_stats = None
        self._server.stats_history = []
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        actual_port = self._server.server_address[1]
        self._port = actual_port
        self._file.write(f"Trino progress dashboard: http://localhost:{actual_port}/\n")
        self._file.flush()

    @property
    def port(self) -> int:
        return self._port

    def on_stats(self, stats: QueryStats) -> None:
        self._server.latest_stats = stats
        self._server.stats_history.append(stats)

    def close(self) -> None:
        self._server.shutdown()
