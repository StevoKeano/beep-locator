// Pure JS detector functions for Beep Locator
// Can be tested with Node.js without WebAudio or DOM

/**
 * Detects if audio contains a beep or clap.
 *
 * @param {Float32Array} audio - Audio data (mono)
 * @param {number} sampleRate - Sampling rate in Hz
 * @param {Object} options - Detection options
 * @returns {Object} Detection result with kind ('beep' or 'clap') and confidence
 */
function detect(audio, sampleRate, options = {}) {
    // Default options
    const opts = {
        minFreq: 1500,     // Minimum frequency to consider a beep
        maxFreq: 8000,     // Maximum frequency to consider a beep
        windowSizeMs: 100, // Analysis window size in milliseconds
        threshold: 0.1,    // Detection threshold
        ...options
    };

    // Check if input is valid
    if (!audio || audio.length === 0) {
        return { kind: null, confidence: 0 };
    }

    // Compute spectral flux over time
    const flux = computeSpectralFlux(audio, sampleRate, opts.windowSizeMs);
    
    // Find peaks in flux
    const peaks = findPeaks(flux);
    
    if (peaks.length === 0) {
        return { kind: null, confidence: 0 };
    }

    // For each peak, analyze frequency content to classify as beep or clap
    for (const peak of peaks) {
        const result = classifyPeak(audio, sampleRate, peak, opts);
        if (result.confidence > opts.threshold) {
            return result;
        }
    }

    return { kind: null, confidence: 0 };
}

/**
 * Computes spectral flux over time.
 *
 * @param {Float32Array} audio - Audio data
 * @param {number} sampleRate - Sampling rate in Hz
 * @param {number} windowSizeMs - Analysis window size in milliseconds
 * @returns {Float32Array} Spectral flux values
 */
function computeSpectralFlux(audio, sampleRate, windowSizeMs) {
    const windowSize = Math.floor(sampleRate * windowSizeMs / 1000);
    const numWindows = Math.floor(audio.length / windowSize);
    
    const flux = new Float32Array(numWindows);
    
    for (let i = 0; i < numWindows; i++) {
        const start = i * windowSize;
        const end = Math.min(start + windowSize, audio.length);
        
        // Simple DFT using Goertzel algorithm or just FFT would be better
        // For now, we'll use a basic approach with magnitude spectrum
        
        const windowData = audio.subarray(start, end);
        const magSpectrum = computeMagnitudeSpectrum(windowData);
        
        if (i === 0) {
            flux[i] = 0;
        } else {
            const prevMagSpectrum = computeMagnitudeSpectrum(audio.subarray((i-1)*windowSize, i*windowSize));
            let sum = 0;
            for (let j = 0; j < magSpectrum.length; j++) {
                sum += Math.max(0, magSpectrum[j] - prevMagSpectrum[j]);
            }
            flux[i] = sum / magSpectrum.length;
        }
    }
    
    return flux;
}

/**
 * Finds peaks in a signal.
 *
 * @param {Float32Array} signal - Input signal
 * @returns {number[]} Indices of peaks
 */
function findPeaks(signal) {
    const peaks = [];
    for (let i = 1; i < signal.length - 1; i++) {
        if (signal[i] > signal[i-1] && signal[i] > signal[i+1]) {
            peaks.push(i);
        }
    }
    return peaks;
}

/**
 * Classifies a peak in the audio.
 *
 * @param {Float32Array} audio - Audio data
 * @param {number} sampleRate - Sampling rate in Hz
 * @param {number} peakIndex - Index of the peak to classify
 * @param {Object} opts - Options
 * @returns {Object} Classification result
 */
function classifyPeak(audio, sampleRate, peakIndex, opts) {
    // Extract a window around the peak
    const windowSize = Math.floor(sampleRate * opts.windowSizeMs / 1000);
    const start = Math.max(0, peakIndex - windowSize/2);
    const end = Math.min(audio.length, peakIndex + windowSize/2);
    
    const windowData = audio.subarray(start, end);
    
    // Compute magnitude spectrum
    const magSpectrum = computeMagnitudeSpectrum(windowData);
    
    // Get dominant frequency (peak in spectrum)
    let maxIdx = 0;
    let maxValue = 0;
    for (let i = 0; i < magSpectrum.length; i++) {
        if (magSpectrum[i] > maxValue) {
            maxValue = magSpectrum[i];
            maxIdx = i;
        }
    }
    
    const dominantFreq = maxIdx * sampleRate / windowData.length;
    
    // Compute spectral flatness (measure of how "noisy" the spectrum is)
    const flatness = computeSpectralFlatness(magSpectrum);
    
    // Compute band energy in beep range
    let totalEnergy = 0;
    let beepEnergy = 0;
    for (let i = 0; i < magSpectrum.length; i++) {
        totalEnergy += magSpectrum[i];
        if (dominantFreq >= opts.minFreq && dominantFreq <= opts.maxFreq) {
            beepEnergy += magSpectrum[i];
        }
    }
    
    const energyRatio = beepEnergy / totalEnergy;
    
    // Classify based on frequency, flatness, and energy ratio
    let kind = 'clap';
    let confidence = 0;
    
    if (dominantFreq >= opts.minFreq && dominantFreq <= opts.maxFreq) {
        // Likely a beep - check for sharpness
        if (flatness < 0.5) { // More tonal than noisy
            kind = 'beep';
            confidence = Math.min(1, energyRatio * 2); // Scale confidence
        }
    } else if (flatness > 0.7) { // Noisy signal
        kind = 'clap';
        confidence = Math.min(1, (1 - flatness) * 2);
    }
    
    return { kind, confidence };
}

/**
 * Computes magnitude spectrum of audio.
 *
 * @param {Float32Array} audio - Audio data
 * @returns {Float32Array} Magnitude spectrum
 */
function computeMagnitudeSpectrum(audio) {
    // Simple approach: use FFT or DFT
    // For now, we'll simulate with a basic approach
    
    const N = audio.length;
    const spectrum = new Float32Array(N / 2);
    
    for (let k = 0; k < N / 2; k++) {
        let real = 0;
        let imag = 0;
        
        for (let n = 0; n < N; n++) {
            const angle = -2 * Math.PI * k * n / N;
            real += audio[n] * Math.cos(angle);
            imag += audio[n] * Math.sin(angle);
        }
        
        spectrum[k] = Math.sqrt(real*real + imag*imag) / N;
    }
    
    return spectrum;
}

/**
 * Computes spectral flatness of a magnitude spectrum.
 *
 * @param {Float32Array} spectrum - Magnitude spectrum
 * @returns {number} Spectral flatness (0-1)
 */
function computeSpectralFlatness(spectrum) {
    if (spectrum.length === 0) return 0;
    
    let sum = 0;
    let prod = 1;
    
    for (let i = 0; i < spectrum.length; i++) {
        sum += spectrum[i];
        prod *= spectrum[i] || 1e-10; // Avoid zero
    }
    
    const mean = sum / spectrum.length;
    const geometricMean = Math.pow(prod, 1/spectrum.length);
    
    return geometricMean / (mean + 1e-10); // Add small epsilon to avoid division by zero
}

// Export for Node.js testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        detect,
        computeSpectralFlux,
        findPeaks,
        classifyPeak,
        computeMagnitudeSpectrum,
        computeSpectralFlatness
    };
}