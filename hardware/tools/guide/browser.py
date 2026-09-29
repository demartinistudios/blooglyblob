#!/usr/bin/env python3
"""Test a built guide on an isolated local server; preserve the user's preview and storage."""

import functools
import http.server
import os
from pathlib import Path
import subprocess
import threading
import uuid
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
PROJECT_PATH = "/blooglyblob/"


def project_path(root, request_path):
    """Resolve an existing, exactly cased project URL without following symlinks.

    Root-relative asset URLs intentionally fail, as they would on Pages. Exact
    directory-entry comparison catches case mistakes on case-insensitive Macs.
    """
    path = unquote(urlsplit(request_path).path)
    if not path.startswith(PROJECT_PATH):
        return None
    relative = path[len(PROJECT_PATH) :].rstrip("/")
    current = Path(root)
    if not relative:
        return current
    for segment in relative.split("/"):
        if segment in ("", ".", "..") or "\\" in segment or "\x00" in segment:
            return None
        if not current.is_dir() or segment not in {p.name for p in current.iterdir()}:
            return None
        current = current / segment
        if current.is_symlink():
            return None
    return current


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def translate_path(self, path):
        resolved = project_path(self.directory, path)
        if resolved is None:
            raise ValueError("Path is outside the case-sensitive project site")
        return str(resolved)

    def send_head(self):
        if project_path(self.directory, self.path) is None:
            self.send_error(404)
            return None
        return super().send_head()


if __name__ == "__main__":
    dist = ROOT / "hardware/build-guide/dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("Build the guide first: make guide-build")
    out = ROOT / "hardware/.work/guide" / ("browser-" + uuid.uuid4().hex[:12])
    out.parent.mkdir(parents=True, exist_ok=True)
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(dist))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        env = dict(
            os.environ,
            BGB_REVIEW_URL=f"http://127.0.0.1:{server.server_port}{PROJECT_PATH}",
            BGB_REVIEW_OUTPUT=str(out),
        )
        result = subprocess.run(
            ["node", str(Path(__file__).with_name("browser-check.cjs"))],
            env=env,
            cwd=ROOT,
        )
        print("Browser evidence:", out.relative_to(ROOT))
        raise SystemExit(result.returncode)
    finally:
        server.shutdown()
        server.server_close()
