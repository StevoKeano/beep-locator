// Listener client JavaScript

let ws = null;
let roomId = 'default';
let nodeId = null;
let audioContext = null;
let mediaStream = null;
let analyser = null;
let scriptProcessor = null;
let ringBuffer = new Float32Array(48000 * 60); // 60 seconds at 48kHz
let bufferIndex = 0;
let isListening = false;

// DOM elements
const statusText = document.getElementById('status-text');
const permissionText = document.getElementById('permission-text');
const audioLevelElement = document.getElementById('audio-level');
const visualizer = document.getElementById('visualizer');
const ctx = visualizer.getContext('2d');

function connectWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws?room=${roomId}`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = function(event) {
        console.log("Connected to WebSocket");
        statusText.textContent = "Connected";
        
        // Send hello message
        sendHello();
    };
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };
    
    ws.onclose = function(event) {
        console.log("WebSocket closed");
        statusText.textContent = "Disconnected - reconnecting...";
        // Attempt to reconnect
        setTimeout(connectWebSocket, 1000);
    };
    
    ws.onerror = function(error) {
        console.error("WebSocket error:", error);
        statusText.textContent = "Connection error";
    };
}

function sendHello() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    
    const helloMessage = {
        type: "hello",
        name: navigator.userAgent,
        capabilities: {
            mic: true,
            speaker: false
        },
        role: "listener"
    };
    
    ws.send(JSON.stringify(helloMessage));
}

function handleMessage(message) {
    if (message.type === 'hello_ok') {
        nodeId = message.node_id;
        console.log("Received hello_ok with node ID:", nodeId);
        startAudioCapture();
    } else if (message.type === 'latency_probe') {
        // Send pong
        ws.send(JSON.stringify({
            type: "pong",
            probe_id: message.probe_id,
            t_server_ms: message.t_server_ms
        }));
    } else if (message.type === 'chirp') {
        console.log("Received chirp command:", message);
        // In a real implementation, this would trigger audio playback and recording
    } else if (message.type === 'install_module') {
        console.log("Received install_module:", message);
        // Handle module installation
        handleModuleInstallation(message.source);
    } else if (message.type === 'error') {
        console.error("Server error:", message.message);
    }
}

function startAudioCapture() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        permissionText.textContent = "getUserMedia not supported in this browser.";
        return;
    }

    // Check for secure context (HTTPS or localhost)
    if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') {
        permissionText.textContent = "Microphone access requires HTTPS or localhost.";
        return;
    }
    
    const constraints = { audio: true };
    
    navigator.mediaDevices.getUserMedia(constraints)
        .then(function(stream) {
            mediaStream = stream;
            setupAudioContext();
            isListening = true;
            statusText.textContent = "Listening...";
            
            // Start the periodic detector
            setInterval(detectBeep, 100); // Every 100ms
        })
        .catch(function(err) {
            console.error("Error accessing microphone:", err);
            permissionText.textContent = `Microphone access denied: ${err.message}`;
        });
}

function setupAudioContext() {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    // Create source from media stream
    const source = audioContext.createMediaStreamSource(mediaStream);
    
    // Create high-pass filter to remove low frequencies
    const highpassFilter = audioContext.createBiquadFilter();
    highpassFilter.type = "highpass";
    highpassFilter.frequency.value = 1500; // 1.5 kHz cutoff
    
    // Connect nodes
    source.connect(highpassFilter);
    
    // Create analyser for visualization
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    highpassFilter.connect(analyser);
    
    // Create script processor for ring buffer capture
    const bufferSize = 2048;
    scriptProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);
    
    // Connect to script processor for ring buffer
    analyser.connect(scriptProcessor);
    scriptProcessor.connect(audioContext.destination);
    
    // Set up buffer writing
    scriptProcessor.onaudioprocess = function(e) {
        const inputBuffer = e.inputBuffer.getChannelData(0);
        
        // Write to ring buffer (circular)
        for (let i = 0; i < bufferSize; i++) {
            ringBuffer[bufferIndex] = inputBuffer[i];
            bufferIndex = (bufferIndex + 1) % ringBuffer.length;
        }
    };
    
    // Start visualization
    visualize();
}

function detectBeep() {
    // In a real implementation, this would run the detector on the ring buffer
    // For now, we'll simulate detection
    
    // Simulate audio level
    const level = Math.random() * 0.5;
    audioLevelElement.textContent = level.toFixed(2);
    
    // Occasionally send a candidate (simulated detection)
    if (Math.random() > 0.95) {
        const candidateEvent = {
            type: "candidate",
            event_id: "evt-" + Date.now(),
            kind: Math.random() > 0.5 ? "beep" : "clap",
            freq_hz: 4200,
            duration_ms: 45,
            level: level,
            confidence: 0.8,
            t_client_ms: Date.now()
        };
        
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(candidateEvent));
        }
    }
}

function visualize() {
    if (!analyser) return;
    
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    function draw() {
        requestAnimationFrame(draw);
        
        analyser.getByteFrequencyData(dataArray);
        
        ctx.clearRect(0, 0, visualizer.width, visualizer.height);
        
        const barWidth = (visualizer.width / bufferLength) * 2.5;
        let barHeight;
        let x = 0;
        
        for (let i = 0; i < bufferLength; i++) {
            barHeight = dataArray[i] / 255 * visualizer.height;
            
            ctx.fillStyle = `rgb(${barHeight + 100}, 50, 50)`;
            ctx.fillRect(x, visualizer.height - barHeight, barWidth, barHeight);
            
            x += barWidth + 1;
        }
    }
    
    draw();
}

function handleModuleInstallation(source) {
    // In a real implementation, this would replace the detector function
    console.log("Installing new module source");
    document.getElementById('module-source').textContent = source;
    document.getElementById('module-version').textContent = "2";
}

// Initialize
connectWebSocket();

// Button handlers
document.getElementById('connect-btn').addEventListener('click', () => {
    if (!isListening) {
        connectWebSocket();
    } else {
        statusText.textContent = "Already connected.";
    }
});

document.getElementById('install-module-btn').addEventListener('click', () => {
    // In a real implementation, this would prompt for module source
    alert("In a real app, this would open a dialog to upload new detector logic.");
});