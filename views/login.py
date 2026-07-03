import os
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

from larccommon.database import db, DBMode
from larccommon.session import AuthResult, ConnMode, session as sess
from larccommon.auth import AuthManager
from larccommon.network import detect_network
from larccommon.l10n import _
from larccommon.theme import theme_manager

from LarcHub.views.hub_window import HubWindow


class _Worker(QThread):
    done = Signal(object)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self.finished.connect(self.deleteLater)

    def run(self):
        try:
            self.done.emit(self._fn(*self._args))
        except Exception as exc:
            self.done.emit((False, None, str(exc)))


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._busy = False
        self.setWindowTitle("LarcHub — Arc-en-Ciel")
        self.setFixedSize(377, 610)
        self._setup_ui()
        QTimer.singleShot(100, self._check_network)

    def _setup_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(34, 34, 34, 21)
        vbox.setSpacing(13)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 '..', 'LarcSuperviseur', 'img', 'logoAEC.png')
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaledToHeight(55, Qt.SmoothTransformation)
            lbl = QLabel()
            lbl.setPixmap(pix)
            lbl.setAlignment(Qt.AlignCenter)
            vbox.addWidget(lbl)

        hdr = QLabel("LarcHub")
        hdr.setAlignment(Qt.AlignCenter)
        hdr.setStyleSheet(f"font-size: 21px; font-weight: bold; color: {theme_manager.palette.primary};")
        vbox.addWidget(hdr)

        sub = QLabel("Supervision · Secrétariat · Coordination")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"font-size: 11px; color: {theme_manager.palette.text_secondary};")
        vbox.addWidget(sub)

        self._tabs = QTabWidget()
        vbox.addWidget(self._tabs)

        self._tabs.addTab(self._tab_intranet(), "Intranet")
        self._tabs.addTab(self._tab_cloud(), "Cloud")

        self._error = QLabel()
        self._error.setAlignment(Qt.AlignCenter)
        self._error.setStyleSheet(f"color: {theme_manager.palette.danger}; font-size: 11px;")
        self._error.setVisible(False)
        vbox.addWidget(self._error)

        self._net_status = QLabel()
        self._net_status.setAlignment(Qt.AlignCenter)
        self._net_status.setStyleSheet(f"font-size: 10px; color: {theme_manager.palette.text_secondary};")
        vbox.addWidget(self._net_status)

    def _tab_intranet(self):
        w = QWidget()
        form = QVBoxLayout(w)
        form.setSpacing(8)

        self._i_email = QLineEdit()
        self._i_email.setPlaceholderText("Email @arc-en-ciel.org")
        self._i_email.setFixedHeight(34)
        self._i_email.setStyleSheet("padding: 0 12px;")
        form.addWidget(self._i_email)

        self._i_pass = QLineEdit()
        self._i_pass.setEchoMode(QLineEdit.Password)
        self._i_pass.setPlaceholderText("Mot de passe")
        self._i_pass.setFixedHeight(34)
        self._i_pass.setStyleSheet("padding: 0 12px;")
        form.addWidget(self._i_pass)

        btn = QPushButton("Connexion Intranet")
        btn.setFixedHeight(34)
        btn.clicked.connect(self._on_intranet)
        self._i_pass.returnPressed.connect(btn.click)
        form.addWidget(btn)

        form.addStretch()
        return w

    def _tab_cloud(self):
        w = QWidget()
        form = QVBoxLayout(w)
        form.setSpacing(8)

        lbl = QLabel("Connexion via Google Workspace @arc-en-ciel.org")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        form.addWidget(lbl)

        btn = QPushButton("Connexion Google")
        btn.setFixedHeight(34)
        btn.clicked.connect(self._on_cloud)
        form.addWidget(btn)

        form.addStretch()
        return w

    def _check_network(self):
        intra, internet = detect_network()
        status = []
        if intra:
            status.append("Intranet ●")
        if internet:
            status.append("Internet ●")
        self._net_status.setText("  ".join(status) if status else "Hors ligne")
        color = "#27ae60" if intra or internet else "#2c3e50"
        self._net_status.setStyleSheet(f"font-size: 10px; color: {color};")

    def _show_error(self, msg: str):
        self._error.setText(msg)
        self._error.setVisible(True)
        QTimer.singleShot(5000, lambda: self._error.setVisible(False))

    def _set_busy(self, busy: bool):
        self._busy = busy
        self._tabs.setEnabled(not busy)

    def _on_intranet(self):
        if self._busy:
            return
        email = self._i_email.text().strip()
        pwd = self._i_pass.text()
        if not email or not pwd:
            self._show_error("Email et mot de passe requis")
            return
        self._error.setVisible(False)
        self._set_busy(True)
        w = _Worker(self._connect_auth_intranet, email, pwd, parent=self)
        w.done.connect(lambda r: self._on_auth_result(r, 'intranet'))
        w.start()

    @staticmethod
    def _connect_auth_intranet(email: str, pwd: str):
        if not db.connect_intranet():
            return False, None, "Connexion à l'intranet impossible"
        return AuthManager.auth_intranet(email, pwd)

    def _on_cloud(self):
        if self._busy:
            return
        self._error.setVisible(False)
        self._set_busy(True)
        w = _Worker(self._connect_auth_cloud, parent=self)
        w.done.connect(lambda r: self._on_auth_result(r, 'cloud'))
        w.start()

    @staticmethod
    def _connect_auth_cloud():
        from larccommon.auth import OAuth2Manager
        if not db.connect_cloud():
            return False, None, "Connexion au cloud impossible"
        return OAuth2Manager.authenticate()

    def _on_auth_result(self, result, mode: str):
        self._set_busy(False)
        ok, res, err = result
        if not ok:
            self._show_error(err or "Authentification échouée")
            return

        if mode == 'intranet' and res.fk_language:
            os.environ['LARC_LANG'] = 'fr' if res.fk_language == 2 else 'en'

        sess.user_id = res.user_id
        sess.email = res.email
        sess.full_name = res.full_name
        sess.role = res.role
        sess.conn_mode = ConnMode.INTRANET if mode == 'intranet' else ConnMode.CLOUD
        sess.active_term_id = res.term_id
        sess.active_term_label = res.term_label

        # Store raw type_* flags from DB
        try:
            conn = db.server_conn
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT type_director, type_coordonator, type_supervisor, "
                        "type_secretary, type_teacher FROM larcauth_aecuser WHERE id = %s",
                        (res.user_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        sess.type_flags = {
                            'director': bool(row[0]),
                            'coordinator': bool(row[1]),
                            'supervisor': bool(row[2]),
                            'secretary': bool(row[3]),
                            'teacher': bool(row[4]),
                        }
        except Exception:
            sess.type_flags = {}

        self._open_hub(res)

    def _open_hub(self, res: AuthResult):
        self._hub = HubWindow()
        self._hub.showMaximized()
        self.close()
