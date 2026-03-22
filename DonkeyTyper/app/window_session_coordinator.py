from __future__ import annotations

import os

from PySide6.QtWidgets import QFileDialog

from file_formats import build_dty_payload, load_document_session, save_dty_payload
from model import Document
from paragraphs.config import load_user_paragraph_type_definitions
from paragraphs.registry import (
    configure_runtime_paragraph_type_registry,
    export_runtime_paragraph_type_definitions,
)
from ui import Win98Dialog


class WindowSessionCoordinator:
    def __init__(self, window):
        self.window = window
        self._current_file_path: str | None = None
        self._dirty = False

    def get_current_file_path(self) -> str | None:
        return self._current_file_path

    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self):
        if self._dirty:
            return
        self._dirty = True
        self.update_window_title()

    def mark_clean(self, *, path: str | None = None):
        if path is not None:
            self._current_file_path = path
        self._dirty = False
        self.update_window_title()

    def update_window_title(self):
        name = "donkeytyper"
        current_path = self._current_file_path
        if current_path:
            base = current_path.split("\\")[-1].split("/")[-1]
            name = f"{name}.{base}"
        else:
            name = f"{name}.selftitled"
        if self._dirty or current_path is None:
            name = f"{name}*"
        self.window.setWindowTitle(name)
        if hasattr(self.window, "title_label"):
            self.window.title_label.setText(name)

    def confirm_discard_if_dirty(self) -> bool:
        if not self._dirty:
            return True
        msg = Win98Dialog(
            self.window,
            "Unsaved Changes",
            "There are unsaved changes. Save before closing?",
        )
        result = msg.exec()
        if result == 1:
            self.save_file()
            return not self._dirty
        if result == 2:
            return True
        return False

    def rebuild_runtime_paragraph_type_registry(
        self,
        *,
        document_definitions: list[dict] | None = None,
    ):
        configure_runtime_paragraph_type_registry(
            user_definitions=load_user_paragraph_type_definitions(),
            document_definitions=document_definitions,
        )

    def load_plain_text_into_controller(self, text: str):
        self.rebuild_runtime_paragraph_type_registry(document_definitions=None)
        self.window.controller.set_document(
            Document.from_plain_text(
                text,
                default_font_size=self.window.format_coordinator.get_desired_size(),
            )
        )
        self.window.preview_coordinator.render_controller_document()
        self.window.preview_coordinator.restore_after_session_apply()
        self.window.editor_bridge.update_word_count()
        self.mark_clean()

    def apply_loaded_document_session(self, session):
        self.rebuild_runtime_paragraph_type_registry(
            document_definitions=session.paragraph_type_definitions
        )
        self.window.controller.set_document(session.document)
        self.window.preview_coordinator.render_controller_document()

        self.window.format_coordinator.set_slot_states(session.slot_states)
        self.window.format_coordinator.set_ui_state(session.ui_state)
        self.window.format_coordinator.apply_format_from_ui(allow_selection_apply=False)

        for btn in self.window.slot_buttons:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        self.window.format_coordinator.set_active_slot(session.active_slot)
        active_slot = self.window.format_coordinator.get_active_slot()
        if active_slot is not None:
            button = self.window.slot_buttons[active_slot]
            button.blockSignals(True)
            button.setChecked(True)
            button.blockSignals(False)
        self.window.format_coordinator.sync_controller_state()
        self.window.preview_coordinator.restore_after_session_apply()
        self.window.editor_bridge.update_word_count()
        self.mark_clean(path=session.path)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open File",
            "",
            "DonkeyTyper Files (*.dty);;Text Files (*.txt);;All Files (*.*)",
        )
        if not path:
            return
        if not self.confirm_discard_if_dirty():
            return

        session = load_document_session(
            path,
            fallback_ui_state=self.window.format_coordinator.get_ui_state(),
            slot_count=len(self.window.format_coordinator.get_slot_states()),
            sanitize_ui_state=self.window.format_coordinator.sanitize_ui_state,
            default_font_size=self.window.format_coordinator.get_desired_size(),
        )
        self.apply_loaded_document_session(session)

    def save_file(self):
        path = self._current_file_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self.window,
                "Save DonkeyTyper File",
                "selftitled.dty",
                "DonkeyTyper Files (*.dty);;All Files (*.*)",
            )
            if not path:
                return
        if not path.lower().endswith(".dty"):
            base, _ = os.path.splitext(path)
            path = f"{base}.dty"

        payload = build_dty_payload(
            document=self.window.controller.get_document().to_dict(),
            paragraph_type_definitions=export_runtime_paragraph_type_definitions(),
            ui_state=self.window.format_coordinator.get_ui_state(),
            active_slot=self.window.format_coordinator.get_active_slot(),
            slot_states=[
                self.window.format_coordinator.sanitize_ui_state(state)
                for state in self.window.format_coordinator.get_slot_states()
            ],
        )
        save_dty_payload(path, payload)
        self.mark_clean(path=path)
