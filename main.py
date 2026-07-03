import os
import sys
import traceback

_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

for _pkg in ('LarcCommon', 'LarcSuperviseur', 'LarcSecretaire'):
    _p = os.path.join(_root, _pkg)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from LarcHub.views.login import LoginWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName('LarcHub')
    app.setOrganizationName('Arc-en-Ciel')
    app.setStyle('Fusion')
    app.setFont(QFont('Segoe UI', 10))

    try:
        win = LoginWindow()
        win.show()
        app.exec()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        input("Appuyez sur Entrée pour quitter...")
        sys.exit(1)
