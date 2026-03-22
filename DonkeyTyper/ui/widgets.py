from PySide6.QtCore import QEvent, Qt, QMimeData, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QInputMethodEvent, QKeySequence, QPainter, QPen, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bridge.layout_policy import (
    build_list_prefix_layout_spec,
    compute_list_prefix_x_from_spec,
    get_rendered_paragraph_font_size,
)
from .clipboard_mime import INTERNAL_PARAGRAPH_MIME
from .styles import build_button_style


class DonkeyTextEdit(QTextEdit):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self.setTabChangesFocus(False)
        self.setFocusPolicy(Qt.StrongFocus)

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride and getattr(event, "key", None) and event.key() == Qt.Key_Tab:
            event.accept()
            return True
        if event.type() == QEvent.KeyPress and getattr(event, "key", None) and event.key() == Qt.Key_Tab:
            if event.isAutoRepeat():
                event.accept()
                return True
            self._owner.preview_coordinator.handle_tab_press()
            event.accept()
            return True
        if event.type() == QEvent.KeyRelease and getattr(event, "key", None) and event.key() == Qt.Key_Tab:
            if event.isAutoRepeat():
                event.accept()
                return True
            self._owner.preview_coordinator.handle_tab_release()
            event.accept()
            return True
        return super().event(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        self._paint_list_prefixes()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            QTimer.singleShot(0, self._owner.format_coordinator.reassert_format)

    def keyPressEvent(self, event):
        if self._is_ctrl_shortcut(event, Qt.Key_Z):
            self._owner._undo_via_controller()
            event.accept()
            return
        if self._is_ctrl_shortcut(event, Qt.Key_R):
            self._owner._redo_via_controller()
            event.accept()
            return
        if event.matches(QKeySequence.Cut):
            self._owner.input_coordinator.handle_model_cut()
            event.accept()
            return
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_W:
            self._owner._step_alpha()
            event.accept()
            return
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_E:
            self._owner._step_color()
            event.accept()
            return
        if event.key() == Qt.Key_Backspace:
            self._owner.input_coordinator.handle_model_backspace()
            event.accept()
            return
        if event.key() == Qt.Key_Delete:
            self._owner.input_coordinator.handle_model_delete()
            event.accept()
            return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._owner.input_coordinator.handle_model_enter()
            event.accept()
            return

        if (
            event.text()
            and event.text() >= " "
            and not (event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
        ):
            if self._owner.input_coordinator.handle_model_text_input(event.text()):
                event.accept()
                return

        super().keyPressEvent(event)

    def inputMethodEvent(self, event):
        commit_text = event.commitString()
        if commit_text:
            if self._owner.input_coordinator.handle_model_ime_commit(commit_text):
                cleanup_event = QInputMethodEvent()
                cleanup_event.setCommitString("", 0, 0)
                self._owner._suppress_editor_backsync = True
                try:
                    super().inputMethodEvent(cleanup_event)
                finally:
                    self._owner._suppress_editor_backsync = False
                event.accept()
                return
        else:
            selection_offsets = self._owner.editor_bridge.get_editor_selection_paragraph_offsets(self.textCursor())
            if selection_offsets is not None:
                self._owner._ime_replacement_selection_offsets = selection_offsets
        self._owner._suppress_editor_backsync = True
        try:
            super().inputMethodEvent(event)
        finally:
            self._owner._suppress_editor_backsync = False
        if not commit_text and not event.preeditString():
            self._owner._clear_ime_replacement_selection_context()

    def insertFromMimeData(self, source):
        if source is None:
            return
        if source.hasFormat(INTERNAL_PARAGRAPH_MIME):
            payload = bytes(source.data(INTERNAL_PARAGRAPH_MIME))
            if self._owner.input_coordinator.handle_model_internal_paste(payload):
                return
        if not source.hasText():
            super().insertFromMimeData(source)
            return

        text = source.text()
        if text is None:
            return

        if self._owner.input_coordinator.handle_model_paste(text):
            return

        cursor = self.textCursor()
        fmt = self._get_block_first_char_format(cursor)
        if fmt is None:
            fmt = self.currentCharFormat()

        cursor.beginEditBlock()
        try:
            cursor.insertText(text, fmt)
        finally:
            cursor.endEditBlock()
            self.setTextCursor(cursor)

    def createMimeDataFromSelection(self):
        base = super().createMimeDataFromSelection()
        mime = QMimeData()
        external_text = self._owner.input_coordinator.build_external_clipboard_text()
        if external_text is not None:
            mime.setText(external_text)
        external_html = self._owner.input_coordinator.build_external_clipboard_html()
        if external_html is not None:
            mime.setHtml(external_html)
        markdown = bytes(base.data("text/markdown"))
        if markdown:
            mime.setData("text/markdown", markdown)
        payload = self._owner.input_coordinator.build_internal_clipboard_payload()
        if payload:
            mime.setData(INTERNAL_PARAGRAPH_MIME, payload)
        return mime

    def _get_block_first_char_format(self, cursor: QTextCursor):
        block = cursor.block()
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            if fragment.isValid() and fragment.length() > 0:
                return fragment.charFormat()
            it += 1
        return None

    def _is_ctrl_shortcut(self, event, key: int) -> bool:
        modifiers = event.modifiers()
        return bool(modifiers & Qt.ControlModifier) and not bool(
            modifiers & (Qt.AltModifier | Qt.MetaModifier)
        ) and event.key() == key

    def _paint_list_prefixes(self):
        document = self._owner.controller.get_document()
        if not document.paragraphs:
            return

        painter = QPainter(self.viewport())
        painter.setPen(QColor("#000000"))

        block = self.document().firstBlock()
        paragraph_index = 0
        while block.isValid() and paragraph_index < len(document.paragraphs):
            paragraph = document.paragraphs[paragraph_index]
            prefix_layout_spec = build_list_prefix_layout_spec(document, paragraph_index)
            if prefix_layout_spec is not None:
                painter.setFont(QFont(self._owner.ui_font_family, get_rendered_paragraph_font_size(paragraph)))
                metrics = painter.fontMetrics()
                prefix_x, prefix_y = self._get_list_prefix_position(block, prefix_layout_spec, metrics)
                if prefix_layout_spec.render_as_bullet:
                    self._paint_unordered_prefix(painter, prefix_x, prefix_y, metrics)
                else:
                    painter.drawText(prefix_x, prefix_y, prefix_layout_spec.prefix_text)

            block = block.next()
            paragraph_index += 1

    def _paint_unordered_prefix(self, painter: QPainter, prefix_x: int, baseline_y: int, metrics):
        diameter = max(4.0, min(6.0, float(metrics.xHeight()) * 0.45))
        center_y = float(baseline_y) - float(metrics.ascent()) + (float(metrics.height()) / 2.0)
        rect = QRectF(
            float(prefix_x),
            center_y - (diameter / 2.0),
            diameter,
            diameter,
        )
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#000000"))
        painter.drawEllipse(rect)
        painter.restore()

    def _get_list_prefix_position(self, block, prefix_layout_spec, metrics):
        doc_layout = self.document().documentLayout()
        block_rect = doc_layout.blockBoundingRect(block)
        block_format = block.blockFormat()
        layout = block.layout()

        left_margin = float(block_format.leftMargin())
        document_margin = float(self.document().documentMargin())
        x = int(
            round(
                document_margin
                + compute_list_prefix_x_from_spec(left_margin, metrics, prefix_layout_spec)
                - self.horizontalScrollBar().value()
            )
        )

        if layout is not None and layout.lineCount() > 0:
            line = layout.lineAt(0)
            y = int(round(block_rect.top() - self.verticalScrollBar().value() + line.y() + line.ascent()))
        else:
            y = int(round(block_rect.top() - self.verticalScrollBar().value() + metrics.ascent()))
        return x, y


class MarkdownPreviewEdit(QTextEdit):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self.setTabChangesFocus(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setStyleSheet("QTextEdit { color: #000000; background: #E0DED4; selection-background-color: #000080; selection-color: #FFFFFF; }")

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride and getattr(event, "key", None) and event.key() == Qt.Key_Tab:
            event.accept()
            return True
        if event.type() == QEvent.KeyPress and getattr(event, "key", None) and event.key() == Qt.Key_Tab:
            if event.isAutoRepeat():
                event.accept()
                return True
            self._owner.preview_coordinator.handle_tab_press()
            event.accept()
            return True
        if event.type() == QEvent.KeyRelease and getattr(event, "key", None) and event.key() == Qt.Key_Tab:
            if event.isAutoRepeat():
                event.accept()
                return True
            self._owner.preview_coordinator.handle_tab_release()
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if self._is_ctrl_shortcut(event, Qt.Key_C):
            if self.textCursor().hasSelection():
                self.copy()
            else:
                self._copy_all_text()
            event.accept()
            return
        if event.matches(QKeySequence.Copy):
            if self.textCursor().hasSelection():
                self.copy()
            else:
                self._copy_all_text()
            event.accept()
            return
        super().keyPressEvent(event)

    def _copy_all_text(self):
        cursor = self.textCursor()
        anchor = cursor.anchor()
        position = cursor.position()
        cursor.select(QTextCursor.Document)
        self.setTextCursor(cursor)
        self.copy()
        restored = self.textCursor()
        restored.setPosition(min(anchor, self.document().characterCount() - 1))
        restored.setPosition(min(position, self.document().characterCount() - 1), QTextCursor.KeepAnchor)
        self.setTextCursor(restored)

    def _is_ctrl_shortcut(self, event, key: int) -> bool:
        modifiers = event.modifiers()
        return bool(modifiers & Qt.ControlModifier) and not bool(
            modifiers & (Qt.AltModifier | Qt.MetaModifier)
        ) and event.key() == key


class Win98TitleBar(QWidget):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self._drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._owner.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self._owner.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._owner.isMaximized():
                self._owner.showNormal()
            else:
                self._owner.showMaximized()
            event.accept()
        super().mouseDoubleClickEvent(event)


class Win98Dialog(QDialog):
    def __init__(self, owner, title: str, message: str):
        super().__init__(owner)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.Dialog, True)
        self.setModal(True)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        titlebar = Win98TitleBar(owner)
        titlebar.setObjectName("TitleBar")
        titlebar.setFixedHeight(24)
        titlebar.setAttribute(Qt.WA_StyledBackground, True)
        titlebar.setAutoFillBackground(True)
        titlebar.setStyleSheet("QWidget#TitleBar { background-color: #000080; }")

        title_layout = QHBoxLayout(titlebar)
        title_layout.setContentsMargins(6, 3, 6, 3)
        title_label = QLabel(title)
        title_label.setObjectName("TitleLabel")
        title_label.setFont(QFont(owner.chrome_font_family, 9, QFont.Bold))
        title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(12)
        body.setStyleSheet("background: #E0DED4;")
        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setFont(QFont(owner.chrome_font_family, 9))
        body_layout.addWidget(msg)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self.btn_yes = QToolButton()
        self.btn_yes.setText("Yes")
        self.btn_yes.setFixedSize(60, 22)
        self.btn_yes.setFont(QFont(owner.chrome_font_family, 8))
        self.btn_yes.setStyleSheet(build_button_style())

        self.btn_no = QToolButton()
        self.btn_no.setText("No")
        self.btn_no.setFixedSize(60, 22)
        self.btn_no.setFont(QFont(owner.chrome_font_family, 8))
        self.btn_no.setStyleSheet(build_button_style())

        self.btn_cancel = QToolButton()
        self.btn_cancel.setText("Cancel")
        self.btn_cancel.setFixedSize(60, 22)
        self.btn_cancel.setFont(QFont(owner.chrome_font_family, 8))
        self.btn_cancel.setStyleSheet(build_button_style())

        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_yes)
        btn_layout.addWidget(self.btn_no)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        body_layout.addWidget(btn_row)

        layout.addWidget(titlebar)
        layout.addWidget(body)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(root)

        self.btn_yes.clicked.connect(lambda: self.done(1))
        self.btn_no.clicked.connect(lambda: self.done(2))
        self.btn_cancel.clicked.connect(lambda: self.done(3))


class TickBar(QWidget):
    def __init__(self, slider: QSlider, parent=None):
        super().__init__(parent)
        self._slider = slider
        self.setFixedHeight(8)

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(QColor("#2A2A2A"))
        pen.setWidth(1)
        pen.setCosmetic(True)
        painter.setPen(pen)

        h = self.height()
        steps = max(1, self._slider.maximum() - self._slider.minimum())
        opt = QStyleOptionSlider()
        self._slider.initStyleOption(opt)
        groove = self._slider.style().subControlRect(
            QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self._slider
        )
        srect = self._slider.rect()
        if srect.width() <= 1 or self.width() <= 1:
            return

        left_ratio = groove.left() / float(srect.width() - 1)
        right_ratio = groove.right() / float(srect.width() - 1)

        tick_right = int(round(right_ratio * (self.width() - 1)))
        tick_left = int(round(left_ratio * (self.width() - 1)))
        w = max(1, tick_right - tick_left)
        tick_left = max(0, tick_right - w)
        if steps <= 0:
            return
        painter.drawLine(1, 0, 1, h)
        painter.drawLine(tick_right, 0, tick_right, h)
        for i in range(1, steps):
            x = tick_left + int(round(w * i / steps))
            painter.drawLine(x, 0, x, h)
