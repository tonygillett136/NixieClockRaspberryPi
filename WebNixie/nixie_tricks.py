"""
Display tricks for the Nixie clock.

Each trick is a generator that yields (digits_string, led_tuple, delay) frames.
The clock engine plays them and then resumes normal time display.
LED tuples are (r, g, b) with values 0-100. None means keep current LEDs.
"""

import random
import time
import math


def _current_time_str():
    """Return current time as HHMMSS string."""
    return time.strftime("%H%M%S", time.localtime())


def slot_machine(duration=5.0):
    """Slot machine: digits spin then lock in one by one with dramatic lighting."""
    target = _current_time_str()
    fps = 30
    total_frames = int(duration * fps)
    lock_times = [int(total_frames * (i + 1) / 7.5) for i in range(6)]

    for frame in range(total_frames):
        digits = []
        locked_count = 0
        for i in range(6):
            if frame >= lock_times[i]:
                digits.append(target[i])
                locked_count += 1
            else:
                digits.append(str(random.randint(0, 9)))

        # LEDs: spinning gold, flash white on each lock, settle to warm
        progress = frame / total_frames
        flash = False
        for lt in lock_times:
            if abs(frame - lt) < 2:
                flash = True

        if flash:
            yield ''.join(digits), (100, 100, 100), 1.0 / fps
        else:
            spin_intensity = int(40 + 40 * abs(math.sin(frame * 0.5)))
            r = spin_intensity
            g = int(spin_intensity * 0.4)
            yield ''.join(digits), (r, g, 0), 1.0 / fps

    # Final reveal flash
    yield target, (100, 80, 30), 0.3
    yield _current_time_str(), None, 0


def cascade(duration=4.0):
    """Digits waterfall 9-0 across tubes with colour trailing."""
    colours = [
        (100, 20, 0), (80, 40, 0), (60, 60, 0),
        (40, 80, 0), (20, 60, 40), (0, 40, 80),
        (0, 20, 100), (20, 0, 80), (40, 0, 60),
        (80, 0, 20),
    ]
    for cycle in range(2):
        for digit in range(9, -1, -1):
            for pos in range(6):
                chars = list(_current_time_str())
                chars[pos] = str(digit)
                r, g, b = colours[digit]
                # Dim tubes not being cascaded
                yield ''.join(chars), (r, g, b), duration / 120

    yield _current_time_str(), None, 0


def hacker_mode(duration=4.0):
    """Rapid random digits like a movie decryption, with green matrix LEDs."""
    target = _current_time_str()
    fps = 30
    total_frames = int(duration * fps)
    resolve_start = int(total_frames * 0.55)

    for frame in range(total_frames):
        digits = []
        resolved = 0
        for i in range(6):
            resolve_point = resolve_start + int((total_frames - resolve_start) * i / 6)
            if frame >= resolve_point:
                digits.append(target[i])
                resolved += 1
            else:
                digits.append(str(random.randint(0, 9)))

        # Flickering green matrix, brighter as more digits resolve
        flicker = random.randint(0, 30)
        base_green = 30 + int(resolved * 12) + flicker
        r = min(100, resolved * 15)  # Shifts warm as it resolves
        yield ''.join(digits), (r, min(100, base_green), 0), 1.0 / fps

    # Resolved - bright flash
    yield target, (100, 100, 50), 0.3
    yield _current_time_str(), None, 0


def wave(cycles=3):
    """A lit digit ripples back and forth with rainbow trailing."""
    for c in range(cycles):
        positions = list(range(6)) + list(range(4, 0, -1))
        for idx, pos in enumerate(positions):
            chars = ['0'] * 6
            # Light up the wave position and its neighbours
            for offset in range(-1, 2):
                p = pos + offset
                if 0 <= p < 6:
                    chars[p] = str(random.randint(1, 9) if offset == 0 else 0)

            # Rainbow based on position
            hue = (pos / 5.0 + c / cycles) % 1.0
            r = int(100 * max(0, math.sin(hue * 6.283)))
            g = int(100 * max(0, math.sin(hue * 6.283 + 2.094)))
            b = int(100 * max(0, math.sin(hue * 6.283 + 4.189)))
            yield ''.join(chars), (max(5, r), max(5, g), max(5, b)), 0.08

    yield _current_time_str(), None, 0


def date_flash(duration=3.0):
    """Show today's date with a blue pulse."""
    t = time.localtime()
    date_str = time.strftime("%d%m%y", t)

    # Sweep in from sides
    for i in range(4):
        display = '0' * (3 - i) + date_str[:i*2+0][:6]
        display = (display + '000000')[:6]
        yield display, (0, 0, 40 + i * 15), 0.12

    # Hold with breathing blue
    fps = 20
    for frame in range(int(duration * fps)):
        t_val = frame / fps
        blue = int(50 + 40 * math.sin(t_val * 3))
        yield date_str, (10, 10, blue), 1.0 / fps

    # Sweep out
    for i in range(3, -1, -1):
        display = '0' * (3 - i) + date_str[:i*2]
        display = (display + '000000')[:6]
        yield display, (0, 0, 20 + i * 10), 0.12

    yield _current_time_str(), None, 0


