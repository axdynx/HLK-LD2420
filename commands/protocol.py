import struct
import time
import math

def parse_debug_frame(buffer):
    """
    Parse a complete debug frame from the buffer
    Format: Header (4) + Length (2) + Data (35) + Footer (4) = 45 bytes total
    Returns parsed data or None if no complete frame is available
    """
    header = bytes.fromhex('F4 F3 F2 F1')
    footer = bytes.fromhex('F8 F7 F6 F5')
    
    # Find header position
    start = buffer.find(header)
    if start == -1:
        return None
    
    # Check if we have enough data for a complete frame (minimum)
    if len(buffer) < start + 4 + 2 + 35 + 4:  # header + length + data + footer
        return None
    
    # Read length field (2 bytes after header)
    length_bytes = buffer[start + 4:start + 6]
    length = struct.unpack('<H', length_bytes)[0]
    
    if length != 35:
        print(f"Debug: Incorrect length: {length}, expected: 35")
        return None
    
    # Extract data (35 bytes after length field)
    payload_start = start + 6
    payload = buffer[payload_start:payload_start + 35]
    
    # Verify footer
    footer_start = payload_start + 35
    if buffer[footer_start:footer_start + 4] != footer:
        print(f"Debug: Incorrect footer at position {footer_start}")
        return None
    
    try:
        # Decode data (original format)
        detection = payload[0]
        distance = struct.unpack('<H', payload[1:3])[0]
        
        # Decode the 16 energy values (32 bytes, 2 bytes each)
        energy_values = []
        energy_raw = []
        for i in range(16):
            offset = 3 + i * 2
            raw_value = struct.unpack('<H', payload[offset:offset + 2])[0]
            energy_raw.append(raw_value)
            if raw_value > 0:
                db_value = 10 * math.log10(raw_value)  # Convert to dB
            else:
                db_value = 0
            energy_values.append(db_value)
        
        return {
            'detection': bool(detection),
            'distance': distance,
            'energy_values': energy_values,
            'energy_raw': energy_raw
        }
    
    except (struct.error, ValueError, IndexError) as e:
        print(f"Debug: Parsing error: {e}")
        return None

def build_command(data_bytes: bytes) -> bytes:
    """
    Structure a command with header, length, data, footer.
    """
    header = bytes.fromhex('FD FC FB FA')
    footer = bytes.fromhex('04 03 02 01')
    length = len(data_bytes)
    length_bytes = length.to_bytes(2, byteorder='little')
    return header + length_bytes + data_bytes + footer

def build_open_command_mode(version_bytes: bytes = b'\x01\x00') -> bytes:
    """Build command to open command mode with specified version"""
    # FF 00 + version (2 bytes)
    return build_command(b'\xFF\x00' + version_bytes)

def build_structured_message(data_bytes: bytes) -> bytes:
    """Build a structured message with proper framing"""
    return build_command(data_bytes)

def to_hex_str(data):
    """Convert bytes to hexadecimal string representation"""
    return ' '.join(f'{b:02X}' for b in data)

def wait_for_ack(ser, timeout=2.0) -> bytes:
    """Wait for acknowledgment response from the serial device"""
    start = time.time()
    buffer = b''
    header = bytes.fromhex('FD FC FB FA')
    footer = bytes.fromhex('04 03 02 01')
    while time.time() - start < timeout:
        if ser.in_waiting:
            buffer += ser.read(ser.in_waiting)
            h = buffer.rfind(header)
            f = buffer.rfind(footer, h)
            if h != -1 and f != -1:
                return buffer[h:f+len(footer)]
            if len(buffer) > 1024:
                buffer = buffer[-1024:]
    return None

