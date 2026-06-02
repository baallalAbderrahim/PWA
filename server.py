#!/usr/bin/env python3
"""
CRIMIN Local Test Server
- Serves the intent launcher page on GET /
- Receives dossier payload on POST /api/rest/mcb/empreintes
- Displays received payloads in a live log UI on GET /logs
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import ssl
from datetime import datetime
from urllib.parse import urlparse, parse_qs

PORT = 8080
received_logs = []      # in-memory log of received dossiers
received_app_logs = []  # in-memory log of submitted app logs

# Static files served as-is from the project directory
STATIC_FILES = {
    "/index.html":          "text/html",
    "/":                    "text/html",          # → index.html
    "/logs":                "text/html",          # → logs.html
    "/logs.html":           "text/html",
    "/app-logs":            "text/html",          # → app-logs.html
    "/app-logs.html":       "text/html",
    "/wpa.html":            "text/html",
    "/config_mock_v2.json": "application/json",
    "/dossier_mock_v2.json":"application/json",
}

# Map URL path → filename on disk (when they differ)
PATH_TO_FILE = {
    "/":         "index.html",
    "/logs":     "logs.html",
    "/app-logs": "app-logs.html",
}


class CriminHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        # ── API routes ────────────────────────────────────────────────────────
        if path == "/api/logs":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(received_logs).encode())
            return

        if path == "/api/clear-logs":
            received_logs.clear()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"cleared": True}).encode())
            return

        if path == "/api/app-logs":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(received_app_logs).encode())
            return

        if path == "/api/clear-app-logs":
            received_app_logs.clear()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"cleared": True}).encode())
            return

        # ── Static files ──────────────────────────────────────────────────────
        if path in STATIC_FILES:
            filename     = PATH_TO_FILE.get(path, path.lstrip("/"))
            content_type = STATIC_FILES[path]
            self.serve_file(filename, content_type)
            return

        # ── 404 ───────────────────────────────────────────────────────────────
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not found")

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/rest/mcb/logs":
            try:
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Bearer ") or len(auth) <= len("Bearer "):
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "error", "code": 401, "message": "Missing or invalid Bearer token"}).encode())
                    return

                content_length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_length)

                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                    error_message = None
                except Exception:
                    payload = {"raw": raw_body.decode("utf-8", errors="replace")}
                    error_message = "Payload JSON invalide"

                status = "error" if error_message else "success"

                log_entry = {
                    "id": len(received_app_logs) + 1,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": status,
                    "error": error_message,
                    "headers": {
                        "content-type": self.headers.get("Content-Type", ""),
                        "authorization": self.headers.get("Authorization", ""),
                    },
                    "payload": payload,
                }
                received_app_logs.insert(0, log_entry)

                if status == "success":
                    self.send_response(200)
                    response = {"status": "success", "message": "Logs received successfully"}
                else:
                    self.send_response(400)
                    response = {"status": "error", "code": 400, "message": error_message}

                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            except Exception as e:
                print(f"[ERROR] /api/rest/mcb/empreintes: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "code": 500, "message": "Erreur interne du serveur"}).encode())
            return

        if parsed.path == "/api/rest/mcb/empreintes":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_length)

                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                    error_message = None
                except Exception:
                    payload = {"raw": raw_body.decode("utf-8", errors="replace")}
                    error_message = "Payload JSON invalide"

                if error_message is None and not payload.get("dossier").get("transactionId"):
                    error_message = "transactionId manquant"

                status = "error" if error_message else "success"

                log_entry = {
                    "id": len(received_logs) + 1,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": status,
                    "error": error_message,
                    "headers": {
                        "content-type": self.headers.get("Content-Type", ""),
                        "authorization": self.headers.get("Authorization", ""),
                    },
                    "payload": payload,
                }
                received_logs.insert(0, log_entry)

                print(f"\n{'='*60}")
                print(f"[RECEIVED] Dossier #{log_entry['id']} at {log_entry['timestamp']}")
                print(json.dumps(payload, indent=2, ensure_ascii=False)[:500] + "...")
                print(f"{'='*60}\n")

                if status == "success":
                    self.send_response(200)
                    response = {
                        "status": "success",
                        "transactionId": payload["dossier"]["transactionId"],
                    }
                else:
                    self.send_response(400)
                    response = {
                        "status": "error",
                        "code": 400,
                        "message": error_message,
                    }

                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            except Exception as e:
                print(f"[ERROR] /api/rest/mcb/empreintes: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "code": 500, "message": "Erreur interne du serveur"}).encode())

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def serve_file(self, filename, content_type):
        filepath = os.path.join(os.path.dirname(__file__), filename)
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found")


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(__file__)
    CERT_FILE = os.path.join(BASE_DIR, "cert.pem")
    KEY_FILE  = os.path.join(BASE_DIR, "key.pem")

    server = HTTPServer(("0.0.0.0", PORT), CriminHandler)

    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    else:
        scheme = "http"
        print("[WARN] Certificats SSL introuvables — serveur lancé en HTTP.")
        print("       Générez-les avec : mkcert localhost 127.0.0.1")

    print(f"""
╔══════════════════════════════════════════════╗
║         CRIMIN Local Test Server             ║
╠══════════════════════════════════════════════╣
║  Launcher :  {scheme}://localhost:{PORT}         ║
║  Logs UI  :  {scheme}://localhost:{PORT}/logs    ║
║  Endpoint :  POST /api/rest/mcb/empreintes   ║
╚══════════════════════════════════════════════╝
    """)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")