#!/usr/bin/env python3
"""
Nixie Clock Web Controller

Replaces the C++ DisplayNixie binary with a Python version that includes
a web interface for controlling the clock, changing settings, and triggering
display tricks.

Uses only Python stdlib (no Flask/pip required) so it runs on Raspbian Stretch
with Python 3.5 out of the box.

Architecture:
  - Clock thread: runs the display loop (SPI + GPIO)
  - HTTP server: serves the web UI and handles API calls
  - Shared ClockState: thread-safe bridge between web and display

Usage:
  sudo python3 nixie_web.py [--port 80]
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from nixie_driver import NixieDriver
from nixie_tricks import TRICKS

# ---------------------------------------------------------------------------
# Shared state between the clock thread and web server
# ---------------------------------------------------------------------------

class ClockState:
    """Thread-safe shared state for the clock."""

    CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    DEFAULTS = {
        'use_24hour': True,
        'brightness': 20,
        'fireworks_enabled': True,
        'fireworks_speed': 2000,
        'sleep_time': '23:00',
        'wake_time': '06:30',
        'cathode_protect': True,
        'cathode_time_1': '02:00',
        'cathode_time_2': '04:00',
    }

    def __init__(self):
        self._lock = threading.Lock()
        self._trick_request = None
        self._clock_on = True
        self.config = dict(self.DEFAULTS)
        self.load_config()

    def load_config(self):
        try:
            with open(self.CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                self.config.update(saved)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            pass

    def save_config(self):
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, key):
        with self._lock:
            return self.config.get(key)

    def set(self, key, value):
        with self._lock:
            self.config[key] = value
        self.save_config()

    def get_all(self):
        with self._lock:
            return dict(self.config)

    def request_trick(self, trick_name):
        with self._lock:
            self._trick_request = trick_name

    def pop_trick_request(self):
        with self._lock:
            trick = self._trick_request
            self._trick_request = None
            return trick

    @property
    def clock_on(self):
        with self._lock:
            return self._clock_on

    @clock_on.setter
    def clock_on(self, val):
        with self._lock:
            self._clock_on = val


# ---------------------------------------------------------------------------
# Clock display thread
# ---------------------------------------------------------------------------

class ClockEngine(threading.Thread):
    """Runs the Nixie display loop in a background thread."""

    def __init__(self, driver, state):
        super().__init__(daemon=True)
        self.driver = driver
        self.state = state
        self.running = True
        # Fireworks state
        self._fw_rotator = 0
        self._fw_cycle = 0
        self._fw_red = 0
        self._fw_green = 0
        self._fw_blue = 0
        self._last_fw_time = 0
        self._last_time_str = ""
        self._is_startup = True

    def run(self):
        self.driver.setup()
        self._fw_red = self.state.get('brightness')
        self._last_fw_time = time.time() * 1000

        while self.running:
            try:
                self._tick()
            except Exception as e:
                print("Clock error: {}".format(e))
                time.sleep(1)

        self.driver.cleanup()

    def _tick(self):
        now = time.localtime()
        brightness = self.state.get('brightness')

        # Check sleep/wake schedule
        current_hm = time.strftime("%H:%M", now)
        sleep_time = self.state.get('sleep_time')
        wake_time = self.state.get('wake_time')

        if sleep_time and current_hm == sleep_time and self.state.clock_on:
            self.state.clock_on = False
            self.driver.blank()
            self.driver.set_leds(0, 0, 0)
        elif wake_time and current_hm == wake_time and not self.state.clock_on:
            self.state.clock_on = True

        # Check for trick requests
        trick_name = self.state.pop_trick_request()
        if trick_name and trick_name in TRICKS:
            self._play_trick(trick_name)
            return

        if not self.state.clock_on:
            time.sleep(0.5)
            return

        # Format time
        if self.state.get('use_24hour'):
            time_str = time.strftime("%H%M%S", now)
        else:
            hour = now.tm_hour
            if hour == 0:
                hour = 12
            elif hour > 12:
                hour -= 12
            time_str = "{:02d}{:02d}{:02d}".format(hour, now.tm_min, now.tm_sec)

        # Cathode protection: on startup and every 10 minutes
        current_sec = time_str[4:6]
        current_min_units = time_str[3]
        if self.state.get('cathode_protect'):
            is_ten_min = (current_sec == "00" and current_min_units == '0')

            # Long protection at configured times
            ct1 = self.state.get('cathode_time_1')
            ct2 = self.state.get('cathode_time_2')
            is_long = current_hm in (ct1, ct2) and current_sec == "00"

            if self._is_startup or is_ten_min or is_long:
                self._is_startup = False
                linger = 10.0 if is_long else 0.1
                self._cathode_protection(linger)
                return

        # Update display if time changed
        if time_str != self._last_time_str:
            self.driver.toggle_dots()
            self.driver.display(time_str)
            self._last_time_str = time_str

        # Fireworks
        if self.state.get('fireworks_enabled'):
            now_ms = time.time() * 1000
            speed = self.state.get('fireworks_speed')
            if now_ms > (self._last_fw_time + speed):
                self._rotate_fireworks(brightness)
                self._last_fw_time = now_ms
        else:
            self.driver.set_leds(0, 0, 0)

        time.sleep(0.01)

    def _rotate_fireworks(self, max_brightness):
        """Rotate through RGB colors, matching the C++ fireworks algorithm."""
        transitions = [
            (0, 0, 1),    # add blue
            (-1, 0, 0),   # remove red
            (0, 1, 0),    # add green
            (0, 0, -1),   # remove blue
            (1, 0, 0),    # add red
            (0, -1, 0),   # remove green
        ]

        dr, dg, db = transitions[self._fw_rotator]
        self._fw_red += dr
        self._fw_green += dg
        self._fw_blue += db

        # Scale to brightness
        scale = max_brightness / 100.0 if max_brightness > 0 else 0
        self.driver.set_leds(
            int(self._fw_red * scale),
            int(self._fw_green * scale),
            int(self._fw_blue * scale)
        )

        self._fw_cycle += 1
        if self._fw_cycle >= max_brightness:
            self._fw_rotator = (self._fw_rotator + 1) % 6
            self._fw_cycle = 0

    def _cathode_protection(self, linger_secs):
        """Cycle all digits through all tubes to prevent cathode poisoning."""
        for cycle in range(10):
            chars = []
            for pos in range(6):
                d = (cycle + pos) % 10
                chars.append(str(d))
            self.driver.display(''.join(chars))
            time.sleep(linger_secs)

    def _play_trick(self, trick_name):
        """Play a display trick, then resume normal display."""
        _, _, trick_fn = TRICKS[trick_name]

        for digits, leds, delay in trick_fn():
            if not self.running:
                break
            self.driver.display(digits)
            if leds is not None:
                self.driver.set_leds(*leds)
            time.sleep(delay)

        # Restore fireworks state or turn off LEDs
        if self.state.get('fireworks_enabled'):
            brightness = self.state.get('brightness')
            scale = brightness / 100.0 if brightness > 0 else 0
            self.driver.set_leds(
                int(self._fw_red * scale),
                int(self._fw_green * scale),
                int(self._fw_blue * scale)
            )
        else:
            self.driver.set_leds(0, 0, 0)

        # Force time update on next tick
        self._last_time_str = ""

    def stop(self):
        self.running = False


# ---------------------------------------------------------------------------
# HTTP request handler (stdlib, no Flask needed)
# ---------------------------------------------------------------------------

# Module-level references set in main()
state = None
driver = None
engine = None

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')


def get_cpu_temp():
    """Read the Pi's CPU temperature."""
    try:
        output = subprocess.check_output(
            ['vcgencmd', 'measure_temp'],
            stderr=subprocess.STDOUT
        ).decode().strip()
        return output.replace("temp=", "").replace("'C", "")
    except Exception:
        return "?"


