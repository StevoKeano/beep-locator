# Beep Locator

A local-network application for locating an intermittent high-pitched beep
using multiple consumer devices (laptop, phone, tablet).

## Setup

```bash
# Install dependencies (if not already installed)
python3 -m pip install aiohttp numpy scipy soundfile cryptography

# Run the server
python3 server.py

# Or with HTTPS (requires --tls-cert and --tls-key)
python3 server.py --tls-cert cert.pem --tls-key key.pem
```

## Running

1. Start the server:
   ```bash
   python3 server.py
   ```

2. Open the admin UI in a browser at:
   ```
   http://<LAN_IP>:8765/
   ```

3. On a listener device (laptop, phone, tablet), open:
   ```
   http://<LAN_IP>:8765/listen?room=default
   ```

4. The join URL is displayed in the admin UI and copyable.

## HTTPS / Certificate

To use the app on phones (which require HTTPS for microphone access), generate a certificate:

```bash
python3 tools/make_cert.py --ip <LAN_IP>
```

Then run with:
```bash
python3 server.py --tls-cert cert.pem --tls-key key.pem
```

## Architecture Overview

- **Server:** aiohttp backend with WebSocket protocol.
- **Admin UI:** HTML/CSS/JS for placing nodes and viewing results.
- **Listener Client:** HTML/CSS/JS that captures audio and reports candidates.
- **Audio Pipeline:** FFT-based detection, chirp matched filtering, TDOA triangulation.
- **Triangulation:** Uses scipy.optimize.least_squares for 2D multilateration.
- **GDOP:** Grid-search to suggest the next best listener position.

## Files

```
server.py              # Entry point
beep_locator/          # Python modules
├── __init__.py
├── app.py             # aiohttp application setup
├── protocol.py        # WebSocket message schema and validation
├── rooms.py           # Room state, node registry, event management
├── audio.py           # Audio processing: chirp generation, WAV I/O, onset detection
├── triangulate.py     # TDOA solver using least squares
├── gdop.py            # GDOP calculation for positioning suggestions
static/                # Web assets (HTML/CSS/JS)
├── admin.html         # Admin UI
├── admin.css          # Admin styles
├── admin.js           # Admin client-side logic
├── listen.html        # Listener UI
├── listen.css         # Listener styles
├── listener.js        # Listener audio capture and reporting
├── detector.js        # Pure JS detector functions (Node-compatible)
tests/                 # Python and JS tests
├── test_server.py
├── test_triangulation.py
├── test_gdop.py
├── test_audio.py
├── detector.test.mjs
tools/
├── make_cert.py       # Generate self-signed TLS certificate with SAN
└── push_module.py     # Push a new detector module to a running client
```

## CLI Options

- `--host` (default: 0.0.0.0)
- `--port` (default: 8765)
- `--tls-cert` (optional, for HTTPS)
- `--tls-key` (optional, for HTTPS)
- `--data-dir` (default: data/)

## WebSocket Protocol

See `problem.md`.

## Testing

```bash
python3 -m pytest -q
node --check static/detector.js
node --test tests/detector.test.mjs
```

## Limitations

- Unsynchronized device clocks.
- Microphone/speaker latency varies by device.
- Requires HTTPS or localhost for phone microphone access.
- Results are rough, not calibrated.