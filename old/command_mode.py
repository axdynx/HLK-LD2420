import serial
import time
import os
import sys
import threading
from commands.protocol import *
import re

def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def select_port(ports):
    while True:
        ports = list_serial_ports()
        os.system('cls' if os.name == 'nt' else 'clear')
        print("Ports disponibles :")
        for i, port in enumerate(ports):
            print(f"{i+1}: {port}")
        print("Tape le numéro du port et Entrée pour sélectionner. (q pour quitter)")
        choix = input("Numéro du port : ").strip()
        if choix.lower() == 'q':
            return None
        try:
            idx = int(choix) - 1
            if 0 <= idx < len(ports):
                return ports[idx]
            else:
                print("Numéro invalide.")
                time.sleep(1)
        except ValueError:
            print("Entrée invalide.")
            time.sleep(1)

def listen_serial(port, baudrate=115200):
    print(f"Écoute sur {port} à {baudrate} bauds. Appuie sur 'q' pour revenir au menu.")
    stop_event = threading.Event()

    def read_serial():
        with serial.Serial(port, baudrate, timeout=1) as ser:
            while not stop_event.is_set():
                if ser.in_waiting:
                    data = ser.readline().decode(errors='ignore').strip()
                    if data:
                        print(f"Reçu: {data}", end='\r\n')

    def listen_for_q():
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch.lower() == 'q':
                    stop_event.set()
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    thread_serial = threading.Thread(target=read_serial, daemon=True)
    thread_q = threading.Thread(target=listen_for_q, daemon=True)
    thread_serial.start()
    thread_q.start()
    thread_q.join()
    print("Retour au menu principal.")

def listen_serial_hex(port, baudrate=115200):
    print(f"Écoute sur {port} à {baudrate} bauds (mode hex). Appuie sur 'q' pour revenir au menu.")
    stop_event = threading.Event()

    def read_serial():
        with serial.Serial(port, baudrate, timeout=1) as ser:
            while not stop_event.is_set():
                if ser.in_waiting:
                    data = ser.read(ser.in_waiting)
                    if data:
                        hex_str = ' '.join(f'{b:02X}' for b in data)
                        print(f"Reçu (hex): {hex_str}", end='\r\n')

    def listen_for_q():
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch.lower() == 'q':
                    stop_event.set()
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    thread_serial = threading.Thread(target=read_serial, daemon=True)
    thread_q = threading.Thread(target=listen_for_q, daemon=True)
    thread_serial.start()
    thread_q.start()
    thread_q.join()
    print("Retour au menu principal.")

def display_sensor_data(port, baudrate=115200):
    print("Affichage capteur : ON/OFF et distance. Appuie sur 'q' pour revenir au menu.")
    stop_event = threading.Event()
    status = {'mode': '--', 'distance': '--'}

    def read_sensor():
        with serial.Serial(port, baudrate, timeout=1) as ser:
            buffer = b''
            while not stop_event.is_set():
                if ser.in_waiting:
                    buffer += ser.read(ser.in_waiting)
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        line = line.decode(errors='ignore').strip()
                        if line == 'ON' or line == 'OFF':
                            status['mode'] = line
                        else:
                            m = re.match(r'Range (\d+)', line)
                            if m:
                                status['distance'] = m.group(1)
                        print(f"Mode: {status['mode']} | Distance: {status['distance']}   ", end='\r', flush=True)

    def listen_for_q():
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch.lower() == 'q':
                    stop_event.set()
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    thread_sensor = threading.Thread(target=read_sensor, daemon=True)
    thread_q = threading.Thread(target=listen_for_q, daemon=True)
    thread_sensor.start()
    thread_q.start()
    thread_q.join()
    print("\nRetour au menu principal.")

