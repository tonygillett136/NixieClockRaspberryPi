"""
Display tricks for the Nixie clock.

Each trick is a generator that yields (digits_string, led_tuple, delay) frames.
The clock engine plays them and then resumes normal time display.
"""

import random
import time
import math


def _current_time_str():
    """Return current time as HHMMSS string."""
    t = time.localtime()
    return time.strftime("%H%M%S", t)


def slot_machine(duration=4.0):
    """Slot machine: digits spin then lock in one by one, left to right."""
    target = _current_time_str()
    fps = 30
    total_frames = int(duration * fps)
    # Each tube locks at a different time
    lock_times = [int(total_frames * (i + 1) / 7) for i in range(6)]

    for frame in range(total_frames):
        digits = []
        for i in range(6):
            if frame >= lock_times[i]:
                digits.append(target[i])
            else:
                digits.append(str(random.randint(0, 9)))
        yield ''.join(digits), None, 1.0 / fps

    # Final frame shows real time
    yield _current_time_str(), None, 0


def cascade(duration=3.0):
    """Digits waterfall 9-8-7...0 sequentially across all tubes."""
    for cycle in range(2):
        for digit in range(9, -1, -1):
            for pos in range(6):
                chars = list("000000")
                chars[pos] = str(digit)
                yield ''.join(chars), None, duration / 120


def hacker_mode(duration=3.0):
    """Rapid random digits like a movie decryption, then resolves to time."""
    target = _current_time_str()
    fps = 25
    total_frames = int(duration * fps)
    resolve_start = int(total_frames * 0.6)

    for frame in range(total_frames):
        digits = []
        for i in range(6):
            # Resolve digits from left to right in the last 40% of frames
            resolve_point = resolve_start + int((total_frames - resolve_start) * i / 6)
            if frame >= resolve_point:
                digits.append(target[i])
            else:
                digits.append(str(random.randint(0, 9)))
        # Green "matrix" LEDs during hacking
        green = min(100, int(frame / total_frames * 100))
        yield ''.join(digits), (0, green, 0), 1.0 / fps

    yield _current_time_str(), None, 0


def wave(cycles=3):
    """A single lit digit runs across the display like a wave."""
    for _ in range(cycles):
        for pos in range(6):
            chars = ['0'] * 6
            chars[pos] = str(random.randint(1, 9))
            # Color follows the wave
            r = max(0, 100 - abs(pos - 0) * 30)
            g = max(0, 100 - abs(pos - 2) * 30)
            b = max(0, 100 - abs(pos - 4) * 30)
            yield ''.join(chars), (r, g, b), 0.12
        for pos in range(4, 0, -1):
            chars = ['0'] * 6
            chars[pos] = str(random.randint(1, 9))
            r = max(0, 100 - abs(pos - 0) * 30)
            g = max(0, 100 - abs(pos - 2) * 30)
            b = max(0, 100 - abs(pos - 4) * 30)
            yield ''.join(chars), (r, g, b), 0.12

    yield _current_time_str(), None, 0


def date_flash(duration=3.0):
    """Briefly show today's date (DD-MM-YY) then fade back to time."""
    t = time.localtime()
    date_str = time.strftime("%d%m%y", t)

    # Flash on with blue LEDs
    for _ in range(int(duration / 0.05)):
        yield date_str, (0, 0, 80), 0.05

    yield _current_time_str(), None, 0


def digit_chase(cycles=4):
    """A single digit 'runs' left to right while others go dark."""
    runner = random.randint(1, 9)
    for _ in range(cycles):
        for pos in range(6):
            chars = ['0'] * 6
            chars[pos] = str(runner)
            # Warm amber trail
            yield ''.join(chars), (80, 30, 0), 0.1
        runner = (runner % 9) + 1

    yield _current_time_str(), None, 0


def countdown(start=10):
    """Count down from a number, then flash zeros."""
    for n in range(start, -1, -1):
        s = str(n).zfill(6)
        # Go from green to red as countdown progresses
        red = int((1 - n / start) * 100)
        green = int((n / start) * 100)
        yield s, (red, green, 0), 1.0

    # Flash at zero
    for flash in range(6):
        if flash % 2 == 0:
            yield "000000", (100, 0, 0), 0.2
        else:
            yield "000000", (0, 0, 0), 0.2

    yield _current_time_str(), None, 0


def breathe_leds(duration=6.0):
    """Slowly pulse the RGB LEDs through a breathing pattern."""
    time_str = _current_time_str()
    fps = 30
    total_frames = int(duration * fps)

    for frame in range(total_frames):
        t = frame / fps
        # Sine wave breathing through RGB
        r = int(50 + 50 * math.sin(t * 2.0))
        g = int(50 + 50 * math.sin(t * 2.0 + 2.094))  # +120 degrees
        b = int(50 + 50 * math.sin(t * 2.0 + 4.189))  # +240 degrees
        yield _current_time_str(), (r, g, b), 1.0 / fps

    yield _current_time_str(), None, 0


def all_nines(duration=2.0):
    """Flash all tubes to 999999 then back - dramatic full display."""
    for flash in range(4):
        if flash % 2 == 0:
            yield "999999", (100, 100, 100), duration / 4
        else:
            yield "000000", (0, 0, 0), duration / 4

    yield _current_time_str(), None, 0


def cathode_clean():
    """Run all digits through each tube to prevent cathode poisoning."""
    for digit in range(10):
        chars = []
        for pos in range(6):
            d = (digit + pos) % 10
            chars.append(str(d))
        yield ''.join(chars), None, 0.3

    yield _current_time_str(), None, 0


def temperature_flash(temp_c):
    """Display a temperature value on the tubes."""
    # Format as "  XX  " centered, or "  XXX " for 100+
    temp_str = str(int(round(temp_c))).zfill(2)
    display = "00" + temp_str + "00"
    if len(display) > 6:
        display = display[:6]

    for _ in range(40):
        # Warm color for temp
        yield display, (100, 40, 0), 0.075

    yield _current_time_str(), None, 0


# Registry of all available tricks
TRICKS = {
    'slot_machine': ('Slot Machine', 'Digits spin like a one-armed bandit', slot_machine),
    'cascade': ('Cascade', 'Digits waterfall across the tubes', cascade),
    'hacker': ('Hacker Mode', 'Random digits resolve to the time', hacker_mode),
    'wave': ('The Wave', 'A digit ripples back and forth', wave),
    'date': ('Show Date', 'Flash today\'s date (DDMMYY)', date_flash),
    'chase': ('Digit Chase', 'A digit runs across the tubes', digit_chase),
    'countdown': ('Countdown', 'Count down from 10', countdown),
    'breathe': ('Breathe', 'Slow RGB LED breathing', breathe_leds),
    'all_nines': ('All Nines', 'Dramatic full-display flash', all_nines),
    'clean': ('Cathode Clean', 'Cycle all digits to prevent poisoning', cathode_clean),
}
