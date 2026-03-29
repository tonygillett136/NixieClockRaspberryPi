# Nixie Clock Web Controller

A Python rewrite of the original C++ `DisplayNixie` binary, adding a web interface
for real-time control, LED lighting modes, display tricks, and weather.

## What It Does

This replaces the standalone C++ clock binary with a Python application that:

1. **Drives the Nixie tubes** via SPI, exactly as the C++ version did
2. **Controls the RGB LEDs** with 14 lighting modes (static and animated)
3. **Serves a web UI** at `http://retroclock.local` for phone/tablet/desktop control
4. **Performs display tricks** - fun animations with synchronised LED effects
5. **Shows outdoor temperature** from Open-Meteo weather API

No external dependencies - runs on Python 3.5 stdlib only.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    nixie_web.py                       │
│                                                       │
│  ┌───────────────┐    ┌─────────────────────────────┐│
│  │ HTTP Server    │    │ ClockEngine Thread          ││
│  │ (stdlib)       │◄──►│                             ││
│  │                │    │ - Time display loop         ││
│  │ GET /          │    │ - LED mode engine           ││
│  │ POST /api/*    │    │ - Cathode protection        ││
│  └───────────────┘    │ - Trick playback            ││
│         ▲              └──────────┬──────────────────┘│
│         │    ┌────────┐           │                   │
│  ┌──────┴──┐│ led_    │ ┌────────▼──────────────────┐│
│  │ Clock   ││ modes   │ │ NixieDriver               ││
│  │ State   ││ .py     │ │ (nixie_driver.py)         ││
│  │         │├─────────┤ │                            ││
│  │ config  ││ nixie_  │ │ - SPI digit encoding      ││
│  │ .json   ││ tricks  │ │ - HV5222 bit reversal     ││
│  └─────────┘│ .py     │ │ - RGB PWM control         ││
│              └─────────┘ │ - Latch enable            ││
│                          └───────────────────────────┘│
│  ┌─────────────────────────────────────────────────┐  │
│  │ Open-Meteo API (outdoor temp, cached 10 min)    │  │
│  └─────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### SPI Protocol (ported from C++)

The NCS314 shield uses daisy-chained shift registers driven via SPI:

- **8 bytes** sent per update at 2 MHz, SPI mode 2
- Each digit (0-9) is one-hot encoded in a 10-bit field: `[1, 2, 4, 8, 16, 32, 64, 128, 256, 512]`
- Three digits are packed into a 32-bit word at bit offsets 0, 10, and 20
- Bits 30-31 control the colon separator dots
- The **LE (Latch Enable) pin** is pulsed LOW->HIGH to latch data into the display
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

## LED Lighting Modes

14 modes selectable from the web UI. The default is **Warm Glow** - a muted
orange that complements the Nixie tube colour.

### Static modes

| Mode         | Description                              |
|--------------|------------------------------------------|
| Warm Glow    | Muted orange, matching the tube glow     |
| Ember        | Deep red, like glowing coals             |
| Cool White   | Subtle cool backlight                    |
| Deep Purple  | Rich understated purple                  |
| Ocean Blue   | Calm deep blue                           |
| Off          | LEDs completely off                      |

### Animated modes

| Mode            | Description                                    |
|-----------------|------------------------------------------------|
| Candlelight     | Flickering warm light, like a candle           |
| Campfire        | Warm flicker with occasional brighter flares   |
| Sunset          | Slow drift through warm tones                  |
| Lava            | Morphing reds and oranges                      |
| Breathing       | Gentle warm pulse                              |
| Fireworks       | Classic RGB colour cycling (original behaviour)|
| Northern Lights | Slow aurora greens, teals, and purples         |
| Storm           | Dark blue with occasional lightning flashes    |

### Adding new modes

Modes are functions in `led_modes.py` that take `(brightness, elapsed_seconds)`
and return an `(r, g, b)` tuple (0-100 each):

```python
def my_mode(brightness, t):
    b = brightness / 100.0
    return (int(50 * b), int(30 * b), int(10 * b))
```

Add it to `LED_MODES` and `MODE_ORDER` and it appears in the web UI automatically.

## Display Tricks

Momentary animations triggered from the web UI. Each runs for a few seconds
with synchronised LED effects, then the display returns to the time.

| Trick          | LED Effect                                       |
|----------------|--------------------------------------------------|
| Temperature    | Fetches outdoor temp, colour-coded (blue/yellow/red) |
| Slot Machine   | White flash on each digit lock                   |
| Cascade        | Rainbow colour trail through the digits          |
| Hacker Mode    | Flickering green matrix, brightens as it resolves|
| The Wave       | Rainbow follows the digit across tubes           |
| Show Date      | Breathing blue pulse while showing DDMMYY        |
| Digit Chase    | Warm comet tail trailing the running digit        |
| Countdown      | Green-to-red shift with strobe finale            |
| Breathe        | Full RGB spectrum breathing                      |
| All Nines      | Rapid strobe with random colours                 |
| Cathode Clean  | Warm shifting colour during digit cycling        |

### Adding new tricks

Tricks are generator functions in `nixie_tricks.py`. Each yields tuples of
`(digit_string, led_tuple_or_none, delay_seconds)`:

```python
def my_trick():
    for i in range(10):
        yield str(i) * 6, (100, 0, 0), 0.2   # 6 of same digit, red LEDs
    yield _current_time_str(), None, 0         # always end with current time
```

Register it in the `TRICKS` dict and it appears in the web UI automatically.

## Weather

Outdoor temperature is fetched from the [Open-Meteo API](https://open-meteo.com/)
(free, no API key required). Currently configured for Droxford, Hampshire, UK
(lat 50.9558, lon -1.1253).

- Shown in the web UI status bar, updated every page load
- The "Temperature" trick button displays the reading on the Nixie tubes
- Results are cached for 10 minutes to be kind to the API
- Colour-coded: blue for cold (<5C), teal (<15C), yellow (<25C), red (25C+)

To change location, edit `WEATHER_URL` in `nixie_web.py`.

## Web API

| Endpoint              | Method | Description                         |
|-----------------------|--------|-------------------------------------|
| `/`                   | GET    | Web UI                              |
| `/api/config`         | GET    | Get current configuration           |
| `/api/config`         | POST   | Update settings (form or JSON)      |
| `/api/trick/<name>`   | POST   | Trigger a display trick             |
| `/api/toggle-clock`   | POST   | Turn display on/off                 |
| `/api/show-weather`   | POST   | Show outdoor temp on tubes          |
| `/api/temperature`    | GET    | Get CPU temperature                 |
| `/api/status`         | GET    | Full status (time, temps, config)   |

### Configuration Keys

| Key               | Type    | Default      | Description                 |
|-------------------|---------|--------------|-----------------------------|
| `use_24hour`      | bool    | true         | 24-hour vs 12-hour display  |
| `brightness`      | int     | 20           | LED brightness (0-100)      |
| `led_mode`        | string  | "warm_glow"  | Active LED lighting mode    |
| `sleep_time`      | string  | "23:00"      | Turn off display            |
| `wake_time`       | string  | "06:30"      | Turn on display             |
| `cathode_protect` | bool    | true         | Cathode poisoning protection|
| `cathode_time_1`  | string  | "02:00"      | Long protection run time    |
| `cathode_time_2`  | string  | "04:00"      | Long protection run time    |

Settings are persisted in `config.json` and survive restarts.

## Installation

```bash
# No pip install needed - uses Python stdlib only

# Deploy the service
sudo cp nixie-web.service /etc/systemd/system/
sudo systemctl daemon-reload

# Stop the old C++ clock (if running)
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

| File                   | Purpose                                        |
|------------------------|------------------------------------------------|
| `nixie_web.py`         | Main app: HTTP server + clock engine thread    |
| `nixie_driver.py`      | SPI/GPIO driver (port of C++ display logic)    |
| `nixie_tricks.py`      | Display trick animations                       |
| `led_modes.py`         | LED lighting mode definitions                  |
| `templates/index.html` | Web UI (vanilla JS, no frameworks)             |
| `nixie-web.service`    | systemd unit file                              |
| `config.json`          | Persistent settings (auto-created on first run)|

## Credits

- Original NCS314 firmware: GRA & AFCH
- C++ DisplayNixie: GRA & AFCH, Leon Shaner, Tony Gillett
- Python web rewrite, LED modes, tricks: Tony Gillett + Claude
