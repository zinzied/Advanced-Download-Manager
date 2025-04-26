import re
import urllib
import pickle
import requests
import math
import os
from threading import Thread, Lock
from time import sleep
import time
from urllib.parse import unquote
from urllib3.exceptions import InsecureRequestWarning
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(InsecureRequestWarning)

class DownloadTask:
    def __init__(self, url, max_threads=4, save_path=None):
        self.url = url
        self.max_threads = max_threads
        self.download_manager = {}
        self.total_size = 0
        self.downloaded_size = 0
        self.progress = 0
        self.status = "initializing"  # initializing, downloading, paused, completed, error
        self.error_message = ""
        self.start_time = time.time()
        self.download_speed = 0
        self.eta = 0
        self.filename = ""
        self.save_path = save_path or os.getcwd()
        self.download_finished = False
        self.partial_saver_turned_on = False
        self.threads = []
        self.lock = Lock()
        self.total_parts = 0
        self.downloaded_parts = 0
        self.last_update_time = time.time()
        self.last_downloaded_size = 0

    def get_splitted_parts(self, total_size, split_size):
        result = []

        if total_size <= split_size:
            result.append((0, total_size))
            return result

        result.append((0, split_size))
        splitted_upto = split_size

        while splitted_upto + split_size < total_size:
            result.append((splitted_upto + 1, splitted_upto + split_size))
            splitted_upto += split_size

        result.append((splitted_upto + 1, total_size))

        return result

    def download_part(self, part_number):
        resume_header = {'Range': f'bytes={self.download_manager[part_number]["range"][0]}-{self.download_manager[part_number]["range"][1]}'}

        for i in range(10):  # Retry up to 10 times
            if self.status == "paused":
                sleep(1)
                continue

            if self.status == "canceled":
                return

            try:
                downloaded_content = b''
                requests_get = requests.get(
                    self.url,
                    headers=resume_header,
                    stream=True,
                    verify=False,
                    allow_redirects=True
                )

                for data in requests_get.iter_content(chunk_size=1024):
                    if self.status == "paused":
                        sleep(1)
                        continue

                    if self.status == "canceled":
                        return

                    downloaded_content += data
                    with self.lock:
                        old_size = len(self.download_manager[part_number]["content"])
                        self.download_manager[part_number]["content"] = downloaded_content
                        new_size = len(downloaded_content)
                        self.downloaded_size += (new_size - old_size)
                        self.progress = int((self.downloaded_size / self.total_size) * 100)

                        # Calculate download speed
                        current_time = time.time()
                        time_diff = current_time - self.last_update_time
                        if time_diff >= 1:  # Update speed every second
                            size_diff = self.downloaded_size - self.last_downloaded_size
                            self.download_speed = size_diff / time_diff

                            # Calculate ETA
                            if self.download_speed > 0:
                                self.eta = (self.total_size - self.downloaded_size) / self.download_speed
                            else:
                                self.eta = 0

                            self.last_update_time = current_time
                            self.last_downloaded_size = self.downloaded_size

                with self.lock:
                    self.download_manager[part_number]["download_completed"] = True
                    self.downloaded_parts += 1

                    if self.downloaded_parts == self.total_parts:
                        # Save the completed file
                        self.save_file()
                        self.status = "completed"
                        self.download_finished = True
                break

            except Exception as e:
                print(f"Part number {part_number} could not be downloaded due to error: {e}\nRetry attempts left: {9-i}")
                if i == 9:  # Last attempt
                    with self.lock:
                        self.error_message = f"Failed to download part {part_number}: {str(e)}"
                        if self.status != "canceled":
                            self.status = "error"

    def start_download(self):
        try:
            self.status = "downloading"
            response = requests.head(self.url)

            try:
                self.total_size = int(response.headers["Content-Length"])
            except KeyError:
                self.status = "error"
                self.error_message = "The server did not provide the file size"
                return False

            # Determine filename
            try:
                d = response.headers['content-disposition']
                filename_match = re.findall('filename=["\']*([^"\']+)', d)
                if filename_match and filename_match[0]:
                    self.filename = filename_match[0].strip('"\'')
                else:
                    raise KeyError
            except KeyError:
                self.filename = unquote(self.url.split('/')[-1].strip('"\''))

            if not self.filename:
                self.filename = f"download_{int(time.time())}"

            # Calculate split size
            split_size = math.floor(self.total_size / self.max_threads)

            # Initialize download manager
            file_parts = self.get_splitted_parts(self.total_size, split_size)

            for count, item in enumerate(file_parts):
                self.download_manager[count] = {
                    "range": item,
                    "content": b'',
                    "download_completed": False
                }

            self.total_parts = len(self.download_manager)

            # Start download threads
            for part_number in self.download_manager:
                download_thread = Thread(target=self.download_part, args=[part_number])
                download_thread.daemon = True
                download_thread.start()
                self.threads.append(download_thread)

            # Start auto-save thread
            auto_save_thread = Thread(target=self.auto_save)
            auto_save_thread.daemon = True
            auto_save_thread.start()

            return True

        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            return False

    def pause_download(self):
        self.status = "paused"

    def resume_download(self):
        self.status = "downloading"

    def cancel_download(self):
        self.status = "canceled"

    def save_file(self):
        try:
            complete_file = b''
            for i in range(self.total_parts):
                complete_file += self.download_manager[i]["content"]

            file_path = os.path.join(self.save_path, self.filename)
            with open(file_path, 'wb') as f:
                f.write(complete_file)

            return True
        except Exception as e:
            self.error_message = f"Failed to save file: {str(e)}"
            return False

    def auto_save(self):
        while not self.download_finished and self.status != "canceled":
            if self.partial_saver_turned_on:
                self.save_file()
            sleep(10)

    def save_backup(self, filename="backup.pickle"):
        try:
            backup = {
                "url": self.url,
                "total_size": self.total_size,
                "max_threads": self.max_threads,
                "download_manager": self.download_manager,
                "filename": self.filename,
                "save_path": self.save_path
            }

            with open(filename, 'wb') as handle:
                pickle.dump(backup, handle, protocol=pickle.HIGHEST_PROTOCOL)
            return True
        except Exception as e:
            self.error_message = f"Failed to save backup: {str(e)}"
            return False

    def load_backup(self, filename="backup.pickle"):
        try:
            with open(filename, 'rb') as handle:
                backup = pickle.load(handle)

            self.url = backup["url"]
            self.total_size = backup["total_size"]
            self.max_threads = backup["max_threads"]
            self.download_manager = backup["download_manager"]
            self.filename = backup["filename"]
            self.save_path = backup["save_path"]

            # Calculate current progress
            self.downloaded_size = 0
            self.downloaded_parts = 0

            for part_number in self.download_manager:
                self.downloaded_size += len(self.download_manager[part_number]["content"])
                if self.download_manager[part_number]["download_completed"]:
                    self.downloaded_parts += 1

            self.progress = int((self.downloaded_size / self.total_size) * 100)
            self.total_parts = len(self.download_manager)

            # Start download for incomplete parts
            for part_number in self.download_manager:
                if not self.download_manager[part_number]["download_completed"]:
                    download_thread = Thread(target=self.download_part, args=[part_number])
                    download_thread.daemon = True
                    download_thread.start()
                    self.threads.append(download_thread)

            # Start auto-save thread
            auto_save_thread = Thread(target=self.auto_save)
            auto_save_thread.daemon = True
            auto_save_thread.start()

            self.status = "downloading"
            return True

        except Exception as e:
            self.error_message = f"Failed to load backup: {str(e)}"
            return False


