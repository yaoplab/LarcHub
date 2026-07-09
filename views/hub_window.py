from phibuilder.widgets import M3Button, M3Label, M3StackedWidget
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from larccommon.session import session
from larccommon.database import db, DBMode
from larccommon.theme import theme_manager


class _SectionButton(QPushButton):
    def __init__(self, label: str, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setFixedHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)

    def set_state(self, enabled: bool, visible: bool):
        self.setVisible(visible)
        self.setEnabled(enabled)


class HubWindow(QWidget):
    SIDEBAR_EXPANDED = 233
    SIDEBAR_COLLAPSED = 0

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"LarcHub — {session.full_name}")
        self.setMinimumSize(987, 610)

        self._sidebar_expanded = True
        self._sections: dict[str, dict] = {}
        self._current_section: str | None = None

        self._setup_ui()
        self._build_sections()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._check_connections)
        self._refresh_timer.start(30000)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self._sidebar = QWidget()
        self._sidebar.setFixedWidth(self.SIDEBAR_EXPANDED)
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setStyleSheet(f"""
            #sidebar {{
                background-color: {theme_manager.palette.surface_variant};
                border-right: 1px solid {theme_manager.palette.border};
            }}
        """)
        sb_layout = QVBoxLayout(self._sidebar)
        sb_layout.setContentsMargins(8, 34, 8, 13)
        sb_layout.setSpacing(5)

        # User info in sidebar
        self._user_label = M3Label(session.full_name or "Utilisateur")
        self._user_label.setStyleSheet(f"""
            font-size: 13px; font-weight: bold;
            color: {theme_manager.palette.text_strong};
            padding: 0 5px;
        """)
        sb_layout.addWidget(self._user_label)

        role_names = {
            'ADMIN': 'Administrateur',
            'COORD': 'Coordinateur',
            'SUPERVISEUR': 'Superviseur',
            'SECR': 'Secrétaire',
            'PROF': 'Enseignant',
        }
        self._role_label = M3Label(role_names.get(session.role.value, session.role.value))
        self._role_label.setStyleSheet(f"""
            font-size: 10px; color: {theme_manager.palette.text_secondary};
            padding: 0 5px 8px 5px;
        """)
        sb_layout.addWidget(self._role_label)

        sep = M3Label()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {theme_manager.palette.border};")
        sb_layout.addWidget(sep)
        sb_layout.addSpacing(8)

        self._btn_layout = QVBoxLayout()
        self._btn_layout.setSpacing(5)
        sb_layout.addLayout(self._btn_layout)
        sb_layout.addStretch()

        layout.addWidget(self._sidebar)

        # Toggle button — always visible, between sidebar and content
        self._toggle_btn = M3Button("◀")
        self._toggle_btn.setFixedSize(21, 55)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme_manager.palette.surface_variant};
                border: 1px solid {theme_manager.palette.border};
                border-left: none;
                border-radius: 0 4px 4px 0;
                font-size: 10px;
                color: {theme_manager.palette.text_strong};
                padding: 0 2px;
            }}
            QPushButton:hover {{
                background: {theme_manager.palette.border};
            }}
        """)
        self._toggle_btn.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self._toggle_btn)

        # Content area (right side)
        content = QWidget()
        content.setStyleSheet(f"background-color: {theme_manager.palette.background};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Header with section title
        self._section_title = M3Label()
        self._section_title.setStyleSheet(f"""
            font-size: 16px; font-weight: bold;
            color: {theme_manager.palette.text_strong};
            background-color: {theme_manager.palette.surface};
            padding: 13px 21px;
            border-bottom: 1px solid {theme_manager.palette.border};
        """)
        content_layout.addWidget(self._section_title)

        self._stack = M3StackedWidget()
        content_layout.addWidget(self._stack, 1)

        layout.addWidget(content, 1)

    def _toggle_sidebar(self):
        self._sidebar_expanded = not self._sidebar_expanded
        w = self.SIDEBAR_EXPANDED if self._sidebar_expanded else 0
        self._sidebar.setFixedWidth(w)
        self._toggle_btn.setText("▶" if not self._sidebar_expanded else "◀")

    def _build_sections(self):
        sections = []

        conn_ok = db.is_server_connected
        tf = getattr(session, 'type_flags', {}) or {}

        has_supervision = tf.get('supervisor') or tf.get('coordinator') or tf.get('director')
        sections.append(('supervision', 'Supervision', has_supervision, conn_ok))

        has_secretariat = tf.get('secretary') or tf.get('director')
        sections.append(('secretariat', 'Secrétariat', has_secretariat, conn_ok))

        has_coordination = tf.get('coordinator') or tf.get('director')
        sections.append(('coordination', 'Coordination', has_coordination, False))

        for key, label, has_role, enabled in sections:
            btn = _SectionButton(label)
            btn.clicked.connect(lambda checked, k=key: self._switch_to(k))
            btn.set_state(enabled=enabled and has_role, visible=has_role)
            if not enabled and has_role:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        color: {theme_manager.palette.text_secondary};
                        background: transparent;
                        border: none; text-align: left; padding: 8px 12px;
                    }}
                    QPushButton:hover {{ background: {theme_manager.palette.surface}; }}
                """)
            self._btn_layout.addWidget(btn)

            page = self._build_page(key, label)
            self._stack.addWidget(page)

            self._sections[key] = {
                'btn': btn,
                'page': page,
                'loaded': False,
            }

        for key, label, has_role, enabled in sections:
            if has_role and enabled:
                self._switch_to(key)
                break

    def _build_page(self, key: str, label: str):
        w = QWidget()
        return w

    def _switch_to(self, key: str):
        if key == self._current_section:
            return

        for info in self._sections.values():
            info['btn'].setChecked(False)

        info = self._sections.get(key)
        if not info:
            return

        info['btn'].setChecked(True)

        if not info['loaded']:
            self._load_section(key)
            info['loaded'] = True

        self._stack.setCurrentWidget(info['page'])
        self._current_section = key
        self._section_title.setText(info['btn'].text())

    def _load_section(self, key: str):
        info = self._sections.get(key)
        if not info:
            return

        try:
            if key == 'supervision':
                from LarcSuperviseur.views.main_window import MainWindow
                main_win = MainWindow()
            elif key == 'secretariat':
                from LarcSecretaire.views.main_window import MainWindow
                main_win = MainWindow()
            else:
                return

            idx = self._stack.indexOf(info['page'])
            self._stack.removeWidget(info['page'])
            info['page'].deleteLater()
            self._stack.insertWidget(idx, main_win)
            info['page'] = main_win
            self._stack.setCurrentWidget(main_win)
        except Exception as e:
            import traceback
            traceback.print_exc()
            lbl = M3Label(f"Erreur de chargement : {e}")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: red; font-size: 13px;")
            idx = self._stack.indexOf(info['page'])
            self._stack.removeWidget(info['page'])
            info['page'].deleteLater()
            self._stack.insertWidget(idx, lbl)
            info['page'] = lbl

    def _check_connections(self):
        conn_ok = db.is_server_connected
        for key, info in self._sections.items():
            has_role = info['btn'].isVisible()
            if has_role:
                info['btn'].setEnabled(conn_ok)
