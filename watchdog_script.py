import time
import os
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === CONFIG ===
WATCH_FOLDER = r"C:\operations"
SCRIPT_TO_RUN = r"C:\operations\process_operations.py"
LOCK_FILE = os.path.join(WATCH_FOLDER, "process.lock")

# === Check if file is fully written and accessible ===
def is_file_ready(filepath, wait_time=2, retries=10):
    for _ in range(retries):
        try:
            size1 = os.path.getsize(filepath)
            time.sleep(wait_time)
            size2 = os.path.getsize(filepath)
            if size1 == size2:
                # Try opening in append mode to check if file is locked
                with open(filepath, "ab"):
                    return True
        except Exception as e:
            time.sleep(wait_time)
    return False

class WatchHandler(FileSystemEventHandler):
    def on_created(self, event):
        self.handle_event(event)

    def on_modified(self, event):
        self.handle_event(event)

    def handle_event(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".csv"):
            return

        print(f"Detected new/modified file: {event.src_path}")

        if not is_file_ready(event.src_path):
            print("File not ready, skipping for now...")
            return

        if os.path.exists(LOCK_FILE):
            print("Process already running, skipping...")
            return

        try:
            # Create lock to prevent multiple runs
            open(LOCK_FILE, "w").close()
            print("File ready. Running processing script...")
            # Use full path to Python if needed
            subprocess.run(["python", SCRIPT_TO_RUN], check=True)
            print("Processing complete.")
        except Exception as e:
            print(f"Error during processing: {e}")
        finally:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)

if __name__ == "__main__":
    observer = Observer()
    observer.schedule(WatchHandler(), WATCH_FOLDER, recursive=False)
    observer.start()

    print(f"Watching folder: {WATCH_FOLDER} for new CSV files...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()