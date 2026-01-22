# HLK-LD2420

This guide explains how to use the code and deploy this systemd service on Linux.

Here you can find MQTT documentation : [MQTT Topics Documentation](./MQTT_TOPIC.md)

You can have more details about the module here : 
- [Hi-Link Website](https://www.hlktech.com/en/Goods-246.html)
- [Hi-Link Aliexpress Store](https://fr.aliexpress.com/item/1005006294789408.html?channel=twinner)

## Prerequisites
- Linux with the module connected to a serial port
- SSH access or local terminal
- Python 3
- Git, pip, `systemd`

## Installation
1. Clone the repository
2. Navigate to the folder
3. Create and activate a Python virtual environment:
    - `python3 -m venv .venv`
    - `source .venv/bin/activate`
4. Run the installation script:
    - `sudo ./install_service.sh`

## Manual Usage
### Install dependencies
- `pip3 install paho-mqtt pyserial` or `apt-get install python3-paho-mqtt python3-serial`
### Test the program manually
- `python3 main.py <port> --mqtt-username <username> --mqtt-password <password>`
Ensure it runs and writes its logs.

## Check Service and Logs
- Status: `sudo systemctl status radar-mqtt.service`
- Logs: `sudo journalctl -u radar-mqtt.service -f`

## Debugging and Updates
- After modifying the unit file: `sudo systemctl daemon-reload` then `sudo systemctl restart radar-mqtt.service`.
- If resource access permissions issue: check `User=` and file permissions.
- Test manual execution to isolate errors before using systemd.

## Best Practices
- Redirect logs to a file or use `logging`.
- Use a `.env` file or `EnvironmentFile=` for sensitive variables.
- Do not run as root unless necessary.