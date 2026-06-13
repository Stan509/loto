# Tirage Scheduler — Configuration Windows Task Scheduler

## Vue d'ensemble

Le scheduler gère automatiquement le cycle des tirages :
- **Fermeture automatique** à l'heure prévue
- **Réouverture automatique** au prochain cycle
- **Rotation session_key** à chaque réouverture (les anciens résultats deviennent obsolètes)

## Commande de management

```bash
# Mode one-shot (recommandé pour Task Scheduler)
python manage.py run_tirage_scheduler --once

# Mode boucle (pour exécution en service)
python manage.py run_tirage_scheduler --interval 30

# Avec logs détaillés
python manage.py run_tirage_scheduler --once --verbose
```

## Configuration Windows Task Scheduler

### Étape 1 : Créer un script batch

Créer `C:\gaboom\run_scheduler.bat` :

```batch
@echo off
cd /d C:\Users\Réginald\Documents\Gaboom Central
call venv\Scripts\activate
python manage.py run_tirage_scheduler --once
```

### Étape 2 : Créer la tâche planifiée

1. Ouvrir **Planificateur de tâches** (Task Scheduler)
2. Cliquer **Créer une tâche de base**
3. Configurer :

| Paramètre | Valeur |
|-----------|--------|
| Nom | `Gaboom Tirage Scheduler` |
| Description | `Gère les cycles ouverture/fermeture des tirages` |
| Déclencheur | **Quotidien** à 00:00 |
| Répéter | Toutes les **1 minute** pendant **24 heures** |
| Action | Démarrer un programme |
| Programme | `C:\gaboom\run_scheduler.bat` |

### Étape 3 : Configuration avancée

Dans les **Propriétés** de la tâche :

**Onglet Général :**
- ☑️ Exécuter même si l'utilisateur n'est pas connecté
- ☑️ Exécuter avec les autorisations les plus élevées

**Onglet Paramètres :**
- ☑️ Autoriser l'exécution de la tâche à la demande
- ☑️ Arrêter la tâche si elle s'exécute plus de : 30 secondes
- ☐ Ne pas démarrer de nouvelle instance (évite doublons)

## Vérification

### Test manuel
```bash
python manage.py run_tirage_scheduler --once --verbose
```

### Vérifier les transitions
Dans la base de données, observer :
- `tirage.last_opened_at` — dernière ouverture
- `tirage.last_closed_at` — dernière fermeture
- `tirage.session_key` — change à chaque ouverture
- `tirage.cached_state` — état actuel mis en cache

### Logs
Les logs sont affichés dans la console :
```
[TirageScheduler] Démarrage (mode one-shot)
[14:30:00] Tirages: 5 | Ouverts: 2 | Fermés: 1
  ✓ [Midi] OUVERT | session: abc12345→def67890
  ✗ [Matin] FERMÉ | session: xyz98765
```

## Règles métier

1. **Ouverture** (`FERME` → `OUVERT`)
   - `session_key` = nouvelle UUID
   - `session_started_at` = maintenant
   - `last_opened_at` = maintenant
   - Les résultats de l'ancienne session restent en DB mais ne sont plus visibles

2. **Fermeture** (`OUVERT` → `FERME`)
   - `last_closed_at` = maintenant
   - `session_key` ne change PAS (on peut encore saisir les résultats)

3. **Résultats**
   - Saisie possible SEULEMENT si tirage fermé
   - Consultent `session_key` courant → nouveaux résultats vides après réouverture

## Alternative : Mode service

Pour une exécution continue sans Task Scheduler :

```bash
# Démarre en boucle infinie (Ctrl+C pour arrêter)
python manage.py run_tirage_scheduler --interval 30
```

Peut être configuré comme service Windows avec NSSM ou similaire.

## Dépannage

| Problème | Solution |
|----------|----------|
| Tirage ne se ferme pas | Vérifier `heure_fermeture` et `fermeture_auto=True` |
| session_key ne change pas | Vérifier `cached_state` et exécution du scheduler |
| Résultats visibles après réouverture | Bug : vérifier que l'endpoint filtre par `session_key` |
| Erreur Django introuvable | Activer le venv avant d'exécuter |
