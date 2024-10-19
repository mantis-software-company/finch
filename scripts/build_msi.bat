
set "target_version=%~1"

REM Include win32ctypes and keyring backend modules manually
cxfreeze build_exe --includes=keyring.backends.SecretService,keyring.backends.libsecret,keyring.backends.chainer,keyring.backends.Windows,keyring.backends.kwallet,keyring.backends.macOS,win32ctypes.core.ctypes._authentication,win32ctypes.core.ctypes._common,win32ctypes.core.ctypes._dll,win32ctypes.core.ctypes._nl_support,win32ctypes.core.ctypes._resource,win32ctypes.core.ctypes._system_information,win32ctypes.core.ctypes._time,win32ctypes.core.ctypes._util

REM Build MSI
cxfreeze bdist_msi --skip-build
move dist\*.msi "dist\finch-%target_version%-windows-x86_64.msi"
