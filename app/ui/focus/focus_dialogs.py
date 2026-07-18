"""Modal decisions for stopping or exiting an active saved focus session."""

from enum import StrEnum

from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget


class StopDecision(StrEnum):
    CONTINUE = "continue"
    STOP_AND_REVIEW = "stop_and_review"


class ExitDecision(StrEnum):
    KEEP_FOCUSING = "keep_focusing"
    MINIMIZE_TO_TRAY = "minimize_to_tray"
    END_AND_EXIT = "end_and_exit"


def ask_stop(parent: QWidget) -> StopDecision:
    box = QMessageBox(parent)
    box.setWindowTitle("Stop this session?")
    box.setIcon(QMessageBox.Icon.Question)
    box.setText("Stopping now will finalize this session locally.")
    box.setInformativeText("Continue focusing, or stop now and review the saved summary?")
    continue_button = box.addButton("Continue Session", QMessageBox.ButtonRole.RejectRole)
    stop_button = box.addButton("Stop and Review", QMessageBox.ButtonRole.DestructiveRole)
    box.setDefaultButton(continue_button)
    box.exec()
    return (
        StopDecision.STOP_AND_REVIEW
        if box.clickedButton() is stop_button
        else StopDecision.CONTINUE
    )


def ask_active_exit(parent: QWidget, *, tray_available: bool) -> ExitDecision:
    box = QMessageBox(parent)
    box.setWindowTitle("Active focus session")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText("This focus session is active and must be finalized before exit.")
    box.setInformativeText("Choose what LockIn should do before closing.")
    keep_button = box.addButton("Keep Focusing", QMessageBox.ButtonRole.RejectRole)
    minimize_button: QPushButton | None = None
    if tray_available:
        minimize_button = box.addButton("Minimize to Tray", QMessageBox.ButtonRole.ActionRole)
    end_button = box.addButton("End Session and Exit", QMessageBox.ButtonRole.DestructiveRole)
    box.setDefaultButton(keep_button)
    box.exec()
    clicked = box.clickedButton()
    if clicked is end_button:
        return ExitDecision.END_AND_EXIT
    if minimize_button is not None and clicked is minimize_button:
        return ExitDecision.MINIMIZE_TO_TRAY
    return ExitDecision.KEEP_FOCUSING
