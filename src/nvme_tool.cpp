/**
 * NVMe Admin Command Tool (C++ Implementation)
 * Sends NVMe admin commands via Windows DeviceIoControl API
 * 
 * Author: Nitish Chowdary
 * 
 * Build: g++ -o nvme_tool.exe nvme_tool.cpp -static
 * Or:    cl /EHsc /O2 nvme_tool.cpp
 */

#include <windows.h>
#include <ntddscsi.h>
#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include <cstring>
#include <cstdint>

// NVMe Protocol Constants
#define NVME_PROTOCOL_TYPE 3

// Storage Property IDs
#define StorageDeviceProtocolSpecificProperty 50

// NVMe Data Types
#define NVMeDataTypeIdentify 1
#define NVMeDataTypeLogPage 2

// NVMe Log Page IDs
#define NVME_LOG_SMART_HEALTH 0x02

// Storage Protocol Specific Data structure
#pragma pack(push, 1)
struct STORAGE_PROTOCOL_SPECIFIC_DATA {
    DWORD ProtocolType;
    DWORD DataType;
    DWORD ProtocolDataRequestValue;
    DWORD ProtocolDataRequestSubValue;
    DWORD ProtocolDataOffset;
    DWORD ProtocolDataLength;
    DWORD FixedProtocolReturnData;
    DWORD ProtocolDataRequestSubValue2;
    DWORD ProtocolDataRequestSubValue3;
    DWORD ProtocolDataRequestSubValue4;
};

struct STORAGE_PROTOCOL_DATA_DESCRIPTOR {
    DWORD Version;
    DWORD Size;
    STORAGE_PROTOCOL_SPECIFIC_DATA ProtocolSpecificData;
};

struct STORAGE_PROPERTY_QUERY_PROTOCOL {
    DWORD PropertyId;
    DWORD QueryType;
    STORAGE_PROTOCOL_SPECIFIC_DATA ProtocolSpecific;
};

// NVMe Identify Controller Data Structure (partial)
struct NVMeIdentifyController {
    uint16_t VID;           // Vendor ID
    uint16_t SSVID;         // Subsystem Vendor ID
    char SN[20];            // Serial Number
    char MN[40];            // Model Number
    char FR[8];             // Firmware Revision
    uint8_t RAB;            // Recommended Arbitration Burst
    uint8_t IEEE[3];        // IEEE OUI Identifier
    uint8_t CMIC;           // Controller Multi-Path I/O
    uint8_t MDTS;           // Maximum Data Transfer Size
    uint16_t CNTLID;        // Controller ID
    uint32_t VER;           // Version
    // ... more fields follow in full 4096 byte structure
};

// NVMe SMART/Health Information Log
struct NVMeSMARTLog {
    uint8_t CriticalWarning;
    uint16_t Temperature;
    uint8_t AvailableSpare;
    uint8_t AvailableSpareThreshold;
    uint8_t PercentageUsed;
    uint8_t Reserved1[26];
    uint64_t DataUnitsReadLo;
    uint64_t DataUnitsReadHi;
    uint64_t DataUnitsWrittenLo;
    uint64_t DataUnitsWrittenHi;
    uint64_t HostReadCommandsLo;
    uint64_t HostReadCommandsHi;
    uint64_t HostWriteCommandsLo;
    uint64_t HostWriteCommandsHi;
    uint64_t ControllerBusyTimeLo;
    uint64_t ControllerBusyTimeHi;
    uint64_t PowerCyclesLo;
    uint64_t PowerCyclesHi;
    uint64_t PowerOnHoursLo;
    uint64_t PowerOnHoursHi;
    uint64_t UnsafeShutdownsLo;
    uint64_t UnsafeShutdownsHi;
    uint64_t MediaErrorsLo;
    uint64_t MediaErrorsHi;
    uint64_t ErrorLogEntriesLo;
    uint64_t ErrorLogEntriesHi;
    // ... more fields follow in full 512 byte structure
};
#pragma pack(pop)

class NVMeTool {
private:
    HANDLE hDevice;
    int driveNumber;
    std::string drivePath;

public:
    NVMeTool(int drive) : driveNumber(drive), hDevice(INVALID_HANDLE_VALUE) {
        drivePath = "\\\\.\\PhysicalDrive" + std::to_string(drive);
    }

