from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vidgrab.linkgrabber import LinkCandidate, extract_urls_from_clipboard_text

if TYPE_CHECKING:  # pragma: no cover - imported only for static typing
    from collections.abc import Sequence

DEFAULT_CATEGORIES = {
    "video",
    "audio",
    "image",
    "archive",
    "subtitle",
    "document",
    "page",
}


@dataclass(frozen=True)
class LinkGrabberRow:
    """UI-facing row shown in the desktop LinkGrabber table."""

    url: str
    category: str
    selected: bool = True
    source_url: str | None = None
    depth: int = 0

    @classmethod
    def from_candidate(cls, candidate: LinkCandidate) -> LinkGrabberRow:
        return cls(
            url=candidate.url,
            category=candidate.category,
            selected=candidate.selected,
            source_url=candidate.source_url,
            depth=candidate.depth,
        )


@dataclass
class DesktopShellState:
    """Headless state/controller for the portable desktop shell.

    Keeping the LinkGrabber behavior outside Qt lets tests verify the MVP behavior without
    requiring a display server, and makes the UI a thin local desktop wrapper rather than a
    background webserver.
    """

    crawl_depth: int = 2
    selected_categories: set[str] = field(default_factory=lambda: set(DEFAULT_CATEGORIES))
    rows: list[LinkGrabberRow] = field(default_factory=list)
    uses_background_webserver: bool = False

    def scan_text(self, text: str) -> list[LinkGrabberRow]:
        self.rows = [
            LinkGrabberRow.from_candidate(LinkCandidate.from_url(url))
            for url in extract_urls_from_clipboard_text(text)
        ]
        return self.rows

    def visible_rows(self) -> list[LinkGrabberRow]:
        return [row for row in self.rows if row.category in self.selected_categories]

    def set_category_enabled(self, category: str, enabled: bool) -> None:
        if category not in DEFAULT_CATEGORIES:
            raise ValueError(f"unknown category: {category}")
        if enabled:
            self.selected_categories.add(category)
        else:
            self.selected_categories.discard(category)

    def set_crawl_depth(self, depth: int) -> None:
        if depth < 0:
            raise ValueError("crawl depth must be zero or greater")
        self.crawl_depth = depth


def run_desktop_app(argv: Sequence[str] | None = None) -> int:
    """Launch the local PySide6 desktop app.

    PySide6 is imported lazily so CLI/test usage still works in headless or minimal
    environments. Installing project dependencies enables the actual window.
    """

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QPushButton,
            QSpinBox,
            QTableWidget,
            QTableWidgetItem,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:  # pragma: no cover - depends on optional GUI dependency
        raise RuntimeError("PySide6 is required to launch the desktop app") from exc

    state = DesktopShellState()
    app = QApplication(list(argv or []))

    window = QMainWindow()
    window.setWindowTitle("VidGrab Portable LinkGrabber")

    root = QWidget()
    layout = QVBoxLayout(root)

    controls = QHBoxLayout()
    paste_box = QTextEdit()
    paste_box.setPlaceholderText("Paste copied browser URL or selected page text here")
    paste_box.setAcceptRichText(False)

    depth = QSpinBox()
    depth.setMinimum(0)
    depth.setMaximum(10)
    depth.setValue(state.crawl_depth)
    controls.addWidget(QLabel("Crawl depth"))
    controls.addWidget(depth)

    category_checks: dict[str, QCheckBox] = {}
    for category in sorted(DEFAULT_CATEGORIES):
        checkbox = QCheckBox(category.title())
        checkbox.setChecked(True)
        category_checks[category] = checkbox
        controls.addWidget(checkbox)

    scan = QPushButton("Paste / Scan")
    controls.addWidget(scan)
    controls.addStretch(1)

    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["Selected", "Category", "Depth", "URL"])
    table.horizontalHeader().setStretchLastSection(True)

    layout.addLayout(controls)
    layout.addWidget(paste_box)
    layout.addWidget(table)

    def refresh_table() -> None:
        visible = state.visible_rows()
        table.setRowCount(len(visible))
        for row_index, row in enumerate(visible):
            selected = QTableWidgetItem("yes" if row.selected else "no")
            selected.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_index, 0, selected)
            table.setItem(row_index, 1, QTableWidgetItem(row.category))
            table.setItem(row_index, 2, QTableWidgetItem(str(row.depth)))
            table.setItem(row_index, 3, QTableWidgetItem(row.url))

    def scan_text() -> None:
        state.set_crawl_depth(depth.value())
        state.scan_text(paste_box.toPlainText())
        refresh_table()

    scan.clicked.connect(scan_text)
    for category, checkbox in category_checks.items():
        checkbox.toggled.connect(
            lambda checked, category=category: (
                state.set_category_enabled(category, checked),
                refresh_table(),
            )
        )

    window.setCentralWidget(root)
    window.resize(1100, 700)
    window.show()
    return app.exec()
