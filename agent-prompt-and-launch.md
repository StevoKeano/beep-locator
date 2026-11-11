nohup env CONTEXTCUT_CTX_LIMIT=98304 CONTEXTCUT_CODING_REASONING=auto \
  ~/contextcut/venv/bin/python ~/contextcut/coding_agent.py \
  --workspace ~/dev/beep-locator \
  --base-url http://192.168.137.1:8080/v1 \
  --model deepseek-v4.1-flash \
  --max-steps 35 \
  --timeout 2400 \
  --max-tokens 16384 \
  --json --quiet \
  "$(< /tmp/beep-locator-prompts/beep-locator.txt)" \
  > /tmp/beep-locator-run.log 2>&1 & echo $! > /tmp/beep-locator-run.pid

/tmp/beep-locator-prompts/beep-locator.txt : 

You are working in an empty sandboxed workspace. Build a complete, runnable
local-network application called "Beep Locator" for locating an intermittent
high-pitched beep using multiple consumer browsers (laptop, phone, tablet).
This codebase is yours: keep it coherent, documented, and runnable.

FIRST DELIVERABLE
Create problem.md before implementing. It must cover:
- The user problem and operating assumptions.
- Architecture: aiohttp server, admin UI, listener client, WebSocket protocol,
  audio pipeline, triangulation, GDOP, persistence.
- Explicit limitations: unsynchronized device clocks, microphone/speaker
  latency, browser permissions, secure-context requirements, multipath,
  and the difference between rough placement and fine acoustic ranging.
- The synthetic-data test plan.

THEN IMPLEMENT IN THIS PRIORITY ORDER
Phase 1 is mandatory. Phase 2 and 3 are next. If you approach the step or time
limit, stop with Phase 1 runnable and tests passing, and leave a short TODO.md
for the remaining work. Do not leave a non-running server or broken tests.

ENVIRONMENT / HARD CONSTRAINTS
- Use system `python3`, never `python`. `python` is not installed.
- Use aiohttp for HTTP and WebSockets. FastAPI is NOT installed.
- Installed and allowed: numpy, scipy, soundfile, cryptography, PIL, pytest,
  node, npm. Do not install packages.
- No external network calls, CDNs, external QR services, images, fonts, or
  audio assets. The app must be self-contained.
- Vanilla HTML/CSS/JS only. No frontend frameworks or build step.
- The tool shell cannot use `;`, pipes, redirects, `&&`, or command
  substitution. Run one command per tool call.
- Do not require real microphones, speakers, phones, or browsers in automated
  tests. Test with synthetic PCM/WAV data and aiohttp's test client.
- Keep detector math in pure functions in static/detector.js so Node can test
  it without WebAudio or a DOM.
- Microphone capture on a phone requires HTTPS. Implement optional TLS:
  `--tls-cert` and `--tls-key`, plus `tools/make_cert.py` using `cryptography`
  to create a self-signed certificate with the LAN IP as a SAN. HTTP on
  localhost is fine for development. Always show a copyable join URL; QR
  rendering is optional and must not use an external service.
- Bind 0.0.0.0 by default. Default port 8765. Auto-detect the LAN IP with a
  local UDP socket trick, not an external request. Use room-scoped state.
- Persist runtime data under data/ and gitignore it. Never read/write secrets.

PREFERRED FILE LAYOUT
server.py
beep_locator/
  __init__.py
  app.py
  protocol.py
  rooms.py
  audio.py
  triangulate.py
  gdop.py
static/
  admin.html
  admin.css
  admin.js
  listen.html
  listen.css
  listener.js
  detector.js
  qr.js
tests/
  test_server.py
  test_triangulation.py
  test_gdop.py
  test_audio.py
  detector.test.mjs
tools/
  make_cert.py
  push_module.py
README.md
problem.md

Equivalent organization is fine, but keep the roles obvious.

PHASE 1: FOUNDATION
1. Aiohttp server:
   - GET /health returns JSON with ok, name, version, room count.
   - GET / serves the admin UI.
   - GET /listen?room=ROOM serves the listener client.
   - GET /api/rooms/{room}/state returns nodes, events, target, and join URL.
   - GET /api/rooms/{room}/audio/{event_id}/{node_id}.wav serves stored clips.
   - POST /api/rooms/{room}/install-module pushes a raw JS module update.
   - POST /api/rooms/{room}/mystery sets the confirmed mystery-beep target.
   - WS /ws?room=ROOM handles all real-time messages.