    ~NVMeTool() {
        close();
    }

    bool open() {
        hDevice = CreateFileA(
            drivePath.c_str(),
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            NULL,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            NULL
        );

        if (hDevice == INVALID_HANDLE_VALUE) {
            DWORD error = GetLastError();
            std::cerr << "[ERROR] Failed to open " << drivePath 
                      << ": Error code " << error << std::endl;
            if (error == 5) {
                std::cerr << "[INFO] Access denied. Run as Administrator." << std::endl;
            }
            return false;
        }

        std::cout << "[OK] Opened handle to " << drivePath << std::endl;
        return true;
    }

    void close() {
        if (hDevice != INVALID_HANDLE_VALUE) {
            CloseHandle(hDevice);
            hDevice = INVALID_HANDLE_VALUE;
            std::cout << "[OK] Handle closed" << std::endl;
        }
    }

    bool sendIdentify(std::vector<uint8_t>& outData) {
        const DWORD bufferSize = 4096 + sizeof(STORAGE_PROPERTY_QUERY_PROTOCOL);
        std::vector<uint8_t> buffer(bufferSize, 0);

        auto* query = reinterpret_cast<STORAGE_PROPERTY_QUERY_PROTOCOL*>(buffer.data());
        query->PropertyId = StorageDeviceProtocolSpecificProperty;
        query->QueryType = 0; // PropertyStandardQuery

        query->ProtocolSpecific.ProtocolType = NVME_PROTOCOL_TYPE;
        query->ProtocolSpecific.DataType = NVMeDataTypeIdentify;
        query->ProtocolSpecific.ProtocolDataRequestValue = 1; // CNS = 1 for Controller
        query->ProtocolSpecific.ProtocolDataRequestSubValue = 0;
        query->ProtocolSpecific.ProtocolDataOffset = sizeof(STORAGE_PROTOCOL_DATA_DESCRIPTOR);
        query->ProtocolSpecific.ProtocolDataLength = 4096;

        DWORD bytesReturned = 0;
        BOOL success = DeviceIoControl(
            hDevice,
            IOCTL_STORAGE_QUERY_PROPERTY,
            buffer.data(),
            bufferSize,
            buffer.data(),
            bufferSize,
            &bytesReturned,
            NULL
        );

        if (!success) {
            DWORD error = GetLastError();
            std::cerr << "[ERROR] Identify command failed: Error code " << error << std::endl;
            return false;
        }

        // Copy identify data (skip header)
        size_t dataOffset = sizeof(STORAGE_PROTOCOL_DATA_DESCRIPTOR);
        if (bytesReturned > dataOffset) {
            outData.assign(buffer.begin() + dataOffset, buffer.begin() + bytesReturned);
            return true;
        }

        return false;
    }

    bool sendSMART(std::vector<uint8_t>& outData) {
        const DWORD bufferSize = 512 + sizeof(STORAGE_PROPERTY_QUERY_PROTOCOL);
        std::vector<uint8_t> buffer(bufferSize, 0);

        auto* query = reinterpret_cast<STORAGE_PROPERTY_QUERY_PROTOCOL*>(buffer.data());
        query->PropertyId = StorageDeviceProtocolSpecificProperty;
        query->QueryType = 0;

        query->ProtocolSpecific.ProtocolType = NVME_PROTOCOL_TYPE;
        query->ProtocolSpecific.DataType = NVMeDataTypeLogPage;
        query->ProtocolSpecific.ProtocolDataRequestValue = NVME_LOG_SMART_HEALTH;
        query->ProtocolSpecific.ProtocolDataRequestSubValue = 0;
        query->ProtocolSpecific.ProtocolDataOffset = sizeof(STORAGE_PROTOCOL_DATA_DESCRIPTOR);
        query->ProtocolSpecific.ProtocolDataLength = 512;

        DWORD bytesReturned = 0;
        BOOL success = DeviceIoControl(
            hDevice,
            IOCTL_STORAGE_QUERY_PROPERTY,
            buffer.data(),
            bufferSize,
            buffer.data(),
            bufferSize,
            &bytesReturned,
            NULL
        );

        if (!success) {
            DWORD error = GetLastError();
            std::cerr << "[ERROR] SMART command failed: Error code " << error << std::endl;
            return false;
        }

        size_t dataOffset = sizeof(STORAGE_PROTOCOL_DATA_DESCRIPTOR);
        if (bytesReturned > dataOffset) {
            outData.assign(buffer.begin() + dataOffset, buffer.begin() + bytesReturned);
            return true;
        }

        return false;
    }

