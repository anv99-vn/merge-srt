#!/usr/bin/env python3
import argparse
import subprocess
import sys
import re
from pathlib import Path


def pick_file(title: str, filetypes: list[tuple]) -> Path | None:
    """Open a Windows file-picker dialog. Returns None if cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(title=title, filetypes=filetypes)
        root.destroy()
        return Path(path) if path else None
    except Exception as e:
        print(f"  [warn] File dialog unavailable: {e}")
        return None


def pick_save(title: str, default_name: str, filetypes: list[tuple]) -> Path | None:
    """Open a Windows save-file dialog. Returns None if cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(
            title=title,
            initialfile=default_name,
            defaultextension=".mp4",
            filetypes=filetypes,
        )
        root.destroy()
        return Path(path) if path else None
    except Exception as e:
        print(f"  [warn] File dialog unavailable: {e}")
        return None

COLORS = {
    "white":  "&H00FFFFFF",
    "yellow": "&H0000FFFF",
    "green":  "&H0000FF00",
    "cyan":   "&H00FFFF00",
    "red":    "&H000000FF",
    "blue":   "&H00FF0000",
}


def get_duration(video_path: Path) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True, text=True,
        )
        return float(result.stdout.strip())
    except (FileNotFoundError, ValueError):
        return None


def time_to_seconds(time_str: str) -> float:
    m = re.match(r"(\d+):(\d+):(\d+)[\.,](\d+)", time_str)
    if not m:
        return 0.0
    h, mn, s, frac = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    return h * 3600 + mn * 60 + s + int(frac) / (10 ** len(frac))


def fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def srt_path_for_filter(srt: Path) -> str:
    """Escape path for FFmpeg subtitles filter (handles Windows drive letters)."""
    p = str(srt.resolve())
    if sys.platform == "win32":
        # Forward slashes + escape colon in drive letter: C: -> C\:
        p = p.replace("\\", "/")
        p = re.sub(r"^([A-Za-z]):", r"\1\\:", p)
    return p


def draw_bar(current: float, total: float, width: int = 40) -> str:
    pct = min(1.0, current / total) if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct*100:5.1f}%  {fmt_time(current)}/{fmt_time(total)}"


def burn(input_video: Path, input_srt: Path, output: Path,
         font_size: int, color: str, font_name: str) -> None:
    srt = srt_path_for_filter(input_srt)
    primary = COLORS.get(color.lower(), "&H00FFFFFF")
    style = (
        f"FontSize={font_size},"
        f"PrimaryColour={primary},"
        f"FontName={font_name},"
        "BorderStyle=1,Outline=1,Shadow=0,MarginV=20"
    )
    vf = f"subtitles='{srt}':force_style='{style}'"

    cmd = [
        "ffmpeg",
        "-i", str(input_video),
        "-vf", vf,
        "-c:a", "copy",
        "-progress", "pipe:1",
        "-nostats",
        "-y",
        str(output),
    ]

    duration = get_duration(input_video)

    print(f"  Input : {input_video}")
    print(f"  Sub   : {input_srt}")
    print(f"  Output: {output}")
    if duration:
        print(f"  Length: {fmt_time(duration)}")
    print()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        print("  ERROR: ffmpeg not found. Make sure ffmpeg is installed and in PATH.")
        sys.exit(1)

    for line in process.stdout:
        line = line.strip()
        if line.startswith("out_time=") and duration:
            t = time_to_seconds(line.split("=", 1)[1])
            print(f"\r  {draw_bar(t, duration)}", end="", flush=True)

    process.wait()
    print()

    if process.returncode == 0:
        size_mb = output.stat().st_size / 1_048_576
        print(f"\n  Done!  {output}  ({size_mb:.1f} MB)")
    else:
        print(f"\n  FFmpeg exited with code {process.returncode}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="merge-srt",
        description="Burn SRT subtitles into an MP4 video using FFmpeg.\n"
                    "Run with no arguments to use file-picker dialogs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  python merge_srt.py                          # interactive file picker
  python merge_srt.py video.mp4 sub.srt
  python merge_srt.py video.mp4 sub.srt -o out.mp4
  python merge_srt.py video.mp4 sub.srt --font-size 28 --color yellow
  python merge_srt.py video.mp4 sub.srt --font "Times New Roman"
""",
    )
    parser.add_argument("video", type=Path, nargs="?", help="Input MP4 video")
    parser.add_argument("srt",   type=Path, nargs="?", help="Input SRT subtitle file")
    parser.add_argument("-o", "--output", type=Path,
                        help="Output file (default: <video>_subbed.mp4)")
    parser.add_argument("--font-size", type=int, default=24, metavar="N",
                        help="Font size (default: 24)")
    parser.add_argument("--color", default="white", choices=list(COLORS),
                        help="Subtitle color (default: white)")
    parser.add_argument("--font", default="Arial", metavar="NAME",
                        help="Font name (default: Arial)")

    args = parser.parse_args()

    # --- file picker mode (no CLI args) ---
    if args.video is None:
        print("  No arguments given — opening file picker...\n")

        video = pick_file(
            "Select MP4 video",
            [("MP4 video", "*.mp4 *.mkv *.avi *.mov"), ("All files", "*.*")],
        )
        if not video:
            print("  Cancelled.")
            sys.exit(0)

        srt = pick_file(
            "Select SRT subtitle",
            [("SRT subtitle", "*.srt"), ("All files", "*.*")],
        )
        if not srt:
            print("  Cancelled.")
            sys.exit(0)

        default_out = video.stem + "_subbed.mp4"
        output = pick_save(
            "Save output as",
            default_out,
            [("MP4 video", "*.mp4")],
        )
        if not output:
            print("  Cancelled.")
            sys.exit(0)

        burn(video, srt, output, args.font_size, args.color, args.font)
        return

    # --- CLI arg mode ---
    if args.srt is None:
        parser.error("Please provide both VIDEO and SRT arguments, or run with no arguments for file picker.")

    if not args.video.exists():
        parser.error(f"Video not found: {args.video}")
    if not args.srt.exists():
        parser.error(f"SRT not found: {args.srt}")

    output = args.output or args.video.with_stem(args.video.stem + "_subbed")
    burn(args.video, args.srt, output, args.font_size, args.color, args.font)


if __name__ == "__main__":
    main()
