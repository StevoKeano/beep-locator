// Admin UI JavaScript

let ws = null;
let roomId = 'default';
let nodes = [];
let events = [];

// Canvas setup
const canvas = document.getElementById('map-canvas');
const ctx = canvas.getContext('2d');

function connectWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws?room=${roomId}`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = function(event) {
        console.log("Connected to WebSocket");
    };
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };
    
    ws.onclose = function(event) {
        console.log("WebSocket closed");
        // Attempt to reconnect
        setTimeout(connectWebSocket, 1000);
    };
    
    ws.onerror = function(error) {
        console.error("WebSocket error:", error);
    };
}

function handleMessage(message) {
    if (message.type === 'hello_ok') {
        roomId = message.room;
        document.getElementById('room-id').textContent = roomId;
        document.getElementById('join-url').href = message.config.join_url;
        document.getElementById('join-url').textContent = message.config.join_url;
        
        nodes = message.nodes;
        events = message.events;
        updateUI();
    } else if (message.type === 'nodes') {
        nodes = message.nodes;
        updateUI();
    } else if (message.type === 'event') {
        events.push(message.event);
        updateUI();
    } else if (message.type === 'error') {
        console.error("Server error:", message.message);
    }
}

function updateUI() {
    updateNodesList();
    updateEventsList();
    drawMap();
}

function updateNodesList() {
    const list = document.getElementById('nodes-list');
    list.innerHTML = '';
    
    nodes.forEach(node => {
        const li = document.createElement('li');
        li.textContent = `${node.name} (${node.id}) - ${node.position[0]},${node.position[1]} - RTT: ${node.rtt_ms || 'N/A'}ms`;
        if (!node.connected) {
            li.style.color = 'red';
        }
        list.appendChild(li);
    });
}

function updateEventsList() {
    const list = document.getElementById('events-list');
    list.innerHTML = '';
    
    events.forEach(event => {
        const li = document.createElement('li');
        li.textContent = `${event.kind} at ${event.t_client_ms}ms - ${event.confidence}`;
        list.appendChild(li);
    });
}

function drawMap() {
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw room grid
    const width = canvas.width;
    const height = canvas.height;
    
    ctx.strokeStyle = '#ccc';
    ctx.lineWidth = 1;
    
    // Vertical lines
    for (let x = 0; x <= width; x += 50) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
    }
    
    // Horizontal lines
    for (let y = 0; y <= height; y += 50) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }
    
    // Draw nodes
    nodes.forEach(node => {
        const x = node.position[0] * width;
        const y = node.position[1] * height;
        
        if (node.connected) {
            ctx.fillStyle = '#007bff';
        } else {
            ctx.fillStyle = '#ccc';
        }
        
        ctx.beginPath();
        ctx.arc(x, y, 8, 0, Math.PI * 2);
        ctx.fill();
        
        // Node ID
        ctx.fillStyle = '#000';
        ctx.font = '12px Arial';
        ctx.fillText(node.id, x + 10, y - 5);
    });
    
    // Draw events
    events.forEach(event => {
        const x = event.position[0] * width;
        const y = event.position[1] * height;
        
        if (event.kind === 'beep') {
            ctx.fillStyle = '#ff0000';
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, Math.PI * 2);
            ctx.fill();
        } else if (event.kind === 'clap') {
            ctx.fillStyle = '#0000ff';
            ctx.beginPath();
            ctx.moveTo(x - 5, y - 5);
            ctx.lineTo(x + 5, y + 5);
            ctx.moveTo(x + 5, y - 5);
            ctx.lineTo(x - 5, y + 5);
            ctx.stroke();
        }
    });
}

// Initialize
connectWebSocket();

// Button handlers
document.getElementById('rough-mode-btn').addEventListener('click', () => {
    alert('Rough mode enabled. Drag nodes to place them.');
});

document.getElementById('play-sequence-btn').addEventListener('click', () => {
    alert('Playing sequence of selected event clips.');
});

document.getElementById('set-target-btn').addEventListener('click', () => {
    alert('Marked selected event as mystery beep target.');
});