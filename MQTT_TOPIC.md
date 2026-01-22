# MQTT Topics Documentation

This document describes all MQTT topics used by the HLK-LD2420 radar service.

## General Topic Structure

The service uses a configurable base topic via the `--mqtt-topic` parameter with the following variables:
- `$port`: Serial port name (e.g., `serial0`, `COM3`)  
- `$sn`: Radar module serial number
- `$version`: Module firmware version

**Default base topic:** `radar/$sn`

## Published Topics (sent by the service)

### 1. Service Status - `radar/{sn}/status`
**Type:** Retain = True  
**Frequency:** At startup and on status changes

```json
{
  "status": true,              // boolean - Serial connection status
  "version": "v1.6.1",  // string - Module firmware version
  "timestamp": "2025-11-18T10:30:00.123456", // string (ISO 8601)
  "port": "/dev/serial0",      // string - Serial port used
  "serial_number": "331861989698133498920968" // string - Module serial number
}
```

### 2. Simple Detection - `radar/{sn}/measurements/detection`
**Type:** Retain = True  
**Frequency:** Every received radar frame

```json
{
  "detected": true,            // boolean - Presence detected or not
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 3. Detection Distance - `radar/{sn}/measurements/distance`
**Type:** Retain = True  
**Frequency:** Every received radar frame

```json
{
  "distance_cm": 245,          // number - Distance in centimeters
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 4. Complete Measurements - `radar/{sn}/measurements`
**Type:** Retain = False  
**Frequency:** Every received radar frame

```json
{
  "gates": [                   // array - Measurements of 16 distance gates
    {
      "gate": 0,               // number (0-15) - Gate number
      "energy_db": 45.32,      // number - Energy in decibels
      "energy_raw": 34021      // number - Raw energy value
    },
    // ... 15 other gates
  ],
  "detection": true,           // boolean - Global detection status
  "distance_cm": 245,          // number - Distance in centimeters
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 5. Measurements by Gate - `radar/{sn}/measurements/gates`
**Type:** Retain = False  
**Frequency:** Every received radar frame

```json
[
  {
    "gate": 0,                 // number (0-15) - Gate number
    "energy_db": 45.32,        // number - Energy in decibels
    "energy_raw": 34021        // number - Raw energy value
  },
  // ... 15 other gates
]
```

### 6. Individual Gate Measurement - `radar/{sn}/measurements/gates/{0-15}`
**Type:** Retain = False  
**Frequency:** Every received radar frame

```json
{
  "energy_db": 45.32,          // number - Energy in decibels
  "energy_raw": 34021,         // number - Raw energy value
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 7. Parameters Summary - `radar/{sn}/parameters`
**Type:** Retain = True  
**Frequency:** At startup, after reading parameters

```json
{
  "total_parameters": 35,      // number - Total number of parameters
  "published_count": 35,       // number - Number of successfully published parameters
  "timestamp": "2025-11-18T10:30:00.123456", // string (ISO 8601)
  "status": "success"          // string - "success", "partial", or "error"
}
```

### 8. Distance and Delay Parameters - `radar/{sn}/parameters/{param_name}`
**Topics:**
- `radar/{sn}/parameters/min_detection_door`
- `radar/{sn}/parameters/max_detection_door` 
- `radar/{sn}/parameters/delay_time`

**Type:** Retain = True  
**Frequency:** At startup and on modifications

```json
{
  "name": "Minimum detection distance door", // string - Descriptive name
  "value": 2,                  // number (0-15 for gates, 0-65535 for delay)
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 9. Trigger Thresholds - `radar/{sn}/parameters/trigger_threshold/{0-15}`
**Type:** Retain = True  
**Frequency:** At startup and on modifications

```json
{
  "name": "Trigger threshold 5", // string - Name with index
  "value_raw": 34021,          // number (0-4294967295) - Raw value
  "value_db": 45.32,           // number|null - Value in dB (null if raw=0)
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 10. Maintain Thresholds - `radar/{sn}/parameters/maintain_threshold/{0-15}`
**Type:** Retain = True  
**Frequency:** At startup and on modifications

```json
{
  "name": "Maintain threshold 12",     // string - Name with index
  "value_raw": 28456,          // number (0-4294967295) - Raw value
  "value_db": 44.54,           // number|null - Value in dB (null if raw=0)
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

## Subscribed Topics (received by the service)

### 1. Module Reboot - `radar/{sn}/reboot`
**Payload:** Ignored (any content)  
**Action:** Completely reboots the radar module and reactivates debug mode

### 2. Modifying Distance/Delay Parameters
**Topics:**
- `radar/{sn}/parameters/set/min_detection_door`
- `radar/{sn}/parameters/set/max_detection_door`
- `radar/{sn}/parameters/set/delay_time`

**Payload for distances (0-15):**
```json
{
  "value": 5                   // number - New value (0-15 for gates)
}
```

**Payload for delay (0-65535):**
```json
{
  "value": 1000                // number - New value in milliseconds
}
```

### 3. Modifying Thresholds - `radar/{sn}/parameters/set/trigger_threshold/{0-15}`
### 4. Modifying Thresholds - `radar/{sn}/parameters/set/maintain_threshold/{0-15}`

**Payload option 1 (raw value):**
```json
{
  "value_raw": 34021           // number (0-4294967295) - Raw value
}
```

**Payload option 2 (dB value):**
```json
{
  "value_db": 45.32            // number - Value in decibels (automatically converted)
}
```

## Conversion Formulas

**Raw to dB:** `dB = 10 * log10(raw)`  
**dB to Raw:** `raw = 10^(dB/10)`

## Useful Wildcard Topics

- `radar/+/status`: Status of all modules
- `radar/+/measurements/detection`: Detections from all modules  
- `radar/+/parameters/trigger_threshold/+`: All trigger thresholds
- `radar/+/parameters/set/#`: All modification commands
