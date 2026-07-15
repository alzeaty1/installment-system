Set WshShell = CreateObject("WScript.Shell")
strDesktop = WshShell.SpecialFolders("Desktop")
strProj = "C:\Users\Elnour Tech\installment-system"

' Start Shortcut
Set Shortcut = WshShell.CreateShortcut(strDesktop & "\Installment System - Start.lnk")
Shortcut.TargetPath = strProj & "\Start System.bat"
Shortcut.WorkingDirectory = strProj
Shortcut.Description = "Installment System Server — تشغيل السيرفر محلياً وعلى الشبكة مع شاشة تحكم"
Shortcut.WindowStyle = 1
Shortcut.Save

' Stop Shortcut
Set Shortcut = WshShell.CreateShortcut(strDesktop & "\Installment System - Stop.lnk")
Shortcut.TargetPath = strProj & "\Stop Server.bat"
Shortcut.WorkingDirectory = strProj
Shortcut.Description = "إيقاف السيرفر"
Shortcut.WindowStyle = 1
Shortcut.Save

' Startup Setup Shortcut
Set Shortcut = WshShell.CreateShortcut(strDesktop & "\Installment System - Startup.lnk")
Shortcut.TargetPath = strProj & "\Startup Setup.bat"
Shortcut.WorkingDirectory = strProj
Shortcut.Description = "إضافة أو إزالة التشغيل التلقائي مع بداية الجهاز"
Shortcut.WindowStyle = 1
Shortcut.Save