2. WebSocket protocol. Document it in problem.md.
   Client -> server:
     hello: node_id?, name, capabilities {mic, speaker}
     position: x, y (normalized 0..1 on the room map)
     candidate: event_id, kind ("beep" or "clap"), freq_hz, duration_ms,
                level, confidence, t_client_ms
     audio: event_id, node_id, sample_rate, wav_b64, plus optional
            beep_offset_samples and chirp_offset_samples
     pong: probe_id, t_server_ms
   Server -> client:
     hello_ok: node_id, room, config, nodes, events, target
     latency_probe: probe_id, t_server_ms
     chirp: event_id, anchor_node_id, chirp parameters, record window,
            play_at_ms
     triangulation: event_id, x, y, error_m, gdop, confidence, clips
     install_module: module, version, source
     target: event_id, signature
3. Room and node registry:
   - Node IDs may be client-supplied on first join, otherwise server-generated.
   - Track name, capabilities, position, last_seen, and measured RTT.
   - Mark stale nodes disconnected after a timeout.
   - Use latency probes (5 pings, median RTT) to rank nodes.
4. Admin UI:
   - 2D canvas map with room boundary, grid, node markers, and event markers.
   - Rough Mode: drag nodes to place them; send normalized positions.
   - Nodes panel with name, position, RTT, and connection state.
   - Join URL display, plus a locally rendered QR if available.
   - Event log with HH:MM:SS, beep as X, clap as diamond, coordinate,
     confidence, and inline audio players.
   - "Play sequence" plays the selected event's clips in listener order.
   - "This is the mystery beep" button marks the selected event as target.
   - Visual GDOP suggestion marker for the best next listener position.
5. Listener client:
   - getUserMedia audio, high-pass filter, analyser, and continuous capture.
   - Maintain a rolling 60-second mono PCM ring buffer in memory.
   - detector.js: FFT/spectral-flux detection for sharp high-frequency beeps
     and transient claps. Make it configurable and pure-function testable.
   - Report candidate events over WebSocket.
   - Extract and upload a WAV clip around the candidate.
   - Reconnect and re-register automatically.
   - Handle mic-permission and secure-context errors with clear UI text.
   - Implement installModule(source): hot-swap the detector logic without
     recreating the AudioContext or MediaStream and without losing mic
     permission. Acknowledge success/failure over WebSocket.
   - Send WebSocket pong replies for latency probes.

PHASE 2: ACOUSTIC SYNC AND TRIANGULATION
- When a candidate event arrives, choose the lowest-median-RTT node with
  speaker capability as the anchor.
- Broadcast a chirp command: 2.5 kHz to 6 kHz, about 120 ms, Hann-windowed,
  moderate gain. All nodes record from 0.6 s before the candidate beep to
  0.8 s after the chirp. Include pre-roll from the ring buffer.
- Upload clips as 16-bit mono WAV. Store them per event/node and expose them
  through the audio endpoint.
- On the server, locate the chirp and beep onsets in each clip by matched
  filtering/cross-correlation with the generated chirp reference.
- Recover TDOA without synchronized clocks. For node i:
    interval_i = beep_onset_i - chirp_onset_i
  Clock offsets cancel. With known chirp travel distances d_chirp_i:
    tdoa_i - tdoa_j = c * ((interval_i - interval_j)
                           - (d_chirp_i - d_chirp_j)/c)
  Use the anchor's own chirp distance as approximately zero. Document and
  validate the sign convention with synthetic data.
- Solve 2D multilateration with scipy.optimize.least_squares or a clear
  Gauss-Newton implementation. Require at least 3 non-collinear nodes.
  Return position, residual/error, confidence, and the node IDs used.
- Reject or flag degenerate geometry rather than inventing coordinates.
- Implement GDOP: grid-search candidate map positions, compute the TDOA
  Jacobian, and use sqrt(trace((H^T H)^-1)). Return the lowest-GDOP point
  inside the room, excluding points too close to existing nodes. Display it
  on the admin map.
- Mystery-beep tracking: store frequency/tolerance and interval signature.
  When a new candidate matches, mark it as the target signature and
  automatically trigger the chirp/triangulation flow. Show tracking state.

PHASE 3: POLISH AND DOCUMENTATION
- README.md with exact setup, run, test, HTTPS/certificate, and phone-join
  instructions. Explain that phone microphones require HTTPS or localhost.
- Explain and display the per-device calibration caveats.
- Add a local module-push helper in tools/push_module.py.
- Add a small seeded demo/test room only if it cannot contaminate live data.
- Ensure no external asset requests occur.

TESTS / DEFINITION OF DONE
Run and report exact results for:
  python3 -m compileall -q server.py beep_locator
  python3 -m pytest -q
  node --check static/detector.js
  node --test tests/detector.test.mjs

Required tests:
- Server integration with aiohttp test client: health, join, positions,
  latency probes, candidate, chirp, audio upload, triangulation broadcast,
  installModule, mystery target, invalid message handling.
