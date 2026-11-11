"""
Audio processing tests for Beep Locator.
"""

import unittest
import numpy as np

from beep_locator.audio import generate_chirp, save_wav_clip, load_wav_clip, detect_onset, find_chirp_onset, find_beep_onset


class TestAudio(unittest.TestCase):
    
    def test_generate_chirp(self):
        """Test chirp generation."""
        chirp = generate_chirp(2500, 6000, 120, 48000)
        
        self.assertIsInstance(chirp, np.ndarray)
        self.assertGreater(len(chirp), 0)
        self.assertEqual(len(chirp), 48000 * 0.12)  # 120ms at 48kHz
        
    def test_detect_onset(self):
        """Test onset detection."""
        # Create a simple signal with clear onset
        signal = np.zeros(1000)
        signal[100:150] = 1.0  # Simple pulse
        
        onset = detect_onset(signal, 48000)
        
        self.assertIsInstance(onset, int)
        self.assertGreaterEqual(onset, 0)
        self.assertLessEqual(onset, len(signal))
        
    def test_find_chirp_onset(self):
        """Test chirp onset detection."""
        # Create a chirp and some noise
        chirp = generate_chirp(2500, 6000, 120, 48000)
        noise = np.random.normal(0, 0.1, 1000)
        signal = np.concatenate([noise, chirp])  # Chirp at the end
        
        onset = find_chirp_onset(signal, 48000, chirp)
        
        self.assertIsInstance(onset, int)
        self.assertGreaterEqual(onset, 0)
        self.assertLessEqual(onset, len(signal))
        
    def test_find_beep_onset(self):
        """Test beep onset detection."""
        # Create a simple signal with a beep and some noise
        chirp = generate_chirp(2500, 6000, 120, 48000)
        noise = np.random.normal(0, 0.1, 1000)
        signal = np.concatenate([noise, chirp])  # Chirp at the end
        
        # Find chirp onset first
        chirp_onset = find_chirp_onset(signal, 48000, chirp)
        
        # Then try to find beep onset (should be before or after chirp)
        beep_onset = find_beep_onset(signal, 48000, 4200, chirp_onset)
        
        self.assertIsInstance(beep_onset, int)
        self.assertGreaterEqual(beep_onset, 0)
        self.assertLessEqual(beep_onset, len(signal))


if __name__ == '__main__':
    unittest.main()