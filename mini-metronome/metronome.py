import time
import argparse
import sys
import os

# Optional sound support
USE_SOUND = False
try:
    import simpleaudio as sa  # optional dependency
    USE_SOUND = True
except Exception:
    USE_SOUND = False

CLICK_HI = os.path.join("sounds", "click_hi.wav")
CLICK_LO = os.path.join("sounds", "click_lo.wav")

def load_sound(path):
    if not USE_SOUND or not os.path.exists(path):
        return None
    try:
        return sa.WaveObject.from_wave_file(path)
    except Exception:
        return None

def play_sound(wave_obj):
    if wave_obj is None or not USE_SOUND:
        # terminal bell fallback
        sys.stdout.write('\a')
        sys.stdout.flush()
        return
    try:
        wave_obj.play()  # fire-and-forget
    except Exception:
        pass

def metronome(bpm: int, beats: int | None, meter: str):
    """
    Run a metronome at the given BPM.

    Args:
        bpm (int): Beats per minute.
        beats (int|None): Total beats to play (None = infinite).
        meter (str): like '4/4' or '3/4'; only the top number accents downbeats.
    """
    try:
        top = int(meter.split('/')[0])
        if top < 1:
            raise ValueError
    except Exception:
        print(f"Invalid meter '{meter}'. Use like '4/4' or '3/4'.")
        sys.exit(1)

    interval = 60.0 / bpm
    count = 0

    hi = load_sound(CLICK_HI)
    lo = load_sound(CLICK_LO)

    print(f"Metronome: {bpm} bpm, meter {meter} ({'sound' if USE_SOUND and (hi or lo) else 'no sound'})")
    print("Press Ctrl+C to stop.\n")

    try:
        start = time.perf_counter()
        while True:
            count += 1
            is_downbeat = (count - 1) % top == 0

            # Visual cue
            sys.stdout.write("TICK\n" if is_downbeat else "tick\n")
            sys.stdout.flush()

            # Sound cue
            play_sound(hi if is_downbeat and hi else (lo if lo else None))

            # Drift-resistant sleep
            next_beat_time = start + count * interval
            remaining = next_beat_time - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)

            if beats is not None and count >= beats:
                break
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"\nError: {e}")

def main():
    p = argparse.ArgumentParser(description="Mini Python Metronome")
    p.add_argument("bpm", type=int, help="Beats per minute (e.g., 60, 90, 120)")
    p.add_argument("-n", "--beats", type=int, default=None, help="Total beats to play (default: infinite)")
    p.add_argument("-m", "--meter", type=str, default="4/4", help="Meter for accenting (e.g., 4/4, 3/4)")
    args = p.parse_args()

    if args.bpm <= 0:
        print("BPM must be a positive integer.")
        sys.exit(1)

    metronome(args.bpm, args.beats, args.meter)

if __name__ == "__main__":
    main()