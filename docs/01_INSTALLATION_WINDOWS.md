# Windows installation

LockIn 1.0.0 supports Windows 10/11 x64. Download the installer and `SHA256SUMS.txt` from the
private GitHub Release. Verify it with:

```powershell
Get-FileHash .\LockIn-Setup-v1.0.0.exe -Algorithm SHA256
```

Compare the lowercase result with `SHA256SUMS.txt`, then run the installer. It is per-user, requires
no administrator access, installs under `%LOCALAPPDATA%\Programs\LockIn`, creates a Start Menu
shortcut, and optionally creates a desktop shortcut. LockIn is unsigned, so SmartScreen may warn.

The portable ZIP must be fully extracted. Run `LockIn\LockIn.exe`; do not move the executable away
from its `_internal` folder. Both variants keep user data outside the application directory.

Uninstall through Windows Apps or `unins000.exe`. Program files and shortcuts are removed, but
runtime and portable history are retained. Reinstallation or upgrade safely replaces program files.
Use **Settings > Use Existing Portable Data** when moving history from another device.
