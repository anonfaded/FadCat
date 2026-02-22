"""
FadCat — Settings Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QInputDialog, QLabel, QComboBox,
    QFrame, QDialogButtonBox, QGroupBox
)
from PyQt6 import QtCore
from src.core.settings import SettingsManager
from src.ui.icons import icon_close


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)
        self.setMinimumHeight(380)
        self.settings = SettingsManager.load()
        self._build_ui()
        self._connect()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Packages group ────────────────────────────────────────────────────
        pkg_group = QGroupBox("Saved packages")
        pkg_layout = QVBoxLayout(pkg_group)
        pkg_layout.setSpacing(8)

        self.package_list = QListWidget()
        self.package_list.addItems(self.settings.get("packages", []))
        pkg_layout.addWidget(self.package_list)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.remove_btn = QPushButton("Remove")
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch()
        pkg_layout.addLayout(btn_row)

        root.addWidget(pkg_group)

        # ── Default package ───────────────────────────────────────────────────
        default_row = QHBoxLayout()
        default_row.setSpacing(10)
        lbl = QLabel("Default package")
        lbl.setProperty("muted", True)
        self.default_cb = QComboBox()
        self._refresh_default_cb()
        default_row.addWidget(lbl)
        default_row.addWidget(self.default_cb, 1)
        root.addLayout(default_row)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        root.addWidget(sep)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_box = QDialogButtonBox()
        self.save_btn   = btn_box.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        self.cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        self.save_btn.setProperty("role", "primary")
        root.addWidget(btn_box)

    def _connect(self):
        self.add_btn.clicked.connect(self._add_package)
        self.remove_btn.clicked.connect(self._remove_package)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _refresh_default_cb(self):
        packages = [self.package_list.item(i).text()
                    for i in range(self.package_list.count())]
        cur = self.default_cb.currentText() if self.default_cb.count() else ""
        self.default_cb.blockSignals(True)
        self.default_cb.clear()
        self.default_cb.addItems(packages)
        if cur in packages:
            self.default_cb.setCurrentText(cur)
        elif packages:
            default_pkg = self.settings.get("default_package", "")
            if default_pkg in packages:
                self.default_cb.setCurrentText(default_pkg)
        self.default_cb.blockSignals(False)

    def _add_package(self):
        pkg, ok = QInputDialog.getText(
            self, "Add Package",
            "Package name (e.g. com.example.app):"
        )
        if ok and pkg.strip():
            pkg = pkg.strip()
            existing = [self.package_list.item(i).text()
                        for i in range(self.package_list.count())]
            if pkg not in existing:
                self.package_list.addItem(pkg)
                self._refresh_default_cb()

    def _remove_package(self):
        item = self.package_list.currentItem()
        if item:
            self.package_list.takeItem(self.package_list.row(item))
            self._refresh_default_cb()

    def _save(self):
        packages = [self.package_list.item(i).text()
                    for i in range(self.package_list.count())]
        self.settings["packages"]        = packages
        self.settings["default_package"] = self.default_cb.currentText()
        SettingsManager.save(self.settings)
        self.accept()

