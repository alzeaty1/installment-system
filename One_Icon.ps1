$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [Environment]::GetFolderPath("Desktop")
$Project = "C:\Users\Elnour Tech\installment-system"

# Delete old shortcuts
$old = @("Start LAN Server.lnk", "Stop Server.lnk", "Check Status.lnk", 
         "Silent LAN Server.lnk", "Installment System Folder.lnk")
foreach ($f in $old) {
    $p = "$Desktop\$f"
    if (Test-Path $p) { Remove-Item $p -Force }
}

# Search for other old ones too
Get-ChildItem "$Desktop\*.lnk" | Where-Object { $_.Name -match "Installment|Start LAN|Network|Server" } | Remove-Item -Force

# Create ONE Smart Shortcut
$S = $WshShell.CreateShortcut("$Desktop\Installment System.lnk")
$S.TargetPath = "$Project\Start.bat"
$S.WorkingDirectory = $Project
$S.Description = "Start Installment System on LAN + Open Browser automatically"
$S.IconLocation = "%SystemRoot%\System32\shell32.dll,44"
$S.WindowStyle = 1
$S.Save()

Write-Host "Done! One icon created on Desktop:" -ForegroundColor Green
Write-Host "  Installment System.lnk" -ForegroundColor Cyan
Write-Host ""
Write-Host "Just double-click it - it will start the server and open browser automatically." -ForegroundColor Yellow
