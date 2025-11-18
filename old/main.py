from command_mode import *

def main_menu():
	while True:
		ports = list_serial_ports()
		if not ports:
			print("Aucun port série détecté.")
			import time
			time.sleep(1)
			continue
		port = select_port(ports)
		if not port:
			continue
		while True:
			print("\n=== MENU PRINCIPAL ===")
			print("1. Écouter le port série")
			print("2. Mode commande")
			print("3. Affichage capteur (ON/OFF + distance)")
			print("4. Écouter le port série (mode hex)")
			print("5. Mode debug (données détaillées)")
			print("q. Quitter")
			choice = input("Choix : ").strip().lower()
			if choice == '1':
				listen_serial(port)
			elif choice == '2':
				result = command_mode(port)
				if result == 'reboot':
					break  # Retour à la sélection du port
			elif choice == '3':
				display_sensor_data(port)
			elif choice == '4':
				listen_serial_hex(port)
			elif choice == '5':
				display_debug_data(port)
			elif choice == 'q':
				print("Au revoir !")
				import sys
				sys.exit(0)
			else:
				print("Choix invalide.")

if __name__ == "__main__":
	try:
		main_menu()
	except Exception as e:
		print(f"Erreur inattendue : {e}")
	print("Appuie sur Entrée pour quitter...")
	input()