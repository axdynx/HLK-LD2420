#!/usr/bin/env python3
"""
MQTT Service for Radar Sensor
Connects the sensor in debug mode and publishes data to MQTT
Usage: python3 mqtt_service.py <serial_port>
"""

import sys
import time
import json
from datetime import datetime
sys.path.append('/opt/radar_service')  # Adjust according to installation
import paho.mqtt.client as mqtt
import serial
import sys
import os
from commands.protocol import *
import math

class RadarMQTTService:
    """Main service class for managing radar sensor communication via MQTT"""
    
    def __init__(self, serial_port, baudrate=115200, mqtt_broker="localhost", mqtt_port=1883, mqtt_username=None, mqtt_password=None, mqtt_topic="radar/$sn", restart_interval=30, mqtt_secure=False):
        """
        Initialize the radar MQTT service
        
        Args:
            serial_port: Serial port path (e.g., /dev/ttyUSB0)
            baudrate: Serial communication baudrate (default: 115200)
            mqtt_broker: MQTT broker address (default: localhost)
            mqtt_port: MQTT broker port (default: 1883)
            mqtt_username: MQTT authentication username (optional)
            mqtt_password: MQTT authentication password (optional)
            mqtt_topic: Base MQTT topic pattern (default: radar/$sn)
            restart_interval: Auto-restart interval in seconds (default: 30)
            mqtt_secure: Enable MQTT over TLS (default: False)
        """
        # Store configuration parameters
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.restart_interval = restart_interval  # Restart interval in seconds
        self.running = False
        self.ser = None
        self.mqtt_client = None
        self.version = "unknown"
        self.sn = "unknown"
        self.port_name = serial_port.replace('/dev/', '').replace('\\', '_').replace(':', '_')
        self.mqtt_secure = mqtt_secure
        
        # Setup serial connection
        if not self.setup_serial():
            print("Serial connection failed")
        self.get_version()
        self.get_sn()

        # Build MQTT topic structure with variable substitution
        self.topic = mqtt_topic.replace("$port", self.port_name).replace("$sn", self.sn).replace("$version", self.version)
        print(f"Using base MQTT topic: {self.topic}")
        self.topic_measurements = f"{self.topic}/measurements"
        self.topic_detection = f"{self.topic_measurements}/detection"
        self.topic_distance = f"{self.topic_measurements}/distance"
        self.topic_gates = f"{self.topic_measurements}/gates"
        self.topic_status = f"{self.topic}/status"
        self.topic_parameters = f"{self.topic}/parameters"
        
        # Setup MQTT connection
        if not self.setup_mqtt():
            print("MQTT connection failed")
        
    def setup_mqtt(self):
        """Configure MQTT connection and set up callbacks"""
        self.mqtt_client = mqtt.Client()

        # Enable TLS for secure connections if requested
        if (self.mqtt_secure):
            self.mqtt_client.tls_set()
        
        def on_mqtt_connect(client, userdata, connect_flags, reason_code):
            """MQTT connection callback"""
            if reason_code == 0:
                print(f"Connected to MQTT broker {self.mqtt_broker}:{self.mqtt_port}")
                # Publish startup status
                self.mqtt_client.publish(self.topic_status, json.dumps({
                    "status": self.ser is not None and self.ser.is_open,
                    "version": self.version,
                    "timestamp": datetime.now().isoformat(),
                    "port": self.serial_port,
                    "serial_number": self.sn
                }), retain=True)
            else:
                print(f"MQTT connection failed, code: {reason_code}")
    
        def on_mqtt_disconnect(client, userdata, reason_code):
            """MQTT disconnection callback"""
            print(f"Disconnected from MQTT broker, code: {reason_code}")
            
        def on_mqtt_message_reboot(client, userdata, msg):
            """Handle reboot command received via MQTT"""
            self.restart_debug_mode()
            self.on_serial_updated()

        def on_mqtt_message_parameters_set(client, userdata, msg): 
            """Handle parameter update messages received via MQTT"""
            print(f"Message received on {msg.topic}: {msg.payload.decode()}")
            topic = msg.topic.split('/')
            set_param_index = topic.index("set") if "set" in topic else -1
            
            # Parse parameter key from topic
            if set_param_index != -1 and len(topic) > set_param_index + 1:
                param_key = topic[set_param_index + 1]
                data = json.loads(msg.payload.decode('utf-8'))
                
                # Handle parameters with simple integer values
                if (data is not None and "value" in data and data['value'] is not None):
                    value = data['value']
                    
                    # Minimum detection door (gate)
                    if (param_key == "min_detection_door"):
                        print(f"Changing min_detection_door => {value}")
                        if 0 <= value <= 15:
                            if (self.set_parameter("Minimum detection distance door", b'\x00\x00', value.to_bytes(4, 'little'))) :
                                new_value = self.get_parameter("Minimum detection distance door", b'\x00\x00')
                                if (new_value is not None) :
                                    self.publish_parameter("min_detection_door", new_value)
                    # Maximum detection door (gate)
                    elif (param_key == "max_detection_door"):
                        print(f"Changing max_detection_door => {value}")
                        if 0 <= value <= 15:
                            if (self.set_parameter("Maximum detection distance door", b'\x01\x00', value.to_bytes(4, 'little'))) :
                                new_value = self.get_parameter("Maximum detection distance door", b'\x01\x00')
                                if (new_value is not None) :
                                    self.publish_parameter("max_detection_door", new_value)
                    
                    # Delay time
                    elif (param_key == "delay_time"):
                        print(f"Changing delay_time => {value}")
                        if 0 <= value <= 65535:
                            if (self.set_parameter("Delay", b'\x04\x00', value.to_bytes(4, 'little'))):
                                new_value = self.get_parameter("Delay", b'\x04\x00')
                                if (new_value is not None):
                                    self.publish_parameter("delay_time", new_value)
                # Handle parameters with dB or raw energy values
                elif (data is not None and ("value_db" in data and data['value_db'] is not None) or ("value_raw" in data and data['value_raw'] is not None)):
                    value_raw = 0
                    
                    # Convert from dB to raw value if needed
                    if ("value_db" in data and data['value_db'] is not None):
                        value_db = data['value_db']
                        value_raw = int(round(10 ** (value_db / 10)))
                    elif ("value_raw" in data and data['value_raw'] is not None):
                        value_raw = data['value_raw']
                    
                    # Trigger threshold for specific gate
                    if (param_key.startswith("trigger_threshold")):
                        print(f"Changing trigger_threshold => {value_raw}")
                        index_str = topic[set_param_index + 2]
                        try:
                            index = int(index_str)
                            if 0 <= index <= 15 and 0 <= value_raw <= (10 ** (232 / 10)):
                                if (self.set_parameter(f"Trigger threshold {index}", (index+0x10).to_bytes(1, 'little') + b'\x00', value_raw.to_bytes(4, 'little'))):
                                    new_value = self.get_parameter(f"Trigger threshold {index}", (index+0x10).to_bytes(1, 'little') + b'\x00', threshold_index=True)
                                    if (new_value is not None):
                                        self.publish_parameter(f"trigger_threshold/{index}", new_value)
                        except ValueError:
                            print(f"Invalid index for trigger_threshold: {index_str}")
                    
                    # Maintain threshold for specific gate
                    elif (param_key.startswith("maintain_threshold")):
                        print(f"Changing maintain_threshold => {value_raw}")
                        index_str = topic[set_param_index + 2]
                        try:
                            index = int(index_str)
                            if 0 <= index <= 15 and 0 <= value_raw <= (10 ** (232 / 10)):
                                if (self.set_parameter(f"Maintain threshold {index}", (index+0x20).to_bytes(1, 'little') + b'\x00', value_raw.to_bytes(4, 'little'))):
                                    new_value = self.get_parameter(f"Maintain threshold {index}", (index+0x20).to_bytes(1, 'little') + b'\x00', threshold_index=True)
                                    if (new_value is not None):
                                        self.publish_parameter(f"maintain_threshold/{index}", new_value)
                        except ValueError:
                            print(f"Invalid index for maintain_threshold: {index_str}")
                else :
                    print("Invalid payload for parameter change")
                
        # Set MQTT callback handlers
        self.mqtt_client.on_connect = on_mqtt_connect
        self.mqtt_client.on_disconnect = on_mqtt_disconnect
            
        # Configure authentication if provided
        if self.mqtt_username and self.mqtt_password:
            print(f"Configuring MQTT authentication for user: {self.mqtt_username}")
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            
        try:
            # Connect to MQTT broker and subscribe to command topics
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.message_callback_add(f"{self.topic_parameters}/set/#", on_mqtt_message_parameters_set)
            self.mqtt_client.subscribe(f"{self.topic_parameters}/set/#")
            self.mqtt_client.message_callback_add(f"{self.topic}/reboot", on_mqtt_message_reboot)
            self.mqtt_client.subscribe(f"{self.topic}/reboot")
            self.mqtt_client.loop_start()
            return True
        except Exception as e:
            print(f"MQTT connection error: {e}")
            return False

    def setup_serial(self):
        """Configure serial connection to the radar module"""
        try:
            self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=1)
            print(f"Connected to serial port {self.serial_port}")
            return True
        except Exception as e:
            print(f"Serial connection error: {e}")
            return False
        
    def on_serial_updated(self):
        """Publish updated serial connection status to MQTT"""
        self.mqtt_client.publish(self.topic_status, json.dumps({
            "status": self.ser is not None and self.ser.is_open,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "port": self.serial_port,
            "serial_number": self.sn
        }), retain=True)
    
    def get_version(self):
        """Read and return the firmware version from the radar module"""
        if (self.version is not None and self.version != "unknown"):
            return self.version
        else:
            cmd = build_command(bytes.fromhex('00 00'))
            ack = build_command(bytes.fromhex('00 01 00 00 00 00 00 00 00 00 00 00'))
            data = send_command_sequence(self.ser, "read version number", cmd, ack, version=1)
            if data and data[2:4] == b'\x00\x00':
                try:
                    version = data[6:].decode(errors='ignore').strip()
                    if version:
                        self.version = version
                    else:
                        self.version = "unknown"
                except Exception:
                    self.version = "unknown"
            return self.version

    def get_sn(self):
        """Read and return the serial number from the radar module"""
        if (self.sn is not None and self.sn != "unknown"):
            return self.sn
        else:
            cmd = build_command(bytes.fromhex('11 00'))
            ack = build_command(bytes.fromhex('11 01 00 00 00 00 00 00 00 00 00 00 00 00'))
            data = send_command_sequence(self.ser, "read serial number", cmd, ack, version=1)
            if data and data[2:4] == b'\x00\x00':
                try:
                    sn = int.from_bytes(data[4:], 'little')
                    if sn:
                        self.sn = str(sn)
                    else:
                        self.sn = "unknown"
                except Exception:
                    self.sn = "unknown"
            return self.sn

    def get_parameter(self, param_name, param_id, threshold_index=False):
        """
        Read a parameter value from the radar module
        
        Args:
            param_name: Human-readable parameter name for logging
            param_id: Binary parameter identifier code
            threshold_index: True if parameter is a threshold (returns dB and raw values)
            
        Returns:
            Dictionary with parameter data or None if read failed
        """
        try:
            timestamp = datetime.now().isoformat()
            
            # Parameter read command (08 00 + parameter code + 4 empty bytes)
            read_cmd = build_command(bytes.fromhex('08 00') + param_id + b'\x00\x00\x00\x00')
            
            # Expected ACK pattern: header + length + 08 01 + status (00 00 for OK) + data (12 bytes) + footer
            ack_pattern = build_command(bytes.fromhex('08 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00'))
                    
            # Send command and retrieve response
            response = send_command_sequence(self.ser, f"read {param_name}", read_cmd, ack_pattern, version=1)
                    
            if response and len(response) >= 14:
                # Check status (bytes 2-3, must be 00 00 for OK)
                status = int.from_bytes(response[2:4], byteorder='little')
                if status == 0:
                    # Extract raw value (first 4 bytes of the 12 bytes of data)
                    value_raw = int.from_bytes(response[4:8], byteorder='little')
                            
                    # For thresholds (trigger/maintain threshold), also calculate dB value
                    if threshold_index:
                        if value_raw > 0:
                            value_db = round(10 * math.log10(value_raw), 2)
                        else:
                            value_db = None  # Cannot calculate log of 0
                                
                        param_data = {
                            "name": param_name,
                            "value_raw": value_raw,
                            "value_db": value_db,
                            "timestamp": timestamp
                        }
                        print(f"  {param_name}: {value_raw} (raw) / {value_db} dB")
                    else:
                        # For other parameters (distances, delay), just the raw value
                        param_data = {
                            "name": param_name,
                            "value": value_raw,
                            "timestamp": timestamp
                        }
                        print(f"  {param_name}: {value_raw}")
                            
                    return param_data
                else:
                    print(f"  {param_name}: Error status {status}")
                    return None
            elif response:
                print(f"  {param_name}: Response too short ({len(response)} bytes)")
                return None
            else:
                print(f"  {param_name}: No response")
                return None

        except Exception as e:
            print(f"  Error reading {param_name}: {e}")

    def set_parameter(self, param_name, param_id, param_value):
        """
        Write a parameter value to the radar module
        
        Args:
            param_name: Human-readable parameter name for logging
            param_id: Binary parameter identifier code
            param_value: New parameter value as bytes
            
        Returns:
            True if parameter was set successfully, False otherwise
        """
        cmd = build_command(bytes.fromhex('07 00') + param_id + param_value)
        ack = build_command(bytes.fromhex('07 01 00 00'))
        data = send_command_sequence(self.ser, f"set {param_name}", cmd, ack, version=1)
        if data and len(data) >= 4:
            # Check status (bytes 2-3, must be 00 00 for OK)
            status = int.from_bytes(data[2:4], 'little')
            if status == 0:
                print(f"Parameter {param_name} set successfully")
                return True
            else :
                print(f"Error setting parameter {param_name} (status: {status})")
                return False
        else:
            print(f"No response or invalid response for setting parameter {param_name}")
            return False

    def reboot_module(self):
        """Reboot the radar module (reboot command)"""
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            print("Rebooting radar module at startup...")
            cmd = build_command(bytes.fromhex('68 00'))
            
            # Send reboot command (no ACK expected)
            send_command_sequence(self.ser, "Reboot module", cmd, None, version=1)
            
            # Wait for module to complete reboot
            print("Waiting for module reboot (8 seconds)...")
            time.sleep(8)
            print("Module rebooted")
            
            # Read and publish parameters after reboot
            print("Reading module parameters...")
            if self.read_and_publish_parameters():
                print("Parameters read and published successfully")
            else:
                print("Failed to read parameters")
            
            return True
            
        except Exception as e:
            print(f"Error rebooting module at startup: {e}")
            return False

    def publish_parameter(self, param_key, param_data):
        """Publish a specific parameter to MQTT"""
        try:
            topic = f"{self.topic_parameters}/{param_key}"
                        
            # Payload is directly param_data (which already contains name, values, timestamp)
            self.mqtt_client.publish(topic, json.dumps(param_data), retain=True)
                        
            # Display adapted to parameter type
            if "value_raw" in param_data:  # Thresholds with raw and dB
                print(f"  → {param_data['name']}: {param_data['value_raw']} (raw) / {param_data['value_db']} dB published to {topic}")
            else:  # Other parameters
                print(f"  → {param_data['name']}: {param_data['value']} published to {topic}")
        except Exception as e:
            print(f"  Error publishing {param_key}: {e}")

    def read_and_publish_parameters(self):
        """Read all module parameters and publish them to MQTT"""
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            print("Reading module parameters...")
            
            # Parameter definitions (same structure as command_mode.py)
            param_list = [
                ("min_detection_door", "Minimum detection distance door", b'\x00\x00'),
                ("max_detection_door", "Maximum detection distance door", b'\x01\x00'),
                ("delay_time", "Delay", b'\x04\x00'),
            ]
            
            # Indexed parameters (thresholds)
            trigger_thresholds = [(f"trigger_threshold/{i}", f"Trigger threshold {i}", (i+0x10).to_bytes(1, 'little') + b'\x00') for i in range(16)]
            maintain_thresholds = [(f"maintain_threshold/{i}", f"Maintain threshold {i}", (i+0x20).to_bytes(1, 'little') + b'\x00') for i in range(16)]
            
            all_params = param_list + trigger_thresholds + maintain_thresholds
            
            parameters = {}
            timestamp = datetime.now().isoformat()
            
            for param_key, param_name, param_code in all_params:
                value = self.get_parameter(param_name, param_code, threshold_index=('threshold' in param_key))
                    
                if value is not None:
                    parameters[param_key] = value
                else :
                    print(f"  Failed to read parameter {param_name}")
                # Small pause between reads
                time.sleep(0.1)
            
            # Publish each parameter to its own MQTT topic with retain
            if parameters:
                published_count = 0
                for param_key, param_data in parameters.items():
                    published_count += 1
                    self.publish_parameter(param_key, param_data)
                
                # Also publish a global summary
                summary_payload = {
                    "total_parameters": len(parameters),
                    "published_count": published_count,
                    "timestamp": timestamp,
                    "status": "success" if published_count == len(parameters) else "partial"
                }
                self.mqtt_client.publish(self.topic_parameters, json.dumps(summary_payload), retain=True)
                print(f"Parameters published to MQTT: {published_count}/{len(parameters)} parameters")
            else:
                # Publish error status
                error_payload = {
                    "total_parameters": 0,
                    "published_count": 0,
                    "timestamp": timestamp,
                    "status": "error",
                    "message": "No parameter read successfully"
                }
                self.mqtt_client.publish(self.topic_parameters, json.dumps(error_payload), retain=True)
                print("No parameter read successfully")
                
            return True
            
        except Exception as e:
            print(f"Error reading parameters: {e}")
            return False

    def activate_radar_debug(self):
        """Activate radar debug mode"""
        try:
            print("Activating radar debug mode...")
            result = activate_debug_mode(self.ser)
            if result:
                print("Debug mode activated")
                return True
            else:
                print("Failed to activate debug mode")
                return False
        except Exception as e:
            print(f"Error activating debug mode: {e}")
            return False
    
    def restart_debug_mode(self):
        """Restart the complete radar module (during operation)"""
        print("Restarting radar module...")
        if self.reboot_module():
            # Reactivate debug mode
            print("Reactivating debug mode after reboot...")
            return self.activate_radar_debug()
        else:
            # Fallback: try restarting just the debug mode
            print("Attempting debug mode restart only...")
            try:
                deactivate_debug_mode(self.ser)
                time.sleep(2)
                return self.activate_radar_debug()
            except Exception as e:
                print(f"Fallback error: {e}")
                return False
    
    def deactivate_radar_debug(self):
        """Deactivate radar debug mode"""
        try:
            print("Deactivating radar debug mode...")
            deactivate_debug_mode(self.ser)
            print("Debug mode deactivated")
        except Exception as e:
            print(f"Error deactivating debug mode: {e}")
    
    def publish_radar_data(self, data):
        """Continuously publish radar data to MQTT"""
        try:
            timestamp = datetime.now().isoformat()
            
            # Topic 1: Detection (simple boolean)
            detection_payload = {
                "detected": data['detection'],
                "timestamp": timestamp
            }
            self.mqtt_client.publish(self.topic_detection, json.dumps(detection_payload), retain=True)
            
            # Topic 2: Distance (numeric value)
            distance_payload = {
                "distance_cm": data['distance'],
                "timestamp": timestamp
            }
            self.mqtt_client.publish(self.topic_distance, json.dumps(distance_payload), retain=True)
            
            # Topic 3: Energy measurements (complete JSON)
            measurements_payload = {
                "gates": [
                    {
                        "gate": i, 
                        "energy_db": round(data['energy_values'][i], 2),
                        "energy_raw": data.get('energy_raw', [0]*16)[i] if 'energy_raw' in data else 0
                    } 
                    for i in range(16)
                ],
                "detection": data['detection'],
                "distance_cm": data['distance'],
                "timestamp": timestamp
            }
            self.mqtt_client.publish(self.topic_measurements, json.dumps(measurements_payload), retain=False)
            self.mqtt_client.publish(f"{self.topic_gates}", json.dumps(measurements_payload["gates"]), retain=False)
            for gate in measurements_payload["gates"]:
                gate_topic = f"{self.topic_gates}/{gate['gate']}"
                gate_payload = {
                    "energy_db": gate['energy_db'],
                    "energy_raw": gate['energy_raw'],
                    "timestamp": timestamp
                }
                self.mqtt_client.publish(gate_topic, json.dumps(gate_payload), retain=False)

            # Condensed log every 10 frames
            if hasattr(self, '_frame_log_count'):
                self._frame_log_count += 1
            else:
                self._frame_log_count = 1
                
            if self._frame_log_count % 10 == 0:
                detection_str = "DETECTED" if data['detection'] else "NONE"
                energy_summary = f"Max:{max(data['energy_values']):.1f}dB Min:{min(data['energy_values']):.1f}dB"
                print(f"[{timestamp[-12:-3]}] {detection_str} | {data['distance']}cm | {energy_summary} | Frame #{self._frame_log_count}")
            
        except Exception as e:
            print(f"MQTT publishing error: {e}")
    
    def run(self):
        """Main service loop"""
        print("Starting MQTT Radar service...")
        
        # Mandatory module reboot at startup
        print("=== MANDATORY MODULE REBOOT ===")
        if not self.reboot_module():
            print("Warning: Initial reboot failed, continuing anyway...")
        
        # Activate debug mode
        if not self.activate_radar_debug():
            return False
        
        self.running = True
        buffer = b''
        frame_count = 0
        
        try:
            print("Service running - Ctrl+C to stop")
            print(f"Waiting for data on {self.serial_port}...")
            
            # Check that we're receiving data
            timeout_counter = 0
            last_restart = 0
            
            while self.running:
                if self.ser.in_waiting:
                    timeout_counter = 0  # Reset timeout
                    new_data = b''
                    try:
                        # Read available data
                        new_data = self.ser.read(self.ser.in_waiting)
                    except Exception as e:
                        print(f"Serial read error: {e}")
                        new_data = b''
                    buffer += new_data
                    
                    # Process all complete frames
                    while True:
                        parsed = parse_debug_frame(buffer)
                        if parsed is None:
                            break
                        
                        frame_count += 1
                        
                        # Publish to MQTT for each received frame
                        self.publish_radar_data(parsed)
                        
                        # Clean the buffer - remove complete frame
                        header = bytes.fromhex('F4 F3 F2 F1')
                        footer = bytes.fromhex('F8 F7 F6 F5')
                        start = buffer.find(header)
                        # Complete frame = header(4) + length(2) + data(35) + footer(4) = 45 bytes
                        buffer = buffer[start + 45:]
                else:
                    timeout_counter += 1
                    
                    # Display status every 5 seconds
                    if timeout_counter % 500 == 0:  # Every 5 seconds
                        elapsed = timeout_counter * 0.01
                        print(f"No data received for {elapsed:.1f}s")
                        self.on_serial_updated()
                        
                        # Restart module if no data for too long
                        if elapsed >= self.restart_interval and elapsed - last_restart >= self.restart_interval:
                            print(f"Auto-restarting module after {elapsed:.1f}s without data")
                            if self.restart_debug_mode():
                                print("Module restarted successfully")
                                last_restart = elapsed
                                timeout_counter = 0  # Reset counter
                                buffer = b''  # Empty the buffer
                            else:
                                print("Module restart failed")
                
                time.sleep(0.01)  # Reduced delay for more responsiveness
                
        except KeyboardInterrupt:
            print("\nShutdown requested by user")
        except Exception as e:
            print(f"Error in main loop: {e}")
        finally:
            self.shutdown()
        
        return True
    
    def shutdown(self):
        """Clean service shutdown"""
        print("Stopping service...")
        self.running = False
        
        # Deactivate debug mode
        if self.ser:
            self.deactivate_radar_debug()
            self.ser.close()
        
        print("Service stopped")