    void printIdentify(const std::vector<uint8_t>& data) {
        if (data.size() < 72) {
            std::cerr << "[WARN] Identify data too short" << std::endl;
            return;
        }

        auto* id = reinterpret_cast<const NVMeIdentifyController*>(data.data());

        // Extract strings (need to copy and null-terminate)
        char serial[21] = {0};
        char model[41] = {0};
        char firmware[9] = {0};
        
        memcpy(serial, id->SN, 20);
        memcpy(model, id->MN, 40);
        memcpy(firmware, id->FR, 8);

        // Trim trailing spaces
        for (int i = 19; i >= 0 && serial[i] == ' '; i--) serial[i] = 0;
        for (int i = 39; i >= 0 && model[i] == ' '; i--) model[i] = 0;
        for (int i = 7; i >= 0 && firmware[i] == ' '; i--) firmware[i] = 0;

        std::cout << "\n" << std::string(60, '=') << std::endl;
        std::cout << "NVMe IDENTIFY CONTROLLER DATA" << std::endl;
        std::cout << std::string(60, '=') << std::endl;
        std::cout << "  Model Number:        " << model << std::endl;
        std::cout << "  Serial Number:       " << serial << std::endl;
        std::cout << "  Firmware Revision:   " << firmware << std::endl;
        std::cout << "  Vendor ID:           0x" << std::hex << std::setw(4) 
                  << std::setfill('0') << id->VID << std::dec << std::endl;
        std::cout << "  Subsystem Vendor ID: 0x" << std::hex << std::setw(4) 
                  << std::setfill('0') << id->SSVID << std::dec << std::endl;
        std::cout << "  Controller ID:       " << id->CNTLID << std::endl;
        std::cout << std::string(60, '=') << std::endl;
    }

    void printSMART(const std::vector<uint8_t>& data) {
        if (data.size() < sizeof(NVMeSMARTLog)) {
            std::cerr << "[WARN] SMART data too short" << std::endl;
            return;
        }

        auto* smart = reinterpret_cast<const NVMeSMARTLog*>(data.data());

        int tempC = smart->Temperature - 273;
        double dataReadGB = (static_cast<double>(smart->DataUnitsReadLo) * 512 * 1000) / (1024.0 * 1024.0 * 1024.0);
        double dataWrittenGB = (static_cast<double>(smart->DataUnitsWrittenLo) * 512 * 1000) / (1024.0 * 1024.0 * 1024.0);

        std::cout << "\n" << std::string(60, '=') << std::endl;
        std::cout << "NVMe SMART/HEALTH INFORMATION" << std::endl;
        std::cout << std::string(60, '=') << std::endl;

        // Critical Warning
        std::cout << "  Critical Warning:    0x" << std::hex << std::setw(2) 
                  << std::setfill('0') << (int)smart->CriticalWarning << std::dec;
        if (smart->CriticalWarning == 0) {
            std::cout << " (No warnings)" << std::endl;
        } else {
            std::cout << " (WARNING PRESENT)" << std::endl;
        }

        std::cout << "  Temperature:         " << tempC << "°C" << std::endl;
        std::cout << "  Available Spare:     " << (int)smart->AvailableSpare << "%" << std::endl;
        std::cout << "  Spare Threshold:     " << (int)smart->AvailableSpareThreshold << "%" << std::endl;
        std::cout << "  Percentage Used:     " << (int)smart->PercentageUsed << "%" << std::endl;

        std::cout << std::fixed << std::setprecision(2);
        std::cout << "\n  Data Read:           " << dataReadGB << " GB" << std::endl;
        std::cout << "  Data Written:        " << dataWrittenGB << " GB" << std::endl;
        std::cout << "  Host Read Commands:  " << smart->HostReadCommandsLo << std::endl;
        std::cout << "  Host Write Commands: " << smart->HostWriteCommandsLo << std::endl;

        std::cout << "\n  Power Cycles:        " << smart->PowerCyclesLo << std::endl;
        std::cout << "  Power On Hours:      " << smart->PowerOnHoursLo << " hours" << std::endl;
        std::cout << "  Unsafe Shutdowns:    " << smart->UnsafeShutdownsLo << std::endl;

        std::cout << "\n  Media Errors:        " << smart->MediaErrorsLo << std::endl;
        std::cout << "  Error Log Entries:   " << smart->ErrorLogEntriesLo << std::endl;

        // Health assessment
        std::cout << "\n" << std::string(60, '-') << std::endl;
        int healthScore = 100 - smart->PercentageUsed;
        std::string status;
        if (healthScore >= 80) status = "EXCELLENT";
        else if (healthScore >= 50) status = "GOOD";
        else if (healthScore >= 20) status = "FAIR";
        else status = "POOR";

        std::cout << "  Overall Health:      " << status << " (" << healthScore << "% life remaining)" << std::endl;
        std::cout << std::string(60, '=') << std::endl;
    }

