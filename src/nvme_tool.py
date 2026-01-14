"""
NVMe Admin Command Tool
Sends NVMe admin commands via Windows DeviceIoControl API
Author: Nitish Chowdary
"""

import ctypes
from ctypes import wintypes
import struct
import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json
import subprocess

# Windows API Constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

# IOCTL codes
IOCTL_STORAGE_QUERY_PROPERTY = 0x2D1400
IOCTL_STORAGE_PROTOCOL_COMMAND = 0x2D1180
IOCTL_SCSI_MINIPORT = 0x4D008

# Storage Property IDs
StorageDeviceProperty = 0
StorageAdapterProperty = 1
StorageDeviceProtocolSpecificProperty = 50

# Protocol Types
ProtocolTypeNvme = 3

# NVMe Admin Commands (Opcodes)
NVME_ADMIN_IDENTIFY = 0x06
NVME_ADMIN_GET_LOG_PAGE = 0x02
NVME_ADMIN_GET_FEATURES = 0x0A
NVME_ADMIN_DEVICE_SELF_TEST = 0x14

# NVMe Log Page IDs
NVME_LOG_ERROR_INFO = 0x01
NVME_LOG_SMART_HEALTH = 0x02
NVME_LOG_FIRMWARE_SLOT = 0x03

# Structures
class STORAGE_PROPERTY_QUERY(ctypes.Structure):
    _fields_ = [
        ("PropertyId", wintypes.DWORD),
        ("QueryType", wintypes.DWORD),
        ("AdditionalParameters", ctypes.c_byte * 1),
    ]

class STORAGE_PROTOCOL_SPECIFIC_DATA(ctypes.Structure):
    _fields_ = [
        ("ProtocolType", wintypes.DWORD),
        ("DataType", wintypes.DWORD),
        ("ProtocolDataRequestValue", wintypes.DWORD),
        ("ProtocolDataRequestSubValue", wintypes.DWORD),
        ("ProtocolDataOffset", wintypes.DWORD),
        ("ProtocolDataLength", wintypes.DWORD),
        ("FixedProtocolReturnData", wintypes.DWORD),
        ("ProtocolDataRequestSubValue2", wintypes.DWORD),
        ("ProtocolDataRequestSubValue3", wintypes.DWORD),
        ("ProtocolDataRequestSubValue4", wintypes.DWORD),
    ]

class STORAGE_PROTOCOL_DATA_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.DWORD),
        ("Size", wintypes.DWORD),
        ("ProtocolSpecificData", STORAGE_PROTOCOL_SPECIFIC_DATA),
    ]

class STORAGE_DEVICE_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.DWORD),
        ("Size", wintypes.DWORD),
        ("DeviceType", ctypes.c_byte),
        ("DeviceTypeModifier", ctypes.c_byte),
        ("RemovableMedia", ctypes.c_byte),
        ("CommandQueueing", ctypes.c_byte),
        ("VendorIdOffset", wintypes.DWORD),
        ("ProductIdOffset", wintypes.DWORD),
        ("ProductRevisionOffset", wintypes.DWORD),
        ("SerialNumberOffset", wintypes.DWORD),
        ("BusType", wintypes.DWORD),
        ("RawPropertiesLength", wintypes.DWORD),
        ("RawDeviceProperties", ctypes.c_byte * 1),
    ]

@dataclass
class NVMeIdentifyData:
    """Parsed NVMe Identify Controller data"""
    vendor_id: int
    subsystem_vendor_id: int
    serial_number: str
    model_number: str
    firmware_revision: str
    total_capacity_bytes: int
    unallocated_capacity_bytes: int
    number_of_namespaces: int
    controller_id: int

@dataclass 
class NVMeSMARTData:
    """Parsed NVMe SMART/Health data"""
    critical_warning: int
    temperature_kelvin: int
    available_spare: int
    available_spare_threshold: int
    percentage_used: int
    data_units_read: int
    data_units_written: int
    host_read_commands: int
    host_write_commands: int
    controller_busy_time: int
    power_cycles: int
    power_on_hours: int
    unsafe_shutdowns: int
    media_errors: int
    error_log_entries: int

