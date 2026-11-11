# Beep Locator — Problem Statement and Design

## 1. The user problem

A short, intermittent, high-pitched beep is coming from somewhere in a room.
The person looking for it has several ordinary consumer devices — a laptop, a
phone and a tablet — that can all capture audio and talk to a small local web
server. The devices are **not** hardware-synchronized, and none of them knows
exactly where it is in the room until the user places it on a map.

The application helps a human do three things:

1. **Place devices roughly on a room map** (drag-and-drop). This is
   "rough placement": the user estimates coordinates by eye.
2. **Detect beep candidates** on every device from live microphone audio.
3. **Turn those candidates into a rough acoustic fix** using a known chirp from
   one speaker-capable device and time-difference-of-arrival (TDOA) between the
   beep and the chirp. A GDOP (geometric dilution of precision) suggestion tells
   the user where to move the next listener for a better fix.

The output is an approximate room coordinate, not a survey-grade acoustic
ranging system.

### Operating assumptions

- One room at a time, represented as a normalized `0..1` map. The default
  physical size is 8 m x 6 m; this is configurable per room.
- At least three listener nodes with microphones and roughly known positions
  are needed for a 2-D fix. At least one node must have a speaker to emit the
  reference chirp.
- The mystery beep is short, narrow-band, and high-pitched (roughly 1.5–8 kHz).
  A clap/impulse is classified separately as a broad transient.
- Device clocks are **not** synchronized. The server never compares raw client
  timestamps across devices.
- Users can tolerate an error of tens of centimetres to a metre for "which
  corner is it in"; fine localization requires calibration and better geometry.
- Clips are stored locally under `data/`; no external services or assets are
  used by the browser.

## 2. Architecture

### 2.1 HTTP / WebSocket server (`server.py`, `beep_locator/app.py`)

`server.py` is the entry point. It parses CLI options (`--host`, `--port`,
`--tls-cert`, `--tls-key`, `--data-dir`), detects the LAN IP with a local UDP
socket trick (a connected UDP socket to a reserved/documentation address, no
payload sent and no external request), builds the aiohttp `Application`, and
starts it.

Routes:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | JSON: `ok`, `name`, `version`, room count |
| GET | `/` | Admin UI |
| GET | `/listen?room=ROOM` | Listener client |
| GET | `/api/rooms/{room}/state` | Nodes, events, target, join URL, config |
| GET | `/api/rooms/{room}/audio/{event_id}/{node_id}.wav` | Stored 16-bit mono WAV clip |
| POST | `/api/rooms/{room}/install-module` | Push raw JS detector module |
| POST | `/api/rooms/{room}/mystery` | Set the confirmed mystery-beep target |
| WS | `/ws?room=ROOM` | All real-time messages |

Static files are served by aiohttp from `static/`. There are no CDNs, fonts,
images, QR services or audio assets.

### 2.2 Room and node registry (`beep_locator/rooms.py`)

A `Room` owns:

- room id, normalized dimensions, physical width/height in metres;
- `nodes`: id, name, role (`listener`/`admin`), capabilities
  `{mic, speaker}`, normalized position, `last_seen`, measured RTT median,
  connected flag;
- `events`: candidate events with kind, frequency, duration, level,
  confidence, source node, server timestamp, clip metadata;
- `target`: confirmed mystery event id plus frequency/tolerance signature;
- triangulation result attached to each event.

Node IDs may be supplied by the client on first join. The server validates
them (`[A-Za-z0-9_-]{1,64}`). If a client does not supply one, the server
generates a short id. A reconnecting listener may reuse its id; the server
treats that as the same device and refreshes `last_seen`.

Stale nodes are disconnected after a timeout (default 25 s). A periodic task
marks them disconnected; state snapshots expose the flag.

Latency probes: after a listener joins, the server sends 5 `latency_probe`
messages. The client replies with `pong` carrying the probe id and the
server's original timestamp. The server computes RTT for each reply and uses
the **median** of the samples. The lowest-median-RTT node with speaker
capability becomes the chirp anchor.

### 2.3 Listener client (`static/listen.html`, `listener.js`, `detector.js`)

