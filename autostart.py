"""
"Start with Windows" via the per-user Run registry key
(HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run) - no admin rights
needed, no extra dependency (winreg is stdlib on Windows). A no-op on other
platforms.
"""
import os
import sys

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DexcomG7"


def is_supported():
    return sys.platform == "win32"


def startup_command():
    """The command line to register: the frozen .exe if packaged, else pythonw.exe + this script."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    interpreter = pythonw if os.path.exists(pythonw) else sys.executable
    script = os.path.abspath(sys.argv[0])
    return f'"{interpreter}" "{script}"'


def is_enabled():
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except FileNotFoundError:
        return False


def enable():
    if not is_supported():
        return
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())


def disable():
    if not is_supported():
        return
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
