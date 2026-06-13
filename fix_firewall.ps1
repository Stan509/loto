# ── Pare-feu Django ── À exécuter en tant qu'Administrateur ──
# Clic droit > Exécuter avec PowerShell (Admin)

Write-Host "Ajout règle pare-feu port 8000..." -ForegroundColor Yellow

netsh advfirewall firewall add rule `
  name="Django Dev Server 8000" `
  dir=in `
  action=allow `
  protocol=tcp `
  localport=8000

netsh advfirewall firewall add rule `
  name="Django Dev Server 8000 out" `
  dir=out `
  action=allow `
  protocol=tcp `
  localport=8000

Write-Host "OK ! Port 8000 autorisé dans les 2 sens." -ForegroundColor Green
Write-Host "Testez depuis le téléphone : http://10.0.0.56:8000/api/agent/health/" -ForegroundColor Cyan

Read-Host "Appuyez sur Entrée pour fermer"
