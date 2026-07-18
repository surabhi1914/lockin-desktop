"""Generate LockIn's deterministic original two-tone completion chime."""

import argparse
import math
import struct
import wave
from pathlib import Path


def generate(path: Path) -> None:
    rate = 44_100
    duration = 0.72
    frames = bytearray()
    total = int(rate * duration)
    for index in range(total):
        time = index / rate
        attack = min(1.0, time / 0.025)
        release = max(0.0, 1.0 - time / duration) ** 2.4
        first = math.sin(2 * math.pi * 523.25 * time)
        second = math.sin(2 * math.pi * 659.25 * time) * min(1.0, time / 0.16)
        shimmer = math.sin(2 * math.pi * 1046.5 * time) * 0.12
        sample = int(32767 * 0.20 * attack * release * (0.62 * first + 0.32 * second + shimmer))
        frames.extend(struct.pack("<h", max(-32768, min(32767, sample))))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(frames)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("app/assets/lockin_completion.wav"),
    )
    args = parser.parse_args(argv)
    generate(args.output)
    print(f"generated: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
