import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

# Create UI directory if it doesn't exist
os.makedirs('ui', exist_ok=True)

from downloader import DownloadManager
from torrent_downloader import TorrentManager
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Advanced Download Manager")

    # Create download managers
    download_manager = DownloadManager()
    torrent_manager = TorrentManager()

    # Create and show main window
    main_window = MainWindow(download_manager, torrent_manager)
    main_window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
