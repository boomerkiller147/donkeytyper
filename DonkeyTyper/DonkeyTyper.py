import sys

from PySide6.QtWidgets import QApplication

from app.main_window import DonkeyTyper


def main() -> int:
    app = QApplication(sys.argv)
    win = DonkeyTyper()
    win.show()
    app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