- Requests `getUserMedia({audio: ...})`.
- Uses an `AudioContext` with a high-pass filter (default ~1.5 kHz) to remove
  rumble/hum, an `AnalyserNode` for visualization, and a `ScriptProcessorNode`
  or `AudioWorklet`-style capture path. The implementation uses
  `ScriptProcessorNode` for maximum cross-browser compatibility; it keeps a
  rolling **60-second mono PCM ring buffer** in memory.
- Runs the pure detector functions from `detector.js` over frames of the ring
  buffer. Silence, low-frequency tones, sharp high-frequency beeps and claps
  are distinguished by spectral flux, band energy, peak prominence and
  spectral flatness.
- For a detected candidate, sends a `candidate` message with event id, kind,
  frequency, duration, level, confidence, and a local `t_client_ms`.
- When the server sends `chirp`, the listener schedules extraction of a clip
  from the ring buffer: from ~0.6 s before the detected candidate to ~0.8 s
  after the chirp playback time. It uploads 16-bit mono WAV as base64.
- Reconnects (with backoff) and re-registers automatically.
- Shows clear text for missing secure context / denied microphone permission.
- `installModule(source)` hot-swaps detector logic using `new Function(source)`
  or an object returned by the source. It does **not** recreate the
  `AudioContext` or `MediaStream`, so microphone permission is retained. The
  client reports success or failure over the WebSocket (`module_ack`).

### 2.4 WebSocket protocol

All messages are UTF-8 JSON objects with a `type` field. The server validates
message structure and sends `{"type":"error", ...}` for invalid messages
without closing the connection. Unknown fields are ignored.

**Client → server**

```json
{"type":"hello","node_id":"optional-id","name":"Laptop",
 "capabilities":{"mic":true,"speaker":false},"role":"listener"}

{"type":"position","x":0.25,"y":0.60}

{"type":"candidate","event_id":"evt-abc","kind":"beep",
 "freq_hz":4200,"duration_ms":45,"level":0.18,"confidence":0.8,
 "t_client_ms":123456}

{"type":"audio","event_id":"evt-abc","node_id":"node-1",
 "sample_rate":48000,"wav_b64":"...",
 "beep_offset_samples":12345,"chirp_offset_samples":21000}
```

The offset fields are optional hints; the server normally detects onsets
itself by matched filtering/cross-correlation.

```json
{"type":"pong","probe_id":"p-1","t_server_ms":1234567890}
{"type":"module_ack","version":"2","ok":true,"message":"loaded"}
```

**Server → client**

```json
{"type":"hello_ok","node_id":"node-1","room":"default",
 "config":{"room_width_m":8,"room_height_m":6,...},
 "nodes":[...],"events":[...],"target":null}

{"type":"latency_probe","probe_id":"p-1","t_server_ms":1234567890}

{"type":"chirp","event_id":"evt-abc","anchor_node_id":"node-2",
 "chirp":{"f_start_hz":2500,"f_end_hz":6000,"duration_ms":120,
          "gain":0.6,"window":"hann"},
 "record_window":{"before_ms":600,"after_ms":800},
 "play_at_ms":1234567890}

{"type":"triangulation","event_id":"evt-abc","x":0.31,"y":0.42,
 "error_m":0.18,"gdop":1.7,"confidence":0.86,
 "clips":[{"node_id":"node-1","chirp_onset":..., "beep_onset":...}]}

{"type":"install_module","module":"detector","version":"2","source":"..."}

{"type":"target","event_id":"evt-abc","signature":{"freq_hz":4200,
 "tolerance_hz":80,"kind":"beep"}}
```

Additional server messages used by the admin UI and documented as extensions:

- `nodes` / `state`: updated node registry snapshot.
- `event`: a candidate event was accepted.
- `event_update`: clip uploads or triangulation result changed.
- `module_ack`: acknowledgment relayed to the admin.
- `error`: validation or processing error.

The protocol is deliberately stateless across reconnects; `hello_ok` contains
the current full room snapshot.

### 2.5 Audio pipeline (`beep_locator/audio.py`, `static/detector.js`)

