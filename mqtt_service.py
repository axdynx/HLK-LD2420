#!/usr/bin/env python3
"""
Service MQTT pour le capteur radar
Connecte le capteur en mode debug et publie les données sur MQTT
Usage: python3 mqtt_service.py <port_serie>
"""

import sys
import time
import json
from datetime import datetime
sys.path.append('/opt/radar_service')  # Ajuste selon l'installation
import paho.mqtt.client as mqtt
import serial
import sys
import os
from commands.protocol import *
import math

class RadarMQTTService:
    def __init__(self, serial_port, baudrate=115200, mqtt_broker="localhost", mqtt_port=1883, mqtt_username=None, mqtt_password=None, mqtt_topic="radar/$sn", restart_interval=30):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.restart_interval = restart_interval  # Intervalle de redémarrage en secondes
        self.running = False
        self.ser = None
        self.mqtt_client = None
        self.version = "unknown"
        self.sn = "unknown"
        self.port_name = serial_port.replace('/dev/', '').replace('\\', '_').replace(':', '_')
        
        # Configuration série
        if not self.setup_serial():
            print("Échec connexion série")
        self.get_version()
        self.get_sn()
        
        self.topic = mqtt_topic.replace("$port", self.port_name).replace("$sn", self.sn).replace("$version", self.version)
        print(f"Utilisation topic MQTT de base: {self.topic}")
        self.topic_measurements = f"{self.topic}/measurements"
        self.topic_detection = f"{self.topic_measurements}/detection"
        self.topic_distance = f"{self.topic_measurements}/distance"
        self.topic_gates = f"{self.topic_measurements}/gates"
        self.topic_status = f"{self.topic}/status"
        self.topic_parameters = f"{self.topic}/parameters"
        
        # Configuration MQTT
        if not self.setup_mqtt():
            print("Échec connexion MQTT")
        
    def setup_mqtt(self):
        """Configure la connexion MQTT"""
        self.mqtt_client = mqtt.Client()
        
        def on_mqtt_connect(client, userdata, connect_flags, reason_code):
            """Callback connexion MQTT"""
            if reason_code == 0:
                print(f"Connecté au broker MQTT {self.mqtt_broker}:{self.mqtt_port}")
                # Publier le statut de démarrage
                self.mqtt_client.publish(self.topic_status, json.dumps({
                    "status": self.ser is not None and self.ser.is_open,
                    "version": self.version,
                    "timestamp": datetime.now().isoformat(),
                    "port": self.serial_port,
                    "serial_number": self.sn
                }), retain=True)
            else:
                print(f"Échec connexion MQTT, code: {reason_code}")
    
        def on_mqtt_disconnect(client, userdata, reason_code):
            """Callback déconnexion MQTT"""
            print(f"Déconnecté du broker MQTT, code: {reason_code}")
            
        def on_mqtt_message_reboot(client, userdata, msg):
            self.restart_debug_mode()
            self.on_serial_updated()

        def on_mqtt_message_parameters_set(client, userdata, msg): 
            """Callback réception message MQTT"""
            print(f"Message reçu sur {msg.topic}: {msg.payload.decode()}")
            topic = msg.topic.split('/')
            set_param_index = topic.index("set") if "set" in topic else -1
            if set_param_index != -1 and len(topic) > set_param_index + 1:
                param_key = topic[set_param_index + 1]
                data = json.loads(msg.payload.decode('utf-8'))
                if (data is not None and "value" in data and data['value'] is not None):
                    value = data['value']
                    if (param_key == "min_detection_door"):
                        print(f"Changement min_detection_door => {value}")
                        if 0 <= value <= 15:
                            if (self.set_parameter("Porte à distance minimale de détection", b'\x00\x00', value.to_bytes(4, 'little'))) :
                                new_value = self.get_parameter("Porte à distance minimale de détection", b'\x00\x00')
                                if (new_value is not None) :
                                    self.publish_parameter("min_detection_door", new_value)
                    elif (param_key == "max_detection_door"):
                        print(f"Changement max_detection_door => {value}")
                        if 0 <= value <= 15:
                            if (self.set_parameter("Porte à distance maximale de détection", b'\x01\x00', value.to_bytes(4, 'little'))) :
                                new_value = self.get_parameter("Porte à distance maximale de détection", b'\x01\x00')
                                if (new_value is not None) :
                                    self.publish_parameter("max_detection_door", new_value)
                    elif (param_key == "delay_time"):
                        print(f"Changement delay_time => {value}")
                        if 0 <= value <= 65535:
                            if (self.set_parameter("Délai", b'\x04\x00', value.to_bytes(4, 'little'))):
                                new_value = self.get_parameter("Délai", b'\x04\x00')
                                if (new_value is not None):
                                    self.publish_parameter("delay_time", new_value)
                elif (data is not None and ("value_db" in data and data['value_db'] is not None) or ("value_raw" in data and data['value_raw'] is not None)):
                    value_raw = 0
                    if ("value_db" in data and data['value_db'] is not None):
                        value_db = data['value_db']
                        value_raw = int(round(10 ** (value_db / 10)))
                    elif ("value_raw" in data and data['value_raw'] is not None):
                        value_raw = data['value_raw']
                    if (param_key.startswith("trigger_threshold")):
                        print(f"Changement trigger_threshold => {value_raw}")
                        index_str = topic[set_param_index + 2]
                        try:
                            index = int(index_str)
                            if 0 <= index <= 15 and 0 <= value_raw <= (10 ** (232 / 10)):
                                if (self.set_parameter(f"Seuil de déclenchement {index}", (index+0x10).to_bytes(1, 'little') + b'\x00', value_raw.to_bytes(4, 'little'))):
                                    new_value = self.get_parameter(f"Seuil de déclenchement {index}", (index+0x10).to_bytes(1, 'little') + b'\x00', threshold_index=True)
                                    if (new_value is not None):
                                        self.publish_parameter(f"trigger_threshold/{index}", new_value)
                        except ValueError:
                            print(f"Index invalide pour trigger_threshold: {index_str}")
                    elif (param_key.startswith("maintain_threshold")):
                        print(f"Changement maintain_threshold => {value_raw}")
                        index_str = topic[set_param_index + 2]
                        try:
                            index = int(index_str)
                            if 0 <= index <= 15 and 0 <= value_raw <= (10 ** (232 / 10)):
                                if (self.set_parameter(f"Seuil de maintien {index}", (index+0x20).to_bytes(1, 'little') + b'\x00', value_raw.to_bytes(4, 'little'))):
                                    new_value = self.get_parameter(f"Seuil de maintien {index}", (index+0x20).to_bytes(1, 'little') + b'\x00', threshold_index=True)
                                    if (new_value is not None):
                                        self.publish_parameter(f"maintain_threshold/{index}", new_value)
                        except ValueError:
                            print(f"Index invalide pour maintain_threshold: {index_str}")
                else :
                    print("Payload invalide pour changement de paramètre")
                
        self.mqtt_client.on_connect = on_mqtt_connect
        self.mqtt_client.on_disconnect = on_mqtt_disconnect
            
        # Configuration de l'authentification si fournie
        if self.mqtt_username and self.mqtt_password:
            print(f"Configuration authentification MQTT pour utilisateur: {self.mqtt_username}")
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            print(f"{self.topic_parameters}/set/#")
            self.mqtt_client.message_callback_add(f"{self.topic_parameters}/set/#", on_mqtt_message_parameters_set)
            self.mqtt_client.subscribe(f"{self.topic_parameters}/set/#")
            self.mqtt_client.message_callback_add(f"{self.topic}/reboot", on_mqtt_message_reboot)
            self.mqtt_client.subscribe(f"{self.topic}/reboot")
            self.mqtt_client.loop_start()
            return True
        except Exception as e:
            print(f"Erreur connexion MQTT: {e}")
            return False

    def setup_serial(self):
        """Configure la connexion série"""
        try:
            self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=1)
            print(f"Connecté au port série {self.serial_port}")
            return True
        except Exception as e:
            print(f"Erreur connexion série: {e}")
            return False
        
    def on_serial_updated(self):
        self.mqtt_client.publish(self.topic_status, json.dumps({
            "status": self.ser is not None and self.ser.is_open,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "port": self.serial_port,
            "serial_number": self.sn
        }), retain=True)
    
    def get_version(self):
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
        try:
            timestamp = datetime.now().isoformat()
            # Commande de lecture de paramètre (08 00 + code paramètre + 4 bytes vides)
            read_cmd = build_command(bytes.fromhex('08 00') + param_id + b'\x00\x00\x00\x00')
            # ACK : header + longueur + 08 01 + status (00 00 pour ok) + data (12 octets) + footer
            ack_pattern = build_command(bytes.fromhex('08 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00'))
                    
            # Envoyer la commande et récupérer la réponse
            response = send_command_sequence(self.ser, f"read {param_name}", read_cmd, ack_pattern, version=1)
                    
            if response and len(response) >= 14:
                # Vérifier le status (bytes 2-3, doit être 00 00 pour OK)
                status = int.from_bytes(response[2:4], byteorder='little')
                if status == 0:
                    # Extraire la valeur raw (4 premiers bytes des 12 bytes de data)
                    value_raw = int.from_bytes(response[4:8], byteorder='little')
                            
                    # Pour les seuils (trigger/maintain threshold), calculer aussi la valeur en dB
                    if threshold_index:
                        if value_raw > 0:
                            value_db = round(10 * math.log10(value_raw), 2)
                        else:
                            value_db = None  # Impossible de calculer log de 0
                                
                        param_data = {
                            "name": param_name,
                            "value_raw": value_raw,
                            "value_db": value_db,
                            "timestamp": timestamp
                        }
                        print(f"  {param_name}: {value_raw} (raw) / {value_db} dB")
                    else:
                        # Pour les autres paramètres (distances, délai), juste la valeur raw
                        param_data = {
                            "name": param_name,
                            "value": value_raw,
                            "timestamp": timestamp
                        }
                        print(f"  {param_name}: {value_raw}")
                            
                    return param_data
                else:
                    print(f"  {param_name}: Erreur status {status}")
                    return None
            elif response:
                print(f"  {param_name}: Réponse trop courte ({len(response)} bytes)")
                return None
            else:
                print(f"  {param_name}: Pas de réponse")
                return None

        except Exception as e:
            print(f"  Erreur lecture {param_name}: {e}")

    def set_parameter(self, param_name, param_id, param_value):
        cmd = build_command(bytes.fromhex('07 00') + param_id + param_value)
        ack = build_command(bytes.fromhex('07 01 00 00'))
        data = send_command_sequence(self.ser, f"set {param_name}", cmd, ack, version=1)
        if data and len(data) >= 4:
            # Vérifier le status (bytes 2-3, doit être 00 00 pour OK)
            status = int.from_bytes(data[2:4], 'little')
            if status == 0:
                print(f"Paramètre {param_name} défini avec succès")
                return True
            else :
                print(f"Erreur définition paramètre {param_name} (status: {status})")
                return False
        else:
            print(f"Pas de réponse ou réponse invalide pour définition paramètre {param_name}")
            return False

    def reboot_module(self):
        """Redémarre le module radar (commande de reboot)"""
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            print("Redémarrage du module radar au démarrage...")
            cmd = build_command(bytes.fromhex('68 00'))
            
            # Envoyer la commande de reboot (pas d'ACK attendu)
            send_command_sequence(self.ser, "Reboot module", cmd, None, version=1)
            
            # Attendre que le module redémarre complètement
            print("Attente redémarrage du module (8 secondes)...")
            time.sleep(8)
            print("Module redémarré")
            
            # Lecture et publication des paramètres après le redémarrage
            print("Lecture des paramètres du module...")
            if self.read_and_publish_parameters():
                print("Paramètres lus et publiés avec succès")
            else:
                print("Échec de la lecture des paramètres")
            
            return True
            
        except Exception as e:
            print(f"Erreur redémarrage module au démarrage: {e}")
            return False

    def publish_parameter(self, param_key, param_data):
        """Publie un paramètre spécifique sur MQTT"""
        try:
            topic = f"{self.topic_parameters}/{param_key}"
                        
            # Le payload est directement param_data (qui contient déjà name, values, timestamp)
            self.mqtt_client.publish(topic, json.dumps(param_data), retain=True)
                        
            # Affichage adapté selon le type de paramètre
            if "value_raw" in param_data:  # Seuils avec raw et dB
                print(f"  → {param_data['name']}: {param_data['value_raw']} (raw) / {param_data['value_db']} dB publié sur {topic}")
            else:  # Autres paramètres
                print(f"  → {param_data['name']}: {param_data['value']} publié sur {topic}")
        except Exception as e:
            print(f"  Erreur publication {param_key}: {e}")

    def read_and_publish_parameters(self):
        """Lit tous les paramètres du module et les publie sur MQTT"""
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            print("Lecture des paramètres du module...")
            
            # Définition des paramètres (même structure que command_mode.py)
            param_list = [
                ("min_detection_door", "Porte à distance minimale de détection", b'\x00\x00'),
                ("max_detection_door", "Porte à distance maximale de détection", b'\x01\x00'),
                ("delay_time", "Délai", b'\x04\x00'),
            ]
            
            # Paramètres avec index (seuils)
            trigger_thresholds = [(f"trigger_threshold/{i}", f"Seuil de déclenchement {i}", (i+0x10).to_bytes(1, 'little') + b'\x00') for i in range(16)]
            maintain_thresholds = [(f"maintain_threshold/{i}", f"Seuil de maintien {i}", (i+0x20).to_bytes(1, 'little') + b'\x00') for i in range(16)]
            
            all_params = param_list + trigger_thresholds + maintain_thresholds
            
            parameters = {}
            timestamp = datetime.now().isoformat()
            
            for param_key, param_name, param_code in all_params:
                value = self.get_parameter(param_name, param_code, threshold_index=('threshold' in param_key))
                    
                if value is not None:
                    parameters[param_key] = value
                else :
                    print(f"  Échec lecture paramètre {param_name}")
                # Petite pause entre les lectures
                time.sleep(0.1)
            
            # Publier chaque paramètre sur son propre topic MQTT avec retain
            if parameters:
                published_count = 0
                for param_key, param_data in parameters.items():
                    published_count += 1
                    self.publish_parameter(param_key, param_data)
                
                # Publier aussi un résumé global
                summary_payload = {
                    "total_parameters": len(parameters),
                    "published_count": published_count,
                    "timestamp": timestamp,
                    "status": "success" if published_count == len(parameters) else "partial"
                }
                self.mqtt_client.publish(self.topic_parameters, json.dumps(summary_payload), retain=True)
                print(f"Paramètres publiés sur MQTT: {published_count}/{len(parameters)} paramètres")
            else:
                # Publier un statut d'échec
                error_payload = {
                    "total_parameters": 0,
                    "published_count": 0,
                    "timestamp": timestamp,
                    "status": "error",
                    "message": "Aucun paramètre lu avec succès"
                }
                self.mqtt_client.publish(self.topic_parameters, json.dumps(error_payload), retain=True)
                print("Aucun paramètre lu avec succès")
                
            return True
            
        except Exception as e:
            print(f"Erreur lecture paramètres: {e}")
            return False

    def activate_radar_debug(self):
        """Active le mode debug du radar"""
        try:
            print("Activation du mode debug radar...")
            result = activate_debug_mode(self.ser)
            if result:
                print("Mode debug activé")
                return True
            else:
                print("Échec activation mode debug")
                return False
        except Exception as e:
            print(f"Erreur activation mode debug: {e}")
            return False
    
    def restart_debug_mode(self):
        """Redémarre le module radar complet (pendant le fonctionnement)"""
        print("Redémarrage du module radar...")
        if self.reboot_module():
            # Réactiver le mode debug
            print("Réactivation du mode debug après reboot...")
            return self.activate_radar_debug()
        else:
            # Fallback: essayer juste de redémarrer le mode debug
            print("Tentative redémarrage mode debug seulement...")
            try:
                deactivate_debug_mode(self.ser)
                time.sleep(2)
                return self.activate_radar_debug()
            except Exception as e:
                print(f"Erreur fallback: {e}")
                return False
    
    def deactivate_radar_debug(self):
        """Désactive le mode debug du radar"""
        try:
            print("Désactivation du mode debug radar...")
            deactivate_debug_mode(self.ser)
            print("Mode debug désactivé")
        except Exception as e:
            print(f"Erreur désactivation mode debug: {e}")
    
    def publish_radar_data(self, data):
        """Publie les données radar sur MQTT de manière continue"""
        try:
            timestamp = datetime.now().isoformat()
            
            # Topic 1: Détection (boolean simple)
            detection_payload = {
                "detected": data['detection'],
                "timestamp": timestamp
            }
            self.mqtt_client.publish(self.topic_detection, json.dumps(detection_payload), retain=True)
            
            # Topic 2: Distance (valeur numérique)
            distance_payload = {
                "distance_cm": data['distance'],
                "timestamp": timestamp
            }
            self.mqtt_client.publish(self.topic_distance, json.dumps(distance_payload), retain=True)
            
            # Topic 3: Mesures énergétiques (JSON complet)
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

            # Log condensé toutes les 10 trames
            if hasattr(self, '_frame_log_count'):
                self._frame_log_count += 1
            else:
                self._frame_log_count = 1
                
            if self._frame_log_count % 10 == 0:
                detection_str = "DÉTECTÉ" if data['detection'] else "RIEN"
                energy_summary = f"Max:{max(data['energy_values']):.1f}dB Min:{min(data['energy_values']):.1f}dB"
                print(f"[{timestamp[-12:-3]}] {detection_str} | {data['distance']}cm | {energy_summary} | Trame #{self._frame_log_count}")
            
        except Exception as e:
            print(f"Erreur publication MQTT: {e}")
    
    def run(self):
        """Boucle principale du service"""
        print("Démarrage du service MQTT Radar...")
        
        # Redémarrage obligatoire du module au démarrage
        print("=== REDÉMARRAGE OBLIGATOIRE DU MODULE ===")
        if not self.reboot_module():
            print("Attention: Échec du redémarrage initial, continuation quand même...")
        
        # Activation mode debug
        if not self.activate_radar_debug():
            return False
        
        self.running = True
        buffer = b''
        frame_count = 0
        
        try:
            print("Service en fonctionnement - Ctrl+C pour arrêter")
            print(f"En attente de données sur {self.serial_port}...")
            
            # Vérifier qu'on reçoit des données
            timeout_counter = 0
            last_restart = 0
            
            while self.running:
                if self.ser.in_waiting:
                    timeout_counter = 0  # Reset timeout
                    new_data = b''
                    try:
                        # Lire les données disponibles
                        new_data = self.ser.read(self.ser.in_waiting)
                    except Exception as e:
                        print(f"Erreur lecture série: {e}")
                        new_data = b''
                    buffer += new_data
                    
                    # Traite toutes les trames complètes
                    while True:
                        parsed = parse_debug_frame(buffer)
                        if parsed is None:
                            break
                        
                        frame_count += 1
                        
                        # Publier sur MQTT pour chaque trame reçue
                        self.publish_radar_data(parsed)
                        
                        # Nettoyer le buffer - retirer la trame complète
                        header = bytes.fromhex('F4 F3 F2 F1')
                        footer = bytes.fromhex('F8 F7 F6 F5')
                        start = buffer.find(header)
                        # Trame complète = header(4) + length(2) + data(35) + footer(4) = 45 bytes
                        buffer = buffer[start + 45:]
                else:
                    timeout_counter += 1
                    
                    # Afficher le statut toutes les 5 secondes
                    if timeout_counter % 500 == 0:  # Toutes les 5 secondes
                        elapsed = timeout_counter * 0.01
                        print(f"Aucune donnée reçue depuis {elapsed:.1f}s")
                        self.on_serial_updated()
                        
                        # Redémarrer le module si pas de données depuis trop longtemps
                        if elapsed >= self.restart_interval and elapsed - last_restart >= self.restart_interval:
                            print(f"Redémarrage automatique du module après {elapsed:.1f}s sans données")
                            if self.restart_debug_mode():
                                print("Module redémarré avec succès")
                                last_restart = elapsed
                                timeout_counter = 0  # Reset compteur
                                buffer = b''  # Vider le buffer
                            else:
                                print("Échec redémarrage module")
                
                time.sleep(0.01)  # Réduction du délai pour plus de réactivité
                
        except KeyboardInterrupt:
            print("\nArrêt demandé par l'utilisateur")
        except Exception as e:
            print(f"Erreur dans la boucle principale: {e}")
        finally:
            self.shutdown()
        
        return True
    
    def shutdown(self):
        """Arrêt propre du service"""
        print("Arrêt du service...")
        self.running = False
        
        # Désactiver le mode debug
        if self.ser:
            self.deactivate_radar_debug()
            self.ser.close()
        
        print("Service arrêté")