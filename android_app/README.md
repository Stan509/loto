# Gaboom Agent - Application Android

Application native Android pour les agents de vente Borlette.

## Stack Technique

- **Kotlin** - Langage principal
- **Jetpack Compose** - UI moderne déclarative
- **Room** - Base de données locale (cache offline)
- **Retrofit** - Client HTTP pour API REST
- **OkHttp** - WebSocket pour temps réel
- **Hilt** - Injection de dépendances
- **ESC/POS** - Impression thermique universelle

## Architecture

```
app/
├── data/
│   ├── api/          # Retrofit services
│   ├── db/           # Room database
│   ├── repository/   # Data repositories
│   └── websocket/    # WebSocket client
├── domain/
│   ├── model/        # Domain models
│   └── usecase/      # Business logic
├── ui/
│   ├── auth/         # Login screen
│   ├── tirages/      # Active draws
│   ├── vente/        # Ticket sale
│   ├── historique/   # History
│   ├── resultats/    # Results
│   └── stats/        # Personal stats
├── print/            # ESC/POS printing
└── di/               # Dependency injection
```

## Fonctionnalités

1. **Authentification** - Login avec JWT
2. **Tirages actifs** - Liste des tirages ouverts
3. **Vente ticket** - Sélection jeux, validation, impression
4. **Historique** - Tickets vendus
5. **Résultats** - Résultats des tirages
6. **Statistiques** - Performance agent

## Impression

Support universel pour imprimantes thermiques Android:
- Bluetooth ESC/POS (générique)
- USB ESC/POS
- SDK constructeur (optionnel)

## Configuration API

```kotlin
object ApiConfig {
    const val BASE_URL = "http://192.168.1.x:8000/api/agent/"
    const val WS_URL = "ws://192.168.1.x:8000/ws/agent/"
}
```

## Build

```bash
./gradlew assembleDebug
```

## Notes

- L'app fonctionne en mode offline avec cache Room
- Synchronisation automatique via WebSocket
- Isolation stricte par borlette (données filtrées côté serveur)
