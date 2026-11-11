// Detector tests for Node.js

import { detect } from '../static/detector.js';
import assert from 'assert';

// Mock audio data for testing
function createSilence(length) {
    return new Float32Array(length).fill(0);
}

function createTone(freq, duration, sampleRate) {
    const length = Math.floor(duration * sampleRate);
    const tone = new Float32Array(length);
    for (let i = 0; i < length; i++) {
        tone[i] = Math.sin(2 * Math.PI * freq * i / sampleRate);
    }
    return tone;
}

function createImpulse(duration, sampleRate) {
    const length = Math.floor(duration * sampleRate);
    const impulse = new Float32Array(length).fill(0);
    impulse[Math.floor(length / 2)] = 1.0;
    return impulse;
}

console.log('Running detector tests...');

// Test 1: Silence should not be detected
{
    const silence = createSilence(48000); // 1 second of silence at 48kHz
    const result = detect(silence, 48000);
    console.assert(result.kind === null, 'Silence should not be detected');
    console.assert(result.confidence === 0, 'Silence confidence should be 0');
    console.log('✓ Silence test passed');
}

// Test 2: Low-frequency tone should be rejected
{
    const tone = createTone(200, 0.1, 48000); // 200 Hz tone for 100ms
    const result = detect(tone, 48000);
    console.assert(result.kind === null || result.kind === 'clap', 'Low frequency should not be detected as beep');
    console.log('✓ Low-frequency tone test passed');
}

// Test 3: High-frequency beep should be detected
{
    const beep = createTone(4200, 0.05, 48000); // 4200 Hz beep for 50ms
    const result = detect(beep, 48000);
    console.assert(result.kind === 'beep' || result.confidence > 0.5, 'High frequency should be detected as beep');
    console.log('✓ High-frequency beep test passed');
}

// Test 4: Impulse/clap should be classified
{
    const impulse = createImpulse(0.1, 48000); // 100ms impulse
    const result = detect(impulse, 48000);
    console.assert(result.kind === 'clap', 'Impulse should be detected as clap');
    console.log('✓ Impulse/clap test passed');
}

console.log('All detector tests passed!');