def digit_chase(cycles=5):
    """A digit runs across with a comet tail effect."""
    for c in range(cycles):
        runner = random.randint(1, 9)
        for pos in range(6):
            chars = ['0'] * 6
            chars[pos] = str(runner)
            # Tail: dim previous positions
            if pos > 0:
                chars[pos - 1] = str(max(0, runner - 3))
            if pos > 1:
                chars[pos - 2] = str(max(0, runner - 6))

            # Warm comet colour
            r = 80 + int(20 * (pos / 5))
            g = 30 + int(20 * (pos / 5))
            yield ''.join(chars), (r, g, 5), 0.07

        # Brief flash at end
        yield str(runner) * 6, (100, 60, 10), 0.1

    yield _current_time_str(), None, 0


def countdown(start=10):
    """Count down with dramatic colour shift and finale."""
    for n in range(start, -1, -1):
        s = str(n).zfill(6)
        progress = 1 - (n / start)
        red = int(progress * 100)
        green = int((1 - progress) * 80)

        # Pulse faster as we get closer to zero
        pulse_speed = 1.0 if n > 5 else (0.5 if n > 2 else 0.3)
        # Bright flash on each number change
        yield s, (min(100, red + 30), green, 0), 0.1
        yield s, (red, max(0, green - 10), 0), pulse_speed - 0.1

    # Dramatic finale at zero
    for flash in range(8):
        if flash % 2 == 0:
            yield "000000", (100, 0, 0), 0.1
        else:
            yield "000000", (100, 100, 100), 0.1

    # Quick ramp back to time
    t = _current_time_str()
    yield t, (80, 40, 0), 0.2
    yield t, (40, 20, 0), 0.2
    yield _current_time_str(), None, 0


def breathe_leds(duration=8.0):
    """Slow RGB breathing through the spectrum while showing time."""
    fps = 25
    total_frames = int(duration * fps)

    for frame in range(total_frames):
        t = frame / fps
        r = int(50 + 50 * math.sin(t * 1.5))
        g = int(50 + 50 * math.sin(t * 1.5 + 2.094))
        b = int(50 + 50 * math.sin(t * 1.5 + 4.189))
        yield _current_time_str(), (r, g, b), 1.0 / fps

    yield _current_time_str(), None, 0


def all_nines(duration=3.0):
    """Dramatic full-display strobe with lightning LEDs."""
    patterns = ['999999', '000000', '888888', '111111', '999999', '000000']
    led_patterns = [
        (100, 100, 100), (0, 0, 0), (80, 80, 0),
        (0, 0, 100), (100, 50, 0), (100, 100, 100),
    ]

    for i, (pat, leds) in enumerate(zip(patterns, led_patterns)):
        yield pat, leds, 0.15

    # Rapid strobe
    for i in range(8):
        d = str(random.randint(0, 9)) * 6
        r = random.randint(50, 100)
        g = random.randint(0, 100)
        b = random.randint(0, 100)
        yield d, (r, g, b), 0.08

    # Settle to 999999 then fade to time
    yield "999999", (100, 80, 30), 0.4
    yield _current_time_str(), (50, 30, 5), 0.3
    yield _current_time_str(), None, 0


def cathode_clean():
    """Run all digits through each tube - functional but with nice lighting."""
    for digit in range(10):
        chars = []
        for pos in range(6):
            d = (digit + pos) % 10
            chars.append(str(d))
        # Warm shifting colour
        hue = digit / 10.0
        r = int(60 * (1 - hue))
        g = int(40 * hue)
        b = int(30 * abs(0.5 - hue) * 2)
        yield ''.join(chars), (r + 20, g + 10, b), 0.4

    yield _current_time_str(), None, 0


def temperature_show(temp_c):
    """Display a temperature value dramatically on the tubes."""
    temp_int = int(round(temp_c))
    temp_str = "{:6d}".format(temp_int).replace(' ', '0')

    # Build up digit by digit
    for i in range(1, 7):
        partial = '0' * (6 - i) + temp_str[-i:]
        yield partial, (0, 0, 60), 0.1

    # Hold with pulsing colour based on temperature
    if temp_c < 5:
        base_colour = (0, 20, 90)    # Cold blue
    elif temp_c < 15:
        base_colour = (10, 50, 60)   # Cool teal
    elif temp_c < 25:
        base_colour = (60, 60, 0)    # Warm yellow
    else:
        base_colour = (90, 20, 0)    # Hot red

    for frame in range(40):
        t = frame * 0.05
        pulse = 0.7 + 0.3 * math.sin(t * 8)
        r = int(base_colour[0] * pulse)
        g = int(base_colour[1] * pulse)
        b = int(base_colour[2] * pulse)
        yield temp_str, (r, g, b), 0.05

    # Fade back to time
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
