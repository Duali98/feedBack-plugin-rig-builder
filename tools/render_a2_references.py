#!/usr/bin/env python3
"""Renderiza REFERENCIAS de calibración desde un pack de capturas NAM A2.

La decisión (2026-07-25): los packs A2 no se usan como amp de juego (poca
flexibilidad) sino como la VERDAD DE TERRENO para calibrar nuestros amp sims
circuit-real — cada captura ES el amp real en un punto de perillas conocido, y
podemos renderizarla con el DI estándar para compararla 1:1 contra el VST
(docs/REFERENCE_MATCHING_WORKFLOW.md: compare_amp_reference / _nonlinear).

Usa el MISMO core WASM del app (nam-core, soporta A2) vía node — render
bit-idéntico a como sonaría en el juego.

Uso:
  python3 tools/render_a2_references.py --out "/ruta/refs" \
      [--pack "<dir del pack o subdir instalado>"] [--di brit] \
      [--select 'TB_V5|N_V10']            # regex sobre el nombre; default: todo
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
APP_NAM = Path("/Applications/feedback.app/Contents/Resources/slopsmith/plugins/nam_tone")
LIB_PACK = (Path.home() / "Library/Application Support/feedback-desktop/"
            "slopsmith-config/nam_models/amps/a2_vox_ac30")
DI_BRIT = (Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/"
           "test logic/ce1_ref/brit_di.wav")

RENDER_JS = r"""
const fs = require('fs');
const [,, glueP, wasmP, namP, inP, outP] = process.argv;
(async () => {
  const NAMCore = require(glueP);
  const M = await NAMCore({ wasmBinary: fs.readFileSync(wasmP) });
  const ctx = M._nam_create();
  M._nam_set_sample_rate(ctx, 48000);
  const json = fs.readFileSync(namP);
  const ptr = M._malloc(json.length + 1);
  M.HEAPU8.set(json, ptr); M.HEAPU8[ptr + json.length] = 0;
  const rc = M._nam_load_model(ctx, ptr, json.length);
  M._free(ptr);
  if (rc !== 0) { console.error('nam_load_model rc=' + rc); process.exit(2); }
  const inRaw = fs.readFileSync(inP);
  const n = inRaw.length >> 2;
  const inF = new Float32Array(inRaw.buffer, inRaw.byteOffset, n);
  const out = Buffer.alloc(n * 4);
  const B = 4096;
  const inPtr = M._malloc(B * 4), outPtr = M._malloc(B * 4);
  for (let off = 0; off < n; off += B) {
    const len = Math.min(B, n - off);
    M.HEAPF32.set(inF.subarray(off, off + len), inPtr >> 2);
    M._nam_process(ctx, inPtr, outPtr, len);
    Buffer.from(M.HEAPU8.buffer, outPtr, len * 4).copy(out, off * 4);
  }
  fs.writeFileSync(outP, out);
})().catch(e => { console.error(e); process.exit(1); });
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="directorio de salida de las refs")
    ap.add_argument("--pack", default=str(LIB_PACK))
    ap.add_argument("--di", default=str(DI_BRIT), help="DI wav (default: brit_di)")
    ap.add_argument("--select", default=None, help="regex sobre el nombre de captura")
    args = ap.parse_args()

    pack = Path(args.pack).expanduser()
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    caps = sorted(pack.glob("*.nam"))
    if args.select:
        rx = re.compile(args.select)
        caps = [c for c in caps if rx.search(c.name)]
    if not caps:
        raise SystemExit("ninguna captura seleccionada")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        js = td / "render_nam.js"
        js.write_text(RENDER_JS)
        di_f32 = td / "di.f32"
        subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-i", args.di,
                        "-ac", "1", "-ar", "48000", "-f", "f32le", str(di_f32)],
                       check=True)
        for i, cap in enumerate(caps, 1):
            # SLAMMIN_VOX_AC30_TB_V5_TC0_B5_T5_NOON_S.nam → TB_V5_TC0_B5_T5_NOON.wav
            stem = re.sub(r"^SLAMMIN_[A-Z0-9_]*?(?=(N|TB)_V)", "", cap.stem)
            stem = re.sub(r"_S$", "", stem).strip("_ ")
            out_wav = out_dir / f"{stem}.wav"
            if out_wav.exists():
                print(f"  [{i}/{len(caps)}] ya está: {out_wav.name}")
                continue
            raw = td / "out.f32"
            subprocess.run(["node", str(js), str(APP_NAM / "wasm" / "nam-core.js"),
                            str(APP_NAM / "wasm" / "nam-core.wasm"), str(cap),
                            str(di_f32), str(raw)], check=True,
                           capture_output=True)
            subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-f", "f32le",
                            "-ar", "48000", "-ac", "1", "-i", str(raw),
                            "-c:a", "pcm_s24le", str(out_wav)], check=True)
            print(f"  [{i}/{len(caps)}] {out_wav.name}")
    print(f"listo → {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
