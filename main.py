import signal
import argparse
import sys
from mqtt_service import RadarMQTTService

def signal_handler(signum, frame):
    """Gestionnaire de signaux pour arrêt propre"""
    print(f"\nSignal {signum} reçu, arrêt en cours...")
    if 'service' in globals():
        service.shutdown()
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description='Service MQTT pour capteur radar')
    parser.add_argument('port', help='Port série (ex: /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Vitesse série (défaut: 115200)')
    parser.add_argument('--mqtt-broker', default='localhost', help='Adresse broker MQTT (défaut: localhost)')
    parser.add_argument('--mqtt-port', type=int, default=1883, help='Port broker MQTT (défaut: 1883)')
    parser.add_argument('--mqtt-username', help='Nom d\'utilisateur MQTT (optionnel)')
    parser.add_argument('--mqtt-password', help='Mot de passe MQTT (optionnel)')
    parser.add_argument('--restart-interval', type=int, default=30, help='Intervalle de redémarrage auto en secondes (défaut: 30)')
    parser.add_argument('--mqtt-topic', default='radar/$sn', help='Topic MQTT (défaut: radar/$sn)')
    parser.add_argument('--mqtt-secure', type=bool, default=False, help='Mode MQTT/MQTTS')
    
    args = parser.parse_args()
    
    # Configuration des signaux pour arrêt propre
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Créer et démarrer le service
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
    
    success = service.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
