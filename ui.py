import os, json, requests
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QGridLayout, QFileDialog, QMessageBox,
    QProgressBar, QRadioButton, QButtonGroup, QGroupBox, QCheckBox,
    QListWidget, QListWidgetItem, QStackedWidget, QTabWidget,
    QApplication, QSizePolicy, QSpacerItem,
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThreadPool, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor, QPalette

import utils
from workers import (
    CancellableDlWorker, DownloadWorker, ManifestWorker,
    ImgWorker, LibraryGameWorker, DeleteGameWorker,
    OFSearchWorker, OFAppIdWorker, OFIconWorker, OFDownloadWorker,
)

COLS = 3
GAP = 10
JSON_URL = "https://raw.githubusercontent.com/857seif/games-bypass/main/fixes.json"


class DlDialog(QFrame):
    def __init__(self, name, worker, parent=None):
        super().__init__(parent)
        self.worker = worker
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(460, 280)

        outer = QFrame()
        outer.setStyleSheet("QFrame{background:#0f0f12;border:1px solid #2a2a32;border-radius:20px;}")
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel(f"Download: {name}")
        title.setStyleSheet("color:#e8e8f0;font-size:16px;font-weight:bold;border:none;")
        layout.addWidget(title)

        self.st_lbl = QLabel("Starting...")
        self.st_lbl.setStyleSheet("color:#9ca3af;font-size:12px;border:none;")
        layout.addWidget(self.st_lbl)

        self.bar = QProgressBar()
        self.bar.setFixedHeight(22)
        self.bar.setTextVisible(True)
        self.bar.setAlignment(Qt.AlignCenter)
        self.bar.setStyleSheet("""
            QProgressBar {
                background-color: #11111a;
                border: 1px solid #2e2e48;
                border-radius: 11px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:0.5 #3b82f6, stop:1 #10b981);
                border-radius: 10px;
            }
        """)
        layout.addWidget(self.bar)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton{background:#7f1d1d;color:#fca5a5;border:none;border-radius:8px;padding:8px;font-weight:bold;}
            QPushButton:hover{background:#991b1b;}
        """)
        self.cancel_btn.clicked.connect(self.cancel_download)
        layout.addWidget(self.cancel_btn)

        v = QVBoxLayout(self)
        v.addWidget(outer)

        worker.sig.progress.connect(self.set_progress)
        worker.sig.status.connect(self.st_lbl.setText)
        worker.sig.finished.connect(lambda ok, msg: self.show_success() if ok else self.show_cancelled())
        worker.sig.cancelled.connect(self.show_cancelled)

    def set_progress(self, val):
        self.bar.setValue(val)

    def show_success(self):
        self.cancel_btn.setText("Done")
        self.cancel_btn.setStyleSheet("""
            QPushButton{background:#065f46;color:#6ee7b7;border:none;border-radius:8px;padding:8px;font-weight:bold;}
            QPushButton:hover{background:#047857;}
        """)
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.close)
        self.st_lbl.setText("Download completed!")
        self.bar.setValue(100)

    def show_cancelled(self):
        self.cancel_btn.setText("Close")
        self.cancel_btn.setStyleSheet("""
            QPushButton{background:#2a2a42;color:#9ca3af;border:none;border-radius:8px;padding:8px;font-weight:bold;}
            QPushButton:hover{background:#3a3a5a;}
        """)
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.close)
        self.st_lbl.setText("Download cancelled")
        self.bar.setValue(0)

    def cancel_download(self):
        self.st_lbl.setText("Cancelling...")
        self.worker.cancel()

    def center_on(self, parent):
        if parent:
            self.move(
                parent.x() + (parent.width() - self.width()) // 2,
                parent.y() + (parent.height() - self.height()) // 2,
            )


class JSONManager:
    @staticmethod
    def load():
        r = requests.get(JSON_URL, timeout=15, verify=False)
        return r.json()


class Card(QFrame):
    def __init__(self, data, cw, parent=None):
        super().__init__(parent)
        self.data = data
        self.cw = cw
        self.setObjectName("Card")
        self.setFixedWidth(cw)
        self.setMinimumHeight(340)
        self.pool = QThreadPool.globalInstance()
        self._dlg = None

        self.setStyleSheet("""
            QFrame#Card {
                background: #14141f;
                border: 1px solid #232335;
                border-radius: 16px;
            }
            QFrame#Card:hover {
                border: 1px solid #7c3aed;
                background: #181829;
            }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # Game Icon/Picture
        appid = data.get("appid", "0")
        self.icon = QLabel()
        self.icon.setFixedSize(cw - 28, 120)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setStyleSheet("background: #101017; border-radius: 10px;")
        lay.addWidget(self.icon, alignment=Qt.AlignCenter)

        # Game name
        name = data.get("name", "Unknown")
        self.lbl_name = QLabel(name)
        self.lbl_name.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_name.setStyleSheet("color: #f3f4f6;")
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_name)

        # AppID
        self.lbl_appid = QLabel(f"AppID: {appid}")
        self.lbl_appid.setStyleSheet("color: #6b7280; font-size: 10px;")
        self.lbl_appid.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_appid)

        lay.addSpacing(4)

        # Fixes list
        fixes = data.get("fixes", [])
        if fixes:
            for fx in fixes:
                url = fx.get("href", "")
                filename = fx.get("filename", "Bypass Package")
                size = fx.get("size", "Unknown size")
                badges = fx.get("badges", [])
                badge_text = f" [{', '.join(badges)}]" if badges else ""
                
                # Size details label
                lbl_size = QLabel(f"Size: {size}{badge_text}")
                lbl_size.setStyleSheet("color: #9ca3af; font-size: 11px;")
                lbl_size.setWordWrap(True)
                lbl_size.setAlignment(Qt.AlignCenter)
                lay.addWidget(lbl_size)
                
                # Download Button for this fix
                btn = QPushButton("↓ Download")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setFixedHeight(34)
                btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #4c1d95, stop:1 #6d28d9);
                        color: #ede9fe;
                        border: 1px solid #7c3aed;
                        border-radius: 8px;
                        font-weight: 500;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #5b21b6, stop:1 #7c3aed);
                        border-color: #a78bfa;
                    }
                    QPushButton:pressed {
                        background: #3b0764;
                    }
                """)
                btn.clicked.connect(self._mk(url))
                lay.addWidget(btn)
                
                lay.addSpacing(4)
        else:
            lbl = QLabel("No fixes available")
            lbl.setStyleSheet("color: #4b5563; font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(lbl)
            
        lay.addStretch()

        # Load image asynchronously
        worker = ImgWorker(appid)
        worker.sig.loaded.connect(self._set_icon)
        self.pool.start(worker)

    def _set_icon(self, key, pix):
        if not pix.isNull():
            self.icon.setPixmap(pix.scaled(self.cw - 28, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _mk(self, url):
        return lambda: self._dl(url)

    def _dl(self, url):
        if not url:
            QMessageBox.warning(self, "Error", "Invalid link.")
            return
        dest = QFileDialog.getExistingDirectory(self, "Choose destination")
        if not dest:
            return
        worker = CancellableDlWorker(url, dest)
        self._dlg = DlDialog(self.data.get("name", "Fix"), worker, self.window())
        self._dlg.center_on(self.window())
        self._dlg.show()
        
        # Save worker reference on MainWindow to prevent GC
        main_win = self.window()
        if hasattr(main_win, "_wk"):
            main_win._wk.append(worker)
            
        worker.sig.progress.connect(self._dlg.set_progress)
        worker.sig.finished.connect(lambda ok, info: self._done(ok, info))
        worker.sig.cancelled.connect(self._dlg.show_cancelled)
        
        self.pool.start(worker)

    def _done(self, ok, info):
        if ok:
            if self._dlg:
                self._dlg.show_success()
        else:
            if self._dlg:
                self._dlg.close()
            QMessageBox.critical(self, "Failed", str(info))


class BypassTab(QWidget):
    def __init__(self):
        super().__init__()
        self.all_games = []
        self.cur = []
        self._last_cw = 0
        self._rtimer = QTimer()
        self._rtimer.setSingleShot(True)
        self._rtimer.timeout.connect(self._rebuild)
        self._setup_ui()

    def _setup_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games by name or AppID...")
        self.search.setStyleSheet("""
            QLineEdit {
                background: #1a1a28; border: 1px solid #2a2a42;
                border-radius: 10px; padding: 10px 16px;
                color: #f0f0f8; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #7c3aed; }
        """)
        self.search.textChanged.connect(self._filter)
        top.addWidget(self.search)

        self.cnt = QLabel("0 Games")
        self.cnt.setStyleSheet("color: #9ca3af; font-size: 12px; padding: 0 8px;")
        top.addWidget(self.cnt)
        v.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #0a0a10; width: 8px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #2a2a42; border-radius: 4px; }
        """)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(GAP)
        self.scroll.setWidget(self.container)
        v.addWidget(self.scroll)

    def _cw(self):
        viewport_w = self.scroll.viewport().width()
        vw = max(180, (viewport_w - GAP * (COLS + 1)) // COLS)
        return vw

    def _rebuild(self, force=False):
        vw = self._cw()
        if abs(vw - self._last_cw) <= 5 and not force:
            print(f"DEBUG _rebuild: skipped, vw={vw} close to _last_cw={self._last_cw}")
            return
        self._last_cw = vw
        
        print(f"DEBUG _rebuild: starting build, force={force}, cur_len={len(self.cur)}, vw={vw}")
        
        self.setUpdatesEnabled(False)
        try:
            # Clear layout
            while self.grid.count():
                item = self.grid.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
                    w.deleteLater()
            
            # Rebuild cards
            row = col = 0
            for i, item in enumerate(self.cur):
                card = Card(item, vw, self.container)
                self.grid.addWidget(card, row, col)
                col += 1
                if col >= COLS:
                    col = 0
                    row += 1
                if i % 10 == 0:
                    QApplication.processEvents()
        except Exception as e:
            print(f"DEBUG _rebuild error: {e}")
        finally:
            self.setUpdatesEnabled(True)
            
        self.cnt.setText(f"{len(self.cur)} Games")
        print(f"DEBUG _rebuild: completed, cnt text: {self.cnt.text()}")

    def load_data(self):
        self.cnt.setText("Loading...")
        QTimer.singleShot(100, self._do_load)

    def _do_load(self):
        try:
            data = JSONManager.load()
            print("DEBUG _do_load: data fetched, len =", len(data) if isinstance(data, list) else "not list")
            self.all_games = data if isinstance(data, list) else data.get("games", [])
            self.cur = self.all_games[:]
            self._rebuild(force=True)
        except Exception as e:
            print("DEBUG _do_load error:", e)
            self.cnt.setText(f"Load error: {e}")

    def _filter(self, txt):
        t = txt.lower().strip()
        print(f"DEBUG _filter: txt={repr(txt)}, t={repr(t)}, all_games_len={len(self.all_games)}")
        if not t:
            self.cur = self.all_games[:]
        else:
            self.cur = [
                g for g in self.all_games
                if t in str(g.get("name", "")).lower()
                or t in str(g.get("appid", ""))
            ]
        self._rebuild(force=True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rtimer.start(200)


class StyledDownloadTab(QWidget):
    def __init__(self, title, description, button_text, icon=None):
        super().__init__()
        self.default_button_text = button_text
        self._setup_ui(title, description, button_text)

    def _setup_ui(self, title, description, button_text):
        v = QVBoxLayout(self)
        v.setContentsMargins(32, 24, 32, 24)
        v.setSpacing(16)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_lbl.setStyleSheet("color: #f0f0f8;")
        v.addWidget(title_lbl)

        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #9ca3af; font-size: 13px;")
        v.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #25253a;")
        v.addWidget(sep)

        self.download_btn = QPushButton(button_text)
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setFixedHeight(44)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6d28d9, stop:1 #7c3aed);
                color: white; border: none; border-radius: 12px;
                font-size: 14px; font-weight: bold; padding: 0 24px;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #7c3aed, stop:1 #8b5cf6); }
            QPushButton:disabled { background: #2a2a3a; color: #6b7280; }
        """)
        self.download_btn.clicked.connect(self.start_download)
        v.addWidget(self.download_btn)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(22)
        self.progress.setTextVisible(True)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #11111a;
                border: 1px solid #2e2e48;
                border-radius: 11px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:0.5 #3b82f6, stop:1 #10b981);
                border-radius: 10px;
            }
        """)
        self.progress.hide()
        v.addWidget(self.progress)

        self.status_label = QLabel("Click the button above to start.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #6b7280; font-size: 12px; padding: 4px 0;")
        v.addWidget(self.status_label)

        v.addStretch()

    def start_download(self):
        raise NotImplementedError

    def reset_ui(self):
        self.download_btn.setEnabled(True)
        self.download_btn.setText(self.default_button_text)
        self.progress.setValue(0)
        self.progress.hide()





class CrackTab(StyledDownloadTab):
    def __init__(self):
        super().__init__(
            "Steam Fox DRM Unlocker",
            "Download and extract the Steam Fox DRM Unlocker package to bypass DRM protection.",
            "Download & Extract Package",
        )
        self.worker = None

    def start_download(self):
        folder = QFileDialog.getExistingDirectory(self, "Select extraction folder")
        if not folder:
            self.status_label.setText("No folder selected.")
            return
        self.download_btn.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        self.status_label.setText("Downloading...")
        self.worker = DownloadWorker(
            "https://raw.githubusercontent.com/857seif/steam-fox-drm-unloacker/main/steam%20fox%20drm%20unloacker.zip",
            folder, extract_to=folder,
        )
        self.worker.sig.status.connect(self.status_label.setText)
        self.worker.sig.progress.connect(self.progress.setValue)
        self.worker.sig.finished.connect(self.download_finished)
        QThreadPool.globalInstance().start(self.worker)

    def download_finished(self, success, result):
        self.reset_ui()
        if success:
            self.status_label.setText(f"Extracted to: {result}")
            self.progress.setValue(100)
            os.startfile(result)
        else:
            self.status_label.setText(f"Extraction failed: {result}")


# ──────────────────────────────────────────────────────────────────────────────
# Online Fix — Search, card-list, and auto-download tab
# ──────────────────────────────────────────────────────────────────────────────

class _OFGameCard(QFrame):
    """A single game row: thumbnail on the left, title on the right."""
    selected = pyqtSignal(dict)

    _PLACEHOLDER = (
        b'<svg width="80" height="44" xmlns="http://www.w3.org/2000/svg">'
        b'<rect width="80" height="44" rx="6" fill="#1a1a2e"/>'
        b'<text x="50%" y="55%" font-size="9" fill="#4b5563"'
        b' text-anchor="middle" dominant-baseline="middle"'
        b' font-family="Segoe UI">...</text></svg>'
    )

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game      = game
        self._selected = False
        self.setFixedHeight(62)
        self.setCursor(Qt.PointingHandCursor)
        self._style(False)

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 8, 14, 8)
        h.setSpacing(12)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(80, 44)
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet("border-radius:5px; background:#1a1a2e;")
        pix = QPixmap()
        pix.loadFromData(self._PLACEHOLDER, "SVG")
        if not pix.isNull():
            self.icon_lbl.setPixmap(pix)
        h.addWidget(self.icon_lbl)

        self.title_lbl = QLabel(game["title"])
        self.title_lbl.setFont(QFont("Segoe UI", 11))
        self.title_lbl.setStyleSheet("color:#ddd8fe; background:transparent;")
        h.addWidget(self.title_lbl, 1)

    def set_icon(self, pix):
        self.icon_lbl.setPixmap(pix)

    def set_selected(self, sel):
        self._selected = sel
        self._style(sel)

    def _style(self, sel):
        if sel:
            self.setStyleSheet(
                "QFrame{background:#2d1a6e;border:1.5px solid #7c3aed;border-radius:10px;}"
            )
        else:
            self.setStyleSheet(
                "QFrame{background:#13131d;border:1px solid #1e1e2f;border-radius:10px;}"
                "QFrame:hover{background:#1a1a2c;border:1px solid #4c1d95;}"
            )

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.selected.emit(self.game)
        super().mousePressEvent(ev)


class OnlineFixTab(QWidget):
    """Search online-fix.me, pick a game, download + extract directly into the game folder."""

    def __init__(self):
        super().__init__()
        self._cards        = []
        self._sel_card     = None
        self._sel_game     = None
        self._pool         = QThreadPool.globalInstance()
        self._setup_ui()

    # ── UI layout ────────────────────────────────────────────────────────────
    def _setup_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 20, 28, 20)
        v.setSpacing(14)

        # Header
        ttl = QLabel("Online Fix  —  Search & Auto-Downloader")
        ttl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        ttl.setStyleSheet("color:#f0f0f8;")
        v.addWidget(ttl)

        sub = QLabel("Type a game name, select from the results, then click Download.")
        sub.setStyleSheet("color:#6b7280; font-size:12px;")
        v.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#1e1e2f;")
        v.addWidget(sep)

        # Search row
        h_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Game name (e.g. Repo, Barotrauma, Elden Ring)…")
        self.search_input.setStyleSheet(
            "QLineEdit{background:#14141c;border:1px solid #25253a;border-radius:8px;"
            "padding:9px 14px;color:#f0f0f8;font-size:13px;}"
            "QLineEdit:focus{border:1px solid #7c3aed;}"
        )
        self.search_input.returnPressed.connect(self._start_search)
        h_row.addWidget(self.search_input)

        self.search_btn = QPushButton("Search")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.setFixedWidth(110)
        self.search_btn.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6d28d9,stop:1 #7c3aed);color:#fff;border:none;"
            "border-radius:8px;padding:9px 18px;font-weight:bold;font-size:13px;}"
            "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #7c3aed,stop:1 #8b5cf6);}"
            "QPushButton:disabled{background:#1e1e28;color:#4b5563;}"
        )
        self.search_btn.clicked.connect(self._start_search)
        h_row.addWidget(self.search_btn)
        v.addLayout(h_row)

        # Cards scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea{background:#0f0f14;border:1px solid #1e1e2f;border-radius:12px;}"
            "QScrollBar:vertical{background:#0f0f14;width:6px;border-radius:3px;}"
            "QScrollBar::handle:vertical{background:#3b3b5c;border-radius:3px;min-height:20px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        self._container = QWidget()
        self._container.setStyleSheet("background:#0f0f14;")
        self._clist = QVBoxLayout(self._container)
        self._clist.setContentsMargins(8, 8, 8, 8)
        self._clist.setSpacing(6)
        self._clist.addStretch()
        self.scroll.setWidget(self._container)
        v.addWidget(self.scroll, 1)

        # Status + progress
        self.status_lbl = QLabel("Search for a game to begin.")
        self.status_lbl.setStyleSheet("color:#9ca3af;font-size:12px;")
        v.addWidget(self.status_lbl)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(22)
        self.progress.setTextVisible(True)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet(
            "QProgressBar{background:#11111a;border:1px solid #2e2e48;"
            "border-radius:11px;text-align:center;color:#fff;font-weight:bold;font-size:11px;}"
            "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #7c3aed,stop:0.5 #3b82f6,stop:1 #10b981);border-radius:10px;}"
        )
        self.progress.hide()
        v.addWidget(self.progress)

        # Download button
        self.dl_btn = QPushButton("⬇  Download & Extract into Game Folder")
        self.dl_btn.setCursor(Qt.PointingHandCursor)
        self.dl_btn.setEnabled(False)
        self.dl_btn.setFixedHeight(46)
        self.dl_btn.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6d28d9,stop:1 #7c3aed);color:#fff;border:none;"
            "border-radius:10px;font-weight:bold;font-size:13px;}"
            "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #7c3aed,stop:1 #8b5cf6);}"
            "QPushButton:disabled{background:#1e1e28;color:#4b5563;}"
        )
        self.dl_btn.clicked.connect(self._start_download)
        v.addWidget(self.dl_btn)

    # ── Cards helpers ─────────────────────────────────────────────────────────
    def _clear_cards(self):
        while self._clist.count() > 1:
            item = self._clist.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()
        self._sel_card = None
        self._sel_game = None
        self.dl_btn.setEnabled(False)

    def _add_card(self, game):
        card = _OFGameCard(game, self._container)
        card.selected.connect(self._on_card_clicked)
        self._clist.insertWidget(self._clist.count() - 1, card)
        self._cards.append(card)
        return card

    def _on_card_clicked(self, game):
        if self._sel_card:
            self._sel_card.set_selected(False)
        for c in self._cards:
            if c.game["url"] == game["url"]:
                c.set_selected(True)
                self._sel_card = c
                break
        self._sel_game = game
        self.dl_btn.setEnabled(True)

    # ── Search ────────────────────────────────────────────────────────────────
    def _start_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)
        self.dl_btn.setEnabled(False)
        self._clear_cards()
        self.status_lbl.setText("Searching online-fix.me…")

        w = OFSearchWorker(query)
        w.sig.finished.connect(self._on_search_done)
        w.sig.error.connect(self._on_search_err)
        self._pool.start(w)

    def _on_search_done(self, results):
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        if not results:
            self.status_lbl.setText("No games found.")
            return
        self.status_lbl.setText(f"Found {len(results)} matches. Select a game to download.")
        for game in results:
            self._add_card(game)
            aw = OFAppIdWorker(game["stem"], game["title"])
            aw.sig.done.connect(self._on_appid)
            self._pool.start(aw)

    def _on_search_err(self, err):
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.status_lbl.setText(f"Search error: {err}")

    # ── Icon pipeline ─────────────────────────────────────────────────────────
    def _on_appid(self, stem, appid):
        iw = OFIconWorker(stem, appid)
        iw.sig.done.connect(self._on_icon)
        self._pool.start(iw)

    def _on_icon(self, stem, pix):
        for card in self._cards:
            if card.game["stem"] == stem:
                card.set_icon(pix)
                break

    # ── Download ──────────────────────────────────────────────────────────────
    def _start_download(self):
        if not self._sel_game:
            return
        folder = QFileDialog.getExistingDirectory(self, "Select Game Installation Folder")
        if not folder:
            self.status_lbl.setText("No folder selected.")
            return

        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)
        self.dl_btn.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        self.status_lbl.setText("Initializing download…")

        w = OFDownloadWorker(self._sel_game["url"], self._sel_game["stem"], folder)
        w.sig.status.connect(self.status_lbl.setText)
        w.sig.progress.connect(self.progress.setValue)
        w.sig.finished.connect(self._on_dl_done)
        self._pool.start(w)

    def _on_dl_done(self, success, result):
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.progress.hide()
        if success:
            self.status_lbl.setText(f"Done! Extracted to: {result}")
            QMessageBox.information(self, "Success",
                "Online Fix files downloaded and extracted into the game folder!")
            self.dl_btn.setEnabled(bool(self._sel_game))
        else:
            self.status_lbl.setText(f"Failed: {result}")
            QMessageBox.critical(self, "Download Failed", result)
            self.dl_btn.setEnabled(True)