def render_index():
    """Render index.html with current config values substituted."""
    with open(os.path.join(TEMPLATE_DIR, 'index.html'), 'r') as f:
        html = f.read()

    config = state.get_all()

    # Build tricks HTML
    icons = {
        'slot_machine': '&#127920;', 'cascade': '&#127912;',
        'hacker': '&#128187;', 'wave': '&#127754;',
        'date': '&#128197;', 'chase': '&#127939;',
        'countdown': '&#9201;', 'breathe': '&#128161;',
        'all_nines': '&#9889;', 'clean': '&#128295;',
    }
    tricks_html = ''
    for key, (name, desc, _) in TRICKS.items():
        icon = icons.get(key, '&#9733;')
        tricks_html += (
            '<button class="trick-btn" onclick="fireTrick(\'{key}\')">'
            '<span class="icon">{icon}</span>'
            '<span class="name">{name}</span>'
            '<span class="desc">{desc}</span>'
            '</button>\n'
        ).format(key=key, icon=icon, name=name, desc=desc)

    # Substitute template variables
    clock_on = state.clock_on
    html = html.replace('{{tricks_buttons}}', tricks_html)
    html = html.replace('{{brightness}}', str(config['brightness']))
    html = html.replace('{{fireworks_speed}}', str(config['fireworks_speed']))
    html = html.replace('{{checked_24hour}}', 'checked' if config['use_24hour'] else '')
    html = html.replace('{{checked_fireworks}}', 'checked' if config['fireworks_enabled'] else '')
    html = html.replace('{{checked_cathode}}', 'checked' if config['cathode_protect'] else '')
    html = html.replace('{{sleep_time}}', config['sleep_time'])
    html = html.replace('{{wake_time}}', config['wake_time'])
    html = html.replace('{{status_class}}', 'on' if clock_on else 'off')
    html = html.replace('{{status_text}}', 'Running' if clock_on else 'Sleeping')
    html = html.replace('{{power_class}}', 'on' if clock_on else 'off')
    html = html.replace('{{power_text}}', 'Turn Off Display' if clock_on else 'Turn On Display')

    return html


class NixieHTTPHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests for the Nixie clock web UI."""

    def log_message(self, format, *args):
        # Suppress default logging to keep journal clean
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode('utf-8')
        content_type = self.headers.get('Content-Type', '')

        if 'application/json' in content_type:
            return json.loads(raw)
        else:
            # Parse form data
            result = {}
            for pair in raw.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    # URL-decode
                    from urllib.parse import unquote_plus
                    result[unquote_plus(k)] = unquote_plus(v)
            return result

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/':
            self._send_html(render_index())

        elif path == '/api/config':
            self._send_json({'config': state.get_all(), 'clock_on': state.clock_on})

        elif path == '/api/status':
            self._send_json({
                'clock_on': state.clock_on,
                'config': state.get_all(),
                'time': datetime.now().strftime('%H:%M:%S'),
                'cpu_temp': get_cpu_temp(),
            })

        elif path == '/api/temperature':
            temp_str = get_cpu_temp()
            try:
                self._send_json({'ok': True, 'temp_c': float(temp_str)})
            except ValueError:
                self._send_json({'ok': False, 'error': 'Could not read temperature'})

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/config':
            data = self._read_body()

            for key in ('brightness', 'fireworks_speed'):
                if key in data:
                    state.set(key, int(data[key]))

            for key in ('use_24hour', 'fireworks_enabled', 'cathode_protect'):
                if key in data:
                    val = data[key]
                    if isinstance(val, str):
                        val = val.lower() in ('true', '1', 'on', 'yes')
                    state.set(key, bool(val))

            for key in ('sleep_time', 'wake_time', 'cathode_time_1', 'cathode_time_2'):
                if key in data:
                    state.set(key, data[key])

            self._send_json({'ok': True, 'config': state.get_all()})

        elif path.startswith('/api/trick/'):
            trick_name = path.split('/api/trick/', 1)[1]
            if trick_name not in TRICKS:
                self._send_json({'ok': False, 'error': 'Unknown trick'}, 404)
            else:
                state.request_trick(trick_name)
                self._send_json({'ok': True, 'trick': trick_name})

        elif path == '/api/toggle-clock':
            if state.clock_on:
                state.clock_on = False
                driver.blank()
                driver.set_leds(0, 0, 0)
            else:
                state.clock_on = True
            self._send_json({'ok': True, 'clock_on': state.clock_on})

        else:
            self.send_error(404)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    global state, driver, engine

    port = 80
    if '--port' in sys.argv:
        idx = sys.argv.index('--port')
        port = int(sys.argv[idx + 1])

    state = ClockState()
    driver = NixieDriver()

    print("Nixie Clock Web Controller starting...")
    print("Web UI: http://retroclock.local{}".format(
        '' if port == 80 else ':{}'.format(port)))

    # Start the clock engine
    engine = ClockEngine(driver, state)
    engine.start()

    # Start the HTTP server
    server = HTTPServer(('0.0.0.0', port), NixieHTTPHandler)

    def shutdown(sig, frame):
        print("\nShutting down...")
        engine.stop()
        engine.join(timeout=5)
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("Listening on port {}".format(port))
    server.serve_forever()


if __name__ == '__main__':
    main()
