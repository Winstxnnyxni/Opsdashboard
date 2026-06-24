import os
import subprocess
import sys
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


# === CONFIG ===
WATCH_FOLDER = r"C:\Operations"
SCRIPT_TO_RUN = r"C:\Operations\process_operations.py"
LOCK_FILE = os.path.join(WATCH_FOLDER, "process.lock")


# === Check if file is fully written and accessible ===
def is_file_ready(filepath, wait_time=2, retries=10):
    for _ in range(retries):
        try:
            size1 = os.path.getsize(filepath)
            time.sleep(wait_time)
            size2 = os.path.getsize(filepath)

            if size1 == size2:
                with open(filepath, "ab"):
                    return True

        except Exception:
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

        if not event.src_path.lower().endswith(".csv"):
            return

        print(f"Detected CSV: {event.src_path}")

        if not is_file_ready(event.src_path):
            print("File not ready yet.")
            return

        if os.path.exists(LOCK_FILE):
            print("Processing already running.")
            return

        try:
            open(LOCK_FILE, "w").close()

            print("Starting process_operations.py...")

            subprocess.run(
                [sys.executable, SCRIPT_TO_RUN],
                check=True,
            )

            print("Processing complete.")

        except Exception as e:
            print(f"Error: {e}")

        finally:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)


if __name__ == "__main__":
    observer = Observer()
    observer.schedule(
        WatchHandler(),
        WATCH_FOLDER,
        recursive=False,
    )

    observer.start()

    print(f"Watching: {WATCH_FOLDER}")

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        observer.stop()

    observer.join()
