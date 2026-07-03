import os
import sys

# Force le parent C:\Projets en tête de sys.path avant tout import
_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if _root in sys.path:
    sys.path.remove(_root)
sys.path.insert(0, _root)

for _pkg in ('LarcCommon', 'LarcSuperviseur', 'LarcSecretaire'):
    _p = os.path.join(_root, _pkg)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

from LarcHub.main import main

if __name__ == '__main__':
    main()
