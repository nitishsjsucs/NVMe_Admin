# NVMe Admin Command Tool

A cross-platform tool for sending NVMe admin commands via system APIs (Windows DeviceIoControl / Linux ioctl). Query SSD information, SMART/health data, and performance metrics directly from NVMe drives.

## Features

- **Identify Controller** - Query drive model, serial number, firmware, vendor ID, capacity
- **SMART/Health Info** - Temperature, wear level, power cycles, data written/read, error counts
- **Health Assessment** - Automated health scoring based on SMART attributes
- **JSON Export** - Machine-readable output for integration with monitoring systems
- **Raw Data Dump** - Hex dump of NVMe command responses for debugging

## Requirements

- **Windows 10/11** with Administrator privileges
- **Python 3.8+** (for Python version)
- **MSVC or MinGW** (for C++ version)
- NVMe SSD (SATA drives not supported)

## Quick Start

### Python Version

```bash
# List available drives
python src/nvme_tool.py --list

# Query drive 0 (all info)
python src/nvme_tool.py --drive 0

# Show only SMART data
python src/nvme_tool.py --drive 0 --smart

# Export as JSON
python src/nvme_tool.py --drive 0 --json > drive_info.json
```

### C++ Version

```bash
# Build with MSVC
cl /EHsc /O2 src/nvme_tool.cpp /Fe:nvme_tool.exe

# Build with MinGW
g++ -o nvme_tool.exe src/nvme_tool.cpp -static

# Run
nvme_tool.exe -d 0
```

## Usage

```
NVMe Admin Command Tool

Options:
  -l, --list          List available physical drives
  -d, --drive N       Physical drive number (default: 0)
  -i, --identify      Show Identify Controller data
  -s, --smart         Show SMART/Health data
  -j, --json          Output as JSON (Python only)
  -r, --raw           Show raw hex dump of data
  -h, --help          Show help message

Examples:
  nvme_tool.py --list              List available drives
  nvme_tool.py --drive 0           Query drive 0 (all info)
  nvme_tool.py --drive 0 --smart   Show only SMART data
  nvme_tool.py --drive 0 --json    Output as JSON
```

## Sample Output

```
NVMe Admin Command Tool
Target: PhysicalDrive0
----------------------------------------

[Device Descriptor]
  Vendor:   NVMe
  Product:  Samsung SSD 980 PRO
  Bus Type: 17 (17=NVMe)

============================================================
NVMe IDENTIFY CONTROLLER DATA
============================================================
  Model Number:        Samsung SSD 980 PRO 1TB
  Serial Number:       S5GXNF0R123456
  Firmware Revision:   5B2QGXA7
  Vendor ID:           0x144D
  Subsystem Vendor ID: 0x144D
  Controller ID:       5
  Number of Namespaces:1
  Total Capacity:      1000.20 GB
============================================================

============================================================
NVMe SMART/HEALTH INFORMATION
============================================================
  Critical Warning:    0x00 (No warnings)
  Temperature:         38°C (311 K)
  Available Spare:     100%
  Spare Threshold:     10%
  Percentage Used:     1%

  Data Read:           12,456.78 GB
  Data Written:        8,234.56 GB
  Host Read Commands:  245,678,901
  Host Write Commands: 123,456,789

  Power Cycles:        156
  Power On Hours:      2,345 hours
  Unsafe Shutdowns:    3
  Controller Busy:     45 minutes

  Media Errors:        0
  Error Log Entries:   0

------------------------------------------------------------
  Overall Health:      EXCELLENT (99% life remaining)
============================================================
```

## Technical Details

### Windows Implementation

The tool uses Windows Storage APIs to send NVMe commands:

1. **CreateFile** - Opens handle to `\\.\PhysicalDriveN`
2. **DeviceIoControl** with `IOCTL_STORAGE_QUERY_PROPERTY`
3. **STORAGE_PROTOCOL_SPECIFIC_DATA** structure for NVMe passthrough

### NVMe Commands Implemented

| Command | Opcode | Description |
|---------|--------|-------------|
| Identify Controller | 0x06 | Returns 4KB controller data structure |
| Get Log Page (SMART) | 0x02 | Returns 512B SMART/health information |

### Data Structures

- **Identify Controller** (NVMe Spec 1.4, Section 5.15.2.1)
  - Vendor ID, Serial Number, Model Number, Firmware Revision
  - Total NVM Capacity, Controller Capabilities

- **SMART/Health Log** (NVMe Spec 1.4, Section 5.14.1.2)
  - Critical Warning, Temperature, Available Spare
  - Data Units Read/Written, Power Cycles, Power On Hours

## Project Structure

```
nvme-tool/
├── src/
│   ├── nvme_tool.py      # Python implementation
│   └── nvme_tool.cpp     # C++ implementation
├── tests/
│   └── test_nvme.py      # Unit tests
├── README.md
├── requirements.txt
└── CMakeLists.txt
```

## Error Handling

| Error Code | Meaning | Solution |
|------------|---------|----------|
| 5 | Access Denied | Run as Administrator |
| 2 | File Not Found | Drive number doesn't exist |
| 87 | Invalid Parameter | Drive may not be NVMe |
| 1117 | Device Not Ready | Check drive connection |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License

## My Contributions

- **NVMe IOCTL Interface** — Implemented the low-level Windows IOCTL interface for sending NVMe admin commands (Identify Controller, Identify Namespace, Get Log Page) through the Windows storage stack.
- **SMART Data Parser** — Built the SMART/Health Information Log Page parser that extracts and displays critical SSD health metrics including temperature, wear leveling, data units read/written, and error counts.
- **Cross-Platform Architecture** — Designed the dual-implementation approach with both Python (ctypes) and C++ versions for maximum compatibility and performance.
- **Error Handling & Validation** — Developed comprehensive error handling for privilege escalation, device access, and NVMe command status code interpretation.

---

## Author

Nitish Chowdary - [GitHub](https://github.com/nitishsjsucs)

## References

- [NVMe Base Specification 1.4](https://nvmexpress.org/specifications/)
- [Windows Storage API Documentation](https://docs.microsoft.com/en-us/windows/win32/api/winioctl/)
- [NVMe CLI (Linux reference)](https://github.com/linux-nvme/nvme-cli)
