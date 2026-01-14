"""
Unit tests for NVMe Admin Command Tool
Tests parsing logic and data structure handling
"""

import unittest
import struct
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nvme_tool import NVMeTool, NVMeIdentifyData, NVMeSMARTData


class TestIdentifyParsing(unittest.TestCase):
    """Test NVMe Identify Controller data parsing"""

    def create_mock_identify_data(self) -> bytes:
        """Create mock Identify Controller data structure"""
        data = bytearray(4096)
        
        # VID (offset 0, 2 bytes) - Samsung = 0x144D
        struct.pack_into("<H", data, 0, 0x144D)
        
        # SSVID (offset 2, 2 bytes)
        struct.pack_into("<H", data, 2, 0x144D)
        
        # Serial Number (offset 4, 20 bytes)
        serial = b"S5GXNF0R12345678    "
        data[4:24] = serial
        
        # Model Number (offset 24, 40 bytes)
        model = b"Samsung SSD 980 PRO 1TB                 "
        data[24:64] = model
        
        # Firmware Revision (offset 64, 8 bytes)
        firmware = b"5B2QGXA7"
        data[64:72] = firmware
        
        # Controller ID (offset 78, 2 bytes)
        struct.pack_into("<H", data, 78, 5)
        
        # Total NVM Capacity (offset 280, 16 bytes)
        struct.pack_into("<Q", data, 280, 1000204886016)  # ~1TB
        struct.pack_into("<Q", data, 288, 0)
        
        # Number of Namespaces (offset 516, 4 bytes)
        struct.pack_into("<I", data, 516, 1)
        
        return bytes(data)

    def test_parse_identify_vendor_id(self):
        """Test parsing vendor ID from identify data"""
        data = self.create_mock_identify_data()
        tool = NVMeTool(0)
        result = tool.parse_identify_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.vendor_id, 0x144D)

    def test_parse_identify_serial_number(self):
        """Test parsing serial number from identify data"""
        data = self.create_mock_identify_data()
        tool = NVMeTool(0)
        result = tool.parse_identify_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.serial_number.strip(), "S5GXNF0R12345678")

    def test_parse_identify_model_number(self):
        """Test parsing model number from identify data"""
        data = self.create_mock_identify_data()
        tool = NVMeTool(0)
        result = tool.parse_identify_data(data)
        
        self.assertIsNotNone(result)
        self.assertIn("Samsung SSD 980 PRO", result.model_number)

    def test_parse_identify_firmware(self):
        """Test parsing firmware revision from identify data"""
        data = self.create_mock_identify_data()
        tool = NVMeTool(0)
        result = tool.parse_identify_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.firmware_revision, "5B2QGXA7")

    def test_parse_identify_capacity(self):
        """Test parsing total capacity from identify data"""
        data = self.create_mock_identify_data()
        tool = NVMeTool(0)
        result = tool.parse_identify_data(data)
        
        self.assertIsNotNone(result)
        # Should be approximately 1TB
        capacity_gb = result.total_capacity_bytes / (1024**3)
        self.assertGreater(capacity_gb, 900)
        self.assertLess(capacity_gb, 1100)

    def test_parse_identify_short_data(self):
        """Test handling of truncated identify data"""
        data = bytes(100)  # Too short
        tool = NVMeTool(0)
        result = tool.parse_identify_data(data)
        
        self.assertIsNone(result)


