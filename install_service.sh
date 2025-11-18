#!/bin/bash
# Script d'installation du service MQTT Radar

set -e

SERVICE_NAME="radar-mqtt"
SERVICE_DIR="/opt/radar_service"
SERVICE_USER="radar"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installation du service MQTT Radar ==="

# Vérifier les privilèges root
if [[ $EUID -ne 0 ]]; then
   echo "Ce script doit être exécuté en tant que root (sudo)"
   exit 1
fi

# Installation des dépendances Python
echo "Installation des dépendances Python..."
apt-get update
apt-get install -y python3 python3-pip python3-venv

# Tentative d'installation via les paquets système d'abord
echo "Tentative d'installation via les paquets système..."
if apt-get install -y python3-paho-mqtt python3-serial; then
    echo "✓ Dépendances installées via les paquets système"
else
    echo "⚠ Paquets système non disponibles, utilisation de pip..."
    if pip3 install paho-mqtt pyserial; then
        echo "✓ Dépendances installées via pip"
    else
        echo "✗ Échec de l'installation des dépendances"
        echo "Essayez manuellement :"
        echo "  sudo apt-get install python3-paho-mqtt python3-serial"
        echo "  ou"
        echo "  sudo pip3 install paho-mqtt pyserial"
        exit 1
    fi
fi

# Créer l'utilisateur du service
echo "Création de l'utilisateur $SERVICE_USER..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -d $SERVICE_DIR $SERVICE_USER
    usermod -a -G dialout $SERVICE_USER
    echo "Utilisateur $SERVICE_USER créé"
else
    echo "Utilisateur $SERVICE_USER existe déjà"
fi

# Créer le répertoire du service
echo "Création du répertoire $SERVICE_DIR..."
mkdir -p $SERVICE_DIR
mkdir -p $SERVICE_DIR/commands

# Copier les fichiers
echo "Copie des fichiers..."
cp "$SCRIPT_DIR/mqtt_service.py" $SERVICE_DIR/
cp "$SCRIPT_DIR/main.py" $SERVICE_DIR/
cp -r "$SCRIPT_DIR/commands/"* $SERVICE_DIR/commands/

# Ajuster les permissions
chown -R $SERVICE_USER:$SERVICE_USER $SERVICE_DIR
chmod +x $SERVICE_DIR/main.py

# Installer le fichier de service systemd
echo "Installation du service systemd..."
cp "$SCRIPT_DIR/radar-mqtt.service" /etc/systemd/system/

# Recharger systemd
systemctl daemon-reload

echo ""
echo "=== Installation terminée ==="
echo ""
echo "Configuration du service :"
echo "1. Modifier le port série dans /etc/systemd/system/radar-mqtt.service si nécessaire"
echo ""
echo "2. Démarrer le service :"
echo "   sudo systemctl start $SERVICE_NAME"
echo ""
echo "3. Activer le démarrage automatique :"
echo "   sudo systemctl enable $SERVICE_NAME"
echo ""
echo "4. Vérifier le statut :"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "5. Voir les logs :"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "Configuration MQTT :"
echo "- Broker par défaut : localhost:1883"
echo "- Pour authentification, modifier /etc/systemd/system/radar-mqtt.service :"
echo "  Environment=MQTT_USERNAME=votre_utilisateur"
echo "  Environment=MQTT_PASSWORD=votre_mot_de_passe"
echo "- Ou utiliser les paramètres en ligne de commande :"
echo "  --mqtt-username utilisateur --mqtt-password motdepasse"
echo "- Topics :"
echo "  * radar/sensor/measurements/detection : État détection"
echo "  * radar/sensor/measurements/distance : Distance mesurée"
echo "  * radar/sensor/measurements/gates/{gate} : Valeurs énergétiques par porte"
echo "  * radar/sensor/measurements/gates : Valeurs énergétiques de toutes les portes"
echo "  * radar/sensor/measurements : Toutes les mesures"
echo "  * radar/sensor/measurements/set/<parameter> : Changer un paramètre du radar"
echo "  * radar/sensor/measurements/set/<parameter>/<id> : Changer un paramètre <id> du radar"