import sys, os
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QMessageBox,
    QButtonGroup,
)
from PyQt5.QtCore import Qt, QThreadPool
from PyQt5.QtGui import QFont, QColor, QPalette

import utils
from ui import (
    AddTab, LibraryTab, BypassTab,
    CrackTab, OnlineFixTab, AchievementManagerTab,
)
from workers import DllDownloadWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Argos OS Team Tool")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(950, 650)
        self._wk = []  # Keep references to workers to prevent GC
        self._setup_ui()
        self._start_dll_download()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -------------------------------------------------------------
        # Left Panel (Sidebar)
        # -------------------------------------------------------------
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 24)
        sidebar_layout.setSpacing(10)

        # Logo Area
        logo_lbl = QLabel("ARGOS OS")
        logo_lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        logo_lbl.setStyleSheet("color: #a78bfa; margin-bottom: 2px;")
        
        sub_lbl = QLabel("STEAM UTILITY SUITE")
        sub_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        sub_lbl.setStyleSheet("color: #6b7280; letter-spacing: 2px; margin-bottom: 20px;")

        sidebar_layout.addWidget(logo_lbl)
        sidebar_layout.addWidget(sub_lbl)

        # Nav Button Group
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_items = [
            ("Bypass Browser", 0),
            ("Library Manager", 1),
            ("Add Custom Game", 2),
            ("DRM Unlocker", 3),
            ("Online Fix", 4),
            ("Ach. Manager", 5),
        ]

        self.nav_btns = []
        for name, idx in nav_items:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(44)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #9ca3af;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 16px;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #1e1e2f;
                    color: #ede9fe;
                }
                QPushButton:checked {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5b21b6, stop:1 #7c3aed);
                    color: #ffffff;
                    font-weight: bold;
                }
            """)
            self.nav_group.addButton(btn, idx)
            sidebar_layout.addWidget(btn)
            self.nav_btns.append(btn)

        sidebar_layout.addStretch()

        # Sidebar Footer
        footer_team = QLabel("ArgusOs Team")
        footer_team.setStyleSheet("color: #4b5563; font-size: 11px; font-weight: bold;")
        footer_team.setAlignment(Qt.AlignCenter)
        
        footer_version = QLabel("v1.1.0")
        footer_version.setStyleSheet("color: #374151; font-size: 10px;")
        footer_version.setAlignment(Qt.AlignCenter)

        sidebar_layout.addWidget(footer_team)
        sidebar_layout.addWidget(footer_version)

        main_layout.addWidget(sidebar)

        # -------------------------------------------------------------
        # Right Panel (Main Content & Topbar)
        # -------------------------------------------------------------
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top Bar
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(64)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(24, 0, 24, 0)
        top_layout.setSpacing(12)

        # Page Title (Dynamic)
        self.page_title = QLabel("Bypass Browser")
        self.page_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.page_title.setStyleSheet("color: #fafafa;")
        top_layout.addWidget(self.page_title)

        top_layout.addStretch()

        # Toggles
        self.btn_family = QPushButton("Family Sharing: ON")
        self.btn_family.setCheckable(True)
        self.btn_family.setChecked(True)
        self.btn_family.setStyleSheet("""
            QPushButton {
                background: #1f1a30; color: #c084fc; border: 1px solid #581c87;
                border-radius: 8px; padding: 6px 12px; font-size: 11px; font-weight: bold;
            }
            QPushButton:!checked {
                background: #111827; color: #4b5563; border: 1px solid #1f2937;
            }
        """)
        self.btn_family.toggled.connect(
            lambda checked: self._update_toggle_text(self.btn_family, "Family Sharing", checked)
        )

        self.btn_updates = QPushButton("Game Updates: ON")
        self.btn_updates.setCheckable(True)
        self.btn_updates.setChecked(True)
        self.btn_updates.setStyleSheet("""
            QPushButton {
                background: #172554; color: #60a5fa; border: 1px solid #1e3a8a;
                border-radius: 8px; padding: 6px 12px; font-size: 11px; font-weight: bold;
            }
            QPushButton:!checked {
                background: #111827; color: #4b5563; border: 1px solid #1f2937;
            }
        """)
        self.btn_updates.toggled.connect(
            lambda checked: self._update_toggle_text(self.btn_updates, "Game Updates", checked)
        )

        self.btn_dlc = QPushButton("DLC Unlocker: ON")
        self.btn_dlc.setCheckable(True)
        self.btn_dlc.setChecked(True)
        self.btn_dlc.setStyleSheet("""
            QPushButton {
                background: #2d1305; color: #fb923c; border: 1px solid #7c2d12;
                border-radius: 8px; padding: 6px 12px; font-size: 11px; font-weight: bold;
            }
            QPushButton:!checked {
                background: #111827; color: #4b5563; border: 1px solid #1f2937;
            }
        """)
        self.btn_dlc.toggled.connect(
            lambda checked: self._update_toggle_text(self.btn_dlc, "DLC Unlocker", checked)
        )

        for btn in (self.btn_family, self.btn_updates, self.btn_dlc):
            btn.setCursor(Qt.PointingHandCursor)
            top_layout.addWidget(btn)

        # Steam & About Buttons
        self.steam_btn = QPushButton("Launch Steam")
        self.steam_btn.setCursor(Qt.PointingHandCursor)
        self.steam_btn.setFixedHeight(34)
        self.steam_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #10b981);
                color: white; border: none; border-radius: 8px;
                padding: 0 16px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #34d399);
            }
        """)
        self.steam_btn.clicked.connect(self.launch_steam)
        top_layout.addWidget(self.steam_btn)

        about_btn = QPushButton("About")
        about_btn.setCursor(Qt.PointingHandCursor)
        about_btn.setFixedHeight(34)
        about_btn.setStyleSheet("""
            QPushButton {
                background: #111827; color: #9ca3af; border: 1px solid #1f2937;
                border-radius: 8px; padding: 0 14px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #1f2937; color: #f3f4f6; }
        """)
        about_btn.clicked.connect(self.show_about)
        top_layout.addWidget(about_btn)

        right_layout.addWidget(top_bar)

        # Content Stack Widget
        self.stack = QStackedWidget()
        
        self.tab_bypass = BypassTab()
        self.tab_library = LibraryTab()
        self.tab_add = AddTab()
        self.tab_crack = CrackTab()
        self.tab_online = OnlineFixTab()
        self.tab_achievement = AchievementManagerTab()

        self.stack.addWidget(self.tab_bypass)       # index 0
        self.stack.addWidget(self.tab_library)      # index 1
        self.stack.addWidget(self.tab_add)          # index 2
        self.stack.addWidget(self.tab_crack)        # index 3
        self.stack.addWidget(self.tab_online)       # index 4
        self.stack.addWidget(self.tab_achievement)  # index 5

        right_layout.addWidget(self.stack)

        # Status Bar
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(32)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(24, 0, 24, 0)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        engine_lbl = QLabel("Argos Engine Active")
        engine_lbl.setStyleSheet("color: #4b5563; font-size: 10px; font-weight: bold;")
        status_layout.addWidget(engine_lbl)
        
        right_layout.addWidget(status_bar)
        main_layout.addWidget(right_container)

        # Set default tab active
        self.nav_btns[0].setChecked(True)
        self.nav_group.buttonClicked.connect(self._on_nav_changed)
        
        # Load bypass JSON data and library
        self.tab_bypass.load_data()
        self.tab_library.load_library()

        self._apply_theme()

    def _on_nav_changed(self, button):
        idx = self.nav_group.id(button)
        self.stack.setCurrentIndex(idx)
        self.page_title.setText(button.text())
        if idx == 1:
            self.tab_library.load_library()

    def _update_toggle_text(self, btn, base_name, checked):
        state = "ON" if checked else "OFF"
        btn.setText(f"{base_name}: {state}")

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background: #09090e; }
            QWidget { background: transparent; }
            QFrame#sidebar { background: #0c0c14; border-right: 1px solid #1c1c28; }
            QFrame#topBar { background: #09090e; border-bottom: 1px solid #1c1c28; }
            QFrame#statusBar { background: #09090e; border-top: 1px solid #1c1c28; }
            
            QScrollBar:vertical {
                background: #09090e; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #2a2a3f; border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            
            QMessageBox {
                background: #14141c;
            }
            QMessageBox QLabel {
                color: #e0e0f0;
            }
            QMessageBox QPushButton {
                background: #2a2a42; color: #e0e0f0;
                border: none; border-radius: 6px; padding: 6px 20px;
            }
        """)

    def launch_steam(self):
        steam_path = utils.get_steam_path()
        if not steam_path:
            QMessageBox.warning(self, "Steam Not Found",
                                "Could not locate Steam installation.")
            return
        steam_exe = Path(steam_path) / "Steam.exe"
        if steam_exe.exists():
            os.startfile(str(steam_exe))
            self.status_label.setText("Steam launched.")
        else:
            QMessageBox.warning(self, "File Not Found",
                                "Steam.exe not found in the installation path.")

    def show_about(self):
        QMessageBox.about(
            self, "About Argos OS Team Tool",
            "Argos OS Team Tool v1.1.0\n\n"
            "All-in-One Steam Utility Suite\n"
            "Rebranded & Re-engineered for Argos OS.\n\n"
            "Features:\n"
            "- Direct bypass ZIP/RAR package downloading\n"
            "- Clean dashboard layout & sidebar navigation\n"
            "- Asynchronous Steam API name & icon fetching\n"
            "- Generic fixes & DRM unlocker\n"
            "- Achievement Manager Integration"
        )

    def _start_dll_download(self):
        worker = DllDownloadWorker()
        worker.sig.finished.connect(
            lambda: self.status_label.setText("DLLs ready")
        )
        QThreadPool.globalInstance().start(worker)


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#09090e"))
    palette.setColor(QPalette.WindowText, QColor("#d7d7db"))
    palette.setColor(QPalette.Base, QColor("#0c0c14"))
    palette.setColor(QPalette.AlternateBase, QColor("#14141f"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1c1c28"))
    palette.setColor(QPalette.ToolTipText, QColor("#f0f0f8"))
    palette.setColor(QPalette.Text, QColor("#f0f0f8"))
    palette.setColor(QPalette.Button, QColor("#0c0c14"))
    palette.setColor(QPalette.ButtonText, QColor("#d7d7db"))
    palette.setColor(QPalette.BrightText, QColor("#f87171"))
    palette.setColor(QPalette.Highlight, QColor("#7c3aed"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
