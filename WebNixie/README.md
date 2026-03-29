# Nixie Clock Web Controller

A Python rewrite of the original C++ `DisplayNixie` binary, adding a web interface
for real-time control and display tricks.

## What It Does

This replaces the standalone C++ clock binary with a Python application that:

1. **Drives the Nixie tubes** via SPI, exactly as the C++ version did
2. **Controls the RGB LEDs** (fireworks colour cycling)
3. **Serves a web UI** at `http://retroclock.local` for phone/tablet/desktop control
4. **Performs display tricks** - fun animations triggered from the web interface

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  nixie_web.py                    │
│                                                  │
│  ┌──────────────┐    ┌────────────────────────┐ │
│  │ Flask Web     │    │ ClockEngine Thread     │ │
│  │ Server        │◄──►│                        │ │
│  │               │    │ - Time display loop    │ │
│  │ GET /         │    │ - Fireworks animation  │ │
│  │ POST /api/*   │    │ - Cathode protection   │ │
│  └──────────────┘    │ - Trick playback       │ │
│         ▲             └──────────┬─────────────┘ │
│         │                        │               │
│  ┌──────┴──────┐    ┌───────────▼─────────────┐ │
│  │ ClockState  │    │ NixieDriver             │ │
│  │ (shared,    │    │ (nixie_driver.py)       │ │
│  │  locked)    │    │                         │ │
│  │             │    │ - SPI digit encoding    │ │
│  │ config.json │    │ - HV5222 bit reversal   │ │
│  └─────────────┘    │ - RGB PWM control       │ │
│                      │ - Latch enable          │ │
│                      └─────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### SPI Protocol (ported from C++)

The NCS314 shield uses daisy-chained shift registers driven via SPI:

- **8 bytes** sent per update at 2 MHz, SPI mode 2
- Each digit (0-9) is one-hot encoded in a 10-bit field: `[1, 2, 4, 8, 16, 32, 64, 128, 256, 512]`
- Three digits are packed into a 32-bit word at bit offsets 0, 10, and 20
- Bits 30-31 control the colon separator dots
- The **LE (Latch Enable) pin** is pulsed LOW→HIGH to latch data into the display
- The **HV5222 variant** requires reversing all 64 bits and swapping halves

### Pin Mapping (BCM numbering)

| Function        | BCM Pin | wiringPi Pin | Notes                    |
|-----------------|---------|--------------|--------------------------|
| Latch Enable    | 22      | 3            | SPI latch                |
| SPI MOSI        | 10      | -            | SPI hardware             |
| SPI SCLK        | 11      | -            | SPI hardware             |
| SPI CE0         | 8       | -            | SPI hardware             |
| Red LED         | 20      | 28           | RGB PWM                  |
| Green LED       | 16      | 27           | RGB PWM                  |
| Blue LED        | 21      | 29           | RGB PWM                  |
| HV5222 Detect   | 6       | 22           | Pull-up, LOW = HV5222    |
| Up Button       | 18      | 1            | Pull-up, active LOW      |
| Down Button     | 23      | 4            | Pull-up, active LOW      |
| Mode Button     | 24      | 5            | Pull-up, active LOW      |

## Display Tricks

Tricks are momentary animations triggered from the web UI. Each trick runs for
a few seconds and then the display returns to showing the time.

| Trick          | Description                                          |
|----------------|------------------------------------------------------|
| Slot Machine   | Digits spin like a one-armed bandit, landing one by one |
| Cascade        | Digits waterfall 9→0 across all tubes                |
| Hacker Mode    | Random digits resolve to the time (Matrix style)     |
| The Wave       | A digit ripples back and forth across the display    |
| Show Date      | Briefly shows today's date (DDMMYY)                 |
| Digit Chase    | A single digit runs across the tubes                 |
| Countdown      | Counts down from 10 with green→red LED transition    |
| Breathe        | Slow RGB LED breathing pattern                       |
| All Nines      | Dramatic 999999/000000 flash                         |
| Cathode Clean  | Cycles all digits to prevent cathode poisoning       |

### Adding New Tricks

Tricks are generator functions in `nixie_tricks.py`. Each yields tuples of
`(digit_string, led_tuple_or_none, delay_seconds)`:

```python
def my_trick():
    for i in range(10):
        yield str(i) * 6, (100, 0, 0), 0.2   # show 6 of same digit, red LEDs
    yield _current_time_str(), None, 0         # always end with current time
```

Register it in the `TRICKS` dict at the bottom of the file and it will
automatically appear in the web UI.

## Web API

| Endpoint                | Method | Description                        |
|-------------------------|--------|------------------------------------|
| `/`                     | GET    | Web UI                             |
| `/api/config`           | GET    | Get current configuration          |
| `/api/config`           | POST   | Update settings (form or JSON)     |
| `/api/trick/<name>`     | POST   | Trigger a display trick            |
| `/api/toggle-clock`     | POST   | Turn display on/off                |
| `/api/temperature`      | GET    | Get CPU temperature                |
| `/api/status`           | GET    | Full status (time, temp, config)   |

### Configuration Keys

| Key               | Type    | Default  | Description                    |
|-------------------|---------|----------|--------------------------------|
| `use_24hour`      | bool    | true     | 24-hour vs 12-hour display     |
| `brightness`      | int     | 20       | LED brightness (0-100)         |
| `fireworks_enabled` | bool  | true     | RGB colour cycling             |
| `fireworks_speed` | int     | 2000     | Colour cycle speed (ms)        |
| `sleep_time`      | string  | "23:00"  | Turn off display               |
| `wake_time`       | string  | "06:30"  | Turn on display                |
| `cathode_protect` | bool    | true     | Cathode poisoning protection   |
| `cathode_time_1`  | string  | "02:00"  | Long protection run time       |
| `cathode_time_2`  | string  | "04:00"  | Long protection run time       |

Settings are persisted in `config.json` and survive restarts.

## Installation

```bash
# Install Flask
sudo pip3 install flask

# Deploy the service
sudo cp nixie-web.service /etc/systemd/system/
sudo systemctl daemon-reload

# Stop the old C++ clock
sudo systemctl stop nixie.service
sudo systemctl disable nixie.service

# Start the new web-controlled clock
sudo systemctl enable nixie-web.service
sudo systemctl start nixie-web.service
```

Then open `http://retroclock.local` in a browser.

## Rolling Back

If anything goes wrong, a rollback script is provided:

```bash
cd /home/pi/NixieClockRaspberryPi
bash rollback.sh
```

This stops the web service, restores the original C++ binary, and re-enables
the original `nixie.service`. The pre-web-rewrite state is also tagged in git
as `v2.3.2-pre-web`.

## Files

| File              | Purpose                                           |
|-------------------|---------------------------------------------------|
| `nixie_web.py`    | Main app: Flask server + clock engine thread       |
| `nixie_driver.py` | SPI/GPIO driver (port of C++ display logic)        |
| `nixie_tricks.py` | Display trick animations                           |
| `templates/index.html` | Web UI (vanilla JS, no frameworks)            |
| `nixie-web.service`    | systemd unit file                             |
| `config.json`     | Persistent settings (auto-created on first run)    |
| `requirements.txt`| Python dependencies                                |

## Credits

- Original NCS314 firmware: GRA&AFCH
- C++ DisplayNixie: GRA&AFCH, Leon Shaner, Tony Gillett
- Python web rewrite: Tony Gillett + Claude
