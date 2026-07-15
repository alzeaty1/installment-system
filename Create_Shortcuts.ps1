# Create Desktop Shortcuts for Installment System

$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [Environment]::GetFolderPath("Desktop")
$Project = "C:\Users\Elnour Tech\installment-system"

# Windows built-in icon dll paths
$IconPlay  = "%SystemRoot%\System32\shell32.dll,14"
$IconStop  = "%SystemRoot%\System32\shell32.dll,15"
$IconInfo  = "%SystemRoot%\System32\shell32.dll,24"
$IconNet   = "%SystemRoot%\System32\shell32.dll,44"
$IconGlobe = "%SystemRoot%\System32\shell32.dll,239"

Write-Host "Creating Installment System shortcuts on Desktop..." -ForegroundColor Cyan
Write-Host ""

# 1. START LAN Server
$Shortcut = $WshShell.CreateShortcut("$Desktop\Start LAN Server.lnk")
$Shortcut.TargetPath = "$Project\Start LAN.bat"
$Shortcut.WorkingDirectory = $Project
$Shortcut.Description = "Start Installment System on your local network. Any device on same WiFi can access it."
$Shortcut.IconLocation = $IconNet
$Shortcut.WindowStyle = 1
$Shortcut.Save()
Write-Host "  [OK] Start LAN Server.lnk" -ForegroundColor Green

# 2. STOP Server
$Shortcut = $WshShell.CreateShortcut("$Desktop\Stop Server.lnk")
$Shortcut.TargetPath = "$Project\Stop Server.bat"
$Shortcut.WorkingDirectory = $Project
$Shortcut.Description = "Stop the Installment System server"
$Shortcut.IconLocation = $IconStop
$Shortcut.WindowStyle = 1
$Shortcut.Save()
Write-Host "  [OK] Stop Server.lnk" -ForegroundColor Green

# 3. CHECK Status
$Shortcut = $WshShell.CreateShortcut("$Desktop\Check Status.lnk")
$Shortcut.TargetPath = "$Project\Check Status.bat"
$Shortcut.WorkingDirectory = $Project
$Shortcut.Description = "Check if the server is running and get the LAN URL"
$Shortcut.IconLocation = $IconInfo
$Shortcut.WindowStyle = 1
$Shortcut.Save()
Write-Host "  [OK] Check Status.lnk" -ForegroundColor Green

# 4. SILENT LAN
$Shortcut = $WshShell.CreateShortcut("$Desktop\Silent LAN Server.lnk")
$Shortcut.TargetPath = "$Project\Silent LAN.bat"
$Shortcut.WorkingDirectory = $Project
$Shortcut.Description = "Start server silently in background with Windows notification"
$Shortcut.IconLocation = $IconGlobe
$Shortcut.WindowStyle = 7
$Shortcut.Save()
Write-Host "  [OK] Silent LAN Server.lnk" -ForegroundColor Green

# 5. Open Project Folder
$Shortcut = $WshShell.CreateShortcut("$Desktop\Installment System Folder.lnk")
$Shortcut.TargetPath = $Project
$Shortcut.WorkingDirectory = $Project
$Shortcut.Description = "Open the Installment System project folder"
$Shortcut.IconLocation = "%SystemRoot%\System32\shell32.dll,4"
$Shortcut.Save()
Write-Host "  [OK] Installment System Folder.lnk" -ForegroundColor Green

Write-Host ""
Write-Host "All shortcuts created successfully!" -ForegroundColor Cyan

# Get LAN IP
$pyCmd = 'import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(("8.8.8.8",80)); print(s.getsockname()[0]); s.close()'
$LAN_IP = & python -c $pyCmd
Write-Host "Your LAN IP: $LAN_IP" -ForegroundColor Yellow
Write-Host "Any device on same WiFi: http://${LAN_IP}:8000" -ForegroundColor Green

Write-Host ""
Write-Host "Press any key to close..." -ForegroundColor Gray
[void][System.Console]::ReadKey($true)
