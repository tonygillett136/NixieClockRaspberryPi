# NixieClockRaspberryPi

A Nixie tube clock driven by a Raspberry Pi, using the NCS314 shield by GRA & AFCH.

Originally a simple C++ program that displayed the time on IN-14 Nixie tubes via SPI.
Now includes a **Python web interface** for controlling the clock from any browser -
adjust settings, trigger display tricks, and choose from 14 LED lighting modes.

![Nixie Clock](https://raw.githubusercontent.com/tonygillett136/NixieClockRaspberryPi/master/DisplayNixie/README.md)

## What's in this repo

| Directory | Description |
|-----------|-------------|
| `WebNixie/` | **Python web-controlled clock** (current, recommended) |
| `DisplayNixie/` | Original C++ clock binary and source |
| `CLITool/` | Command-line tool for manual tube control |
| `Firmware/` | NCS314 shield firmware |
| `rollback.sh` | Script to revert from WebNixie to the C++ version |

## WebNixie (Python web interface)

The main way to run the clock. A Python application that drives the Nixie tubes
via SPI and serves a web UI for control. See [`WebNixie/README.md`](WebNixie/README.md)
for full documentation.

### Features

- **Web UI** at `http://retroclock.local` - works from phone, tablet, or desktop
- **14 LED lighting modes** - from muted Warm Glow (default) to animated Campfire,
  Northern Lights, Storm, and more
- **10 display tricks** - Slot Machine, Hacker Mode, Countdown, Wave, and more,
  all with synchronised LED effects
- **Outdoor temperature** - fetched from Open-Meteo API and displayed on the tubes
- **Configurable schedule** - sleep/wake times, 12/24 hour, cathode protection
- **Zero dependencies** - runs on Python 3.5 stdlib only (no pip install needed)
- **Settings persist** across reboots via `config.json`

### Quick start

```bash
# On a fresh Raspberry Pi with SPI and I2C enabled:
git clone https://github.com/tonygillett136/NixieClockRaspberryPi.git
cd NixieClockRaspberryPi/WebNixie

# Install and start the service
sudo cp nixie-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nixie-web.service
sudo systemctl start nixie-web.service
```

Then open `http://retroclock.local` in a browser.

## Original C++ DisplayNixie

The original clock program, compiled against wiringPi. Still available and can
be used as a fallback.

### Building from source

```bash
cd DisplayNixie/src
make
# Binary output: ../bin/DisplayNixie
```

Requires the `wiringPi` library.

### Running

```bash
# Run directly:
sudo ./DisplayNixie/bin/DisplayNixie --24hour -f 2000 -b 20

# Or via systemd:
sudo cp DisplayNixie/nixie.service /etc/systemd/system/
sudo systemctl enable nixie.service
sudo systemctl start nixie.service
```

### Command line options

| Option | Description |
|--------|-------------|
| `--24hour` | 24-hour display mode |
| `--12hour` | 12-hour display mode |
| `-f <ms>` | Fireworks LED cycle speed (0 to disable) |
| `-b <0-100>` | LED brightness |
| `-s <HHMMSS>` | Sleep time (turn off display) |
| `-o <HHMMSS>` | Wake time (turn on display) |
| `-p <HHMMSS>` | Extended cathode protection time 1 |
| `-q <HHMMSS>` | Extended cathode protection time 2 |
| `-n` | Disable cathode protection |
| `-c` | Use onboard RTC instead of system clock |

## Required hardware

1. Raspberry Pi with 40-pin GPIO (Pi 3B+ recommended)
2. [Arduino to Raspberry Pi adapter](https://gra-afch.com/catalog/shield-nixie-clock-for-arduino/raspberry-pi-shield-nixie-tubes-clock-ncs314-for-in-14-nixie-tubes-options-tubes-gps-remote-arduino-columns-copy/) by GRA & AFCH
3. [NCS314 Nixie Clock Shield](https://gra-afch.com/catalog/shield-nixie-clock-for-arduino/nixie-tubes-clock-arduino-shield-ncs314-for-xussr-in-14-nixie-tubes/) (v1.2 or v2.x)

### Raspberry Pi configuration

Enable SPI and I2C via `sudo raspi-config` -> Interfacing Options.

## Rolling back

If the Python web version has issues, revert to the C++ binary:

```bash
cd /home/pi/NixieClockRaspberryPi
bash rollback.sh
```

The last known-good C++ version is tagged `v2.3.2-pre-web` in git.

## Credits

- Original NCS314 firmware and hardware: [GRA & AFCH](https://gra-afch.com/)
- C++ DisplayNixie enhancements: Leon Shaner ([UberEclectic](https://github.com/UberEclectic/NixieClockRaspberryPi))
- C++ bug fixes, Python web rewrite, LED modes, tricks: Tony Gillett + Claude

## Links

- [Step-by-step video (original)](https://youtu.be/-58clsFwA3I)
- [WebNixie documentation](WebNixie/README.md)
- [Open-Meteo weather API](https://open-meteo.com/) (used for outdoor temperature)
