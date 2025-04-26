from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar,
    QSizePolicy, QToolButton
)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon

import os
import time


def format_size(size_bytes):
    """Format bytes to human-readable size"""
    if size_bytes == 0:
        return "0B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1

    return f"{size_bytes:.2f} {size_names[i]}"


def format_time(seconds):
    """Format seconds to human-readable time"""
    if seconds < 60:
        return f"{seconds:.0f} sec"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.0f} min"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hr"


class DownloadItemWidget(QWidget):
    pause_resume_clicked = pyqtSignal(int)
    cancel_clicked = pyqtSignal(int)
    show_in_folder_clicked = pyqtSignal(int)
    remove_clicked = pyqtSignal(int)

    def __init__(self, download_task, download_index):
        super().__init__()

        self.download_task = download_task
        self.download_index = download_index

        self.init_ui()

        # Enable mouse tracking for double-click
        self.setMouseTracking(True)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Top row: filename and status
        top_layout = QHBoxLayout()

        self.filename_label = QLabel(self.download_task.filename or "Initializing...")
        self.filename_label.setFont(self.font())
        self.filename_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.status_label = QLabel(self.download_task.status.capitalize())

        # Action buttons
        action_layout = QHBoxLayout()

        # Show in folder button
        self.show_folder_button = QToolButton()
        self.show_folder_button.setIcon(QIcon.fromTheme("folder-open", QIcon()))
        self.show_folder_button.setToolTip("Show in folder")
        self.show_folder_button.clicked.connect(
            lambda: self.show_in_folder_clicked.emit(self.download_index)
        )

        # Remove button
        self.remove_button = QToolButton()
        self.remove_button.setIcon(QIcon.fromTheme("edit-delete", QIcon()))
        self.remove_button.setToolTip("Remove from list")
        self.remove_button.clicked.connect(
            lambda: self.remove_clicked.emit(self.download_index)
        )

        action_layout.addWidget(self.show_folder_button)
        action_layout.addWidget(self.remove_button)

        top_layout.addWidget(self.filename_label)
        top_layout.addWidget(self.status_label)
        top_layout.addLayout(action_layout)

        # Middle row: progress bar
        middle_layout = QHBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(self.download_task.progress)
        self.progress_bar.setTextVisible(True)

        middle_layout.addWidget(self.progress_bar)

        # Bottom row: details and buttons
        bottom_layout = QHBoxLayout()

        self.details_label = QLabel()
        self.update_details_label()

        self.pause_resume_button = QPushButton("Pause")
        self.pause_resume_button.clicked.connect(
            lambda: self.pause_resume_clicked.emit(self.download_index)
        )

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(
            lambda: self.cancel_clicked.emit(self.download_index)
        )

        bottom_layout.addWidget(self.details_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.pause_resume_button)
        bottom_layout.addWidget(self.cancel_button)

        # Add all layouts to main layout
        main_layout.addLayout(top_layout)
        main_layout.addLayout(middle_layout)
        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open the downloaded file"""
        if self.download_task.status == "completed":
            file_path = os.path.join(self.download_task.save_path, self.download_task.filename)
            if os.path.exists(file_path):
                try:
                    # Open file with default application
                    # Since we're on Windows, use os.startfile
                    os.startfile(file_path)
                except Exception as e:
                    print(f"Error opening file: {e}")

        # Call the parent class implementation
        super().mouseDoubleClickEvent(event)

    def update_ui(self):
        # Update filename
        if self.download_task.filename:
            self.filename_label.setText(self.download_task.filename)

        # Update status
        self.status_label.setText(self.download_task.status.capitalize())

        # Update progress
        self.progress_bar.setValue(self.download_task.progress)

        # Update details
        self.update_details_label()

        # Update action buttons visibility
        if self.download_task.status == "completed":
            self.show_folder_button.setVisible(True)
            self.show_folder_button.setEnabled(True)
        else:
            self.show_folder_button.setVisible(False)

        # Update buttons
        if self.download_task.status == "downloading":
            self.pause_resume_button.setText("Pause")
            self.pause_resume_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
        elif self.download_task.status == "paused":
            self.pause_resume_button.setText("Resume")
            self.pause_resume_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
        elif self.download_task.status == "completed":
            self.pause_resume_button.setText("Completed")
            self.pause_resume_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
        elif self.download_task.status == "error":
            self.pause_resume_button.setText("Error")
            self.pause_resume_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
        elif self.download_task.status == "canceled":
            self.pause_resume_button.setText("Canceled")
            self.pause_resume_button.setEnabled(False)
            self.cancel_button.setEnabled(False)

    def update_details_label(self):
        downloaded = format_size(self.download_task.downloaded_size)
        total = format_size(self.download_task.total_size)

        details = f"{downloaded} of {total}"

        if self.download_task.download_speed > 0:
            speed = format_size(self.download_task.download_speed)
            details += f" | {speed}/s"

        if self.download_task.eta > 0:
            eta = format_time(self.download_task.eta)
            details += f" | {eta} remaining"

        self.details_label.setText(details)
