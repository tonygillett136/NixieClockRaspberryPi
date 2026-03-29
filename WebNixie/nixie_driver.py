"""
Nixie tube driver - Python port of the C++ DisplayNixie SPI protocol.

Drives NCS314 v2.x / NCS312 Nixie clock shields via SPI, with RGB LED control.
Pin numbering uses BCM mode throughout.
"""

import time
import threading

try:
    import spidev
    import RPi.GPIO as GPIO
    ON_PI = True
except ImportError:
    ON_PI = False

# BCM pin mapping (converted from wiringPi numbering)
LE_PIN = 22        # Latch Enable (wPi 3)
RED_PIN = 20       # RGB red (wPi 28)
GREEN_PIN = 16     # RGB green (wPi 27)
BLUE_PIN = 21      # RGB blue (wPi 29)
R5222_PIN = 6      # HV5222 detect (wPi 22)
UP_BUTTON = 18     # wPi 1
DOWN_BUTTON = 23   # wPi 4
MODE_BUTTON = 24   # wPi 5

# Digit encoding: each digit 0-9 maps to a single bit in a 10-bit field
SYMBOL = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]

UPPER_DOTS = 0x80000000
LOWER_DOTS = 0x40000000

# SPI settings
SPI_CHANNEL = 0
SPI_SPEED = 2000000
SPI_MODE = 2


class NixieDriver:
    def __init__(self):
        self.hv5222 = False
        self.spi = None
        self.dot_state = False
        self.last_displayed = ""

        # LED state
        self.led_red = 0
        self.led_green = 0
        self.led_blue = 0
        self._pwm_red = None
        self._pwm_green = None
        self._pwm_blue = None
        self._lock = threading.Lock()

    def setup(self):
        """Initialize GPIO and SPI."""
        if not ON_PI:
            print("[SIM] NixieDriver running in simulation mode")
            return

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # LE pin
        GPIO.setup(LE_PIN, GPIO.OUT, initial=GPIO.LOW)

        # Detect HV5222
        GPIO.setup(R5222_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.hv5222 = not GPIO.input(R5222_PIN)
        if self.hv5222:
            print("HV5222 detected.")

        # RGB LEDs using hardware PWM emulation
        GPIO.setup(RED_PIN, GPIO.OUT)
        GPIO.setup(GREEN_PIN, GPIO.OUT)
        GPIO.setup(BLUE_PIN, GPIO.OUT)
        self._pwm_red = GPIO.PWM(RED_PIN, 200)
        self._pwm_green = GPIO.PWM(GREEN_PIN, 200)
        self._pwm_blue = GPIO.PWM(BLUE_PIN, 200)
        self._pwm_red.start(0)
        self._pwm_green.start(0)
        self._pwm_blue.start(0)

        # Buttons
        for pin in (UP_BUTTON, DOWN_BUTTON, MODE_BUTTON):
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # SPI
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = SPI_SPEED
        self.spi.mode = SPI_MODE

        print("SPI ok")

    def cleanup(self):
        """Turn off display and clean up GPIO."""
        if not ON_PI:
            return
        self.set_leds(0, 0, 0)
        self.blank()
        if self._pwm_red:
            self._pwm_red.stop()
            self._pwm_green.stop()
            self._pwm_blue.stop()
        if self.spi:
            self.spi.close()
        GPIO.cleanup()

    def _encode_three_digits(self, d2, d1, d0):
        """Encode 3 digits into a 30-bit value (matching C++ get32Rep)."""
        val = (SYMBOL[d2] << 20) | (SYMBOL[d1] << 10) | SYMBOL[d0]
        return val

    def _add_dots(self, val):
        """Add or remove dot indicators based on current blink state."""
        if self.dot_state:
            val &= ~UPPER_DOTS
            val &= ~LOWER_DOTS
        else:
            val |= UPPER_DOTS
            val |= LOWER_DOTS
        return val

    def _reverse_bits_64(self, num):
        """Reverse all 64 bits (for HV5222 variant)."""
        result = 0
        for i in range(64):
            if num & (1 << i):
                result |= (1 << (63 - i))
        return result

    def display(self, digits_str):
        """
        Display a 6-character digit string on the tubes.
        Format: "HHMMSS" where each character is '0'-'9'.
        """
        if len(digits_str) != 6:
            return

        d = [ord(c) - 0x30 for c in digits_str]

        # Left half: positions 5,4,3 (SS and tens-of-minutes)
        left = self._encode_three_digits(d[5], d[4], d[3])
        left = self._add_dots(left)

        # Right half: positions 2,1,0 (units-of-minutes and HH)
        right = self._encode_three_digits(d[2], d[1], d[0])
        right = self._add_dots(right)

        # Pack into 8-byte buffer
        buff = [
            (left >> 24) & 0xFF, (left >> 16) & 0xFF,
            (left >> 8) & 0xFF, left & 0xFF,
            (right >> 24) & 0xFF, (right >> 16) & 0xFF,
            (right >> 8) & 0xFF, right & 0xFF,
        ]

        if self.hv5222:
            val64 = 0
            for i, b in enumerate(buff):
                val64 |= b << (8 * (7 - i))
            rev = self._reverse_bits_64(val64)
            buff = [
                (rev >> 32) & 0xFF, (rev >> 40) & 0xFF,
                (rev >> 48) & 0xFF, (rev >> 56) & 0xFF,
                rev & 0xFF, (rev >> 8) & 0xFF,
                (rev >> 16) & 0xFF, (rev >> 24) & 0xFF,
            ]

        if ON_PI:
            GPIO.output(LE_PIN, GPIO.LOW)
            self.spi.xfer2(buff)
            GPIO.output(LE_PIN, GPIO.HIGH)

        self.last_displayed = digits_str

    def blank(self):
        """Turn off all tubes by sending zeros with LE low."""
        if ON_PI:
            GPIO.output(LE_PIN, GPIO.LOW)
            self.spi.xfer2([0] * 8)
            # Leave LE low to keep display blank

    def toggle_dots(self):
        """Toggle the colon dots state."""
        self.dot_state = not self.dot_state

    def set_leds(self, red, green, blue):
        """Set RGB LED brightness (0-100 each)."""
        with self._lock:
            self.led_red = max(0, min(100, red))
            self.led_green = max(0, min(100, green))
            self.led_blue = max(0, min(100, blue))
            if ON_PI and self._pwm_red:
                self._pwm_red.ChangeDutyCycle(self.led_red)
                self._pwm_green.ChangeDutyCycle(self.led_green)
                self._pwm_blue.ChangeDutyCycle(self.led_blue)

    def get_leds(self):
        """Return current (red, green, blue) values."""
        with self._lock:
            return (self.led_red, self.led_green, self.led_blue)
