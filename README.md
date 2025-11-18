# HLK-LD2420

Ce guide explique comment utiliser le code et déployer ce service systemd sur un Linux

## Prérequis
- Linux avec le module connecté en port série
- Accès SSH ou terminal local
- Python 3
- Git, pip, `systemd`

## Installation
1. Cloner le dépôt
2. Aller dans le dossier
3. Créer et activer un environnement virtuel Python :
    - `python3 -m venv .venv`
    - `source .venv/bin/activate`
4. Executer le fichier d'installation :
    - `./install_service.sh`

## Utilisation manuelle
### Installer les dépendances
- `pip3 install paho-mqtt pyserial` ou `apt-get install python3-paho-mqtt python3-serial`
### Tester le programme manuellement
- `python3 mqtt_service.py <port> --mqtt-username <username> --mqtt-password <password>`
S’assurer qu’il fonctionne et qu’il écrit ses logs.

## Vérifier le service et les logs
- Statut : `sudo systemctl status radar-mqtt.service`
- Logs : `sudo journalctl -u radar-mqtt.service -f`

## Débogage et mises à jour
- Après modification du fichier d’unité : `sudo systemctl daemon-reload` puis `sudo systemctl restart radar-mqtt.service`.
- Si permissions d’accès à des ressources : vérifier `User=` et droits des fichiers.
- Tester l’exécution manuelle pour isoler les erreurs avant d’utiliser systemd.

## Bonnes pratiques
- Rediriger les logs vers un fichier ou utiliser `logging`.
- Utiliser un fichier `.env` ou `EnvironmentFile=` pour les variables sensibles.
- Ne pas exécuter en root sauf si nécessaire.