class AchievementManagerTab(StyledDownloadTab):
    def __init__(self):
        super().__init__(
            "Achievement Manager",
            "Download and extract Steam Achievement Manager to manage game achievements.",
            "Download & Extract SAM",
        )
        self.worker = None

    def start_download(self):
        folder = QFileDialog.getExistingDirectory(self, "Select extraction folder")
        if not folder:
            self.status_label.setText("No folder selected.")
            return
        self.download_btn.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        self.status_label.setText("Downloading...")
        self.worker = DownloadWorker(
            "https://github.com/gibbed/SteamAchievementManager/releases/download/7.0.41/SteamAchievementManager-7.0.41.zip",
            folder, extract_to=folder,
        )
        self.worker.sig.status.connect(self.status_label.setText)
        self.worker.sig.progress.connect(self.progress.setValue)
        self.worker.sig.finished.connect(self.download_finished)
        QThreadPool.globalInstance().start(self.worker)

    def download_finished(self, success, result):
        self.reset_ui()
        if success:
            self.status_label.setText(f"Extracted to: {result}")
            self.progress.setValue(100)
            os.startfile(result)
        else:
            self.status_label.setText(f"Failed: {result}")


class DropZone(QLabel):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(120)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #7c3aed;
                border-radius: 14px;
                background-color: #14141c;
                color: #a78bfa;
                font-size: 14px;
            }
            QLabel:hover {
                background-color: #1c1c2e;
                border: 2px dashed #8b5cf6;
            }
        """)
        self.setText("Drop .lua file here")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(".lua"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if path.lower().endswith(".lua"):
                    self.file_dropped.emit(path)
                    event.acceptProposedAction()
                    return
        event.ignore()


class AddTab(QWidget):
    def __init__(self):
        super().__init__()
        self.steam_path = utils.get_steam_path()
        self.selected_appid = None
        self.pool = QThreadPool.globalInstance()
        self._setup_ui()

    def _setup_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)

        self.mode_group = QButtonGroup(self)
        mode_layout = QHBoxLayout()
        self.radio_search = QRadioButton("Search by Name")
        self.radio_search.setChecked(True)
        self.radio_manual = QRadioButton("Direct AppID")
        for rb in (self.radio_search, self.radio_manual):
            rb.setStyleSheet("""
                QRadioButton { color: #d0d0e0; font-size: 13px; spacing: 6px; }
                QRadioButton::indicator { width: 18px; height: 18px; border-radius: 9px;
                    border: 2px solid #4a4a5a; }
                QRadioButton::indicator:checked { border: 2px solid #7c3aed;
                    background: qradialgradient(cx:0.5,cy:0.5,radius:0.4,
                        stop:0 #7c3aed,stop:1 #14141c); }
            """)
            self.mode_group.addButton(rb)
            mode_layout.addWidget(rb)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        v.addLayout(mode_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #25253a;")
        v.addWidget(line)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter game name...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #1a1a28; border: 1px solid #2a2a42;
                border-radius: 10px; padding: 10px 16px;
                color: #f0f0f8; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #7c3aed; }
        """)
        self.search_input.textChanged.connect(self.on_search)
        v.addWidget(self.search_input)

        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Enter AppID...")
        self.manual_input.setStyleSheet(self.search_input.styleSheet())
        self.manual_input.hide()
        v.addWidget(self.manual_input)

        self.results_list = QListWidget()
        self.results_list.setStyleSheet("""
            QListWidget {
                background: #14141c; border: 1px solid #25253a;
                border-radius: 10px; color: #e0e0f0;
                font-size: 13px; padding: 4px;
            }
            QListWidget::item { padding: 8px 12px; border-radius: 6px; }
            QListWidget::item:selected { background: #2a2a4a; }
            QListWidget::item:hover { background: #1e1e32; }
        """)
        self.results_list.itemClicked.connect(self.on_result_selected)
        v.addWidget(self.results_list)

        self.download_btn = QPushButton("Download Script")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setEnabled(False)
        self.download_btn.setFixedHeight(40)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6d28d9, stop:1 #7c3aed);
                color: white; border: none; border-radius: 10px;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #7c3aed, stop:1 #8b5cf6); }
            QPushButton:disabled { background: #2a2a3a; color: #6b7280; }
        """)
        self.download_btn.clicked.connect(self.download_script)
        v.addWidget(self.download_btn)

        drop_group = QGroupBox("Add local .lua file")
        drop_group.setStyleSheet("""
            QGroupBox { color: #a78bfa; font-weight: bold; border: 1px solid #25253a;
                border-radius: 10px; margin-top: 12px; padding-top: 16px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
        """)
        drop_layout = QVBoxLayout(drop_group)
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.add_local_lua)
        drop_layout.addWidget(self.drop_zone)
        v.addWidget(drop_group)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        v.addWidget(self.status_label)

        if not self.steam_path:
            self.status_label.setText("Steam not found! Scripts will save to current folder.")

    def on_mode_changed(self):
        search_mode = self.radio_search.isChecked()
        self.search_input.setVisible(search_mode)
        self.manual_input.setVisible(not search_mode)
        self.results_list.clear()
        self.download_btn.setEnabled(False)

    def on_search(self, text):
        text = text.strip()
        if len(text) < 2:
            self.results_list.clear()
            self.download_btn.setEnabled(False)
            return
        self.results_list.clear()
        self.download_btn.setEnabled(False)
        self.status_label.setText("Searching...")
        QApplication.processEvents()
        try:
            resp = requests.get(
                "https://store.steampowered.com/api/storesearch/",
                params={"term": text, "l": "english", "cc": "US"},
                timeout=15, verify=False,
            )
            data = resp.json()
            for item in data.get("items", []):
                if item.get("type") == "app":
                    name = item.get("name", "?")
                    appid = str(item.get("id", 0))
                    li = QListWidgetItem(f"{name} (ID: {appid})")
                    li.setData(Qt.UserRole, appid)
                    self.results_list.addItem(li)
                    
                    # Fetch search result icon asynchronously
                    worker = ImgWorker(appid)
                    worker.sig.loaded.connect(self._set_result_icon)
                    self.pool.start(worker)

            self.status_label.setText(f"Found {self.results_list.count()} results.")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _set_result_icon(self, key, pix):
        for i in range(self.results_list.count()):
            item = self.results_list.item(i)
            if item.data(Qt.UserRole) == key and not pix.isNull():
                item.setIcon(QIcon(pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                break

    def on_result_selected(self, item):
        self.selected_appid = item.data(Qt.UserRole)
        self.download_btn.setEnabled(True)
        self.status_label.setText(f"Selected: {item.text()}")

    def download_script(self):
        if self.radio_search.isChecked():
            appid = self.selected_appid
        else:
            appid = self.manual_input.text().strip()
        if not appid or not appid.isdigit():
            self.status_label.setText("Invalid AppID")
            return
        lua_dir = utils.prepare_lua_folder(self.steam_path) if self.steam_path else str(Path.cwd())
        self.download_btn.setEnabled(False)
        self.status_label.setText("Starting download...")
        worker = ManifestWorker(appid, lua_dir)
        worker.sig.status.connect(self.status_label.setText)
        worker.sig.finished.connect(lambda ok, msg: self._on_done(ok, msg))
        self.pool.start(worker)

    def _on_done(self, ok, msg):
        self.download_btn.setEnabled(True)
        self.status_label.setText(f"{'Done' if ok else 'Failed'}: {msg}")

    def add_local_lua(self, file_path):
        if not file_path.lower().endswith(".lua"):
            self.status_label.setText("Only .lua files accepted.")
            return
        try:
            src = Path(file_path)
            if not src.exists():
                self.status_label.setText("File not found.")
                return
            if self.steam_path:
                lua_dir = utils.prepare_lua_folder(self.steam_path)
            else:
                lua_dir = str(Path.cwd())
            dest = Path(lua_dir) / src.name
            if dest.exists():
                reply = QMessageBox.question(
                    self, "File exists",
                    f"A file named '{src.name}' exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    self.status_label.setText(f"Skipped {src.name}")
                    return
            import shutil
            shutil.copy2(str(src), str(dest))
            self.status_label.setText(f"Copied '{src.name}' to {lua_dir}")
        except Exception as e:
            self.status_label.setText(f"Failed: {e}")


class LibraryTab(QWidget):
    def __init__(self):
        super().__init__()
        self.all_game_widgets = {}
        self.item_widgets = {}
        self.pending_tasks = 0
        self.pool = QThreadPool.globalInstance()
        self._setup_ui()

    def _setup_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        header = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Library")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #1f1f35; color: #c0c0e0;
                border: 1px solid #2a2a42; border-radius: 8px;
                padding: 8px 16px; font-size: 12px;
            }
            QPushButton:hover { background: #2a2a42; }
        """)
        self.refresh_btn.clicked.connect(self.load_library)
        header.addWidget(self.refresh_btn)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter games...")
        self.search_input.setFixedHeight(32)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #1a1a28; border: 1px solid #2a2a42;
                border-radius: 8px; padding: 4px 12px;
                color: #f0f0f8; font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #7c3aed; }
        """)
        self.search_input.textChanged.connect(self.filter_games)
        header.addWidget(self.search_input)

        self.count_label = QLabel("0 Games")
        self.count_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        header.addWidget(self.count_label)
        v.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #0a0a10; width: 8px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #2a2a42; border-radius: 4px; }
        """)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(8)
        scroll.setWidget(self.container)
        v.addWidget(scroll)

    def load_library(self):
        self.refresh_btn.setEnabled(False)
        self.search_input.setEnabled(False)
        self.pending_tasks = 0
        for w in self.all_game_widgets.values():
            w.setParent(None)
            w.deleteLater()
        self.all_game_widgets.clear()
        self.item_widgets.clear()

        steam_path = utils.get_steam_path()
        if not steam_path:
            lbl = QLabel("Steam not found.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #6b7280; font-size: 14px; padding: 30px;")
            self.container_layout.addWidget(lbl)
            self.refresh_btn.setEnabled(True)
            self.search_input.setEnabled(True)
            return

        lua_dir = Path(steam_path) / "config" / "lua"
        if not lua_dir.exists():
            lbl = QLabel("No Lua scripts found.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #6b7280; font-size: 14px; padding: 30px;")
            self.container_layout.addWidget(lbl)
            self.refresh_btn.setEnabled(True)
            self.search_input.setEnabled(True)
            return

        lua_files = sorted(lua_dir.glob("*.lua"))
        if not lua_files:
            lbl = QLabel("No Lua scripts found.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #6b7280; font-size: 14px; padding: 30px;")
            self.container_layout.addWidget(lbl)
            self.refresh_btn.setEnabled(True)
            self.search_input.setEnabled(True)
            return

        for lf in lua_files:
            appid = lf.stem
            self._create_game_widget(lf, appid)

    def _create_game_widget(self, lua_file, appid):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #14141c; border: 1px solid #25253a;
                border-radius: 10px; padding: 8px;
            }
            QFrame:hover { border: 1px solid #3a3a5a; }
        """)
        h = QHBoxLayout(frame)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(10)

        icon = QLabel()
        icon.setFixedSize(60, 34)
        icon.setStyleSheet("background: #1a1a28; border-radius: 6px;")
        icon.setAlignment(Qt.AlignCenter)
        icon.setText("...")
        h.addWidget(icon)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(f"Loading AppID {appid}...")
        name_lbl.setStyleSheet("color: #e0e0f0; font-size: 13px; font-weight: 600; border: none;")
        info.addWidget(name_lbl)
        appid_lbl = QLabel(f"AppID: {appid}")
        appid_lbl.setStyleSheet("color: #6b7280; font-size: 11px; border: none;")
        info.addWidget(appid_lbl)
        h.addLayout(info, 1)

        del_btn = QPushButton("Delete")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setFixedSize(72, 30)
        del_btn.setStyleSheet("""
            QPushButton {
                background: #7f1d1d; color: #fca5a5;
                border: none; border-radius: 6px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #991b1b; }
        """)
        del_btn.clicked.connect(lambda checked, lf=lua_file, aid=appid: self.delete_game(lf, aid))
        h.addWidget(del_btn)

        self.container_layout.addWidget(frame)
        self.all_game_widgets[appid] = frame
        self.item_widgets[appid] = {
            "widget": frame, "appid": appid,
            "icon_label": icon, "name_label": name_lbl,
            "lua_file": lua_file,
            "name": f"Game {appid}"
        }
        self.pending_tasks += 1

        worker = LibraryGameWorker(appid)
        worker.sig.loaded.connect(lambda aid, pix, name: self._on_game_info(aid, pix, name))
        self.pool.start(worker)

    def _on_game_info(self, appid, pix, name):
        info = self.item_widgets.get(appid)
        if not info:
            return
        info["name"] = name
        icon = info["icon_label"]
        name_lbl = info["name_label"]
        if not pix.isNull():
            icon.setPixmap(pix.scaled(60, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        name_lbl.setText(name)
        self.pending_tasks -= 1
        if self.pending_tasks <= 0:
            self._check_pending()

    def _check_pending(self):
        self.refresh_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.update_count_label()

    def filter_games(self, text):
        t = text.lower().strip()
        visible = 0
        for aid, info in self.item_widgets.items():
            widget = info["widget"]
            if not t:
                widget.show()
                visible += 1
            else:
                match = t in info.get("name", "").lower() or t in aid
                widget.setVisible(match)
                if match:
                    visible += 1
        self.count_label.setText(f"{visible}/{len(self.item_widgets)} Games")

    def update_count_label(self):
        total = len(self.item_widgets)
        visible = sum(1 for w in self.all_game_widgets.values() if w.isVisible())
        self.count_label.setText(f"{visible}/{total} Games")

    def delete_game(self, lua_file, appid):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete game {appid}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return
        self.refresh_btn.setEnabled(False)
        self.search_input.setEnabled(False)
        worker = DeleteGameWorker(str(lua_file))
        worker.sig.finished.connect(lambda aid, ok: self._on_delete(aid, ok))
        self.pool.start(worker)

    def _on_delete(self, appid, success):
        if success:
            if appid in self.all_game_widgets:
                self.all_game_widgets[appid].setParent(None)
                del self.all_game_widgets[appid]
                del self.item_widgets[appid]
            self.update_count_label()
        self.refresh_btn.setEnabled(True)
        self.search_input.setEnabled(True)



