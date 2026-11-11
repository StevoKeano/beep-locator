"""
Audio processing utilities for Beep Locator.
"""

import base64
import io
import logging
from typing import Tuple

import numpy as np
import soundfile as sf


logger = logging.getLogger(__name__)


def generate_chirp(f_start_hz: float, f_end_hz: float, duration_ms: float, 
                   sample_rate: int = 48000, window: str = "hann") -> np.ndarray:
    """
    Generate a linear chirp signal.
    
    Args:
        f_start_hz: Start frequency in Hz
        f_end_hz: End frequency in Hz  
        duration_ms: Duration in milliseconds
        sample_rate: Sampling rate in Hz
        window: Window function name (e.g., 'hann')
        
    Returns:
        Chirp signal as numpy array
    """
    # Convert duration to seconds
    duration_s = duration_ms / 1000.0
    
    # Generate time vector
    t = np.linspace(0, duration_s, int(duration_s * sample_rate), endpoint=False)
    
    # Generate linear chirp: f(t) = f_start + (f_end - f_start) * t / T
    # We'll use the standard formula for a chirp signal
    chirp_signal = np.sin(2 * np.pi * (
        f_start_hz * t + (f_end_hz - f_start_hz) * t**2 / (2 * duration_s)
    ))
    
    # Apply window if specified
    if window == "hann":
        win = np.hanning(len(chirp_signal))
        chirp_signal *= win
    
    return chirp_signal


def save_wav_clip(clips_dir: str, event_id: str, node_id: str, wav_b64: str) -> None:
    """
    Save a base64-encoded WAV clip to disk.
    
    Args:
        clips_dir: Directory to save clips
        event_id: Event identifier
        node_id: Node identifier  
        wav_b64: Base64-encoded WAV data
    """
    # Decode base64
    wav_data = base64.b64decode(wav_b64)
    
    # Create event directory if needed
    event_dir = f"{clips_dir}/{event_id}"
    import os
    os.makedirs(event_dir, exist_ok=True)
    
    # Save to file
    filepath = f"{event_dir}/{node_id}.wav"
    with open(filepath, "wb") as f:
        f.write(wav_data)


def load_wav_clip(clips_dir: str, event_id: str, node_id: str) -> Tuple[np.ndarray, int]:
    """
    Load a WAV clip from disk.
    
    Args:
        clips_dir: Directory containing clips
        event_id: Event identifier
        node_id: Node identifier
        
    Returns:
        Tuple of (audio_data, sample_rate)
    """
    filepath = f"{clips_dir}/{event_id}/{node_id}.wav"
    data, sr = sf.read(filepath)
    return data, sr


def detect_onset(audio: np.ndarray, sample_rate: int, method: str = "cross_correlation") -> int:
    """
    Detect onset of a signal.
    
    Args:
        audio: Audio signal
        sample_rate: Sampling rate in Hz
        method: Detection method
        
    Returns:
        Sample index of onset
    """
    if method == "cross_correlation":
        # For now, we'll use a simple threshold-based approach
        # In real implementation, this would be more sophisticated
        envelope = np.abs(audio)
        threshold = np.mean(envelope) * 2.0  # Adjust threshold as needed
        onset_indices = np.where(envelope > threshold)[0]
        if len(onset_indices) > 0:
            return int(onset_indices[0])  # Return first onset
        else:
            return 0  # No clear onset found
            
    return 0  # Default fallback


def find_chirp_onset(audio: np.ndarray, sample_rate: int, chirp_signal: np.ndarray) -> int:
    """
    Find the onset of a chirp in audio using cross-correlation.
    
    Args:
        audio: Audio signal
        sample_rate: Sampling rate in Hz
        chirp_signal: Reference chirp signal
        
    Returns:
        Sample index of chirp onset
    """
    # Normalize chirp for correlation
    chirp_norm = chirp_signal / np.linalg.norm(chirp_signal)
    
    # Correlate with audio (reverse chirp for cross-correlation)
    correlation = np.correlate(audio, chirp_norm[::-1], mode='full')
    
    # Find peak in correlation
    peak_idx = np.argmax(correlation)
    
    # Return the corresponding index in the audio
    # Note: correlation is longer than audio, so we need to adjust
    delay = len(correlation) - len(audio)  # The offset due to correlation length
    return int(peak_idx - delay)


def find_beep_onset(audio: np.ndarray, sample_rate: int, freq_hz: float, 
                    chirp_onset: int, window_size_ms: int = 100) -> int:
    """
    Find the onset of a beep in audio using band-pass filtering and thresholding.
    
    Args:
        audio: Audio signal
        sample_rate: Sampling rate in Hz
        freq_hz: Target frequency of the beep
        chirp_onset: Known chirp onset (to constrain search)
        window_size_ms: Window size for analysis
        
    Returns:
        Sample index of beep onset
    """
    # Band-pass filter around the beep frequency
    # For now, use a simple approach: detect envelope in a window before chirp
    window_size = int(window_size_ms * sample_rate / 1000)
    
    # We'll search for the first significant rise in the envelope
    start_idx = max(0, chirp_onset - window_size)
    end_idx = chirp_onset
    
    if start_idx >= end_idx:
        return chirp_onset
        
    # Compute envelope (absolute values)
    envelope = np.abs(audio[start_idx:end_idx])
    
    # Find significant increase
    threshold = np.mean(envelope) * 2.0  # Adjust as needed
    onset_indices = np.where(envelope > threshold)[0]
    
    if len(onset_indices) > 0:
        return int(start_idx + onset_indices[0])  # Return first onset in original audio
    else:
        return start_idx  # Default to window start if no clear onset found