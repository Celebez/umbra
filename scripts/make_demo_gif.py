#!/usr/bin/env python3
"""Render a terminal-style demo GIF for Umbra from real command output.

Pure local render (no network, no server). Frames simulate typing the demo
commands and printing captured output, in a dark premium terminal skin.
"""
import io, textwrap, subprocess, pathlib
from PIL import Image, ImageDraw, ImageFont

FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

W, H = 960, 540
BG = (5, 8, 22)
BAR = (12, 16, 34)
PROMPT = (33, 233, 154)      # emerald
TEXT = (220, 235, 230)
MUTED = (120, 140, 150)
GOLD = (255, 209, 102)

# Real captured lines (loopback demo, no server contact)
SCENES = [
    ("$ pip install umbra", []),
    ("$ curl -fsSL https://raw.githubusercontent.com/Celebez/umbra/main/install.sh | bash",
     ["[umbra] engine: h4ckf0r0day/obscura @ v0.1.10 (obscura-x86_64-linux.tar.gz)",
      "[umbra] engine installed: ~/.local/bin/umbra-engine",
      "[umbra] installing python package...",
      "[umbra] done. Usage (local loopback, not public):",
      "  umbra fetch https://example.com --dump markdown",
      "  umbra serve --port 9222   # binds 127.0.0.1:9222"]),
    ("$ umbra fetch https://example.com --dump markdown",
     ["# Example Domain",
      "",
      "This domain is for use in documentation examples without needing permission.",
      "Avoid use in operations.",
      "",
      "[Learn more](https://iana.org/domains/example)"]),
    ("$ umbra identities new --name demo",
     ['{"seed": "c2e4e6991ae3568b", "name": "demo",',
      ' "platform_string": "Macintosh; Intel Mac OS X 10_15_7",',
      ' "viewport": "2560x1440", "timezone": "Europe/London",',
      ' "locale": "en-GB", "proxy": ""}']),
    ("$ umbra serve --port 9222",
     ["[umbra] CDP endpoint: ws://127.0.0.1:9222/devtools/browser/...",
      "[umbra] bound to 127.0.0.1:9222 (local only, not public)",
      "[umbra] press Ctrl-C to stop"]),
]

def font(sz, bold=False):
    return ImageFont.truetype(FONT_MONO_BOLD if bold else FONT_MONO, sz)

def wrap(text, fnt, maxw):
    out = []
    for line in text.split("\n"):
        if fnt.getlength(line) <= maxw:
            out.append(line)
        else:
            out.extend(textwrap.wrap(line, width=max(10, int(maxw / (fnt.getlength("m") or 1)))))
    return out

def draw_terminal(d, scenes_shown, typing=None, typed=0):
    d.rectangle([0, 0, W, H], fill=BG)
    # title bar
    d.rectangle([0, 0, W, 34], fill=BAR)
    for i, c in enumerate([(255,95,86),(255,189,46),(39,201,63)]):
        d.ellipse([16 + i*22, 11, 28 + i*22, 23], fill=c)
    f = font(15, bold=True)
    d.text((W/2 - f.getlength("Umbra — shadow engine  (local, 127.0.0.1)")/2, 8),
           "Umbra — shadow engine  (local, 127.0.0.1)", font=f, fill=MUTED)
    y = 52
    lh = 22
    for cmd, out in scenes_shown:
        d.text((24, y), cmd, font=font(16, bold=True), fill=PROMPT); y += lh
        for ln in out:
            col = GOLD if ln.startswith("[umbra]") or ln.startswith("  ") or ln.startswith("\"") else TEXT
            d.text((24, y), ln, font=font(15), fill=col); y += lh
        y += 6
    if typing is not None:
        line = typing[:typed]
        d.text((24, y), line, font=font(16, bold=True), fill=PROMPT)
        d.rectangle([24 + font(16,True).getlength(line), y, 24 + font(16,True).getlength(line)+9, y+18], fill=TEXT)

def main():
    frames = []
    for cmd, out in SCENES:
        # typing the command
        sub = []
        for t in range(1, len(cmd)+1, 2):
            img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
            draw_terminal(d, sub, typing=cmd, typed=t)
            frames.append(img)
        sub = [(cmd, out)]
        img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
        draw_terminal(d, sub, typing=None)
        frames.append(img)
        # hold output
        for _ in range(8):
            img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
            draw_terminal(d, sub)
            frames.append(img)
    # final hold + loop
    for _ in range(20):
        frames.append(frames[-1])
    out_path = pathlib.Path(__file__).resolve().parent.parent / "assets" / "demo.gif"
    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=70, loop=0, optimize=False)
    print("wrote", out_path, len(frames), "frames")

if __name__ == "__main__":
    main()