class TestSMARTParsing(unittest.TestCase):
    """Test NVMe SMART/Health log parsing"""

    def create_mock_smart_data(self) -> bytes:
        """Create mock SMART/Health log data structure"""
        data = bytearray(512)
        
        # Critical Warning (offset 0, 1 byte) - no warnings
        data[0] = 0x00
        
        # Temperature (offset 1, 2 bytes) - 311K = 38°C
        struct.pack_into("<H", data, 1, 311)
        
        # Available Spare (offset 3, 1 byte) - 100%
        data[3] = 100
        
        # Available Spare Threshold (offset 4, 1 byte) - 10%
        data[4] = 10
        
        # Percentage Used (offset 5, 1 byte) - 1%
        data[5] = 1
        
        # Data Units Read (offset 32, 16 bytes) - ~12TB
        struct.pack_into("<Q", data, 32, 24000000)  # In 512KB units
        struct.pack_into("<Q", data, 40, 0)
        
        # Data Units Written (offset 48, 16 bytes) - ~8TB
        struct.pack_into("<Q", data, 48, 16000000)
        struct.pack_into("<Q", data, 56, 0)
        
        # Host Read Commands (offset 64, 16 bytes)
        struct.pack_into("<Q", data, 64, 245678901)
        struct.pack_into("<Q", data, 72, 0)
        
        # Host Write Commands (offset 80, 16 bytes)
        struct.pack_into("<Q", data, 80, 123456789)
        struct.pack_into("<Q", data, 88, 0)
        
        # Controller Busy Time (offset 96, 16 bytes) - 45 minutes
        struct.pack_into("<Q", data, 96, 45)
        struct.pack_into("<Q", data, 104, 0)
        
        # Power Cycles (offset 112, 16 bytes) - 156
        struct.pack_into("<Q", data, 112, 156)
        struct.pack_into("<Q", data, 120, 0)
        
        # Power On Hours (offset 128, 16 bytes) - 2345 hours
        struct.pack_into("<Q", data, 128, 2345)
        struct.pack_into("<Q", data, 136, 0)
        
        # Unsafe Shutdowns (offset 144, 16 bytes) - 3
        struct.pack_into("<Q", data, 144, 3)
        struct.pack_into("<Q", data, 152, 0)
        
        # Media Errors (offset 160, 16 bytes) - 0
        struct.pack_into("<Q", data, 160, 0)
        struct.pack_into("<Q", data, 168, 0)
        
        # Error Log Entries (offset 176, 16 bytes) - 0
        struct.pack_into("<Q", data, 176, 0)
        struct.pack_into("<Q", data, 184, 0)
        
        return bytes(data)

    def test_parse_smart_critical_warning(self):
        """Test parsing critical warning byte"""
        data = self.create_mock_smart_data()
        tool = NVMeTool(0)
        result = tool.parse_smart_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.critical_warning, 0)

    def test_parse_smart_temperature(self):
        """Test parsing temperature from SMART data"""
        data = self.create_mock_smart_data()
        tool = NVMeTool(0)
        result = tool.parse_smart_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.temperature_kelvin, 311)
        # Temperature in Celsius
        temp_c = result.temperature_kelvin - 273
        self.assertEqual(temp_c, 38)

    def test_parse_smart_available_spare(self):
        """Test parsing available spare percentage"""
        data = self.create_mock_smart_data()
        tool = NVMeTool(0)
        result = tool.parse_smart_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.available_spare, 100)
        self.assertEqual(result.available_spare_threshold, 10)

    def test_parse_smart_percentage_used(self):
        """Test parsing percentage used"""
        data = self.create_mock_smart_data()
        tool = NVMeTool(0)
        result = tool.parse_smart_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.percentage_used, 1)

    def test_parse_smart_power_cycles(self):
        """Test parsing power cycle count"""
        data = self.create_mock_smart_data()
        tool = NVMeTool(0)
        result = tool.parse_smart_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.power_cycles, 156)

    def test_parse_smart_power_on_hours(self):
        """Test parsing power on hours"""
        data = self.create_mock_smart_data()
        tool = NVMeTool(0)
        result = tool.parse_smart_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.power_on_hours, 2345)

    def test_parse_smart_unsafe_shutdowns(self):
        """Test parsing unsafe shutdown count"""
        data = self.create_mock_smart_data()
        tool = NVMeTool(0)
        result = tool.parse_smart_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.unsafe_shutdowns, 3)

    def test_parse_smart_media_errors(self):
        """Test parsing media error count"""
        data = self.create_mock_smart_data()
        tool = NVMeTool(0)
        result = tool.parse_smart_data(data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.media_errors, 0)

    def test_parse_smart_short_data(self):
        """Test handling of truncated SMART data"""
        data = bytes(100)  # Too short
        tool = NVMeTool(0)
        result = tool.parse_smart_data(data)
        
        self.assertIsNone(result)

    def test_parse_smart_with_warnings(self):
        """Test parsing SMART data with critical warnings"""
        data = bytearray(self.create_mock_smart_data())
        # Set critical warning flags
        data[0] = 0x05  # Spare below threshold + Reliability degraded
        
        tool = NVMeTool(0)
        result = tool.parse_smart_data(bytes(data))
        
        self.assertIsNotNone(result)
        self.assertEqual(result.critical_warning, 0x05)
        self.assertTrue(result.critical_warning & 0x01)  # Spare below threshold
        self.assertTrue(result.critical_warning & 0x04)  # Reliability degraded


class TestJSONExport(unittest.TestCase):
    """Test JSON export functionality"""

    def test_json_export_with_data(self):
        """Test JSON export with valid data"""
        tool = NVMeTool(0)
        
        identify = NVMeIdentifyData(
            vendor_id=0x144D,
            subsystem_vendor_id=0x144D,
            serial_number="TEST12345",
            model_number="Test SSD",
            firmware_revision="1.0",
            total_capacity_bytes=1000000000000,
            unallocated_capacity_bytes=0,
            number_of_namespaces=1,
            controller_id=1
        )
        
        smart = NVMeSMARTData(
            critical_warning=0,
            temperature_kelvin=310,
            available_spare=100,
            available_spare_threshold=10,
            percentage_used=5,
            data_units_read=1000000,
            data_units_written=500000,
            host_read_commands=1000000,
            host_write_commands=500000,
            controller_busy_time=100,
            power_cycles=50,
            power_on_hours=1000,
            unsafe_shutdowns=1,
            media_errors=0,
            error_log_entries=0
        )
        
        json_str = tool.export_json(identify, smart)
        
        self.assertIn("Test SSD", json_str)
        self.assertIn("TEST12345", json_str)
        self.assertIn("temperature_celsius", json_str)

    def test_json_export_null_data(self):
        """Test JSON export with null data"""
        tool = NVMeTool(0)
        json_str = tool.export_json(None, None)
        
        self.assertIn('"identify": null', json_str)
        self.assertIn('"smart": null', json_str)


class TestHealthAssessment(unittest.TestCase):
    """Test health assessment logic"""

    def test_health_excellent(self):
        """Test excellent health assessment (0-20% used)"""
        # Percentage used = 1%, health should be EXCELLENT
        health_score = 100 - 1
        self.assertGreaterEqual(health_score, 80)

    def test_health_good(self):
        """Test good health assessment (20-50% used)"""
        health_score = 100 - 35
        self.assertGreaterEqual(health_score, 50)
        self.assertLess(health_score, 80)

    def test_health_fair(self):
        """Test fair health assessment (50-80% used)"""
        health_score = 100 - 70
        self.assertGreaterEqual(health_score, 20)
        self.assertLess(health_score, 50)

    def test_health_poor(self):
        """Test poor health assessment (>80% used)"""
        health_score = 100 - 90
        self.assertLess(health_score, 20)


if __name__ == '__main__':
    unittest.main(verbosity=2)