def display_debug_data(port, baudrate=115200):
    """Affiche les données du mode rapport en temps réel"""
    print("Mode debug : affichage des données de rapport. Appuie sur 'q' pour revenir au menu.")
    
    with serial.Serial(port, baudrate, timeout=1) as ser:
        # Activation du mode debug
        print("Activation du mode debug...")
        try:
            activate_debug_mode(ser)
            print("Mode debug activé. En attente des données...")
        except Exception as e:
            print(f"Erreur lors de l'activation du mode debug: {e}")
            return
        
        buffer = b''
        frame_count = 0
        current_data = {
            'detection': False,
            'distance': 0,
            'energy_values': [0.0] * 16
        }
        
        # Configuration du terminal pour lecture non-bloquante
        import termios
        import tty
        import select
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        try:
            tty.setraw(fd)
            
            while True:
                # Vérifie si une touche a été pressée
                if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                    ch = sys.stdin.read(1)
                    if ch.lower() == 'q':
                        break
                
                # Lit les données série
                if ser.in_waiting:
                    new_data = ser.read(ser.in_waiting)
                    buffer += new_data
                    
                    # Traite toutes les trames complètes dans le buffer
                    updated = False
                    while True:
                        parsed = parse_debug_frame(buffer)
                        if parsed is None:
                            break
                        
                        frame_count += 1
                        current_data.update(parsed)
                        updated = True
                        
                        # Retire la trame traitée du buffer
                        header = bytes.fromhex('F4 F3 F2 F1')
                        footer = bytes.fromhex('F8 F7 F6 F5')
                        start = buffer.find(header)
                        # Trame complète = header(4) + length(2) + data(35) + footer(4) = 45 bytes
                        buffer = buffer[start + 45:]
                    
                    # Affichage mis à jour seulement s'il y a eu une nouvelle trame
                    if updated:
                        detection_str = "DÉTECTÉ" if current_data['detection'] else "RIEN    "
                        energy_str = " ".join([f"P{j:02d}:{current_data['energy_values'][j]:4.0f}" for j in range(16)])
                        print(f"\rTrame #{frame_count} - Détection: {detection_str} | Distance: {current_data['distance']:3d}cm | Énergies(dB): {energy_str}", end="", flush=True)
                
                # Petite pause pour éviter la surcharge CPU
                time.sleep(0.05)
        
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
        # Désactivation du mode debug avant de sortir
        print("\nDésactivation du mode debug...")
        try:
            deactivate_debug_mode(ser)
        except Exception as e:
            print(f"Erreur lors de la désactivation: {e}")
    
    print("Retour au menu principal.")

