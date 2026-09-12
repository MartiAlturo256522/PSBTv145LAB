"""Sparrow-inspired dense dark palette. No engine logic."""

STYLESHEET = """
QWidget {
  background: #1b1b1b;
  color: #e4e4e4;
  font-family: "Segoe UI", "Inter", sans-serif;
  font-size: 12px;
}
QMainWindow, QDialog { background: #1b1b1b; }
QFrame#sidebar {
  background: #141414;
  border-right: 1px solid #333;
}
QLabel#brand {
  color: #f0f0f0;
  font-weight: 600;
  font-size: 13px;
  letter-spacing: 0.04em;
}
QLabel#muted { color: #8d8d8d; }
QLabel#gold { color: #d4a017; }
QPushButton {
  background: #2a2a2a;
  border: 1px solid #3d3d3d;
  padding: 5px 10px;
  color: #e4e4e4;
}
QPushButton:hover { border-color: #d4a017; }
QPushButton#primary {
  background: #3a2e10;
  border: 1px solid #d4a017;
  color: #f5d67b;
  font-weight: 600;
  padding: 8px 14px;
}
QPushButton#primary:hover { background: #4a3a14; }
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
  background: #111;
  border: 1px solid #3a3a3a;
  padding: 3px 6px;
  selection-background-color: #3a2e10;
  font-family: "Cascadia Mono", "Consolas", monospace;
  font-size: 11px;
}
QGroupBox {
  border: 1px solid #333;
  margin-top: 10px;
  padding: 8px 6px 6px 6px;
  font-weight: 600;
  color: #c9c9c9;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QTabWidget::pane { border: 1px solid #333; }
QTabBar::tab {
  background: #222;
  border: 1px solid #333;
  padding: 5px 10px;
  color: #aaa;
}
QTabBar::tab:selected { background: #2c2c2c; color: #f5d67b; border-bottom: 1px solid #2c2c2c; }
QListWidget, QTreeWidget {
  background: #141414;
  border: none;
  outline: none;
}
QListWidget::item { padding: 6px 8px; }
QListWidget::item:selected { background: #2a2414; color: #f5d67b; }
QSplitter::handle { background: #333; width: 1px; height: 1px; }
QStatusBar {
  background: #121212;
  border-top: 1px solid #333;
  color: #8d8d8d;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 11px;
}
QScrollArea { border: none; }
QCheckBox, QRadioButton { spacing: 6px; }
QToolTip { background: #222; color: #eee; border: 1px solid #555; }
"""
