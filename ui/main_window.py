from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QFileDialog,
    QSpinBox, QListWidget, QListWidgetItem,
    QMenu, QAction, QMessageBox, QTabWidget,
    QCheckBox, QGroupBox, QFormLayout, QRadioButton,
    QButtonGroup
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

import os
import re

from ui.download_item import DownloadItemWidget
from ui.torrent_item import TorrentItemWidget, FileSelectionDialog
from torrent_downloader import LIBTORRENT_AVAILABLE


class MainWindow(QMainWindow):
    def __init__(self, download_manager, torrent_manager):
        super().__init__()

        self.download_manager = download_manager
        self.torrent_manager = torrent_manager
        self.default_save_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.init_ui()

        # Setup timer for updating UI
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_ui)
        self.update_timer.start(500)  # Update every 500ms

    def init_ui(self):
        self.setWindowTitle("Advanced Download Manager")
        self.setMinimumSize(800, 600)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Downloads tab
        downloads_tab = QWidget()
        downloads_layout = QVBoxLayout(downloads_tab)

        # URL input section
        url_group = QGroupBox("Add New Download")
        url_layout = QVBoxLayout()

        input_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL or magnet link to download")
        input_layout.addWidget(url_label)
        input_layout.addWidget(self.url_input)

        # Download type selection
        type_layout = QHBoxLayout()
        type_label = QLabel("Type:")
        self.type_http = QRadioButton("HTTP/HTTPS")
        self.type_http.setChecked(True)
        self.type_torrent = QRadioButton("Torrent/Magnet")

        # Create button group
        self.type_group = QButtonGroup()
        self.type_group.addButton(self.type_http)
        self.type_group.addButton(self.type_torrent)

        # Connect signals
        self.type_http.toggled.connect(self.toggle_download_type)
        self.type_torrent.toggled.connect(self.toggle_download_type)

        type_layout.addWidget(type_label)
        type_layout.addWidget(self.type_http)
        type_layout.addWidget(self.type_torrent)
        type_layout.addStretch()

        options_layout = QHBoxLayout()

        # HTTP options
        self.http_options = QWidget()
        http_layout = QHBoxLayout(self.http_options)
        http_layout.setContentsMargins(0, 0, 0, 0)

        threads_layout = QHBoxLayout()
        threads_label = QLabel("Threads:")
        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setRange(1, 32)
        self.threads_spinbox.setValue(4)
        threads_layout.addWidget(threads_label)
        threads_layout.addWidget(self.threads_spinbox)

        http_layout.addLayout(threads_layout)

        # Torrent options
        self.torrent_options = QWidget()
        torrent_layout = QHBoxLayout(self.torrent_options)
        torrent_layout.setContentsMargins(0, 0, 0, 0)

        # Initially hide torrent options
        self.torrent_options.setVisible(False)

        # Save location (common for both)
        save_layout = QHBoxLayout()
        save_label = QLabel("Save to:")
        self.save_path_input = QLineEdit()
        self.save_path_input.setReadOnly(True)
        self.save_path_input.setText(self.default_save_path)  # Set default save path
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_save_location)
        save_layout.addWidget(save_label)
        save_layout.addWidget(self.save_path_input)
        save_layout.addWidget(self.browse_button)

        options_layout.addWidget(self.http_options)
        options_layout.addWidget(self.torrent_options)
        options_layout.addLayout(save_layout)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Download")
        self.add_button.clicked.connect(self.add_download)
        self.add_button.setMinimumHeight(40)
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)

        url_layout.addLayout(input_layout)
        url_layout.addLayout(type_layout)
        url_layout.addLayout(options_layout)
        url_layout.addLayout(button_layout)
        url_group.setLayout(url_layout)

        downloads_layout.addWidget(url_group)

        # Downloads list
        downloads_list_group = QGroupBox("Downloads")
        downloads_list_layout = QVBoxLayout()

        self.downloads_list = QListWidget()
        self.downloads_list.setSelectionMode(QListWidget.SingleSelection)
        self.downloads_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.downloads_list.customContextMenuRequested.connect(self.show_context_menu)

        downloads_list_layout.addWidget(self.downloads_list)
        downloads_list_group.setLayout(downloads_list_layout)

        downloads_layout.addWidget(downloads_list_group)

        # Settings tab
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)

        # General settings
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout()

        self.max_concurrent_downloads = QSpinBox()
        self.max_concurrent_downloads.setRange(1, 10)
        self.max_concurrent_downloads.setValue(3)
        self.max_concurrent_downloads.valueChanged.connect(self.update_max_concurrent_downloads)

        self.auto_start_downloads = QCheckBox()
        self.auto_start_downloads.setChecked(True)

        general_layout.addRow("Max Concurrent Downloads:", self.max_concurrent_downloads)
        general_layout.addRow("Auto-start Downloads:", self.auto_start_downloads)

        general_group.setLayout(general_layout)
        settings_layout.addWidget(general_group)

        # Add tabs
        self.tabs.addTab(downloads_tab, "Downloads")
        self.tabs.addTab(settings_tab, "Settings")

        # Status bar
        self.statusBar().showMessage("Ready")

    def browse_save_location(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Save Location")
        if directory:
            self.save_path_input.setText(directory)

    def toggle_download_type(self):
        """Toggle between HTTP and Torrent download options"""
        if self.type_http.isChecked():
            self.http_options.setVisible(True)
            self.torrent_options.setVisible(False)
            self.url_input.setPlaceholderText("Enter URL to download")
        else:
            if not LIBTORRENT_AVAILABLE:
                QMessageBox.warning(
                    self,
                    "Torrent Support Not Available",
                    "Torrent functionality is not available because libtorrent is not installed.\n\n"
                    "To enable torrent support, please install libtorrent with:\n"
                    "pip install python-libtorrent"
                )
                # Switch back to HTTP
                self.type_http.setChecked(True)
                return

            self.http_options.setVisible(False)
            self.torrent_options.setVisible(True)
            self.url_input.setPlaceholderText("Enter magnet link or torrent URL")

    def add_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a URL or magnet link to download")
            return

        save_path = self.save_path_input.text() if self.save_path_input.text() else None

        # Check if it's a HTTP or Torrent download
        if self.type_http.isChecked():
            # HTTP download
            threads = self.threads_spinbox.value()

            # Add download to manager
            download_index = self.download_manager.add_download(url, threads, save_path)

            # Create widget for the download
            download_item = DownloadItemWidget(self.download_manager.downloads[download_index], download_index)
            download_item.pause_resume_clicked.connect(self.toggle_pause_resume)
            download_item.cancel_clicked.connect(self.cancel_download)
            download_item.show_in_folder_clicked.connect(self.open_containing_folder)
            download_item.remove_clicked.connect(self.remove_download)

            # Add to list
            item = QListWidgetItem(self.downloads_list)
            item.setSizeHint(download_item.sizeHint())
            self.downloads_list.addItem(item)
            self.downloads_list.setItemWidget(item, download_item)
        else:
            # Torrent download
            # Check if libtorrent is available
            if not LIBTORRENT_AVAILABLE:
                QMessageBox.warning(
                    self,
                    "Torrent Support Not Available",
                    "Torrent functionality is not available because libtorrent is not installed.\n\n"
                    "To enable torrent support, please install libtorrent with:\n"
                    "pip install python-libtorrent"
                )
                return

            # Check if it's a valid magnet link
            if not url.startswith("magnet:"):
                QMessageBox.warning(self, "Input Error", "Please enter a valid magnet link")
                return

            try:
                # Add download to torrent manager
                download_index = self.torrent_manager.add_download(url, save_path)

                # Create widget for the torrent download
                torrent_item = TorrentItemWidget(self.torrent_manager.downloads[download_index], download_index)
                torrent_item.pause_resume_clicked.connect(self.toggle_pause_resume_torrent)
                torrent_item.cancel_clicked.connect(self.cancel_download_torrent)
                torrent_item.show_in_folder_clicked.connect(self.open_containing_folder_torrent)
                torrent_item.remove_clicked.connect(self.remove_download_torrent)
                torrent_item.select_files_clicked.connect(self.select_torrent_files)

                # Add to list
                item = QListWidgetItem(self.downloads_list)
                item.setSizeHint(torrent_item.sizeHint())
                self.downloads_list.addItem(item)
                self.downloads_list.setItemWidget(item, torrent_item)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add torrent: {str(e)}")

        # Clear input
        self.url_input.clear()

    def update_ui(self):
        # Update all download items
        for i in range(self.downloads_list.count()):
            item = self.downloads_list.item(i)
            widget = self.downloads_list.itemWidget(item)
            if widget:
                widget.update_ui()

        # Update status bar
        http_active = sum(1 for d in self.download_manager.downloads if d.status == "downloading")
        http_queued = sum(1 for d in self.download_manager.downloads if d.status == "initializing")
        http_completed = sum(1 for d in self.download_manager.downloads if d.status == "completed")

        torrent_active = sum(1 for d in self.torrent_manager.downloads if d.status == "downloading")
        torrent_queued = sum(1 for d in self.torrent_manager.downloads if d.status == "initializing")
        torrent_completed = sum(1 for d in self.torrent_manager.downloads if d.status == "completed")

        active = http_active + torrent_active
        queued = http_queued + torrent_queued
        completed = http_completed + torrent_completed

        self.statusBar().showMessage(f"Active: {active} | Queued: {queued} | Completed: {completed} | HTTP: {len(self.download_manager.downloads)} | Torrents: {len(self.torrent_manager.downloads)}")

    def show_context_menu(self, position):
        item = self.downloads_list.itemAt(position)
        if not item:
            return

        widget = self.downloads_list.itemWidget(item)
        if not widget:
            return

        download_index = widget.download_index
        download = self.download_manager.downloads[download_index]

        menu = QMenu()

        if download.status == "downloading":
            pause_action = QAction("Pause", self)
            pause_action.triggered.connect(lambda: self.toggle_pause_resume(download_index))
            menu.addAction(pause_action)
        elif download.status == "paused":
            resume_action = QAction("Resume", self)
            resume_action.triggered.connect(lambda: self.toggle_pause_resume(download_index))
            menu.addAction(resume_action)

        if download.status in ["downloading", "paused"]:
            cancel_action = QAction("Cancel", self)
            cancel_action.triggered.connect(lambda: self.cancel_download(download_index))
            menu.addAction(cancel_action)

        if download.status == "completed":
            open_folder_action = QAction("Open Containing Folder", self)
            open_folder_action.triggered.connect(lambda: self.open_containing_folder(download_index))
            menu.addAction(open_folder_action)

        remove_action = QAction("Remove from List", self)
        remove_action.triggered.connect(lambda: self.remove_download(download_index))
        menu.addAction(remove_action)

        menu.exec_(self.downloads_list.mapToGlobal(position))

    def toggle_pause_resume(self, download_index):
        download = self.download_manager.downloads[download_index]

        if download.status == "downloading":
            self.download_manager.pause_download(download_index)
        elif download.status == "paused":
            self.download_manager.resume_download(download_index)

    def cancel_download(self, download_index):
        reply = QMessageBox.question(
            self,
            "Confirm Cancel",
            "Are you sure you want to cancel this download?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.download_manager.cancel_download(download_index)

    def remove_download(self, download_index):
        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            "Are you sure you want to remove this download from the list?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Find the item in the list
            for i in range(self.downloads_list.count()):
                item = self.downloads_list.item(i)
                widget = self.downloads_list.itemWidget(item)
                if widget and widget.download_index == download_index:
                    self.downloads_list.takeItem(i)
                    break

            self.download_manager.remove_download(download_index)

    def open_containing_folder(self, download_index):
        """Open the folder containing the downloaded file"""
        if 0 <= download_index < len(self.download_manager.downloads):
            download = self.download_manager.downloads[download_index]
            folder_path = download.save_path

            if os.path.exists(folder_path):
                try:
                    # Open folder with default file explorer
                    # Since we're on Windows, use os.startfile
                    os.startfile(folder_path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not open folder: {str(e)}")

    def update_max_concurrent_downloads(self, value):
        self.download_manager.set_max_concurrent_downloads(value)
        self.torrent_manager.set_max_concurrent_downloads(value)

    # Torrent-specific methods
    def toggle_pause_resume_torrent(self, download_index):
        download = self.torrent_manager.downloads[download_index]

        if download.status == "downloading":
            self.torrent_manager.pause_download(download_index)
        elif download.status == "paused":
            self.torrent_manager.resume_download(download_index)

    def cancel_download_torrent(self, download_index):
        reply = QMessageBox.question(
            self,
            "Confirm Cancel",
            "Are you sure you want to cancel this torrent download?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.torrent_manager.cancel_download(download_index)

    def remove_download_torrent(self, download_index):
        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            "Are you sure you want to remove this torrent from the list?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Find the item in the list
            for i in range(self.downloads_list.count()):
                item = self.downloads_list.item(i)
                widget = self.downloads_list.itemWidget(item)
                if isinstance(widget, TorrentItemWidget) and widget.download_index == download_index:
                    self.downloads_list.takeItem(i)
                    break

            self.torrent_manager.remove_download(download_index)

    def open_containing_folder_torrent(self, download_index):
        """Open the folder containing the torrent files"""
        if 0 <= download_index < len(self.torrent_manager.downloads):
            download = self.torrent_manager.downloads[download_index]
            folder_path = download.save_path

            if os.path.exists(folder_path):
                try:
                    # Open folder with default file explorer
                    # Since we're on Windows, use os.startfile
                    os.startfile(folder_path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not open folder: {str(e)}")

    def select_torrent_files(self, download_index):
        """Open dialog to select which files to download from the torrent"""
        if 0 <= download_index < len(self.torrent_manager.downloads):
            torrent = self.torrent_manager.downloads[download_index]

            # Check if metadata is available
            if not torrent.torrent_info:
                QMessageBox.information(self, "Please Wait", "Torrent metadata is still being downloaded. Please try again in a moment.")
                return

            # Open file selection dialog
            dialog = FileSelectionDialog(torrent.files, torrent.selected_files, self)
            if dialog.exec_():
                selected_indices = dialog.get_selected_indices()
                self.torrent_manager.select_files(download_index, selected_indices)