Server side:

- WAV is 16-bit mono PCM, encoded/decoded with `wave` + `numpy` (no external
  assets or services).
- Chirp reference: linear sweep 2.5 kHz → 6 kHz over ~120 ms, Hann windowed,
  moderate gain (default 0.6).
- Chirp onset is found by normalized cross-correlation
  (`scipy.signal.fftconvolve` with the reversed reference).
- Beep onset is found by band-pass filtering around the candidate frequency,
  taking the analytic envelope, and finding the first significant threshold
  crossing. Only the portion before the chirp onset is searched, so the chirp
  sweep cannot masquerade as the beep.
- Clips are stored per event/node as
  `data/rooms/<room>/clips/<event_id>/<node_id>.wav`; metadata is in
  `data/rooms.json`. The audio endpoint serves the stored bytes.
- The client ring buffer is the pre-roll source; the listener extracts the
  requested window without needing synchronized clocks.

### 2.6 Triangulation (`beep_locator/triangulate.py`)

For node `i`, let

```
interval_i = beep_onset_i - chirp_onset_i
```

If node `i` records a beep and a chirp emitted by anchor `a`, then

```
interval_i = (T_beep - T_chirp) + (d_beep_i - d_chirp_i) / c + clock_i - clock_i
```

The unknown per-device clock offset cancels. For any reference node `j`
(usually the anchor, whose chirp distance is zero):

```
d_beep_i - d_beep_j
    = c * (interval_i - interval_j) + (d_chirp_i - d_chirp_j)
```

So the signed TDOA distance difference used by the solver is

```
tau_i = c * (interval_i - interval_ref) + (d_chirp_i - d_chirp_ref)
```

with `tau_ref = 0`. This is the sign convention validated by the synthetic
tests: positive `tau_i` means the beep reached node `i` later than the
reference node (node `i` is farther from the source than the reference by
`tau_i` metres). The chirp distances are known from the rough node map, and
the anchor's own chirp distance is approximately zero.

The solver minimizes

```
sum_i (||p - node_i|| - ||p - node_ref|| - tau_i)^2
```

using `scipy.optimize.least_squares` with bounds inside the room. A coarse
grid initialization avoids the mirror-solution branch. It requires at least
three non-collinear nodes; otherwise it returns a flagged degenerate result
rather than inventing a coordinate. The result reports position in normalized
map coordinates, residual/error in metres, confidence, the node ids used, and
the per-clip onsets. A high residual or poor node geometry lowers confidence
and sets `valid=false` where appropriate.

### 2.7 GDOP (`beep_locator/gdop.py`)

For a candidate source position `p`, measurement rows are gradients of the
range differences:

```
h_i = (p - node_i)/||p - node_i|| - (p - node_ref)/||p - node_ref||
H = [h_1, h_2, ...]^T          # (n-1) x 2
GDOP(p) = sqrt(trace((H^T H)^-1))
```

The server grid-searches positions inside the room, excludes points within a
minimum separation of existing nodes, and returns the lowest-GDOP point. That
point is displayed on the admin map as the best next listener position.
Collinear or clustered nodes produce large GDOP; spread nodes produce lower
GDOP. Degenerate matrices are treated as high GDOP, not as a valid suggestion.

### 2.8 Persistence (`data/`)

`data/rooms.json` stores room configuration, nodes (including last-seen and
RTT), event metadata, target signature, and triangulation results. WAV clips
are stored under `data/rooms/<room>/clips/...`. Writes are atomic
(temporary file + replace). `data/` is gitignored. No secrets are stored or
read by the application.

## 3. Explicit limitations

- **Unsynchronized device clocks.** Client timestamps (`t_client_ms`) are
  used only for ordering/display on that device. TDOA is computed from
  within-clip beep/chirp intervals so per-device clock offsets cancel.
- **Microphone and speaker latency.** Consumer microphones, audio drivers,
  and speaker output have unknown and device-specific delays. The chirp
  method partially cancels common-mode latency only for the same device;
  different devices introduce residual offsets. Results are rough, not
  calibrated.
