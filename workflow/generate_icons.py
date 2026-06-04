#!/usr/bin/env python3
"""Generate PNG icons for Alfred workflow items. Requires macOS."""

import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(SCRIPT_DIR, "icons")

EMOJI_ICONS = {
    "clear.png":    "🧹",   # sweep / clear
    "meeting.png":  "📅",
    "focusing.png": "🎧",
    "lunch.png":    "🍴",
    "sick.png":     "🤒",
    "vacation.png": "🌴",
    "wfh.png":      "🏠",
    "dnd.png":      "🔕",
    "commute.png":  "🚌",
    "coffee.png":   "☕",
    "call.png":     "📞",
    "brb.png":      "🔙",
    "custom.png":   "💬",
    "setup.png":    "⚙️",
}

JXA_TEMPLATE = """\
ObjC.import('AppKit');

var emoji   = EMOJI;
var outPath = OUTPATH;
var size    = SIZE;

// NSBitmapImageRep + NSGraphicsContext works headless (no lockFocus/screen needed)
var rep = $.NSBitmapImageRep.alloc\
.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBitmapFormatBytesPerRowBitsPerPixel(
    null, size, size, 8, 4, true, false, "NSCalibratedRGBColorSpace", 0, 0, 0
);
$.NSGraphicsContext.setCurrentContext($.NSGraphicsContext.graphicsContextWithBitmapImageRep(rep));

var font    = $.NSFont.systemFontOfSize(size * 0.80);
var attrs   = ObjC.wrap({"NSFont": font});
var str     = $.NSString.stringWithString(emoji);
var strSize = str.sizeWithAttributes(attrs);
str.drawAtPointWithAttributes(
    $.NSMakePoint((size - strSize.width) / 2, (size - strSize.height) / 2),
    attrs
);

rep.representationUsingTypeProperties(4, ObjC.wrap({})).writeToFileAtomically(outPath, true);
"""


def make_emoji_png(emoji, output_path, size=160):
    jxa = (JXA_TEMPLATE
           .replace("EMOJI",   json.dumps(emoji))
           .replace("OUTPATH", json.dumps(output_path))
           .replace("SIZE",    str(size)))
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", jxa],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ✗  {r.stderr.strip()}", file=sys.stderr)
        return False
    return True


def extract_slack_icon(output_path, size=256):
    """Copy Slack.app's icns → PNG. Returns True on success."""
    candidates = [
        "/Applications/Slack.app/Contents/Resources/slack.icns",
        "/Applications/Slack.app/Contents/Resources/electron.icns",
        "/Applications/Slack.app/Contents/Resources/app.icns",
    ]
    for src in candidates:
        if not os.path.exists(src):
            continue
        r = subprocess.run(
            ["sips", "-s", "format", "png", src,
             "--out", output_path, "--resampleWidth", str(size)],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            return True
    return False


def main():
    os.makedirs(ICONS_DIR, exist_ok=True)

    print("Generating status icons…")
    for filename, emoji in EMOJI_ICONS.items():
        out = os.path.join(ICONS_DIR, filename)
        ok = make_emoji_png(emoji, out)
        print(f"  {'✓' if ok else '✗'}  {emoji}  →  icons/{filename}")

    print("\nGenerating workflow icon…")
    icon_path = os.path.join(SCRIPT_DIR, "icon.png")
    if extract_slack_icon(icon_path):
        print("  ✓  Extracted from Slack.app  →  icon.png")
    else:
        print("  Slack.app not found — using fallback emoji…")
        ok = make_emoji_png("💬", icon_path, size=256)
        print(f"  {'✓' if ok else '✗'}  icon.png")


if __name__ == "__main__":
    main()
