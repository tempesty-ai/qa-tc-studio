# -*- coding: utf-8 -*-
"""qa-tc-studio — 공유 대시보드 서버 (파이썬 기본 모듈만 사용, 외부 의존성 없음).

실행:  python serve_dashboard.py                 (기본: dashboard.html, 포트 8787)
       python serve_dashboard.py 9000            (포트 지정)
       python serve_dashboard.py 8787 out/dashboard.html   (HTML 경로 지정)

접속:  http://localhost:8787
       같은 네트워크의 다른 PC: http://<이 PC IP>:8787

Pass/Fail 결과는 statuses.json, 비고는 notes.json 에 서버 저장 → 여러 명이 결과를 공유한다.
"""
import http.server, json, os, sys, threading

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
HTML = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(HERE, "dashboard.html")
DATADIR = os.path.dirname(HTML)
STORE = os.path.join(DATADIR, "statuses.json")
NOTESTORE = os.path.join(DATADIR, "notes.json")
_lock = threading.Lock()

def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(path, d):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)

class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/status"):
            self._send(200, json.dumps(_load(STORE), ensure_ascii=False))
        elif self.path.startswith("/api/note"):
            self._send(200, json.dumps(_load(NOTESTORE), ensure_ascii=False))
        else:
            try:
                self._send(200, open(HTML, encoding="utf-8").read(), "text/html")
            except Exception as e:
                self._send(500, "dashboard html not found: " + str(e), "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            j = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            j = {}
        path, key = (STORE, "status") if self.path.startswith("/api/status") else \
                    (NOTESTORE, "note") if self.path.startswith("/api/note") else (None, None)
        if not path:
            return self._send(404, "{}")
        with _lock:
            d = _load(path); tid = j.get("id")
            if tid:
                if j.get(key): d[tid] = j[key]
                else: d.pop(tid, None)
                _save(path, d)
        self._send(200, '{"ok":true}')

    def log_message(self, *a):
        pass

def main():
    if not os.path.exists(HTML):
        print("[!] 대시보드 HTML이 없습니다:", HTML)
        print("    먼저 render_report.py 를 실행해 dashboard.html 을 생성하세요.")
        return
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("qa-tc-studio 공유 대시보드 실행 중")
    print("  로컬:  http://localhost:%d" % PORT)
    print("  HTML:  %s" % HTML)
    print("  저장:  %s / %s" % (STORE, NOTESTORE))
    print("  (중지: Ctrl+C)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")

if __name__ == "__main__":
    main()
