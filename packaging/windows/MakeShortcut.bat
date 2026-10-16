@echo off
rem Creates a "Nice VPN" shortcut on the Desktop with the app icon
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Nice VPN.lnk');$s.TargetPath='%~dp0NiceVPN.bat';$s.WorkingDirectory='%~dp0';$s.IconLocation='%~dp0runtime\Lib\site-packages\nicevpn\assets\icons\nicevpn.ico,0';$s.Save()"
echo Shortcut created on Desktop.
pause
