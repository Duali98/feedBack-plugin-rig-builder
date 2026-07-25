#!/usr/bin/env python3
"""Tester visual standalone de la grilla A2 — NO toca el juego.

Sirve una página con el MISMO canvas del BOX AC30 (pedal_canvas.js) conectado
al pack de capturas A2: mover las perillas elige las 2 capturas vecinas y las
mezcla con crossfade equal-power en vivo (dos worklets NAM en paralelo — aquí
sí hay paralelo, es WebAudio). Entrada: loop del brit DI o tu guitarra en vivo.

Uso:  python3 tools/a2_tester.py       (abre http://localhost:8797)
"""

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
APP_NAM = Path("/Applications/feedback.app/Contents/Resources/slopsmith/plugins/nam_tone")
LIB = Path.home() / "Library/Application Support/feedback-desktop/slopsmith-config/nam_models"
DI = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/"
                    "test logic/ce1_ref/brit_di.wav")
PORT = 8797

ROUTES: dict[str, tuple[Path, str]] = {
    "/": (HERE / "tools" / "a2_tester.html", "text/html; charset=utf-8"),
    "/pedal_canvas.js": (HERE / "pedal_canvas.js", "text/javascript"),
    "/grids.json": (HERE / "data" / "a2_capture_grids.json", "application/json"),
    "/nam-core.js": (APP_NAM / "wasm" / "nam-core.js", "text/javascript"),
    "/nam-core.wasm": (APP_NAM / "wasm" / "nam-core.wasm", "application/wasm"),
    "/nam-processor.js": (APP_NAM / "worklet" / "nam-processor.js", "text/javascript"),
    "/di.wav": (DI, "audio/wav"),
    "/cab.wav": (HERE / "assets" / "cab_irs" / "Box_AC30_2x12" / "dyn_cone.wav", "audio/wav"),
}
FONT_ALLOW = {"bebas", "barlow", "anton", "crete", "graffiti", "ink"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencioso
        pass

    def _send(self, data: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ROUTES:
                f, ct = ROUTES[path]
                self._send(f.read_bytes(), ct)
                return
            if path.startswith("/api/plugins/rig_builder/asset/font/"):
                key = path.rsplit("/", 1)[-1].split(".")[0].lower()
                if key in FONT_ALLOW:
                    self._send((HERE / "assets" / "fonts" / f"{key}.ttf").read_bytes(),
                               "font/ttf")
                    return
            if path.startswith("/nam/"):
                name = path[len("/nam/"):]
                cand = (LIB / "amps" / "a2_vox_ac30" / name).resolve()
                if cand.is_file() and cand.is_relative_to(LIB.resolve()):
                    self._send(cand.read_bytes(), "application/json")
                    return
        except OSError as e:
            self.send_error(500, str(e))
            return
        self.send_error(404)


if __name__ == "__main__":
    missing = [str(p) for p, _ in ROUTES.values() if not p.exists()]
    if missing:
        print("⚠ faltan archivos:\n  " + "\n  ".join(missing))
    grids = json.loads((HERE / "data" / "a2_capture_grids.json").read_text())
    n = len((grids.get("Amp_EN30") or {}).get("captures") or [])
    print(f"A2 tester — {n} capturas indexadas · http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
