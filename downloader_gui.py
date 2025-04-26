import sys
import os
import math
import time
import pickle
import re
from threading import Thread
from PyQt6.QtWidgets import (
    QApplication, 
    QMainWindow, 
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout, 
    QLineEdit, 
    QPushButton, 
    QProgressBar, 
    QLabel, 
    QSpinBox, 
    QFileDialog,
    QMessageBox,
    QCheckBox,
    QGroupBox,
    QGridLayout
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
import requests
import urllib.parse
from downloader_to_bypass_server_side_speed_limiting import (
    get_splitted_parts, 
    download_part, 
    save_backup, 
    load_backup
)

class DownloaderThread(QThread):
    """Thread to handle the downloading process."""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url, threads, output_path=None, use_backup=False):
        super().__init__()
        self.url = url
        self.threads = threads
        self.output_path = output_path
        self.use_backup = use_backup
        self.is_running = True
        self.download_manager = {}
        self.total_size = 0
        self.partial_saver_turned_on = True
        self.local_filename = ""
        self.download_finished = False

    def run(self):
        try:
            if self.use_backup:
                self.status.emit("Loading from backup...")
                success = self.load_backup_data()
                if not success:
                    self.error.emit("Failed to load backup data.")
                    return
            else:
                self.status.emit("Starting download...")
                response = requests.head(self.url)
                
                try:
                    self.total_size = int(response.headers["Content-Length"])
                except KeyError:
                    self.error.emit("Server did not provide file size. Cannot download.")
                    return
                
                split_size = math.floor(self.total_size / self.threads)
                
                # Determine filename
                try:
                    d = response.headers['content-disposition']
                    filename_match = re.findall('filename=["\']*([^"\']+)', d)
                    if filename_match and filename_match[0]:
                        self.local_filename = filename_match[0].strip('"\'')
                    else:
                        raise KeyError
                except (KeyError, NameError):
                    self.local_filename = urllib.parse.unquote(self.url.split('/')[-1].strip('"\''))
                
                if self.output_path:
                    self.local_filename = os.path.join(self.output_path, self.local_filename)
                
                # Initialize download parts
                file_parts = get_splitted_parts(self.total_size, split_size)
                
                for i, item in enumerate(file_parts):
                    self.download_manager[i] = {
                        "range": item,
                        "content": b'',
                        "download_completed": False
                    }
            
            # Start download threads
            download_threads = []
            for part_number in self.download_manager:
                if not self.download_manager[part_number]["download_completed"]:
                    thread = Thread(
                        target=self.download_part_thread, 
                        args=[part_number]
                    )
                    thread.daemon = True
                    thread.start()
                    download_threads.append(thread)
            
            # Start auto-backup thread
            backup_thread = Thread(target=self.auto_backup_saver)
            backup_thread.daemon = True
            backup_thread.start()
            
            # Start partial save thread
            partial_save_thread = Thread(target=self.save_parts)
            partial_save_thread.daemon = True
            partial_save_thread.start()
            
            start_time = time.time()
            
            # Monitor progress
            while self.is_running:
                downloaded_size = sum(len(self.download_manager[i]["content"]) 
                                   for i in self.download_manager)
                progress = int((downloaded_size / self.total_size) * 100)
                self.progress.emit(progress)
                
                downloaded_parts = sum(1 for i in self.download_manager 
                                     if self.download_manager[i]["download_completed"])
                
                elapsed_time = time.time() - start_time
                if elapsed_time > 0:
                    speed = downloaded_size / elapsed_time / 1024  # KB/s
                    eta = (self.total_size - downloaded_size) / (speed * 1024) if speed > 0 else 0
                    
                    status_msg = (f"{progress}% ({downloaded_size}/{self.total_size} bytes) "
                                 f"downloaded in {elapsed_time:.1f}s | "
                                 f"Speed: {speed:.2f} KB/s | "
                                 f"ETA: {eta:.1f}s | "
                                 f"Parts: {downloaded_parts}/{len(self.download_manager)}")
                    
                    self.status.emit(status_msg)
                
                if len(self.download_manager) == downloaded_parts:
                    self.download_finished = True
                    break
                
                self.msleep(500)
            
            if self.download_finished:
                # Combine parts and save final file
                self.status.emit("Combining downloaded parts...")
                complete_file = b''
                for i in range(len(self.download_manager)):
                    complete_file += self.download_manager[i]["content"]
                
                with open(self.local_filename, 'wb') as f:
                    f.write(complete_file)
                
                self.finished.emit(self.local_filename)
            
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")

    def download_part_thread(self, part_number):
        """Wrapper function to download a part and update the download manager."""
        global url  # This is needed to access the url from the imported downloader module
        url = self.url
        
        resume_header = {'Range': 'bytes={}-{}'.format(
            self.download_manager[part_number]["range"][0], 
            self.download_manager[part_number]["range"][1]
        )}
        
        for i in range(10):  # 10 retry attempts
            try:
                downloaded_content = b''
                response = requests.get(self.url, headers=resume_header, stream=True, 
                                       verify=False, allow_redirects=True)
                
                for data in response.iter_content(chunk_size=1024):
                    if not self.is_running:
                        return
                    downloaded_content += data
                    self.download_manager[part_number]["content"] = downloaded_content
                
                self.download_manager[part_number]["content"] = downloaded_content
                self.download_manager[part_number]["download_completed"] = True
                break
                
            except Exception as e:
                if i == 9:  # Last attempt
                    self.error.emit(f"Part {part_number} failed after 10 attempts: {str(e)}")
                # Continue trying

    def auto_backup_saver(self):
        """Periodically save backup data."""
        while not self.download_finished and self.is_running:
            try:
                self.save_backup_data()
                time.sleep(10)
            except Exception as e:
                self.error.emit(f"Auto backup failed: {str(e)}")

    def save_parts(self):
        """Periodically save partially downloaded file."""
        while not self.download_finished and self.is_running:
            if self.partial_saver_turned_on:
                try:
                    complete_file = b''
                    for i in range(len(self.download_manager)):
                        complete_file += self.download_manager[i]["content"]
                    
                    with open(self.local_filename, 'wb') as f:
                        f.write(complete_file)
                except Exception as e:
                    self.error.emit(f"Partial save failed: {str(e)}")
            
            time.sleep(15)  # Save every 15 seconds

    def save_backup_data(self, filename="backup.pickle"):
        """Save backup data to a file."""
        backup = {
            "url": self.url,
            "total_size": self.total_size,
            "max_threads_allowed": self.threads,
            "split_size": math.floor(self.total_size / self.threads),
            "download_manager": self.download_manager,
            "local_filename": self.local_filename
        }
        
        save_backup(filename, backup)

    def load_backup_data(self):
        """Load backup data from a file."""
        try:
            backup = load_backup("backup.pickle")
            
            self.url = backup["url"]
            self.total_size = backup["total_size"]
            self.threads = backup["max_threads_allowed"]
            self.download_manager = backup["download_manager"]
            
            try:
                self.local_filename = backup["local_filename"]
            except KeyError:
                # For backwards compatibility with old backups
                self.local_filename = urllib.parse.unquote(self.url.split('/')[-1].strip('"\''))
                if self.output_path:
                    self.local_filename = os.path.join(self.output_path, self.local_filename)
            
            return True
        except Exception as e:
            self.error.emit(f"Failed to load backup: {str(e)}")
            return False

    def stop(self):
        """Stop the download process."""
        self.is_running = False
        self.save_backup_data("last_session.pickle")


class DownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-threaded Downloader")
        self.setGeometry(100, 100, 700, 500)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # URL input section
        url_group = QGroupBox("Download URL")
        url_layout = QVBoxLayout()
        
        # URL input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL to download")
        url_layout.addWidget(self.url_input)
        
        # URL buttons
        url_buttons = QHBoxLayout()
        self.paste_button = QPushButton("Paste")
        self.paste_button.clicked.connect(self.paste_url)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_url)
        url_buttons.addWidget(self.paste_button)
        url_buttons.addWidget(self.clear_button)
        url_layout.addLayout(url_buttons)
        
        url_group.setLayout(url_layout)
        layout.addWidget(url_group)
        
        # Settings section
        settings_group = QGroupBox("Download Settings")
        settings_layout = QGridLayout()
        
        # Thread count
        settings_layout.addWidget(QLabel("Number of threads:"), 0, 0)
        self.thread_count = QSpinBox()
        self.thread_count.setRange(1, 64)
        self.thread_count.setValue(8)
        settings_layout.addWidget(self.thread_count, 0, 1)
        
        # Output directory
        settings_layout.addWidget(QLabel("Output directory:"), 1, 0)
        self.output_dir = QLineEdit()
        self.output_dir.setText(os.path.expanduser("~") + "/Downloads")
        settings_layout.addWidget(self.output_dir, 1, 1)
        
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_directory)
        settings_layout.addWidget(self.browse_button, 1, 2)
        
        # Use backup option
        self.use_backup = QCheckBox("Use existing backup if available")
        settings_layout.addWidget(self.use_backup, 2, 0, 1, 2)
        
        # Auto save partial downloads
        self.auto_save = QCheckBox("Auto-save partial downloads")
        self.auto_save.setChecked(True)
        settings_layout.addWidget(self.auto_save, 3, 0, 1, 2)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Progress section
        progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout()
        
        # Progress bar
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        progress_layout.addWidget(self.status_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Download")
        self.start_button.clicked.connect(self.start_download)
        self.start_button.setStyleSheet("font-weight: bold;")
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_download)
        self.pause_button.setEnabled(False)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_download)
        self.stop_button.setEnabled(False)
        
        self.backup_button = QPushButton("Save Backup")
        self.backup_button.clicked.connect(self.save_manual_backup)
        self.backup_button.setEnabled(False)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.backup_button)
        layout.addLayout(button_layout)
        
        self.downloader = None
        self.download_active = False
        self.download_paused = False

    def paste_url(self):
        """Paste URL from clipboard."""
        clipboard = QApplication.clipboard()
        self.url_input.setText(clipboard.text())

    def clear_url(self):
        """Clear the URL input field."""
        self.url_input.clear()

    def browse_directory(self):
        """Open dialog to select output directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.output_dir.text()
        )
        if dir_path:
            self.output_dir.setText(dir_path)

    def start_download(self):
        """Start or resume the download process."""
        if self.download_paused:
            # Resume download
            self.download_paused = False
            self.downloader.partial_saver_turned_on = self.auto_save.isChecked()
            self.downloader.is_running = True
            self.pause_button.setText("Pause")
            self.status_label.setText("Resuming download...")
            return
        
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a URL")
            return
        
        output_dir = self.output_dir.text()
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                QMessageBox.critical(self, "Directory Error", 
                                    f"Could not create output directory: {str(e)}")
                return
        
        self.downloader = DownloaderThread(
            url, 
            self.thread_count.value(), 
            output_dir,
            self.use_backup.isChecked()
        )
        
        self.downloader.partial_saver_turned_on = self.auto_save.isChecked()
        self.downloader.progress.connect(self.update_progress)
        self.downloader.status.connect(self.update_status)
        self.downloader.finished.connect(self.download_finished)
        self.downloader.error.connect(self.show_error)
        
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.backup_button.setEnabled(True)
        self.download_active = True
        
        self.downloader.start()

    def pause_download(self):
        """Pause or resume the download process."""
        if not self.downloader:
            return
        
        if not self.download_paused:
            # Pause download
            self.downloader.is_running = False
            self.pause_button.setText("Resume")
            self.start_button.setEnabled(True)
            self.status_label.setText("Download paused")
            self.download_paused = True
        else:
            # Resume download
            self.downloader.is_running = True
            self.pause_button.setText("Pause")
            self.start_button.setEnabled(False)
            self.status_label.setText("Resuming download...")
            self.download_paused = False

    def stop_download(self):
        """Stop the download process and save backup."""
        if self.downloader:
            self.downloader.stop()
            self.downloader = None
            self.download_active = False
            self.download_paused = False
            
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.backup_button.setEnabled(False)
            
            self.status_label.setText("Download stopped and backup saved")

    def save_manual_backup(self):
        """Manually save a backup file."""
        if self.downloader:
            try:
                self.downloader.save_backup_data("manual_backup.pickle")
                self.status_label.setText("Manual backup saved")
            except Exception as e:
                self.show_error(f"Failed to save backup: {str(e)}")

    def update_progress(self, value):
        """Update the progress bar."""
        self.progress_bar.setValue(value)

    def update_status(self, message):
        """Update the status label."""
        self.status_label.setText(message)

    def download_finished(self, filename):
        """Handle download completion."""
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.backup_button.setEnabled(False)
        self.download_active = False
        
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Download completed! File saved to: {filename}")
        
        QMessageBox.information(self, "Download Complete", 
                              f"File has been downloaded to:\n{filename}")

    def show_error(self, message):
        """Display error message."""
        QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        """Handle window close event."""
        if self.download_active:
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "A download is in progress. Do you want to save a backup before exiting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.StandardButton.Yes:
                if self.downloader:
                    try:
                        self.downloader.stop()  # This saves a backup
                    except:
                        pass
        
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DownloaderGUI()
    window.show()
    sys.exit(app.exec())
