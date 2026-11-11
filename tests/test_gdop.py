"""
GDOP tests for Beep Locator.
"""

import unittest
import numpy as np

from beep_locator.gdop import calculate_gdop, suggest_next_position


class TestGDOP(unittest.TestCase):
    
    def test_calculate_gdop_basic(self):
        """Test basic GDOP calculation."""
        positions = [
            [0.2, 0.3],
            [0.8, 0.4], 
            [0.5, 0.9]
        ]
        
        source_pos = (0.5, 0.5)
        gdop = calculate_gdop(positions, source_pos)
        
        self.assertGreaterEqual(gdop, 0.0)
        self.assertNotEqual(gdop, float('inf'))
        
    def test_calculate_gdop_collinear(self):
        """Test GDOP with collinear nodes."""
        positions = [
            [0.2, 0.3],
            [0.5, 0.6], 
            [0.8, 0.9]
        ]
        
        source_pos = (0.5, 0.5)
        gdop = calculate_gdop(positions, source_pos)
        
        # Should return a finite value (though higher than spread nodes)
        self.assertGreaterEqual(gdop, 0.0)
        self.assertNotEqual(gdop, float('inf'))
        
    def test_suggest_next_position(self):
        """Test suggestion of next position."""
        positions = [
            [0.2, 0.3],
            [0.8, 0.4], 
            [0.5, 0.9]
        ]
        
        suggested_pos = suggest_next_position(positions, 8.0, 6.0)
        
        self.assertIsInstance(suggested_pos, tuple)
        self.assertEqual(len(suggested_pos), 2)
        self.assertGreaterEqual(suggested_pos[0], 0.0)
        self.assertLessEqual(suggested_pos[0], 1.0)
        self.assertGreaterEqual(suggested_pos[1], 0.0)
        self.assertLessEqual(suggested_pos[1], 1.0)


if __name__ == '__main__':
    unittest.main()