- **Browser permissions.** Microphone access requires explicit user consent.
  A denied or missing device produces no candidates. The UI explains this.
- **Secure context.** `getUserMedia` generally requires HTTPS or
  `localhost`/`127.0.0.1`. Plain HTTP to a LAN IP will fail on phones.
  Optional TLS (`--tls-cert`, `--tls-key`) and `tools/make_cert.py` provide a
  self-signed certificate with the LAN IP in the SAN. Browsers will show a
  certificate warning that the user must accept.
- **Multipath and reverberation.** Reflections shift apparent onsets,
  especially for claps and in hard-walled rooms. The chirp and beep matched
  filters are vulnerable to echo; the confidence score is reduced but cannot
  remove multipath.
- **Rough placement vs fine acoustic ranging.** Dragging node markers gives
  rough coordinates only. Fine acoustic ranging would need surveyed node
  positions, calibrated device latency, synchronized clocks or a more
  sophisticated joint estimation, and repeated measurements. This app
  deliberately stops at rough placement + TDOA triangulation.
- **Intermittent beeps.** If the beep is too short, too quiet, or outside the
  detector band, it may not be captured. A confirmed mystery-beep signature
  is matched by frequency/tolerance, not by a full audio fingerprint.
- **Only 2-D.** The model assumes all devices and the source are in the same
  horizontal plane; height differences are ignored.
- **No external QR service.** The join URL is always displayed and copyable.
  QR rendering, if present, is generated locally in the browser.

## 4. Synthetic-data test plan

No test uses a real microphone, speaker, browser, or external network.

### Server integration (`tests/test_server.py`)

Using `aiohttp.test_utils.TestServer` and `TestClient`:

1. `/health` returns `ok`, name, version, room count.
2. WebSocket join → `hello_ok` with room/node/config.
3. Position update → state endpoint shows the new normalized position.
4. Latency probes → client sends pong replies → node RTT becomes available.
5. Candidate message → event is stored and broadcast; a `chirp` is broadcast
   when a speaker-capable anchor exists.
6. Audio upload → WAV stored; state/event update; triangulation broadcast
   when at least three valid clips exist.
7. `install-module` HTTP POST → `install_module` broadcast; listener ack
   relayed.
8. Mystery target POST → target stored/broadcast.
9. Invalid JSON/structure → `error` message, connection remains usable.

### Triangulation (`tests/test_triangulation.py`)

Simulate an 8 m x 6 m room with known node and source positions. Generate
per-node intervals from true distances and a common unmodeled beep/chirp time
gap plus per-node clock offsets; add a small noise term. Assert the estimated
source is within 0.3 m of truth. Also test the sign convention:
a node farther from the source has a larger TDOA and positive interval
difference after chirp-distance correction. Test degenerate collinear input
returns a flagged result.

### GDOP (`tests/test_gdop.py`)

- Collinear nodes produce a worse (larger) GDOP score than spread nodes.
- The suggested next point lies inside the room.
- The suggested point is not on top of an existing node.
- A degenerate geometry does not crash.

### Audio (`tests/test_audio.py`)

- 16-bit mono WAV encode/decode round trip (sample and rate preservation).
- Clip window bounds clamp correctly at the start/end of the ring buffer.
- Chirp reference generation has the expected length and frequency range.
- Synthetic chirp+beep clip yields onsets consistent with the generated
  offsets, and interval differences recover the expected TDOA.

### Detector (`tests/detector.test.mjs`)

Node-only tests of `static/detector.js`:

- Silence → no detection.
- Low-frequency tone (e.g. 200 Hz) → rejected.
- Synthetic high-frequency beep (e.g. 4.2 kHz burst) → detected as `beep`.
- Broadband impulse/clap → classified as `clap`, not `beep`.
- Configurable thresholds are respected.

## 5. Definition of done

```
python3 -m compileall -q server.py beep_locator
python3 -m pytest -q
node --check static/detector.js
node --test tests/detector.test.mjs
```

All must pass. The server must start on `0.0.0.0:8765` by default and serve
the admin and listener UIs. A short `TODO.md` may list optional polish if the
time limit is reached; Phase 1 must always be runnable.
