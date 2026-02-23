"""Built-in QStyle icons — no custom painting."""
from PyQt6.QtWidgets import QApplication, QStyle
from PyQt6.QtGui import QIcon


def _std(sp: QStyle.StandardPixmap) -> QIcon:
    style = QApplication.style()
    if style is None:
        return QIcon()
    return style.standardIcon(sp)


def icon_play() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_MediaPlay)

def icon_stop() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_MediaStop)

def icon_refresh() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_BrowserReload)

def icon_clear() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_LineEditClearButton)

def icon_copy() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_FileDialogDetailedView)

def icon_save() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_DialogSaveButton)

def icon_settings() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_FileDialogNewFolder)

def icon_new_tab() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_DirOpenIcon)

def icon_up() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_ArrowUp)

def icon_down() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_ArrowDown)

def icon_search() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_FileDialogContentsView)

def icon_filter() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_FileDialogInfoView)

def icon_device() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_ComputerIcon)

def icon_package() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_FileDialogDetailedView)

def icon_close() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_TitleBarCloseButton)

def icon_info() -> QIcon:
    return _std(QStyle.StandardPixmap.SP_MessageBoxInformation)

