# Script pour ajouter une règle de pare-feu pour le port 8000
# Ce script doit être exécuté avec des droits administrateur

# Vérifier si le script est exécuté avec des droits administrateur
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    # Si non, relancer le script avec des droits administrateur
    Start-Process powershell -Verb RunAs -ArgumentList "-File", "$PSCommandPath"
    exit
}

# Ajouter la règle de pare-feu
Write-Host "Ajout de la règle de pare-feu pour le port 8000..."
netsh advfirewall firewall add rule name="Django Server Port 8000" dir=in action=allow protocol=TCP localport=8000

Write-Host "Règle ajoutée avec succès!"
Write-Host "Appuyez sur n'importe quelle touche pour continuer..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
