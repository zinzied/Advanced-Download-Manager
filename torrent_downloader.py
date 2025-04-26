import os
import time
from threading import Thread, Lock
from urllib.parse import unquote

# Try to import libtorrent, but provide a fallback if not available
try:
    import libtorrent as lt
    LIBTORRENT_AVAILABLE = True
except ImportError:
    LIBTORRENT_AVAILABLE = False
    print("Warning: libtorrent is not installed. Torrent functionality will be disabled.")
    print("To enable torrent support, install libtorrent with: pip install python-libtorrent")

class TorrentDownloadTask:
    def __init__(self, magnet_uri, save_path=None):
        self.magnet_uri = magnet_uri
        self.save_path = save_path or os.getcwd()
        self.status = "initializing"  # initializing, downloading, paused, completed, error
        self.error_message = ""
        self.progress = 0
        self.download_speed = 0
        self.upload_speed = 0
        self.eta = 0
        self.total_size = 0
        self.downloaded_size = 0
        self.name = ""
        self.files = []
        self.selected_files = []
        self.session = None
        self.handle = None
        self.lock = Lock()
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.download_finished = False
        self.torrent_info = None
        self.update_thread = None

    def start_download(self):
        try:
            # Initialize libtorrent session
            self.session = lt.session()
            self.session.listen_on(6881, 6891)

            # Add extensions
            self.session.add_extension('ut_metadata')
            self.session.add_extension('ut_pex')
            self.session.add_extension('metadata_transfer')

            # Set session settings
            settings = self.session.get_settings()
            settings['announce_to_all_tiers'] = True
            settings['announce_to_all_trackers'] = True
            settings['auto_manage_interval'] = 5
            settings['auto_scrape_interval'] = 60
            self.session.set_settings(settings)

            # Add torrent
            params = {
                'save_path': self.save_path,
                'storage_mode': lt.storage_mode_t.storage_mode_sparse,
                'paused': False,
                'auto_managed': True,
                'duplicate_is_error': True
            }

            # Add from magnet URI
            self.handle = lt.add_magnet_uri(self.session, self.magnet_uri, params)
            self.status = "downloading"

            # Start update thread
            self.update_thread = Thread(target=self.update_status)
            self.update_thread.daemon = True
            self.update_thread.start()

            return True

        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            return False

    def update_status(self):
        while not self.download_finished and self.status != "canceled":
            if self.status == "paused":
                time.sleep(1)
                continue

            try:
                # Get torrent status
                status = self.handle.status()

                with self.lock:
                    # Update progress
                    if status.total_wanted > 0:
                        self.progress = int(status.total_wanted_done * 100 / status.total_wanted)
                    else:
                        self.progress = 0

                    # Update speeds
                    self.download_speed = status.download_rate
                    self.upload_speed = status.upload_rate

                    # Update sizes
                    self.total_size = status.total_wanted
                    self.downloaded_size = status.total_wanted_done

                    # Update ETA
                    if self.download_speed > 0:
                        self.eta = (self.total_size - self.downloaded_size) / self.download_speed
                    else:
                        self.eta = 0

                    # Update name if available
                    if status.name:
                        self.name = status.name

                    # Check if metadata is received
                    if not self.torrent_info and self.handle.has_metadata():
                        self.torrent_info = self.handle.get_torrent_info()
                        self.files = []

                        # Get file list
                        for i in range(self.torrent_info.num_files()):
                            file_entry = self.torrent_info.file_at(i)
                            self.files.append({
                                'index': i,
                                'path': file_entry.path,
                                'size': file_entry.size,
                                'selected': True
                            })

                        # By default, select all files
                        self.selected_files = list(range(len(self.files)))

                    # Check if download is complete
                    if status.is_seeding or status.is_finished:
                        self.status = "completed"
                        self.download_finished = True
                        self.progress = 100
                        break

            except Exception as e:
                self.error_message = f"Error updating status: {str(e)}"

            time.sleep(1)

    def pause_download(self):
        if self.handle:
            self.handle.pause()
            self.status = "paused"

    def resume_download(self):
        if self.handle:
            self.handle.resume()
            self.status = "downloading"

    def cancel_download(self):
        if self.handle:
            self.session.remove_torrent(self.handle)
            self.status = "canceled"

    def select_files(self, file_indices):
        """Select specific files to download"""
        if not self.handle or not self.handle.has_metadata():
            return False

        try:
            # Create a priority list (0 = don't download, 1 = normal)
            priorities = [0] * len(self.files)

            # Set priorities for selected files
            for index in file_indices:
                if 0 <= index < len(self.files):
                    priorities[index] = 1

            # Apply priorities
            self.handle.prioritize_files(priorities)

            # Update selected files
            self.selected_files = file_indices

            return True

        except Exception as e:
            self.error_message = f"Error selecting files: {str(e)}"
            return False


class TorrentManager:
    def __init__(self):
        self.downloads = []
        self.active_downloads = 0
        self.max_concurrent_downloads = 3
        self.is_available = LIBTORRENT_AVAILABLE

    def add_download(self, magnet_uri, save_path=None):
        if not self.is_available:
            raise RuntimeError("Torrent functionality is not available. Please install libtorrent.")

        download_task = TorrentDownloadTask(magnet_uri, save_path)
        self.downloads.append(download_task)

        if self.active_downloads < self.max_concurrent_downloads:
            download_task.start_download()
            self.active_downloads += 1

        return len(self.downloads) - 1  # Return index of the download

    def start_download(self, index):
        if not self.is_available:
            return False

        if 0 <= index < len(self.downloads):
            if self.downloads[index].status not in ["downloading", "completed"]:
                success = self.downloads[index].start_download()
                if success:
                    self.active_downloads += 1
                return success
        return False

    def pause_download(self, index):
        if not self.is_available:
            return False

        if 0 <= index < len(self.downloads):
            if self.downloads[index].status == "downloading":
                self.downloads[index].pause_download()
                self.active_downloads -= 1
                self._start_queued_downloads()
                return True
        return False

    def resume_download(self, index):
        if not self.is_available:
            return False

        if 0 <= index < len(self.downloads):
            if self.downloads[index].status == "paused":
                if self.active_downloads < self.max_concurrent_downloads:
                    self.downloads[index].resume_download()
                    self.active_downloads += 1
                    return True
        return False

    def cancel_download(self, index):
        if not self.is_available:
            return False

        if 0 <= index < len(self.downloads):
            if self.downloads[index].status in ["downloading", "paused"]:
                self.downloads[index].cancel_download()
                if self.downloads[index].status == "downloading":
                    self.active_downloads -= 1
                    self._start_queued_downloads()
                return True
        return False

    def remove_download(self, index):
        if not self.is_available:
            return False

        if 0 <= index < len(self.downloads):
            if self.downloads[index].status in ["downloading"]:
                self.active_downloads -= 1
            self.downloads.pop(index)
            self._start_queued_downloads()
            return True
        return False

    def select_files(self, download_index, file_indices):
        if not self.is_available:
            return False

        if 0 <= download_index < len(self.downloads):
            return self.downloads[download_index].select_files(file_indices)
        return False

    def _start_queued_downloads(self):
        if not self.is_available:
            return

        for download in self.downloads:
            if download.status == "initializing" and self.active_downloads < self.max_concurrent_downloads:
                download.start_download()
                self.active_downloads += 1

    def set_max_concurrent_downloads(self, max_downloads):
        self.max_concurrent_downloads = max_downloads
        self._start_queued_downloads()