def send_command_sequence(ser, command_name: str, command_data: bytes, command_ack: bytes, version: int = 1):
    """
    Send command sequence: enable, command, end, waiting for ACK at each step.
    
    Args:
        ser: Serial connection object
        command_name: Human-readable name for logging
        command_data: Command data bytes to send
        command_ack: Expected acknowledgment bytes
        version: Protocol version (default: 1)
        
    Returns:
        Data payload from response if successful, False otherwise
    """
    is_reboot = command_data == build_command(bytes.fromhex('68 00'))

    version_bytes = version.to_bytes(2, byteorder='little')

    # Command sequence
    enable_cmd = build_open_command_mode(version_bytes)  # Open command mode with configurable version
    end_cmd = build_command(bytes.fromhex('FE 00'))  # Close command mode

    cmds = [enable_cmd, command_data, end_cmd]
    names = ['Open command mode', command_name, 'Close command mode']

    expected_acks = [
        build_structured_message(bytes.fromhex('FF 01 00 00 02 00 20 00')),
        command_ack,
        build_structured_message(bytes.fromhex('FE 01 00 00'))
    ]

    def extract_structured_message(data: bytes) -> bytes:
        """Extract structured message from response data"""
        header = bytes.fromhex('FD FC FB FA')
        footer = bytes.fromhex('04 03 02 01')
        start = data.rfind(header)
        end = data.rfind(footer, start)
        if start != -1 and end != -1:
            return data[start:end+len(footer)]
        else:
            print(f"extract_structured_message failed on data: {to_hex_str(data)}")
            return b''
    
    def remove_data(data: bytes) -> bytes:
        """Remove data payload from structured message for comparison"""
        header = bytes.fromhex('FD FC FB FA')
        footer = bytes.fromhex('04 03 02 01')
        start = data.rfind(header)
        end = data.rfind(footer, start)
        if start != -1 and end != -1:
            return data[:start+len(header)+4] + data[end:]
        return data

    def extract_data_if_applicable(resp: bytes):
        """Extract data payload from response if present"""
        header = bytes.fromhex('FD FC FB FA')
        footer = bytes.fromhex('04 03 02 01')
        start = resp.rfind(header)
        end = resp.rfind(footer, start)
        if start != -1 and end != -1:
            payload = resp[start+len(header)+2:end]
            if payload:
                try:
                    return payload
                except Exception:
                    return None
            else :
                return None

    data = None

    # Execute command sequence
    for name, cmd, expected_ack in zip(names, cmds, expected_acks):
        print(f"Sending [{name}]: {to_hex_str(cmd)}")
        i = 0
        resp = None
        while resp == None and i < 3:
            ser.write(cmd)
            ser.flush()
            if expected_ack is None:
                time.sleep(2)
                return True
            resp = wait_for_ack(ser)
            i += 1
        
        if resp is None:
            print(f"Error: No acknowledgment received for {name} after 3 attempts.")
            return False
        
        main_ack = extract_structured_message(resp)
        if main_ack == expected_ack or (name == command_name and remove_data(main_ack) == remove_data(expected_ack)):
            print(f"Acknowledgment received for [{name}]: {to_hex_str(main_ack)}")
        else:
            print(f"Error: Unexpected acknowledgment after {name}! Received: {to_hex_str(main_ack) if main_ack else to_hex_str(resp)}")
            return False
        if name == command_name:
            data = extract_data_if_applicable(resp)

    return data

def activate_debug_mode(ser):
    """Activate report/debug mode"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from commands.protocol import build_command, send_command_sequence
    cmd = build_command(bytes.fromhex('12 00 00 00 04 00 00 00'))
    ack = build_command(bytes.fromhex('12 01 00 00'))
    return send_command_sequence(ser, "activate debug mode", cmd, ack, version=1)

def deactivate_debug_mode(ser):
    """Deactivate report/debug mode"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from commands.protocol import build_command, send_command_sequence
    cmd = build_command(bytes.fromhex('12 00 00 00 00 00 00 00'))
    ack = build_command(bytes.fromhex('12 01 00 00'))
    return send_command_sequence(ser, "deactivate debug mode", cmd, ack, version=1)