class DownloadManager:
    def __init__(self):
        self.downloads = []
        self.active_downloads = 0
        self.max_concurrent_downloads = 3

    def add_download(self, url, max_threads=4, save_path=None):
        download_task = DownloadTask(url, max_threads, save_path)
        self.downloads.append(download_task)

        if self.active_downloads < self.max_concurrent_downloads:
            download_task.start_download()
            self.active_downloads += 1

        return len(self.downloads) - 1  # Return index of the download

    def start_download(self, index):
        if 0 <= index < len(self.downloads):
            if self.downloads[index].status not in ["downloading", "completed"]:
                success = self.downloads[index].start_download()
                if success:
                    self.active_downloads += 1
                return success
        return False

    def pause_download(self, index):
        if 0 <= index < len(self.downloads):
            if self.downloads[index].status == "downloading":
                self.downloads[index].pause_download()
                self.active_downloads -= 1
                self._start_queued_downloads()
                return True
        return False

    def resume_download(self, index):
        if 0 <= index < len(self.downloads):
            if self.downloads[index].status == "paused":
                if self.active_downloads < self.max_concurrent_downloads:
                    self.downloads[index].resume_download()
                    self.active_downloads += 1
                    return True
        return False

    def cancel_download(self, index):
        if 0 <= index < len(self.downloads):
            if self.downloads[index].status in ["downloading", "paused"]:
                self.downloads[index].cancel_download()
                if self.downloads[index].status == "downloading":
                    self.active_downloads -= 1
                    self._start_queued_downloads()
                return True
        return False

    def remove_download(self, index):
        if 0 <= index < len(self.downloads):
            if self.downloads[index].status in ["downloading"]:
                self.active_downloads -= 1
            self.downloads.pop(index)
            self._start_queued_downloads()
            return True
        return False

    def _start_queued_downloads(self):
        for download in self.downloads:
            if download.status == "initializing" and self.active_downloads < self.max_concurrent_downloads:
                download.start_download()
                self.active_downloads += 1

    def set_max_concurrent_downloads(self, max_downloads):
        self.max_concurrent_downloads = max_downloads
        self._start_queued_downloads()
