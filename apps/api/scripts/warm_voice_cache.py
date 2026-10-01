"""Register one explicitly reviewed rehearsal clip for offline ASR replay."""

import argparse
from pathlib import Path

from daari.voice.asr import register_rehearsal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("transcript", type=Path, help="UTF-8 file containing the reviewed transcript")
    parser.add_argument("--locale", choices=("en", "te", "hi"), required=True)
    args = parser.parse_args()
    register_rehearsal(args.audio.read_bytes(), args.transcript.read_text(), args.locale)
    print("Rehearsal transcript cached locally for this exact audio clip.")


if __name__ == "__main__":
    main()
