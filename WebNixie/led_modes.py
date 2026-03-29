"""
LED lighting modes for the Nixie clock.

Each mode is a function that takes (brightness, elapsed_seconds) and returns
an (r, g, b) tuple where each value is 0-100.

Modes run continuously until the user selects a different one.
"""

import math
import random

# ---------------------------------------------------------------------------
# Static modes
# ---------------------------------------------------------------------------

def warm_glow(brightness, t):
    """Muted orange - like the warm cathode glow of the tubes themselves."""
    b = brightness / 100.0
    return (int(60 * b), int(25 * b), int(3 * b))


def off(brightness, t):
    """LEDs completely off."""
    return (0, 0, 0)


def ember(brightness, t):
    """Deep red/orange, like glowing coals."""
    b = brightness / 100.0
    return (int(70 * b), int(15 * b), int(0))


def cool_white(brightness, t):
    """Subtle cool white backlight."""
    b = brightness / 100.0
    v = int(40 * b)
    return (v, v, int(50 * b))


def deep_purple(brightness, t):
    """Rich purple, understated."""
    b = brightness / 100.0
    return (int(35 * b), int(5 * b), int(50 * b))


def ocean_blue(brightness, t):
    """Calm deep blue."""
    b = brightness / 100.0
    return (int(3 * b), int(15 * b), int(55 * b))


# ---------------------------------------------------------------------------
# Animated modes
# ---------------------------------------------------------------------------

def candlelight(brightness, t):
    """Flickering warm light, like a candle beside the clock."""
    b = brightness / 100.0
    # Multiple overlapping sine waves for organic flicker
    flicker = (
        math.sin(t * 3.7) * 0.15 +
        math.sin(t * 7.3) * 0.08 +
        math.sin(t * 13.1) * 0.05
    )
    base_r = 55 + flicker * 55
    base_g = 20 + flicker * 20
    base_b = 2 + flicker * 2
    return (int(base_r * b), int(base_g * b), int(base_b * b))


def sunset(brightness, t):
    """Slow drift through warm tones: amber, rose, coral, back to amber."""
    b = brightness / 100.0
    cycle = t * 0.08  # Very slow - full cycle ~80 seconds
    r = 50 + 20 * math.sin(cycle)
    g = 18 + 12 * math.sin(cycle + 1.2)
    b_val = 5 + 15 * math.sin(cycle + 2.8)
    return (int(r * b), int(g * b), int(b_val * b))


def northern_lights(brightness, t):
    """Slow-moving aurora: greens, teals, and hints of purple."""
    b = brightness / 100.0
    cycle = t * 0.06
    r = 8 + 12 * max(0, math.sin(cycle + 3.5))
    g = 25 + 25 * (0.5 + 0.5 * math.sin(cycle))
    b_val = 15 + 20 * (0.5 + 0.5 * math.sin(cycle + 1.8))
    return (int(r * b), int(g * b), int(b_val * b))


def breathing(brightness, t):
    """Gentle warm pulse, like the clock is breathing."""
    b = brightness / 100.0
    # Sine wave with a long pause at the bottom (like real breathing)
    phase = (math.sin(t * 0.8 - math.pi / 2) + 1) / 2  # 0 to 1
    phase = phase ** 2  # Ease - spend more time dim
    r = int(55 * phase * b)
    g = int(22 * phase * b)
    b_val = int(3 * phase * b)
    return (r, g, b_val)


def fireworks(brightness, t):
    """Classic RGB colour cycling from the original C++ code."""
    b = brightness / 100.0
    cycle = t * 0.5  # Moderate speed
    r = int(50 * b * max(0, math.sin(cycle)))
    g = int(50 * b * max(0, math.sin(cycle + 2.094)))
    b_val = int(50 * b * max(0, math.sin(cycle + 4.189)))
    return (r, g, b_val)


def lava(brightness, t):
    """Slow morphing reds and oranges, like a lava lamp."""
    b = brightness / 100.0
    s1 = math.sin(t * 0.12)
    s2 = math.sin(t * 0.19 + 1.3)
    r = 50 + 20 * s1
    g = 10 + 15 * max(0, s2)
    b_val = 2 + 5 * max(0, math.sin(t * 0.15 + 2.6))
    return (int(r * b), int(g * b), int(b_val * b))


def storm(brightness, t):
    """Dark blue with occasional white lightning flashes."""
    b = brightness / 100.0
    # Base: dark blue
    r, g, b_val = 2, 5, 30

    # Occasional flash (pseudo-random using sine)
    flash_trigger = math.sin(t * 1.7) + math.sin(t * 2.3) + math.sin(t * 3.1)
    if flash_trigger > 2.7:
        # Lightning flash
        intensity = min(1.0, (flash_trigger - 2.7) * 3)
        r = int(r + 90 * intensity)
        g = int(g + 90 * intensity)
        b_val = int(b_val + 70 * intensity)
    return (int(r * b), int(g * b), int(b_val * b))


def campfire(brightness, t):
    """Warm flickering with occasional brighter flares, like sitting by a fire."""
    b = brightness / 100.0
    # Base warm glow with multi-frequency flicker
    base = 0.7 + 0.15 * math.sin(t * 4.1) + 0.1 * math.sin(t * 9.7) + 0.05 * math.sin(t * 17.3)
    # Occasional flare
    flare = max(0, math.sin(t * 0.7) + math.sin(t * 1.1) - 1.3) * 0.4
    intensity = min(1.0, base + flare)
    r = int(65 * intensity * b)
    g = int(22 * intensity * b * (0.8 + 0.2 * math.sin(t * 3.3)))
    b_val = int(3 * intensity * b)
    return (r, g, b_val)


# ---------------------------------------------------------------------------
# Mode registry
# ---------------------------------------------------------------------------

# (id, display_name, description, function, is_animated)
LED_MODES = {
    'warm_glow':      ('Warm Glow',      'Muted orange, like the tube glow',    warm_glow,      False),
    'off':            ('Off',            'LEDs completely off',                  off,            False),
    'ember':          ('Ember',          'Deep red, glowing coals',              ember,          False),
    'cool_white':     ('Cool White',     'Subtle cool backlight',                cool_white,     False),
    'deep_purple':    ('Deep Purple',    'Rich understated purple',              deep_purple,    False),
    'ocean_blue':     ('Ocean Blue',     'Calm deep blue',                       ocean_blue,     False),
    'candlelight':    ('Candlelight',    'Flickering warm light',                candlelight,    True),
    'sunset':         ('Sunset',         'Drifting warm tones',                  sunset,         True),
    'northern_lights':('Northern Lights','Slow aurora greens and teals',         northern_lights,True),
    'breathing':      ('Breathing',      'Gentle warm pulse',                    breathing,      True),
    'fireworks':      ('Fireworks',      'Classic RGB colour cycling',           fireworks,      True),
    'lava':           ('Lava',           'Morphing reds and oranges',            lava,           True),
    'storm':          ('Storm',          'Dark blue with lightning flashes',     storm,          True),
    'campfire':       ('Campfire',       'Warm flicker with flares',             campfire,       True),
}

# Ordered list for the UI - statics first, then animated
MODE_ORDER = [
    'warm_glow', 'ember', 'candlelight', 'campfire', 'sunset', 'lava',
    'breathing', 'fireworks', 'northern_lights', 'ocean_blue', 'storm',
    'deep_purple', 'cool_white', 'off',
]
