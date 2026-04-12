"""
Activity Tracker – Installationsscript
Installerar beroenden och konfigurerar autostart i Windows.
Kör med: python setup.py
"""

import subprocess
import sys
import os
from pathlib import Path


APP_DIR  = Path(__file__).parent.resolve()
DATA_DIR = Path.home() / "activity_tracker"
STARTUP_NAME = "ActivityTracker"


def pip_install(packages):
    print(f"  Installerar: {', '.join(packages)}")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet"] + packages
    )


def install_dependencies():
    print("\n[1/3] Installerar Python-beroenden...")
    pip_install(["flask", "pystray", "pillow"])
    print("  ✓ Klart")


def create_data_dir():
    print("\n[2/3] Skapar datamapp...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ {DATA_DIR}")


def setup_autostart():
    """Lägger till en .bat-fil i Windows Startup-mappen."""
    print("\n[3/3] Konfigurerar autostart...")

    startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    if not startup_dir.exists():
        print(f"  ⚠ Kunde inte hitta Startup-mapp: {startup_dir}")
        print("    Starta manuellt med: start.bat")
        return

    pythonw = Path(sys.executable).parent / "pythonw.exe"
    bat_content = f'@echo off\nstart "" "{pythonw}" "{APP_DIR / "tray_app.py"}"\n'
    bat_path = startup_dir / f"{STARTUP_NAME}.bat"
    bat_path.write_text(bat_content, encoding="utf-8")
    print(f"  ✓ Autostart: {bat_path}")


def create_start_bat():
    """Skapar en start.bat i app-mappen för manuell start."""
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    bat = APP_DIR / "start.bat"
    bat.write_text(
        f'@echo off\nstart "" "{pythonw}" "{APP_DIR / "tray_app.py"}"\n',
        encoding="utf-8"
    )
    print(f"\n  Manuell start: {bat}")


def main():
    print("=" * 50)
    print("   Activity Tracker – Installation")
    print("=" * 50)

    install_dependencies()
    create_data_dir()
    setup_autostart()
    create_start_bat()

    print("\n" + "=" * 50)
    print("  ✓ Installation klar!")
    print(f"\n  Data sparas i: {DATA_DIR}")
    print(f"  Starta nu:     {APP_DIR / 'start.bat'}")
    print(f"  Dashboard:     http://localhost:5757")
    print("=" * 50)

    input("\nTryck Enter för att starta trackern nu...")
    subprocess.Popen(
        [sys.executable, str(APP_DIR / "tray_app.py")],
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    )


if __name__ == "__main__":
    main()
