# Android Release Build Guide

Guide complet pour créer un APK release signé de Gaboom Agent, installable sur tous les POS Android.

## Prérequis

- **Java JDK 17** installé
- **Android Studio** ou **Gradle CLI**
- Terminal (PowerShell sur Windows)

---

## 1. Générer un Keystore (première fois seulement)

### Windows (PowerShell)

```powershell
cd android_app

# Générer le keystore
keytool -genkeypair -v -keystore release-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias gaboom-agent
```

Répondez aux questions :
- **Mot de passe keystore** : Choisissez un mot de passe fort (ex: `G@b00m2025!`)
- **Prénom et nom** : `Gaboom Central`
- **Unité organisationnelle** : `IT`
- **Organisation** : `Gaboom`
- **Ville** : Votre ville
- **Province** : Votre province
- **Code pays** : `HT` (Haïti)

⚠️ **IMPORTANT** : Gardez le keystore et les mots de passe en lieu sûr. Si vous les perdez, vous ne pourrez plus mettre à jour l'app.

---

## 2. Configurer les credentials

### Créer keystore.properties

```powershell
cd android_app
copy keystore.properties.example keystore.properties
```

Éditez `keystore.properties` avec vos valeurs :

```properties
storeFile=release-keystore.jks
storePassword=votre_mot_de_passe_keystore
keyAlias=gaboom-agent
keyPassword=votre_mot_de_passe_cle
```

⚠️ **Ne commitez JAMAIS ce fichier dans git !**

---

## 3. Build APK Release

### Option A : Via Android Studio

1. Ouvrir `android_app` dans Android Studio
2. Menu **Build** → **Build Bundle(s) / APK(s)** → **Build APK(s)**
3. Attendre la compilation
4. Cliquer sur **locate** dans la notification pour trouver l'APK

### Option B : Via Gradle CLI

```powershell
cd android_app

# Windows
.\gradlew.bat assembleRelease

# Linux/Mac
./gradlew assembleRelease
```

### Emplacement de l'APK

```
android_app/app/build/outputs/apk/release/app-release.apk
```

---

## 4. Installation sur POS Android

### Préparer le POS

1. Aller dans **Paramètres** → **Sécurité**
2. Activer **Sources inconnues** (ou **Installer apps inconnues**)

### Méthodes d'installation

#### Via USB

```powershell
# Connecter le POS en USB (mode débogage activé)
adb install app/build/outputs/apk/release/app-release.apk
```

#### Via fichier

1. Copier `app-release.apk` sur une clé USB ou carte SD
2. Sur le POS, ouvrir un gestionnaire de fichiers
3. Naviguer vers l'APK et taper dessus pour installer

#### Via réseau local

1. Héberger l'APK sur un serveur local
2. Sur le POS, ouvrir le navigateur
3. Télécharger l'APK depuis `http://[votre-ip]/app-release.apk`
4. Ouvrir le fichier téléchargé pour installer

---

## 5. Configuration initiale de l'app

### Premier lancement

1. **Ouvrir l'app** Gaboom Agent
2. **Taper sur l'icône ⚙️** (Paramètres) en haut à droite
3. **Configurer l'URL du serveur** :
   - Format : `http://[IP-SERVEUR]:[PORT]/api/agent/`
   - Exemple : `http://192.168.1.100:8000/api/agent/`
4. **Tester la connexion** (bouton "Tester")
5. **Sauvegarder** si le test réussit
6. **Retour** et **Se connecter** avec les identifiants agent

### Obtenir l'IP du serveur

Sur le serveur Django (Windows PowerShell) :

```powershell
ipconfig | findstr "IPv4"
```

Sur le serveur Django (Linux/Mac) :

```bash
ip addr | grep "inet " | grep -v 127.0.0.1
```

---

## 6. Checklist de test

Après installation, vérifier ces fonctionnalités :

- [ ] **Login** : Connexion avec identifiants agent
- [ ] **Tirages** : Liste des tirages affichée
- [ ] **Vente** : Créer un ticket simple (boule)
- [ ] **Multi-tirage** : Créer ticket sur plusieurs tirages
- [ ] **Impression** : Test impression Bluetooth
- [ ] **Recherche** : Trouver un ticket par numéro
- [ ] **Paiement** : Payer un ticket gagnant
- [ ] **Annulation** : Annuler un ticket (<7 min)
- [ ] **Historique** : Voir les tickets créés
- [ ] **Résultats** : Afficher les derniers résultats
- [ ] **Stats** : Voir les statistiques agent
- [ ] **Paramètres** : Changer l'URL et tester

---

## 7. Dépannage

### "Connexion refusée" dans le test

- Vérifier que le serveur Django tourne
- Vérifier que le pare-feu autorise le port (généralement 8000)
- Vérifier que le POS et le serveur sont sur le même réseau

### "Timeout" dans le test

- L'adresse IP est peut-être incorrecte
- Le serveur met trop de temps à répondre

### "Erreur SSL"

- Utiliser `http://` au lieu de `https://` pour le développement local
- Pour la production, configurer un certificat SSL valide

### L'app plante au démarrage

- Désinstaller et réinstaller
- Vérifier que le POS a Android 7.0+ (API 24)

---

## 8. Mise à jour de l'app

1. Incrémenter `versionCode` et `versionName` dans `app/build.gradle.kts`
2. Rebuild l'APK release
3. Installer la nouvelle version (elle remplacera l'ancienne)

```kotlin
// Dans defaultConfig
versionCode = 2
versionName = "1.1.0"
```

---

## Versions

| Version | Date | Changements |
|---------|------|-------------|
| 1.0.0 | Février 2025 | Version initiale avec URL dynamique |

---

## Support

Pour toute question, contacter l'administrateur Gaboom Central.
