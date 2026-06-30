# Plan d'implémentation

## 1. Système de code de confirmation (Inscription)
- Déjà existant dans `accounts/signup_api.py` (génère code 6 chiffres, envoie email)
- ✅ Fonctionnel: génération de token, email HTML, vérification

## 2. Système de récupération de compte/mot de passe (NOUVEAU)
- Créer API endpoint `POST /api/request-password-reset/` → génère code, l'envoie par email
- Créer API endpoint `POST /api/reset-password/` → vérifie code + expire, réinitialise mot de passe
- Email HTML pour la récupération de mot de passe

## 3. Correction Erreur 500 sur voir agent
- Analyser la vue `agent_detail` - problème potentiel: `request.user.borlette` 
- Problème: `_require_admin` utilise `get_user_borlette()` qui attrape les exceptions, mais `agent_detail` utilise `request.user.borlette` directement ce qui peut lancer une exception `RelatedObjectDoesNotExist`

## 4. Carte Leaflet localisation agent
- Vérifier si les fichiers statiques Leaflet existent (CSS/JS)
- Si non, utiliser CDN directement
- S'assurer que les coordonnées GPS sont bien envoyées dans l'API stats

## 5. Templates email
- Template HTML pour code de vérification
- Template HTML pour récupération mot de passe