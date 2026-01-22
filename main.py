import signal
import argparse
import sys
from mqtt_service import RadarMQTTService

def signal_handler(signum, frame):
    """Signal handler for clean shutdown"""
    print(f"\nSignal {signum} received, shutting down...")
    if 'service' in globals():
        service.shutdown()
    sys.exit(0)

def main():
    """Main entry point for the radar MQTT service"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='MQTT service for radar sensor')
    parser.add_argument('port', help='Serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Serial baudrate (default: 115200)')
    parser.add_argument('--mqtt-broker', default='localhost', help='MQTT broker address (default: localhost)')
    parser.add_argument('--mqtt-port', type=int, default=1883, help='MQTT broker port (default: 1883)')
    parser.add_argument('--mqtt-username', help='MQTT username (optional)')
    parser.add_argument('--mqtt-password', help='MQTT password (optional)')
    parser.add_argument('--restart-interval', type=int, default=30, help='Auto-restart interval in seconds (default: 30)')
    parser.add_argument('--mqtt-topic', default='radar/$sn', help='MQTT topic (default: radar/$sn)')
    parser.add_argument('--mqtt-secure', type=bool, default=False, help='MQTT/MQTTS mode')
    
    args = parser.parse_args()
    
    # Configure signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start the service
    global service
    service = RadarMQTTService(
        serial_port=args.port,
        baudrate=args.baudrate,
        mqtt_broker=args.mqtt_broker,
        mqtt_port=args.mqtt_port,
        mqtt_username=args.mqtt_username,
        mqtt_password=args.mqtt_password,
        restart_interval=args.restart_interval,
        mqtt_topic=args.mqtt_topic,
	mqtt_secure=args.mqtt_secure
    )
    
    # Run the service and exit with appropriate status code
    success = service.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
