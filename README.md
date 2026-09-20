# NVMe admin command tool (Windows)

A small command-line tool that asks an NVMe SSD for two things: its Identify Controller
page (model, serial, firmware, vendor ID, capacity) and its SMART/health log page
(temperature, percentage used, spare, power cycles, power-on hours, media errors), then
prints them in readable form. It does that by opening `\\.\PhysicalDriveN` and issuing
`IOCTL_STORAGE_QUERY_PROPERTY` with a `STORAGE_PROTOCOL_SPECIFIC_DATA` request — the
Windows storage stack's NVMe passthrough. The same thing is written twice, once in Python
via `ctypes` and once in C++.

**Windows only.** Both implementations call Windows APIs directly (`ctypes.windll.kernel32`
in Python, `<windows.h>` and `<ntddscsi.h>` in C++). There is no Linux or macOS path. It
also needs an Administrator shell, because opening a physical drive handle otherwise fails
with error 5.

## What's here

- `src/nvme_tool.py` (~815 lines) — the main implementation. Declares the Windows storage
  structs with `ctypes`, sends the two commands, parses the returned buffers, derives a
  rough health verdict from `percentage_used`, and can emit JSON. Falls back to
  `Get-PhysicalDisk` / `Get-StorageReliabilityCounter` over PowerShell when the ioctl path
  returns nothing. `--list` probes PhysicalDrive0-15 for openable handles.
- `src/nvme_tool.cpp` (~435 lines) — a C++ version of the same two commands with the same
  flags, minus `--json`.
- `tests/test_nvme.py` — 22 `unittest` cases over the parsing logic, using
  `struct.pack_into` to build synthetic Identify and SMART buffers.
- `CMakeLists.txt` — C++17, MSVC `/W4 /O2` or GCC `-Wall -Wextra -O2`.
- `requirements.txt` — empty on purpose; the Python tool is standard library only.

## Running it

```bash
python src/nvme_tool.py --list          # openable physical drives
python src/nvme_tool.py --drive 0       # identify + SMART
python src/nvme_tool.py --drive 0 --smart
python src/nvme_tool.py --drive 0 --json > drive.json
python src/nvme_tool.py --drive 0 --raw # hex dump of the returned buffers
```

Build the C++ version with MSVC (`cl /EHsc /O2 src/nvme_tool.cpp`) or CMake, then
`nvme_tool.exe -d 0`. Note that `CMakeLists.txt` adds the executable unconditionally and
the source includes `windows.h`, so configuring it on Linux or macOS fails at compile time
rather than being skipped.

## Tests

```bash
python -m unittest discover -s tests
```

4 of the 22 tests (the health-assessment ones) are pure functions and pass anywhere. The
other 18 construct an `NVMeTool`, whose constructor touches `ctypes.windll`, so off Windows
they error out rather than fail — they need a Windows interpreter, though not real
hardware, since the buffers are synthetic.

## References

- NVMe Base Specification 1.4 — Identify Controller (5.15.2.1) and SMART/Health Information
  log page (5.14.1.2): <https://nvmexpress.org/specifications/>
- Microsoft, working with NVMe devices via `IOCTL_STORAGE_QUERY_PROPERTY`:
  <https://learn.microsoft.com/en-us/windows/win32/fileio/working-with-nvme-devices>
- `nvme-cli` — the Linux reference implementation these commands mirror:
  <https://github.com/linux-nvme/nvme-cli>