    void printHexDump(const std::vector<uint8_t>& data, size_t maxBytes = 256) {
        size_t len = std::min(data.size(), maxBytes);
        std::cout << "\nHex Dump (" << data.size() << " bytes, showing " << len << "):" << std::endl;

        for (size_t i = 0; i < len; i += 16) {
            std::cout << "  " << std::hex << std::setw(4) << std::setfill('0') << i << ": ";
            for (size_t j = 0; j < 16 && (i + j) < len; j++) {
                std::cout << std::hex << std::setw(2) << std::setfill('0') 
                          << (int)data[i + j] << " ";
            }
            std::cout << std::dec << std::endl;
        }
    }
};

void printUsage(const char* program) {
    std::cout << "NVMe Admin Command Tool (C++)\n\n";
    std::cout << "Usage: " << program << " [options]\n\n";
    std::cout << "Options:\n";
    std::cout << "  -d, --drive N     Physical drive number (default: 0)\n";
    std::cout << "  -i, --identify    Show Identify Controller data\n";
    std::cout << "  -s, --smart       Show SMART/Health data\n";
    std::cout << "  -r, --raw         Show raw hex dump\n";
    std::cout << "  -h, --help        Show this help message\n\n";
    std::cout << "Examples:\n";
    std::cout << "  " << program << " -d 0              Query drive 0 (all info)\n";
    std::cout << "  " << program << " -d 1 -s          Show SMART data for drive 1\n";
    std::cout << "  " << program << " -d 0 -i -r      Show Identify with hex dump\n\n";
    std::cout << "Note: Requires Administrator privileges.\n";
}

int main(int argc, char* argv[]) {
    int driveNumber = 0;
    bool showIdentify = false;
    bool showSMART = false;
    bool showRaw = false;

    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        
        if (arg == "-h" || arg == "--help") {
            printUsage(argv[0]);
            return 0;
        }
        else if (arg == "-d" || arg == "--drive") {
            if (i + 1 < argc) {
                driveNumber = std::stoi(argv[++i]);
            }
        }
        else if (arg == "-i" || arg == "--identify") {
            showIdentify = true;
        }
        else if (arg == "-s" || arg == "--smart") {
            showSMART = true;
        }
        else if (arg == "-r" || arg == "--raw") {
            showRaw = true;
        }
    }

    // Default to showing all if nothing specified
    if (!showIdentify && !showSMART) {
        showIdentify = true;
        showSMART = true;
    }

    std::cout << "NVMe Admin Command Tool (C++)\n";
    std::cout << "Target: PhysicalDrive" << driveNumber << "\n";
    std::cout << std::string(40, '-') << std::endl;

    NVMeTool tool(driveNumber);

    if (!tool.open()) {
        return 1;
    }

    std::vector<uint8_t> data;

    if (showIdentify) {
        std::cout << "\n[Sending NVMe Identify Controller command...]\n";
        if (tool.sendIdentify(data)) {
            if (showRaw) {
                tool.printHexDump(data);
            }
            tool.printIdentify(data);
        } else {
            std::cout << "[WARN] Could not retrieve Identify data\n";
        }
    }

    if (showSMART) {
        std::cout << "\n[Sending NVMe Get Log Page (SMART) command...]\n";
        if (tool.sendSMART(data)) {
            if (showRaw) {
                tool.printHexDump(data);
            }
            tool.printSMART(data);
        } else {
            std::cout << "[WARN] Could not retrieve SMART data\n";
        }
    }

    return 0;
}
