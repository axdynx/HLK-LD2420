# MQTT Topics Documentation

Ce document décrit tous les topics MQTT utilisés par le service radar HLK-LD2420.

## Structure générale des topics

Le service utilise un topic de base configurable via le paramètre `--mqtt-topic` avec les variables suivantes :
- `$port` : Nom du port série (ex: `serial0`, `COM3`)  
- `$sn` : Numéro de série du module radar
- `$version` : Version du firmware du module

**Topic de base par défaut :** `radar/$sn`

## Topics de publication (envoyés par le service)

### 1. Status du service - `radar/{sn}/status`
**Type :** Retain = True  
**Fréquence :** Au démarrage et lors de changements d'état

```json
{
  "status": true,              // boolean - État de la connexion série
  "version": "v1.6.1",  // string - Version firmware du module
  "timestamp": "2025-11-18T10:30:00.123456", // string (ISO 8601)
  "port": "/dev/serial0",      // string - Port série utilisé
  "serial_number": "331861989698133498920968" // string - Numéro de série du module
}
```

### 2. Détection simple - `radar/{sn}/measurements/detection`
**Type :** Retain = True  
**Fréquence :** À chaque trame radar reçue

```json
{
  "detected": true,            // boolean - Présence détectée ou non
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 3. Distance de détection - `radar/{sn}/measurements/distance`
**Type :** Retain = True  
**Fréquence :** À chaque trame radar reçue

```json
{
  "distance_cm": 245,          // number - Distance en centimètres
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 4. Mesures complètes - `radar/{sn}/measurements`
**Type :** Retain = False  
**Fréquence :** À chaque trame radar reçue

```json
{
  "gates": [                   // array - Mesures des 16 portes de distance
    {
      "gate": 0,               // number (0-15) - Numéro de la porte
      "energy_db": 45.32,      // number - Énergie en décibels
      "energy_raw": 34021      // number - Valeur brute d'énergie
    },
    // ... 15 autres portes
  ],
  "detection": true,           // boolean - État de détection global
  "distance_cm": 245,          // number - Distance en centimètres
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 5. Mesures par porte - `radar/{sn}/measurements/gates`
**Type :** Retain = False  
**Fréquence :** À chaque trame radar reçue

```json
[
  {
    "gate": 0,                 // number (0-15) - Numéro de la porte
    "energy_db": 45.32,        // number - Énergie en décibels
    "energy_raw": 34021        // number - Valeur brute d'énergie
  },
  // ... 15 autres portes
]
```

### 6. Mesure individuelle par porte - `radar/{sn}/measurements/gates/{0-15}`
**Type :** Retain = False  
**Fréquence :** À chaque trame radar reçue

```json
{
  "energy_db": 45.32,          // number - Énergie en décibels
  "energy_raw": 34021,         // number - Valeur brute d'énergie
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 7. Résumé des paramètres - `radar/{sn}/parameters`
**Type :** Retain = True  
**Fréquence :** Au démarrage, après lecture des paramètres

```json
{
  "total_parameters": 35,      // number - Nombre total de paramètres
  "published_count": 35,       // number - Nombre de paramètres publiés avec succès
  "timestamp": "2025-11-18T10:30:00.123456", // string (ISO 8601)
  "status": "success"          // string - "success", "partial", ou "error"
}
```

### 8. Paramètres de distance et délai - `radar/{sn}/parameters/{param_name}`
**Topics :**
- `radar/{sn}/parameters/min_detection_door`
- `radar/{sn}/parameters/max_detection_door` 
- `radar/{sn}/parameters/delay_time`

**Type :** Retain = True  
**Fréquence :** Au démarrage et lors de modifications

```json
{
  "name": "Porte à distance minimale de détection", // string - Nom descriptif
  "value": 2,                  // number (0-15 pour portes, 0-65535 pour délai)
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 9. Seuils de déclenchement - `radar/{sn}/parameters/trigger_threshold/{0-15}`
**Type :** Retain = True  
**Fréquence :** Au démarrage et lors de modifications

```json
{
  "name": "Seuil de déclenchement 5", // string - Nom avec index
  "value_raw": 34021,          // number (0-4294967295) - Valeur brute
  "value_db": 45.32,           // number|null - Valeur en dB (null si raw=0)
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

### 10. Seuils de maintien - `radar/{sn}/parameters/maintain_threshold/{0-15}`
**Type :** Retain = True  
**Fréquence :** Au démarrage et lors de modifications

```json
{
  "name": "Seuil de maintien 12",     // string - Nom avec index
  "value_raw": 28456,          // number (0-4294967295) - Valeur brute
  "value_db": 44.54,           // number|null - Valeur en dB (null si raw=0)
  "timestamp": "2025-11-18T10:30:00.123456" // string (ISO 8601)
}
```

## Topics d'écoute (reçus par le service)

### 1. Redémarrage du module - `radar/{sn}/reboot`
**Payload :** Ignoré (n'importe quel contenu)  
**Action :** Redémarre complètement le module radar et réactive le mode debug

### 2. Modification des paramètres de distance/délai
**Topics :**
- `radar/{sn}/parameters/set/min_detection_door`
- `radar/{sn}/parameters/set/max_detection_door`
- `radar/{sn}/parameters/set/delay_time`

**Payload pour distances (0-15) :**
```json
{
  "value": 5                   // number - Nouvelle valeur (0-15 pour portes)
}
```

**Payload pour délai (0-65535) :**
```json
{
  "value": 1000                // number - Nouvelle valeur en millisecondes
}
```

### 3. Modification des seuils - `radar/{sn}/parameters/set/trigger_threshold/{0-15}`
### 4. Modification des seuils - `radar/{sn}/parameters/set/maintain_threshold/{0-15}`

**Payload option 1 (valeur brute) :**
```json
{
  "value_raw": 34021           // number (0-4294967295) - Valeur brute
}
```

**Payload option 2 (valeur en dB) :**
```json
{
  "value_db": 45.32            // number - Valeur en décibels (convertie automatiquement)
}
```

## Formules de conversion

**Raw vers dB :** `dB = 10 * log10(raw)`  
**dB vers Raw :** `raw = 10^(dB/10)`

## Wildcard topics utiles

- `radar/+/status` : Status de tous les modules
- `radar/+/measurements/detection` : Détections de tous les modules  
- `radar/+/parameters/trigger_threshold/+` : Tous les seuils de déclenchement
- `radar/+/parameters/set/#` : Toutes les commandes de modification