class NVMeTool:
    """NVMe Admin Command Tool using Windows DeviceIoControl"""
    
    def __init__(self, drive_number: int):
        self.drive_number = drive_number
        self.drive_path = f"\\\\.\\PhysicalDrive{drive_number}"
        self.handle = None
        self.kernel32 = ctypes.windll.kernel32
        
    def open(self) -> bool:
        """Open handle to the NVMe drive"""
        self.handle = self.kernel32.CreateFileW(
            self.drive_path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        
        if self.handle == -1 or self.handle == 0xFFFFFFFFFFFFFFFF:
            error = ctypes.get_last_error()
            print(f"[ERROR] Failed to open {self.drive_path}: Error code {error}")
            if error == 5:
                print("[INFO] Access denied. Run as Administrator.")
            return False
        
        print(f"[OK] Opened handle to {self.drive_path}")
        return True
    
    def close(self):
        """Close the drive handle"""
        if self.handle and self.handle != -1:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None
            print("[OK] Handle closed")
    
    def device_io_control(self, ioctl_code: int, in_buffer: bytes, out_size: int) -> Optional[bytes]:
        """Send DeviceIoControl command - uses same buffer for input/output"""
        # Create a buffer large enough for both input and output
        buffer_size = max(len(in_buffer), out_size)
        buffer = ctypes.create_string_buffer(buffer_size)
        
        # Copy input data to buffer
        ctypes.memmove(buffer, in_buffer, len(in_buffer))
        
        bytes_returned = wintypes.DWORD(0)
        
        # Set up DeviceIoControl with proper typing
        DeviceIoControl = self.kernel32.DeviceIoControl
        DeviceIoControl.argtypes = [
            wintypes.HANDLE,    # hDevice
            wintypes.DWORD,     # dwIoControlCode
            ctypes.c_void_p,    # lpInBuffer
            wintypes.DWORD,     # nInBufferSize
            ctypes.c_void_p,    # lpOutBuffer
            wintypes.DWORD,     # nOutBufferSize
            ctypes.POINTER(wintypes.DWORD),  # lpBytesReturned
            ctypes.c_void_p     # lpOverlapped
        ]
        DeviceIoControl.restype = wintypes.BOOL
        
        success = DeviceIoControl(
            self.handle,
            ioctl_code,
            ctypes.cast(buffer, ctypes.c_void_p),
            buffer_size,
            ctypes.cast(buffer, ctypes.c_void_p),
            buffer_size,
            ctypes.byref(bytes_returned),
            None
        )
        
        if not success:
            error = ctypes.get_last_error()
            print(f"[ERROR] DeviceIoControl failed: Error code {error}")
            return None
        
        if bytes_returned.value == 0:
            print(f"[WARN] DeviceIoControl returned 0 bytes")
            return None
            
        return buffer.raw[:bytes_returned.value]
    
    def get_device_descriptor(self) -> Optional[Dict[str, Any]]:
        """Query basic storage device descriptor"""
        # Build query structure
        query = STORAGE_PROPERTY_QUERY()
        query.PropertyId = StorageDeviceProperty
        query.QueryType = 0  # PropertyStandardQuery
        
        buffer_size = 1024
        result = self.device_io_control(
            IOCTL_STORAGE_QUERY_PROPERTY,
            bytes(query),
            buffer_size
        )
        
        if not result or len(result) < 36:
            return None
        
        # Parse the descriptor
        desc = {
            "version": struct.unpack_from("<I", result, 0)[0],
            "size": struct.unpack_from("<I", result, 4)[0],
            "device_type": result[8],
            "bus_type": struct.unpack_from("<I", result, 24)[0],
        }
        
        # Extract strings from offsets
        vendor_offset = struct.unpack_from("<I", result, 12)[0]
        product_offset = struct.unpack_from("<I", result, 16)[0]
        revision_offset = struct.unpack_from("<I", result, 20)[0]
        serial_offset = struct.unpack_from("<I", result, 24)[0]
        
        def extract_string(data: bytes, offset: int) -> str:
            if offset == 0 or offset >= len(data):
                return ""
            end = data.find(b'\x00', offset)
            if end == -1:
                end = len(data)
            return data[offset:end].decode('ascii', errors='ignore').strip()
        
        desc["vendor"] = extract_string(result, vendor_offset) if vendor_offset else ""
        desc["product"] = extract_string(result, product_offset) if product_offset else ""
        desc["revision"] = extract_string(result, revision_offset) if revision_offset else ""
        
        return desc
    
    def send_nvme_identify(self) -> Optional[bytes]:
        """Send NVMe Identify Controller command"""
        # Calculate proper offsets
        # STORAGE_PROPERTY_QUERY: PropertyId (4) + QueryType (4) = 8 bytes
        # STORAGE_PROTOCOL_SPECIFIC_DATA: 40 bytes
        # Total header: 48 bytes, then 4096 bytes of identify data
        
        header_size = 48
        data_size = 4096
        buffer_size = header_size + data_size
        
        query_buffer = bytearray(buffer_size)
        
        # STORAGE_PROPERTY_QUERY
        struct.pack_into("<I", query_buffer, 0, StorageDeviceProtocolSpecificProperty)  # PropertyId
        struct.pack_into("<I", query_buffer, 4, 0)  # QueryType = PropertyStandardQuery
        
        # STORAGE_PROTOCOL_SPECIFIC_DATA (starts at offset 8)
        struct.pack_into("<I", query_buffer, 8, ProtocolTypeNvme)   # ProtocolType
        struct.pack_into("<I", query_buffer, 12, 1)                  # DataType = NVMeDataTypeIdentify
        struct.pack_into("<I", query_buffer, 16, 1)                  # ProtocolDataRequestValue (CNS=1 for Controller)
        struct.pack_into("<I", query_buffer, 20, 0)                  # ProtocolDataRequestSubValue
        struct.pack_into("<I", query_buffer, 24, header_size)        # ProtocolDataOffset
        struct.pack_into("<I", query_buffer, 28, data_size)          # ProtocolDataLength
        struct.pack_into("<I", query_buffer, 32, 0)                  # FixedProtocolReturnData
        struct.pack_into("<I", query_buffer, 36, 0)                  # ProtocolDataRequestSubValue2
        struct.pack_into("<I", query_buffer, 40, 0)                  # ProtocolDataRequestSubValue3
        struct.pack_into("<I", query_buffer, 44, 0)                  # ProtocolDataRequestSubValue4
        
        result = self.device_io_control(
            IOCTL_STORAGE_QUERY_PROPERTY,
            bytes(query_buffer),
            buffer_size
        )
        
        if result and len(result) > header_size:
            return result[header_size:]
        return None
    
    def parse_identify_data(self, data: bytes) -> Optional[NVMeIdentifyData]:
        """Parse NVMe Identify Controller data structure"""
        if len(data) < 4096:
            print(f"[WARN] Identify data too short: {len(data)} bytes")
            return None
        
        try:
            vendor_id = struct.unpack_from("<H", data, 0)[0]
            subsys_vendor_id = struct.unpack_from("<H", data, 2)[0]
            serial = data[4:24].decode('ascii', errors='ignore').strip()
            model = data[24:64].decode('ascii', errors='ignore').strip()
            firmware = data[64:72].decode('ascii', errors='ignore').strip()
            
            # Total NVM Capacity (bytes 280-295)
            tnvmcap_lo = struct.unpack_from("<Q", data, 280)[0]
            tnvmcap_hi = struct.unpack_from("<Q", data, 288)[0]
            total_cap = (tnvmcap_hi << 64) | tnvmcap_lo
            
            # Unallocated NVM Capacity
            unvmcap_lo = struct.unpack_from("<Q", data, 296)[0]
            unvmcap_hi = struct.unpack_from("<Q", data, 304)[0]
            unalloc_cap = (unvmcap_hi << 64) | unvmcap_lo
            
            # Number of Namespaces (byte 516)
            nn = struct.unpack_from("<I", data, 516)[0]
            
            # Controller ID (bytes 78-79)
            cntlid = struct.unpack_from("<H", data, 78)[0]
            
            return NVMeIdentifyData(
                vendor_id=vendor_id,
                subsystem_vendor_id=subsys_vendor_id,
                serial_number=serial,
                model_number=model,
                firmware_revision=firmware,
                total_capacity_bytes=total_cap,
                unallocated_capacity_bytes=unalloc_cap,
                number_of_namespaces=nn,
                controller_id=cntlid
            )
        except Exception as e:
            print(f"[ERROR] Failed to parse identify data: {e}")
            return None
    
    def send_nvme_smart(self) -> Optional[bytes]:
        """Send NVMe Get Log Page command for SMART/Health data"""
        header_size = 48
        data_size = 512
        buffer_size = header_size + data_size
        
        query_buffer = bytearray(buffer_size)
        
        # STORAGE_PROPERTY_QUERY
        struct.pack_into("<I", query_buffer, 0, StorageDeviceProtocolSpecificProperty)  # PropertyId
        struct.pack_into("<I", query_buffer, 4, 0)  # QueryType = PropertyStandardQuery
        
        # STORAGE_PROTOCOL_SPECIFIC_DATA (starts at offset 8)
        struct.pack_into("<I", query_buffer, 8, ProtocolTypeNvme)    # ProtocolType
        struct.pack_into("<I", query_buffer, 12, 2)                   # DataType = NVMeDataTypeLogPage
        struct.pack_into("<I", query_buffer, 16, NVME_LOG_SMART_HEALTH)  # ProtocolDataRequestValue (Log ID)
        struct.pack_into("<I", query_buffer, 20, 0)                   # ProtocolDataRequestSubValue
        struct.pack_into("<I", query_buffer, 24, header_size)         # ProtocolDataOffset
        struct.pack_into("<I", query_buffer, 28, data_size)           # ProtocolDataLength
        struct.pack_into("<I", query_buffer, 32, 0)                   # FixedProtocolReturnData
        struct.pack_into("<I", query_buffer, 36, 0)                   # ProtocolDataRequestSubValue2
        struct.pack_into("<I", query_buffer, 40, 0)                   # ProtocolDataRequestSubValue3
        struct.pack_into("<I", query_buffer, 44, 0)                   # ProtocolDataRequestSubValue4
        
        result = self.device_io_control(
            IOCTL_STORAGE_QUERY_PROPERTY,
            bytes(query_buffer),
            buffer_size
        )
        
        if result and len(result) > header_size:
            return result[header_size:]
        return None
    
    def parse_smart_data(self, data: bytes) -> Optional[NVMeSMARTData]:
        """Parse NVMe SMART/Health Information Log"""
        if len(data) < 512:
            print(f"[WARN] SMART data too short: {len(data)} bytes")
            return None
        
        try:
            critical_warning = data[0]
            
            # Temperature is 2 bytes at offset 1-2 (Kelvin)
            temp = struct.unpack_from("<H", data, 1)[0]
            
            available_spare = data[3]
            available_spare_threshold = data[4]
            percentage_used = data[5]
            
            # Data Units Read (16 bytes at offset 32)
            dur_lo = struct.unpack_from("<Q", data, 32)[0]
            dur_hi = struct.unpack_from("<Q", data, 40)[0]
            data_units_read = (dur_hi << 64) | dur_lo
            
            # Data Units Written (16 bytes at offset 48)
            duw_lo = struct.unpack_from("<Q", data, 48)[0]
            duw_hi = struct.unpack_from("<Q", data, 56)[0]
            data_units_written = (duw_hi << 64) | duw_lo
            
            # Host Read Commands (16 bytes at offset 64)
            hrc_lo = struct.unpack_from("<Q", data, 64)[0]
            hrc_hi = struct.unpack_from("<Q", data, 72)[0]
            host_read_commands = (hrc_hi << 64) | hrc_lo
            
            # Host Write Commands (16 bytes at offset 80)
            hwc_lo = struct.unpack_from("<Q", data, 80)[0]
            hwc_hi = struct.unpack_from("<Q", data, 88)[0]
            host_write_commands = (hwc_hi << 64) | hwc_lo
            
            # Controller Busy Time (16 bytes at offset 96)
            cbt_lo = struct.unpack_from("<Q", data, 96)[0]
            cbt_hi = struct.unpack_from("<Q", data, 104)[0]
            controller_busy = (cbt_hi << 64) | cbt_lo
            
            # Power Cycles (16 bytes at offset 112)
            pc_lo = struct.unpack_from("<Q", data, 112)[0]
            pc_hi = struct.unpack_from("<Q", data, 120)[0]
            power_cycles = (pc_hi << 64) | pc_lo
            
            # Power On Hours (16 bytes at offset 128)
            poh_lo = struct.unpack_from("<Q", data, 128)[0]
            poh_hi = struct.unpack_from("<Q", data, 136)[0]
            power_on_hours = (poh_hi << 64) | poh_lo
            
            # Unsafe Shutdowns (16 bytes at offset 144)
            us_lo = struct.unpack_from("<Q", data, 144)[0]
            us_hi = struct.unpack_from("<Q", data, 152)[0]
            unsafe_shutdowns = (us_hi << 64) | us_lo
            
            # Media Errors (16 bytes at offset 160)
            me_lo = struct.unpack_from("<Q", data, 160)[0]
            me_hi = struct.unpack_from("<Q", data, 168)[0]
            media_errors = (me_hi << 64) | me_lo
            
            # Error Log Entries (16 bytes at offset 176)
            ele_lo = struct.unpack_from("<Q", data, 176)[0]
            ele_hi = struct.unpack_from("<Q", data, 184)[0]
            error_log_entries = (ele_hi << 64) | ele_lo
            
            return NVMeSMARTData(
                critical_warning=critical_warning,
                temperature_kelvin=temp,
                available_spare=available_spare,
                available_spare_threshold=available_spare_threshold,
                percentage_used=percentage_used,
                data_units_read=data_units_read,
                data_units_written=data_units_written,
                host_read_commands=host_read_commands,
                host_write_commands=host_write_commands,
                controller_busy_time=controller_busy,
                power_cycles=power_cycles,
                power_on_hours=power_on_hours,
                unsafe_shutdowns=unsafe_shutdowns,
                media_errors=media_errors,
                error_log_entries=error_log_entries
            )
        except Exception as e:
            print(f"[ERROR] Failed to parse SMART data: {e}")
            return None
    
    def print_identify_info(self, identify: NVMeIdentifyData):
        """Print formatted Identify Controller information"""
        print("\n" + "=" * 60)
        print("NVMe IDENTIFY CONTROLLER DATA")
        print("=" * 60)
        print(f"  Model Number:        {identify.model_number}")
        print(f"  Serial Number:       {identify.serial_number}")
        print(f"  Firmware Revision:   {identify.firmware_revision}")
        print(f"  Vendor ID:           0x{identify.vendor_id:04X}")
        print(f"  Subsystem Vendor ID: 0x{identify.subsystem_vendor_id:04X}")
        print(f"  Controller ID:       {identify.controller_id}")
        print(f"  Number of Namespaces:{identify.number_of_namespaces}")
        
        if identify.total_capacity_bytes > 0:
            cap_gb = identify.total_capacity_bytes / (1024**3)
            print(f"  Total Capacity:      {cap_gb:.2f} GB")
        print("=" * 60)
    
    def print_smart_info(self, smart: NVMeSMARTData):
        """Print formatted SMART/Health information"""
        print("\n" + "=" * 60)
        print("NVMe SMART/HEALTH INFORMATION")
        print("=" * 60)
        
        # Critical Warning flags
        cw = smart.critical_warning
        print(f"  Critical Warning:    0x{cw:02X}", end="")
        if cw == 0:
            print(" (No warnings)")
        else:
            warnings = []
            if cw & 0x01: warnings.append("Spare Below Threshold")
            if cw & 0x02: warnings.append("Temperature Exceeded")
            if cw & 0x04: warnings.append("Reliability Degraded")
            if cw & 0x08: warnings.append("Read-Only Mode")
            if cw & 0x10: warnings.append("Volatile Backup Failed")
            print(f" ({', '.join(warnings)})")
        
        # Temperature
        temp_c = smart.temperature_kelvin - 273
        print(f"  Temperature:         {temp_c}°C ({smart.temperature_kelvin} K)")
        
        # Health indicators
        print(f"  Available Spare:     {smart.available_spare}%")
        print(f"  Spare Threshold:     {smart.available_spare_threshold}%")
        print(f"  Percentage Used:     {smart.percentage_used}%")
        
        # Data statistics (convert to human-readable)
        # Data units are in 512KB units
        read_gb = (smart.data_units_read * 512 * 1000) / (1024**3)
        write_gb = (smart.data_units_written * 512 * 1000) / (1024**3)
        print(f"\n  Data Read:           {read_gb:.2f} GB")
        print(f"  Data Written:        {write_gb:.2f} GB")
        print(f"  Host Read Commands:  {smart.host_read_commands:,}")
        print(f"  Host Write Commands: {smart.host_write_commands:,}")
        
        # Lifecycle statistics
        print(f"\n  Power Cycles:        {smart.power_cycles:,}")
        print(f"  Power On Hours:      {smart.power_on_hours:,} hours")
        print(f"  Unsafe Shutdowns:    {smart.unsafe_shutdowns:,}")
        print(f"  Controller Busy:     {smart.controller_busy_time:,} minutes")
        
        # Error statistics
        print(f"\n  Media Errors:        {smart.media_errors:,}")
        print(f"  Error Log Entries:   {smart.error_log_entries:,}")
        
        # Health assessment
        print("\n" + "-" * 60)
        health_score = 100 - smart.percentage_used
        if health_score >= 80:
            health_status = "EXCELLENT"
        elif health_score >= 50:
            health_status = "GOOD"
        elif health_score >= 20:
            health_status = "FAIR"
        else:
            health_status = "POOR"
        
        print(f"  Overall Health:      {health_status} ({health_score}% life remaining)")
        print("=" * 60)
    
    def export_json(self, identify: Optional[NVMeIdentifyData], smart: Optional[NVMeSMARTData]) -> str:
        """Export data as JSON for integration with other tools"""
        data = {
            "drive": self.drive_path,
            "identify": None,
            "smart": None
        }
        
        if identify:
            data["identify"] = {
                "model": identify.model_number,
                "serial": identify.serial_number,
                "firmware": identify.firmware_revision,
                "vendor_id": identify.vendor_id,
                "capacity_bytes": identify.total_capacity_bytes,
                "namespaces": identify.number_of_namespaces
            }
        
        if smart:
            data["smart"] = {
                "critical_warning": smart.critical_warning,
                "temperature_celsius": smart.temperature_kelvin - 273,
                "available_spare_percent": smart.available_spare,
                "percentage_used": smart.percentage_used,
                "power_cycles": smart.power_cycles,
                "power_on_hours": smart.power_on_hours,
                "unsafe_shutdowns": smart.unsafe_shutdowns,
                "media_errors": smart.media_errors,
                "data_read_gb": round((smart.data_units_read * 512 * 1000) / (1024**3), 2),
                "data_written_gb": round((smart.data_units_written * 512 * 1000) / (1024**3), 2)
            }
        
        return json.dumps(data, indent=2)


def list_nvme_drives() -> List[int]:
    """List available physical drives that might be NVMe"""
    drives = []
    kernel32 = ctypes.windll.kernel32
    
    for i in range(16):  # Check drives 0-15
        path = f"\\\\.\\PhysicalDrive{i}"
        handle = kernel32.CreateFileW(
            path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        
        if handle != -1 and handle != 0xFFFFFFFFFFFFFFFF:
            drives.append(i)
            kernel32.CloseHandle(handle)
    
    return drives


def get_disk_info_wmi(drive_number: int) -> Optional[Dict[str, Any]]:
    """Fallback: Get disk info via WMI/PowerShell"""
    try:
        # Get disk info using PowerShell
        ps_cmd = f'''
        $disk = Get-PhysicalDisk | Where-Object {{ $_.DeviceId -eq "{drive_number}" }}
        if ($disk) {{
            $disk | Select-Object FriendlyName, SerialNumber, FirmwareVersion, MediaType, BusType, Size, HealthStatus, OperationalStatus | ConvertTo-Json
        }}
        '''
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception as e:
        print(f"[DEBUG] WMI fallback failed: {e}")
    return None


def get_smart_info_wmi(drive_number: int) -> Optional[Dict[str, Any]]:
    """Fallback: Get SMART/reliability info via WMI/PowerShell"""
    try:
        ps_cmd = f'''
        $disk = Get-PhysicalDisk | Where-Object {{ $_.DeviceId -eq "{drive_number}" }}
        if ($disk) {{
            $reliability = $disk | Get-StorageReliabilityCounter
            $reliability | Select-Object Temperature, Wear, ReadErrorsTotal, WriteErrorsTotal, PowerOnHours | ConvertTo-Json
        }}
        '''
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception as e:
        print(f"[DEBUG] SMART WMI fallback failed: {e}")
    return None


def print_wmi_disk_info(info: Dict[str, Any]):
    """Print disk info from WMI"""
    print("\n" + "=" * 60)
    print("DISK INFORMATION (via Windows Storage API)")
    print("=" * 60)
    print(f"  Model:             {info.get('FriendlyName', 'N/A')}")
    print(f"  Serial Number:     {info.get('SerialNumber', 'N/A')}")
    print(f"  Firmware:          {info.get('FirmwareVersion', 'N/A')}")
    print(f"  Media Type:        {info.get('MediaType', 'N/A')}")
    print(f"  Bus Type:          {info.get('BusType', 'N/A')}")
    
    size = info.get('Size', 0)
    if size:
        size_gb = int(size) / (1024**3)
        print(f"  Capacity:          {size_gb:.2f} GB")
    
    print(f"  Health Status:     {info.get('HealthStatus', 'N/A')}")
    print(f"  Operational:       {info.get('OperationalStatus', 'N/A')}")
    print("=" * 60)


def print_wmi_smart_info(info: Dict[str, Any]):
    """Print SMART info from WMI"""
    print("\n" + "=" * 60)
    print("RELIABILITY COUNTERS (via Windows Storage API)")
    print("=" * 60)
    
    temp = info.get('Temperature')
    if temp is not None:
        print(f"  Temperature:       {temp}°C")
    
    wear = info.get('Wear')
    if wear is not None:
        print(f"  Wear Level:        {wear}%")
        print(f"  Life Remaining:    {100 - wear}%")
    
    read_errors = info.get('ReadErrorsTotal')
    if read_errors is not None:
        print(f"  Read Errors:       {read_errors}")
    
    write_errors = info.get('WriteErrorsTotal')
    if write_errors is not None:
        print(f"  Write Errors:      {write_errors}")
    
    poh = info.get('PowerOnHours')
    if poh is not None:
        print(f"  Power On Hours:    {poh}")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="NVMe Admin Command Tool - Query NVMe SSD information via Windows DeviceIoControl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python nvme_tool.py --list              List available drives
  python nvme_tool.py --drive 0           Query drive 0 (all info)
  python nvme_tool.py --drive 0 --smart   Show only SMART data
  python nvme_tool.py --drive 0 --json    Output as JSON

Note: Requires Administrator privileges to access physical drives.
        """
    )
    
    parser.add_argument("--list", "-l", action="store_true", 
                        help="List available physical drives")
    parser.add_argument("--drive", "-d", type=int, default=0,
                        help="Physical drive number (default: 0)")
    parser.add_argument("--identify", "-i", action="store_true",
                        help="Show Identify Controller data")
    parser.add_argument("--smart", "-s", action="store_true",
                        help="Show SMART/Health data")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--raw", "-r", action="store_true",
                        help="Show raw hex dump of data")
    
    args = parser.parse_args()
    
    # Enable Windows error codes
    ctypes.windll.kernel32.SetLastError(0)
    
    if args.list:
        print("Scanning for physical drives...")
        drives = list_nvme_drives()
        if drives:
            print(f"\nFound {len(drives)} drive(s): {drives}")
            print("\nUse --drive N to query a specific drive")
        else:
            print("\nNo accessible drives found. Run as Administrator.")
        return
    
    # Default to showing all info if no specific option given
    show_all = not (args.identify or args.smart)
    
    print(f"\nNVMe Admin Command Tool")
    print(f"Target: PhysicalDrive{args.drive}")
    print("-" * 40)
    
    tool = NVMeTool(args.drive)
    
    if not tool.open():
        sys.exit(1)
    
    try:
        identify_data = None
        smart_data = None
        
        # Get basic device descriptor first
        desc = tool.get_device_descriptor()
        if desc and not args.json:
            print(f"\n[Device Descriptor]")
            print(f"  Vendor:   {desc.get('vendor', 'N/A')}")
            print(f"  Product:  {desc.get('product', 'N/A')}")
            print(f"  Bus Type: {desc.get('bus_type', 'N/A')} (17=NVMe)")
        
        # Query Identify data
        if show_all or args.identify:
            print("\n[Sending NVMe Identify Controller command...]")
            raw_identify = tool.send_nvme_identify()
            
            if raw_identify:
                if args.raw:
                    print(f"\nRaw Identify Data ({len(raw_identify)} bytes):")
                    for i in range(0, min(256, len(raw_identify)), 16):
                        hex_str = ' '.join(f'{b:02X}' for b in raw_identify[i:i+16])
                        print(f"  {i:04X}: {hex_str}")
                
                identify_data = tool.parse_identify_data(raw_identify)
                if identify_data and not args.json:
                    tool.print_identify_info(identify_data)
            else:
                print("[WARN] Could not retrieve Identify data via NVMe protocol")
                print("[INFO] Trying Windows Storage API fallback...")
                wmi_disk = get_disk_info_wmi(args.drive)
                if wmi_disk and not args.json:
                    print_wmi_disk_info(wmi_disk)
        
        # Query SMART data
        if show_all or args.smart:
            print("\n[Sending NVMe Get Log Page (SMART) command...]")
            raw_smart = tool.send_nvme_smart()
            
            if raw_smart:
                if args.raw:
                    print(f"\nRaw SMART Data ({len(raw_smart)} bytes):")
                    for i in range(0, min(256, len(raw_smart)), 16):
                        hex_str = ' '.join(f'{b:02X}' for b in raw_smart[i:i+16])
                        print(f"  {i:04X}: {hex_str}")
                
                smart_data = tool.parse_smart_data(raw_smart)
                if smart_data and not args.json:
                    tool.print_smart_info(smart_data)
            else:
                print("[WARN] Could not retrieve SMART data via NVMe protocol")
                print("[INFO] Trying Windows Storage API fallback...")
                wmi_smart = get_smart_info_wmi(args.drive)
                if wmi_smart and not args.json:
                    print_wmi_smart_info(wmi_smart)
        
        # JSON output
        if args.json:
            print(tool.export_json(identify_data, smart_data))
            
    finally:
        tool.close()


if __name__ == "__main__":
    main()
