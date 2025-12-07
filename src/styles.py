from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

def apply_dark_theme(app):
    app.setStyle("Fusion")
    
    palette = QPalette()
    
    # Base Colors
    dark_gray = QColor(45, 45, 45)
    gray = QColor(53, 53, 53)
    black = QColor(25, 25, 25)
    blue = QColor(42, 130, 218)
    
    # Text
    white = QColor(255, 255, 255)
    
    palette.setColor(QPalette.Window, gray)
    palette.setColor(QPalette.WindowText, white)
    palette.setColor(QPalette.Base, black)
    palette.setColor(QPalette.AlternateBase, dark_gray)
    palette.setColor(QPalette.ToolTipBase, white)
    palette.setColor(QPalette.ToolTipText, white)
    palette.setColor(QPalette.Text, white)
    palette.setColor(QPalette.Button, gray)
    palette.setColor(QPalette.ButtonText, white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, blue)
    palette.setColor(QPalette.Highlight, blue)
    palette.setColor(QPalette.HighlightedText, black)
    
    # Placeholder text color (Important for dark themes)
    palette.setColor(QPalette.PlaceholderText, QColor(127, 127, 127))
    
    # Disabled state
    palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
    
    app.setPalette(palette)
    
    # Add some common stylesheet fixes
    app.setStyleSheet("""
        QToolTip { 
            color: #ffffff; 
            background-color: #2a82da; 
            border: 1px solid white; 
        }
        QInputDialog {
            background-color: #353535;
        }
        QLineEdit {
            placeholder-text-color: #7f7f7f;
        }
    """)
