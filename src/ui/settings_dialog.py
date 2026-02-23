"""Settings dialog — manage saved packages."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton,
    QComboBox, QLineEdit, QLabel, QDialogButtonBox,
    QSizePolicy,
)

from src.core.settings import Settings
from src.ui import icons


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(480, 420)
        self._settings = Settings()
        self._build_ui()
        self._populate()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # Package list group
        grp = QGroupBox("Saved Packages")
        grp_lay = QVBoxLayout(grp)
        grp_lay.setContentsMargins(12, 16, 12, 12)
        grp_lay.setSpacing(8)

        self.pkg_list = QListWidget()
        self.pkg_list.setFixedHeight(160)
        self.pkg_list.itemSelectionChanged.connect(self._on_selection)
        grp_lay.addWidget(self.pkg_list)

        # Add row
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.edit_add = QLineEdit()
        self.edit_add.setPlaceholderText("com.example.app")
        self.edit_add.returnPressed.connect(self._add_package)
        add_row.addWidget(self.edit_add, stretch=1)
        btn_add = QPushButton("Add")
        btn_add.setProperty("role", "primary")
        btn_add.setFixedWidth(64)
        btn_add.clicked.connect(self._add_package)
        add_row.addWidget(btn_add)
        grp_lay.addLayout(add_row)

        # Remove
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.setEnabled(False)
        self.btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(self.btn_remove)
        btn_row.addStretch()
        grp_lay.addLayout(btn_row)

        root.addWidget(grp)

        # Default package
        def_row = QHBoxLayout()
        def_row.setSpacing(10)
        def_row.addWidget(QLabel("Default package:"))
        self.default_combo = QComboBox()
        self.default_combo.setMinimumWidth(240)
        def_row.addWidget(self.default_combo, stretch=1)
        root.addLayout(def_row)

        root.addStretch()

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
        self.pkg_list.clear()
        for pkg in self._settings.packages:
            self.pkg_list.addItem(pkg)
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

    def _on_selection(self):
        self.btn_remove.setEnabled(len(self.pkg_list.selectedItems()) > 0)

    def _add_package(self):
        text = self.edit_add.text().strip()
        if not text:
            return
        # No duplicates
        for i in range(self.pkg_list.count()):
            if self.pkg_list.item(i).text() == text:
                return
        self.pkg_list.addItem(text)
        self.edit_add.clear()
        self._refresh_default_combo()

    def _remove_selected(self):
        for item in self.pkg_list.selectedItems():
            self.pkg_list.takeItem(self.pkg_list.row(item))
        self._refresh_default_combo()

    def _save(self):
        packages = [
            self.pkg_list.item(i).text()
            for i in range(self.pkg_list.count())
        ]
        default = self.default_combo.currentText()
        if default == "(none)":
            default = ""
        self._settings.packages = packages
        self._settings.default_package = default
        self._settings.save()
        self.accept()

