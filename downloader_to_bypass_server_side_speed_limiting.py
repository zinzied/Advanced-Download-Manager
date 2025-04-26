import re
import urllib
import pickle
import requests
import math
from threading import Thread
from time import sleep
import time

from urllib3.exceptions import InsecureRequestWarning
import urllib3
urllib3.disable_warnings(InsecureRequestWarning)

def get_splitted_parts(total_size, split_size):
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

def save_parts():
    global total_parts, download_manager, local_filename

    while download_finished is False:
        complete_file = b''
        
        if partial_saver_turned_on is True:
            print("\n\nStarting to save partial file\n")
            for i in range(total_parts):
                complete_file += download_manager[i]["content"]

            with open(local_filename, 'wb') as f:
                f.write(complete_file)
                complete_file = b''

            print("\nPartial file saved\n\n")

        sleep(10)


def auto_backup_saver():
    while download_finished is False:
        save_backup("auto_backup.pickle", None)
        sleep(10)


def download_part(part_number):
    global download_manager
    global url

    resume_header = {'Range': 'bytes={}-{}'.format(download_manager[part_number]["range"][0], download_manager[part_number]["range"][1])}
    for i in range(10):

        try:
            downloded_content = b''
            requests_get = requests.get(url, headers=resume_header, stream=True,  verify=False, allow_redirects=True)
            for data in requests_get.iter_content(chunk_size=1024):
                downloded_content += data
                download_manager[part_number]["content"] = downloded_content
            break

        except Exception as e:
            print("Part number {} could not be downloaded due to error : {}\nRetry attempts left for this part = {}".format(part_number, e, 9-i))

    download_manager[part_number]["content"] = downloded_content
    download_manager[part_number]["download_completed"] = True
    # print("Part number {} downlaoded.".format(part_number))


def save_backup(filename="backup.pickle", message="Backup saved"):
    global url, response, total_size, max_threads_allowed, split_size, download_manager
    try:
        backup = {}
        backup["url"] = url
        backup["response"] = response
        backup["total_size"] = total_size
        backup["max_threads_allowed"] = max_threads_allowed
        backup["split_size"] = split_size
        backup["download_manager"] = download_manager

        with open(filename, 'wb') as handle:
            pickle.dump(backup, handle, protocol=pickle.HIGHEST_PROTOCOL)
    
        if message is not None:
            print(message)

    except Exception as e:
        print("\n\nSaving of backup failed with following error : {}\n\n".format(e))


def load_backup():
    global url, response, total_size, max_threads_allowed, split_size, download_manager
    try:
        with open('backup.pickle', 'rb') as handle:
            backup = pickle.load(handle)

        url = backup["url"]
        response = backup["response"]
        total_size = backup["total_size"]
        max_threads_allowed = backup["max_threads_allowed"] 
        split_size = backup["split_size"] 
        download_manager = backup["download_manager"] 

        return True

    except Exception as e:
        print("\n\nLoading of backup failed with following error : {}\n\n".format(e))
        return False


url = input("\n\nEnter the url or press y to load backup : ")

backup_loaded = False
download_manager = {}
response = None  # Initialize response variable

if url == 'y':
    backup_loaded = load_backup()
    if not backup_loaded:
        print("\nNo backup file found. Starting new download...")
        url = input("Enter the url: ")

if not backup_loaded:
    try:
        response = requests.head(url)
        total_size = int(response.headers["Content-Length"])
    except KeyError:
        input("\nThe server did not tell the size of this file. Cannot download. Press enter to exit : ")
        exit(0)

    max_threads_allowed = int(input("How many times to speed up the download : "))
    split_size = math.floor(total_size / max_threads_allowed)
    download_manager = {}

download_finished = False
partial_saver_turned_on = False

# download_manager = [ [part_number, (start_pos, end_pos), content, bool_download_complete], [], [].....]

start_time = time.time()


if backup_loaded is False:
    file_parts = get_splitted_parts(total_size, split_size)

    count = -1
    for item in file_parts:
        count += 1
        download_manager[count] = {"range": item, "content": b'', "download_completed": False}
    # print(download_manager)

    for part_number in download_manager:
        download_thread = Thread(target = download_part, args=[part_number])
        download_thread.daemon = True
        download_thread.start()

else:
    for part_number in download_manager:
        if download_manager[part_number]["download_completed"] is False:
            download_thread = Thread(target = download_part, args=[part_number])
            download_thread.daemon = True
            download_thread.start()


total_parts = len(download_manager)
complete_file = b''

try:
    d = response.headers['content-disposition']
    filename_match = re.findall('filename=["\']*([^"\']+)', d)
    if filename_match and filename_match[0]:
        local_filename = filename_match[0].strip('"\'')  # Remove any remaining quotes
    else:
        raise KeyError
except KeyError:
    local_filename = urllib.parse.unquote(url.split('/')[-1].strip('"\''))


partially_downloaded_file_saver_thread = Thread(target = save_parts)
partially_downloaded_file_saver_thread.daemon = True
partially_downloaded_file_saver_thread.start()

auto_backup_saver_thread = Thread(target=auto_backup_saver)
auto_backup_saver_thread.daemon = True
auto_backup_saver_thread.start()


while True:
    try:
        downloaded_parts = 0
        total_size_currently_downloaded = 0

        for part_number in download_manager:
            total_size_currently_downloaded += len(download_manager[part_number]["content"])

            if download_manager[part_number]["download_completed"] == True:
                downloaded_parts += 1

        print("\n{}% ({} bytes)downloaded in {} seconds".format(int(math.floor((total_size_currently_downloaded/ total_size) * 100)), total_size_currently_downloaded ,time.time()-start_time))

        sleep(1)


        if total_parts == downloaded_parts:
            download_finished = True
            break

    except KeyboardInterrupt:
        choice = input("\n\nChoose from menu :\n1. Turn OFF partial saver\n2. Turn ON partial saver\n3. Save current progress and exit\n4. Go back\n5. Count undownloaded parts\n6. Save backup\n9. Force exit\n\nI choose : ")

        if choice == '1':
            partial_saver_turned_on = False

        if choice == '2':
            partial_saver_turned_on = True

        elif choice == '3':
            print("\n\n*** Saving file.. Press ctrl c again to force quit ***")
            break

        elif choice == '4':
            pass

        elif choice == '5':
            undownloaded_parts = 0
            for part_number in download_manager:
                if download_manager[part_number]["download_completed"] == False:
                    undownloaded_parts += 1

            print("\n\n{} parts have not finished downloading.\n\n".format(undownloaded_parts))
            sleep(1)

        elif choice == '6':
            save_backup()

        elif choice == '9':
            exit(0)
    

print("\n\nFile downloaded\n\nSaving your file\n\n")

save_backup()
complete_file = b''
for i in range(total_parts):
    complete_file += download_manager[i]["content"]

with open(local_filename, 'wb') as f:
    f.write(complete_file)
