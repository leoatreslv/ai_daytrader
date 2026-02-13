import unittest
from unittest.mock import patch, MagicMock
import config
from ctrader_fix_client import CTraderFixClient

class TestMaxPositions(unittest.TestCase):
    def test_config_loaded(self):
        print(f"MAX_OPEN_POSITIONS: {config.MAX_OPEN_POSITIONS}")
        self.assertTrue(isinstance(config.MAX_OPEN_POSITIONS, int))

    def test_position_counting(self):
        client = CTraderFixClient()
        
        # Case 0: Empty
        self.assertEqual(client.get_open_position_count(), 0)
        
        # Case 1: One Long
        client.positions['1'] = {'long': 1000, 'short': 0}
        self.assertEqual(client.get_open_position_count(), 1)
        
        # Case 2: One Long, One Short (Different symbols)
        client.positions['2'] = {'long': 0, 'short': 1000}
        self.assertEqual(client.get_open_position_count(), 2)
        
        # Case 3: Zero quantity (Closed)
        client.positions['3'] = {'long': 0, 'short': 0}
        self.assertEqual(client.get_open_position_count(), 2)
        
        # Case 4: Hedged (Both Long and Short on same symbol)
        client.positions.clear() # Clear previous to test isolation
        client.positions['4'] = {'long': 1000, 'short': 1000}
        # In new logic, this counts as 2 independent positions (directions)
        self.assertEqual(client.get_open_position_count(), 2)

if __name__ == '__main__':
    unittest.main()
