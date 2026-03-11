"""Settings dialog — manage saved packages and ignore list."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton,
    QComboBox, QLineEdit, QLabel, QDialogButtonBox,
    QSizePolicy, QTabWidget, QWidget, QMessageBox,
)

from src.core.settings import Settings, DEFAULT_SETTINGS
from src.ui import icons


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(520, 500)
        self._settings = Settings()
        self._build_ui()
        self._populate()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        # ── Tab 1: Packages ───────────────────────────────────────────────────
        pkg_tab = QWidget()
        pkg_lay = QVBoxLayout(pkg_tab)
        
        grp_pkg = QGroupBox("Saved Packages")
        grp_pkg_lay = QVBoxLayout(grp_pkg)
        
        self.pkg_list = QListWidget()
        self.pkg_list.setFixedHeight(180)
        self.pkg_list.itemSelectionChanged.connect(self._on_pkg_selection)
        grp_pkg_lay.addWidget(self.pkg_list)

        add_row = QHBoxLayout()
        self.edit_add = QLineEdit()
        self.edit_add.setPlaceholderText("com.example.app")
        self.edit_add.returnPressed.connect(self._add_package)
        add_row.addWidget(self.edit_add, stretch=1)
        btn_add = QPushButton("Add")
        btn_add.setProperty("role", "primary")
        btn_add.setFixedWidth(64)
        btn_add.clicked.connect(self._add_package)
        add_row.addWidget(btn_add)
        grp_pkg_lay.addLayout(add_row)

        self.btn_remove_pkg = QPushButton("Remove Selected")
        self.btn_remove_pkg.setEnabled(False)
        self.btn_remove_pkg.clicked.connect(self._remove_selected_pkg)
        grp_pkg_lay.addWidget(self.btn_remove_pkg)
        
        pkg_lay.addWidget(grp_pkg)

        def_row = QHBoxLayout()
        def_row.addWidget(QLabel("Default package:"))
        self.default_combo = QComboBox()
        self.default_combo.setMinimumWidth(240)
        def_row.addWidget(self.default_combo, stretch=1)
        pkg_lay.addLayout(def_row)
        pkg_lay.addStretch()

        self.tabs.addTab(pkg_tab, "Packages")

        # ── Tab 2: Ignore List ────────────────────────────────────────────────
        ign_tab = QWidget()
        ign_lay = QVBoxLayout(ign_tab)

        help_lbl = QLabel(
            "Lines containing these tags will be hidden from the log view. "
            "Great for filtering out system noise (like GPU or Bluetooth spam)."
        )
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet("color: #888888; font-size: 12px; margin-bottom: 8px;")
        ign_lay.addWidget(help_lbl)

        grp_ign = QGroupBox("Ignored Tags")
        grp_ign_lay = QVBoxLayout(grp_ign)

        self.ign_list = QListWidget()
        self.ign_list.itemSelectionChanged.connect(self._on_ign_selection)
        grp_ign_lay.addWidget(self.ign_list)

        ign_add_row = QHBoxLayout()
        self.edit_add_ign = QLineEdit()
        self.edit_add_ign.setPlaceholderText("TagToIgnore")
        self.edit_add_ign.returnPressed.connect(self._add_ignore)
        ign_add_row.addWidget(self.edit_add_ign, stretch=1)
        btn_add_ign = QPushButton("Add")
        btn_add_ign.setProperty("role", "primary")
        btn_add_ign.setFixedWidth(64)
        btn_add_ign.clicked.connect(self._add_ignore)
        ign_add_row.addWidget(btn_add_ign)
        grp_ign_lay.addLayout(ign_add_row)

        ign_btn_row = QHBoxLayout()
        self.btn_remove_ign = QPushButton("Remove Selected")
        self.btn_remove_ign.setEnabled(False)
        self.btn_remove_ign.clicked.connect(self._remove_selected_ign)
        ign_btn_row.addWidget(self.btn_remove_ign)
        
        ign_btn_row.addStretch()
        
        btn_reset_ign = QPushButton("Reset to Defaults")
        btn_reset_ign.clicked.connect(self._reset_ignores)
        ign_btn_row.addWidget(btn_reset_ign)
        
        grp_ign_lay.addLayout(ign_btn_row)
        ign_lay.addWidget(grp_ign)

        self.tabs.addTab(ign_tab, "Ignore List")

        # Dialog buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = btns.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setProperty("role", "primary")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _populate(self):
        # Packages
        self.pkg_list.clear()
        for pkg in self._settings.packages:
            self.pkg_list.addItem(pkg)
        
        # Ignores
        self.ign_list.clear()
        for tag in self._settings.ignored_tags:
            self.ign_list.addItem(tag)
            
        self._refresh_default_combo()

    def _refresh_default_combo(self):
        current = self.default_combo.currentText()
        self.default_combo.clear()
        self.default_combo.addItem("(none)")
        for i in range(self.pkg_list.count()):
            self.default_combo.addItem(self.pkg_list.item(i).text())
        idx = self.default_combo.findText(current)
        if idx > 0:
            self.default_combo.setCurrentIndex(idx)
        elif self._settings.default_package:
            idx2 = self.default_combo.findText(self._settings.default_package)
            if idx2 >= 0:
                self.default_combo.setCurrentIndex(idx2)

    def _on_pkg_selection(self):
        self.btn_remove_pkg.setEnabled(len(self.pkg_list.selectedItems()) > 0)

    def _on_ign_selection(self):
        self.btn_remove_ign.setEnabled(len(self.ign_list.selectedItems()) > 0)

    def _add_package(self):
        text = self.edit_add.text().strip()
        if not text: return
        for i in range(self.pkg_list.count()):
            if self.pkg_list.item(i).text() == text: return
        self.pkg_list.addItem(text)
        self.edit_add.clear()
        self._refresh_default_combo()

    def _remove_selected_pkg(self):
        for item in self.pkg_list.selectedItems():
            self.pkg_list.takeItem(self.pkg_list.row(item))
        self._refresh_default_combo()

    def _add_ignore(self):
        text = self.edit_add_ign.text().strip()
        if not text: return
        for i in range(self.ign_list.count()):
            if self.ign_list.item(i).text() == text: return
        self.ign_list.addItem(text)
        self.edit_add_ign.clear()

    def _remove_selected_ign(self):
        for item in self.ign_list.selectedItems():
            self.ign_list.takeItem(self.ign_list.row(item))

    def _reset_ignores(self):
        repl = QMessageBox.question(
            self, "Reset Ignores",
            "Are you sure you want to reset the ignore list to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if repl == QMessageBox.StandardButton.Yes:
            self.ign_list.clear()
            for tag in DEFAULT_SETTINGS["ignored_tags"]:
                self.ign_list.addItem(tag)

    def _save(self):
        packages = [self.pkg_list.item(i).text() for i in range(self.pkg_list.count())]
        ignores = [self.ign_list.item(i).text() for i in range(self.ign_list.count())]
        
        default = self.default_combo.currentText()
        if default == "(none)":
            default = ""
            
        self._settings.packages = packages
        self._settings.ignored_tags = ignores
        self._settings.default_package = default
        self._settings.save()
        self.accept()

