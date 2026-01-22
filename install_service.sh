#!/bin/bash
# MQTT Radar Service Installation Script

set -e

SERVICE_NAME="radar-mqtt"
SERVICE_DIR="/opt/radar_service"
SERVICE_USER="radar"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== MQTT Radar Service Installation ==="

# Check for root privileges
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (sudo)"
   exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv

# Try installing via system packages first
echo "Attempting installation via system packages..."
if apt-get install -y python3-paho-mqtt python3-serial; then
    echo "✓ Dependencies installed via system packages"
else
    echo "⚠ System packages not available, using pip..."
    if pip3 install paho-mqtt pyserial; then
        echo "✓ Dependencies installed via pip"
    else
        echo "✗ Failed to install dependencies"
        echo "Try manually:"
        echo "  sudo apt-get install python3-paho-mqtt python3-serial"
        echo "  or"
        echo "  sudo pip3 install paho-mqtt pyserial"
        exit 1
    fi
fi

# Create service user
echo "Creating user $SERVICE_USER..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -d $SERVICE_DIR $SERVICE_USER
    usermod -a -G dialout $SERVICE_USER
    echo "User $SERVICE_USER created"
else
    echo "User $SERVICE_USER already exists"
fi

# Create service directory
echo "Creating directory $SERVICE_DIR..."
mkdir -p $SERVICE_DIR
mkdir -p $SERVICE_DIR/commands

# Copy files
echo "Copying files..."
cp "$SCRIPT_DIR/mqtt_service.py" $SERVICE_DIR/
cp "$SCRIPT_DIR/main.py" $SERVICE_DIR/
cp -r "$SCRIPT_DIR/commands/"* $SERVICE_DIR/commands/

# Adjust permissions
chown -R $SERVICE_USER:$SERVICE_USER $SERVICE_DIR
chmod +x $SERVICE_DIR/main.py

# Install systemd service file
echo "Installing systemd service..."
cp "$SCRIPT_DIR/radar-mqtt.service" /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Service Configuration:"
echo "1. Modify the serial port in /etc/systemd/system/radar-mqtt.service if necessary"
echo ""
echo "2. Start the service:"
echo "   sudo systemctl start $SERVICE_NAME"
echo ""
echo "3. Enable automatic startup:"
echo "   sudo systemctl enable $SERVICE_NAME"
echo ""
echo "4. Check status:"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "5. View logs:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "MQTT Configuration:"
echo "- Default broker: localhost:1883"
echo "- For authentication, modify /etc/systemd/system/radar-mqtt.service:"
echo "  Environment=MQTT_USERNAME=your_username"
echo "  Environment=MQTT_PASSWORD=your_password"
echo "- Or use command line parameters:"
echo "  --mqtt-username username --mqtt-password password"
echo "- Topics:"
echo "  * radar/sensor/measurements/detection: Detection status"
echo "  * radar/sensor/measurements/distance: Measured distance"
echo "  * radar/sensor/measurements/gates/{gate}: Energy values per gate"
echo "  * radar/sensor/measurements/gates: Energy values of all gates"
echo "  * radar/sensor/measurements: All measurements"
echo "  * radar/sensor/measurements/set/<parameter>: Change a radar parameter"
echo "  * radar/sensor/measurements/set/<parameter>/<id>: Change a radar parameter <id>"