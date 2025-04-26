# Advanced Download Manager

A powerful, multi-threaded download manager with torrent support built with Python and PyQt5.

![Advanced Download Manager](https://github.com/yourusername/advanced-download-manager/raw/main/screenshots/main.png)

## Features

### Core Features
- **Multi-threaded Downloads**: Split files into parts for faster downloading
- **Pause/Resume/Cancel**: Full control over download tasks
- **Torrent Support**: Download using magnet links
- **Progress Tracking**: Shows percentage, download speed, and estimated time remaining
- **Multiple URL Support**: Queue system with configurable concurrent downloads

### User Interface
- **Modern UI**: Clean, responsive interface using PyQt5
- **Double-click to Open**: Easily open downloaded files
- **Action Icons**: Show in folder and remove from list
- **File Selection**: Choose which files to download from torrents
- **Download Queue Management**: Prioritize and manage multiple downloads

### Additional Features
- **Auto-save**: Periodically saves partial downloads
- **Backup/Restore**: Can save and load download state
- **Customizable Threads**: Set the number of threads per download
- **Custom Save Location**: Choose where to save each download

## Screenshots

### Main Interface
![Main Interface](https://github.com/yourusername/advanced-download-manager/raw/main/screenshots/main.png)

### Torrent File Selection
![Torrent File Selection](https://github.com/yourusername/advanced-download-manager/raw/main/screenshots/file-selection.png)

## Installation

### Prerequisites
- Python 3.6+
- PyQt5
- Requests
- (Optional) Libtorrent for torrent support

### Install from source
1. Clone the repository:
```bash
git clone https://github.com/yourusername/advanced-download-manager.git
cd advanced-download-manager
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

3. (Optional) For torrent support, install libtorrent:
```bash
pip install python-libtorrent
```

4. Run the application:
```bash
python main.py
```

## Usage

### Adding a Download
1. Enter the URL in the input field
2. Select download type (HTTP/HTTPS or Torrent/Magnet)
3. Set the number of threads (for HTTP downloads)
4. Choose a save location
5. Click "Add Download"

### Managing Downloads
- **Pause/Resume**: Click the button on each download item
- **Cancel**: Click the cancel button
- **Show in Folder**: Click the folder icon
- **Remove from List**: Click the trash icon
- **Open File**: Double-click on a completed download
- **Select Files** (Torrents): Click the file selection icon

### Settings
- Set the maximum number of concurrent downloads
- Configure auto-start behavior

## How It Works

### HTTP Downloads
The application splits large files into multiple parts and downloads them simultaneously using multiple threads. This can significantly increase download speeds, especially when downloading from servers with per-connection bandwidth limits.

### Torrent Downloads
The application uses libtorrent to handle torrent downloads. It supports magnet links and allows you to select which files to download from the torrent.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) for the GUI framework
- [Requests](https://requests.readthedocs.io/) for HTTP handling
- [Libtorrent](https://www.libtorrent.org/) for torrent support
