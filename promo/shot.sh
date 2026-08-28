#!/usr/bin/env bash
# 把 poster.html 截成 X 用的图。Chrome headless，2 倍图。
#
#   ./shot.sh                 出 4:5 和 3:4 两种
#   ./shot.sh 1200 1500 名字   自定义
#
# 4:5 (1200x1500) 是 X 单图不被裁的最高竖版比例，优先用它。
# 3:4 (1200x1600) 在 timeline 里可能被裁掉底部，点开才完整。
set -euo pipefail
cd "$(dirname "$0")"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
mkdir -p out

shoot() { # w h name
  "$CHROME" --headless --disable-gpu --hide-scrollbars \
    --force-device-scale-factor=2 --window-size="$1,$2" \
    --screenshot="out/$3.png" "file://$PWD/poster.html" 2>/dev/null || true
  python3 - "$3" <<'PY'
import struct, sys, pathlib
p = pathlib.Path(f"out/{sys.argv[1]}.png")
w, h = struct.unpack(">II", p.read_bytes()[16:24])
print(f"  out/{p.name}  {w}x{h}  高/宽 {h/w:.3f}  {p.stat().st_size//1024}KB")
PY
}

if [ $# -eq 3 ]; then
  shoot "$1" "$2" "$3"
else
  shoot 1200 1500 poster_4x5
  shoot 1200 1600 poster_3x4
fi