def command_mode(port, baudrate=115200):
    print(f"Mode commande sur {port} à {baudrate} bauds.")
    with serial.Serial(port, baudrate, timeout=1) as ser:
        while True:
            print("\n=== MODE COMMANDE ===")
            print("1. Test (n'envoie rien)")
            print("2. Lire le numéro de version")
            print("3. Redémarrer le module")
            print("4. Lire/Définir un paramètre")
            print("5. Commande de test (12 00 00 00 04 00 00 00)")
            print("q. Retour menu principal")
            choice = input("Choix : ").strip().lower()
            if choice == '1':
                print("Mode test : envoi uniquement des commandes d'ouverture et de fermeture du mode commande...")
                open_cmd = build_open_command_mode()  # FF 00 + version 01 00
                close_cmd = build_command(bytes.fromhex('FE 00'))
                expected_ack_open = build_structured_message(bytes.fromhex('FF 01 00 00 02 00 20 00'))
                expected_ack_close = build_structured_message(bytes.fromhex('FE 01 00 00'))
                with serial.Serial(port, baudrate, timeout=1) as test_ser:
                    print(f"Données envoyées (hex) : {to_hex_str(open_cmd)}")
                    test_ser.write(open_cmd)
                    test_ser.flush()
                    ack_open = wait_for_ack(test_ser)
                    print(f"Données reçues (hex) : {to_hex_str(ack_open) if ack_open else '--'}")
                    if ack_open.strip() == expected_ack_open:
                        print("Acquittement correct pour Open command mode.")
                    else:
                        print("Acquittement incorrect pour Open command mode !")
                    print(f"Données envoyées (hex) : {to_hex_str(close_cmd)}")
                    test_ser.write(close_cmd)
                    test_ser.flush()
                    ack_close = wait_for_ack(test_ser)
                    print(f"Données reçues (hex) : {to_hex_str(ack_close) if ack_close else '--'}")
                    if ack_close.strip() == expected_ack_close:
                        print("Acquittement correct pour Close command mode.")
                    else:
                        print("Acquittement incorrect pour Close command mode !")
            elif choice == '2':
                print("Envoi de la commande 'read version number'...")
                cmd = build_command(bytes.fromhex('00 00'))
                ack = build_command(bytes.fromhex('00 01 00 00 00 00 00 00 00 00 00 00'))
                data = send_command_sequence(ser, "read version number", cmd, ack, version=1)
                version = None
                if data:
                    try:
                        version = data.decode(errors='ignore').strip()
                    except Exception:
                        version = None
                if version is not None:
                    print(f"\nNuméro de version reçu : {version}")
                else:
                    print("Aucune donnée de version reçue.")
            elif choice == '3':
                print("Envoi de la commande 'Reboot module'...")
                cmd = build_command(bytes.fromhex('68 00'))
                send_command_sequence(ser, "Reboot module", cmd, None, version=1)
                return 'reboot'
            elif choice == '4':
                param_list = [
                    ("Minimum detection distance door", b'\x00\x00', 0, 15),
                    ("Maximum detection distance door", b'\x01\x00', 0, 15),
                    ("Delay time", b'\x04\x00', 0, 64),
                    ("Trigger threshold", [(f"{i}", (i+0x10).to_bytes(1, 'little') + b'\x00', 0, 65536) for i in range(16)]),
                    ("Maintain threshold", [(f"{i}", (i+0x20).to_bytes(1, 'little') + b'\x00', 0, 65536) for i in range(16)]),
                ]
                while True:
                    print("\n--- Sous-menu Paramètres ---")
                    print("1. Lire un paramètre")
                    print("2. Définir un paramètre")
                    print("q. Retour menu commande")
                    sub_choice = input("Choix : ").strip().lower()
                    if sub_choice in ('1', '2'):
                        print("\nSélectionne le paramètre :")
                        for idx, entry in enumerate(param_list):
                            if isinstance(entry[1], list):
                                print(f"{idx+1}. {entry[0]}")
                            else:
                                print(f"{idx+1}. {entry[0]}")
                        pidx = input("Numéro du paramètre : ").strip()
                        tidx = None
                        try:
                            pidx = int(pidx) - 1
                            entry = param_list[pidx]
                        except (ValueError, IndexError):
                            print("Numéro invalide.")
                            continue
                        if isinstance(entry[1], list):
                            print(f"Quel index (0-15) pour {entry[0]} ?")
                            for i, (iname, _, _, _) in enumerate(entry[1]):
                                print(f"{i}: {entry[0]} {iname}")
                            tidx = input("Index : ").strip()
                            try:
                                tidx = int(tidx)
                                param_bytes = entry[1][tidx][1]
                                vmin, vmax = entry[1][tidx][2], entry[1][tidx][3]
                            except (ValueError, IndexError):
                                print("Index invalide.")
                                continue
                        else:
                            param_bytes = entry[1]
                            vmin, vmax = entry[2], entry[3]
                        if sub_choice == '1':
                            cmd = build_command(bytes.fromhex('08 00') + param_bytes + b'\x00\x00\x00\x00')
                            # ACK : header + longueur + 08 01 + status (00 00 pour ok) + data (12 octets) + footer
                            ack = build_command(bytes.fromhex('08 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00'))
                            print("Envoi de la commande de lecture de paramètre...")
                            data = send_command_sequence(ser, "read parameter", cmd, ack, version=1)
                            value = None
                            if data and len(data) >= 14:
                                # Vérifier le status (bytes 2-3, doit être 00 00 pour OK)
                                status = int.from_bytes(data[2:4], 'little')
                                if status == 0:
                                    # Extraire la valeur (4 premiers bytes des 12 bytes de data)
                                    value = int.from_bytes(data[4:8], 'little')
                                    if tidx is not None:
                                        print(f"\n{entry[0]} {tidx} : {value}")
                                    else:
                                        print(f"\n{entry[0]} : {value}")
                                else:
                                    print(f"Erreur lecture paramètre (status: {status})")
                            else:
                                print("Réponse trop courte ou invalide")
                        else:
                            val = input(f"Valeur à écrire (entier {vmin}-{vmax}) : ").strip()
                            try:
                                ival = int(val)
                                if not (vmin <= ival <= vmax):
                                    print("Valeur hors limites.")
                                    continue
                                value_bytes = ival.to_bytes(4, 'little')
                            except Exception:
                                print("Entrée invalide.")
                                continue
                            cmd = build_command(bytes.fromhex('07 00') + param_bytes + value_bytes)
                            ack = build_command(bytes.fromhex('07 01 00 00'))
                            print("Envoi de la commande de modification de paramètre...")
                            send_command_sequence(ser, "write parameter", cmd, ack, version=1)
                    elif sub_choice == 'q':
                        break
                    else:
                        print("Choix invalide.")
            elif choice == '5':
                print("Fonctionnalité déplacée vers le menu principal (option 5: Mode debug)")
            elif choice == 'q':
                print("Retour au menu principal.")
                break
            else:
                print("Choix invalide.")