- Triangulation with synthetic 8m x 6m room, known node/source positions,
  simulated delays and noise. Assert estimated source is within 0.3 m.
- GDOP: collinear nodes score worse than spread nodes; suggested point is
  inside the room and not on top of an existing node.
- Audio: WAV encode/decode round trip and clip window bounds.
- Detector: silence has no detection; low-frequency tone is rejected;
  synthetic high-frequency beep is detected; clap transient is classified.
- No test may require a real microphone, speaker, browser, or external network.

Finish with a concise summary containing:
- Files created and their roles.
- Exact commands run and pass/fail results.
- How to start the server and join a phone.
- Remaining limitations and TODO items.

Three generation executions produced the current Beep Locator; the final orchestrator run only audited it.
1. Initial scaffold — run 20261111-115847-ab803d
Recorded command from agent-prompt-and-launch.md:
nohup env CONTEXTCUT_CTX_LIMIT=98304 CONTEXTCUT_CODING_REASONING=auto \
  ~/contextcut/venv/bin/python ~/contextcut/coding_agent.py \
  --workspace ~/dev/beep-locator \
  --base-url http://192.168.137.1:8080/v1 \
  --model deepseek-v4.1-flash \
  --max-steps 35 --timeout 2400 --max-tokens 16384 \
  --json --quiet "$(< /tmp/beep-locator-prompts/beep-locator.txt)"
Prompt: /tmp/beep-locator-prompts/beep-locator.txt — 194 lines:
“You are working in an empty sandboxed workspace. Build a complete, runnable local-network application called ‘Beep Locator’…”
It specified problem.md first, then aiohttp server, WebSocket protocol, admin/listener UI, detector.js, triangulation/GDOP, tests, and hard constraints.
Result: DeepSeek timed out after 4 steps at 2515s. The same run log contains a follow-up qwen3-coder:30b execution that finished 29 steps in 338s and wrote the scaffold. Commit b965be6.

2. First repair — run 20261111-150819-71536f
Direct coding_agent.py run; exact timeout/max-token flags were not persisted. Observed command shape:
CONTEXTCUT_CTX_LIMIT=32768 python3 coding_agent.py \
  --workspace /home/steve/dev/beep-locator \
  --model qwen3-coder:30b \
  --base-url http://192.168.137.1:11434/v1 \
  --max-steps 24 --json \
  "$(cat prompts/beep-locator-fix.txt)"
Prompt: prompts/beep-locator-fix.txt — 79 lines:
“You are fixing an existing Beep Locator project. Do not rebuild it.”
It required: FileResponse UI routes, URLSearchParams room parsing, hello_ok join_url, canonical event shape, awaited broadcast_message, strengthened test_server.py; protected triangulate.py and its tests.
Result: max_steps=24, 1237.927s. Fixed M1–M5, but missed M6 and the remaining app.py awaits; verifier failed.

3. Targeted repair — run 20261111-161903-a4a9e1
Exact command:
CONTEXTCUT_CTX_LIMIT=32768 python3 coding_agent.py \
  --workspace /home/steve/dev/beep-locator \
  --model qwen3-coder:30b \
  --base-url http://192.168.137.1:11434/v1 \
  --max-steps 16 --timeout 1200 --max-tokens 8192 --json \
  "$(cat prompts/beep-locator-fix-cycle2.txt)"
Prompt: prompts/beep-locator-fix-cycle2.txt — 54 lines:
“You are fixing the existing Beep Locator project. Do not rebuild it. The previous implementer already fixed the UI routes…”
It required: await every room.broadcast_message(...) in app.py, strengthen test_admin_ui/test_listener_ui, add M7/M8 TODO.md entries; do not touch triangulation or already-fixed routes.
Result: max_steps=16, 37.694s; all intended edits completed; 18 passed

Audit only
Final verifier run 20261111-162110-87e620 did not generate code. It ran with qwen3:14b-q8_0 and returned overall pass. The committed result is 03cf0b0.
▣  Plan · Big Pickle · 1m 45s
Wait, so the deepseek model run was followed by 2 Qwen repair runs?
+ Thought: 2.3s
Almost. DeepSeek’s timed-out attempt was followed by:
1. Qwen3-Coder continuation — run 20261111-115847-ab803d, 29 steps, completed the initial scaffold.
2. Qwen3-Coder repair #1 — run 20261111-150819-71536f, fixed M1–M5.
3. Qwen3-Coder repair #2 — run 20261111-161903-a4a9e1, fixed M6, awaits, and TODO.md.
So it was 1 DeepSeek attempt + 3 Qwen code executions total. The final qwen3:14b-q8_0 run was audit-only.
