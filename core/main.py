import json
import os
import subprocess
import time
import uuid

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from core.config.config import ROOT_DIR

_DOWNLOAD_LIMIT: int | None = None
_START_PAGE: int = 1

_TRACKING_FILE = os.path.join(ROOT_DIR, "downloads", "downloaded_samples.json")

load_dotenv()

SESSIONID = os.getenv("SESSIONID")
CSRFTOKEN = os.getenv("CSRFTOKEN")
SEARCH_URL = os.getenv("SEARCH_URL")


def load_downloaded_samples_map():
    if os.path.exists(_TRACKING_FILE):
        with open(_TRACKING_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_downloaded_samples_map(downloaded_samples_map):
    with open(_TRACKING_FILE, "w") as f:
        json.dump(downloaded_samples_map, f, indent=2)


def get_downloaded_filenames(downloaded_samples_map):
    full_names = [item["full_name"] for item in downloaded_samples_map.values()]
    return set(full_names)


def get_downloaded_author_sound_id_pairs(downloaded_samples_map):
    author_sound_id_pairs = []
    for _, item in downloaded_samples_map.items():
        parts = item["full_name"].split("__")
        if len(parts) != 3:
            print(f"Unexpected file name: {item['full_name']} (too many parts)")
            continue # Will be handled later
        sound_id, author, _ = parts
        author_sound_id_pairs.append((author.lower(), sound_id))
    return set(author_sound_id_pairs)


def scrape_freesound():
    print("Scraping...")
    session = requests.Session()
    cookies = {
        "sessionid": SESSIONID,
        "csrftoken": CSRFTOKEN
    }
    session.cookies.update(cookies)

    downloaded_samples_map = load_downloaded_samples_map()
    downloaded_filenames = get_downloaded_filenames(downloaded_samples_map)
    downloaded_author_sound_id_pairs = get_downloaded_author_sound_id_pairs(downloaded_samples_map)
    newly_downloaded = []

    failed_conversion_urls = []

    downloaded_count = 0
    page = _START_PAGE

    is_end = False

    try:
        while not is_end:
            print(f"\nFetching page {page}")
            # Fetch page
            SEARCH_URL =
            page_url = f"{SEARCH_URL}&page={page}" if page > 1 else SEARCH_URL
            try:
                response = session.get(page_url)
            except Exception as e:
                print(f"No more pages. Exception: {e}")
                break

            soup = BeautifulSoup(response.text, "html.parser")

            # Find sample links
            sample_links = [a["href"] for a in soup.find_all("a", href=True)
                            if "/people/" in a["href"] and "/sounds/" in a["href"]]
            if not sample_links:
                print("No sample links found, probably end of pages")
                break

            for sample_page_path in sample_links:
                if _DOWNLOAD_LIMIT and downloaded_count >= _DOWNLOAD_LIMIT:
                    is_end = True
                    print(f"Reached END")
                    break

                extracted_author, _, extracted_sound_id = sample_page_path.split("/")[2:5]
                if (extracted_author.lower(), extracted_sound_id) in downloaded_author_sound_id_pairs:
                    # Early circuit break, assuming author + sound ID pairs are unique
                    print(f"Skipping {extracted_sound_id} by {extracted_author} - already downloaded")
                    continue

                # Fetch sample page to get download link
                full_sample_page_url = f"https://freesound.org{sample_page_path}"
                sample_response = session.get(full_sample_page_url)
                sample_soup = BeautifulSoup(sample_response.text, "html.parser")

                # Find download link
                download_link = sample_soup.find("a", href=lambda x: x and "/download/" in x)

                if not download_link:
                    print(f"No download link found on {full_sample_page_url}")
                    continue

                # Skip if downloaded
                author, _, sound_id, _, original_full_file_name = download_link["href"].split('/')[2:7]
                if original_full_file_name in downloaded_filenames:
                    print(f"Skipping {original_full_file_name} - already downloaded")
                    continue

                # Download file
                file_response = session.get(f"https://freesound.org{download_link["href"]}")
                if file_response.headers.get('content-type', '').startswith('text/html'):
                    print("ERROR: Got HTML instead of audio - authentication failed!")
                    print("Please add valid cookies to the script")
                    break

                # Store original file
                downloads_dir = ROOT_DIR / "downloads"
                os.makedirs(downloads_dir, exist_ok=True)
                original_file_path = os.path.join(downloads_dir, original_full_file_name)
                with open(original_file_path, "wb") as f:
                    f.write(file_response.content)

                # Convert and store as m4a
                file_id = str(uuid.uuid4())

                m4a_output_file_name = file_id + ".m4a"
                m4a_dir = downloads_dir / "m4a"
                os.makedirs(m4a_dir, exist_ok=True)
                m4a_file_path = os.path.join(m4a_dir, m4a_output_file_name)

                try:
                    subprocess.run([
                        "ffmpeg",
                        "-i", original_file_path,
                        "-c:a", "aac",
                        "-b:a", "128k",
                        "-y",
                        m4a_file_path
                    ], check=True, capture_output=True)
                    print(f"(f{downloaded_count + 1} on p{page}) Done with file {original_full_file_name}")
                except subprocess.CalledProcessError as e:
                    print(f"Conversion failed for {original_full_file_name}: {e}")
                    failed_conversion_urls.append(full_sample_page_url)
                    continue

                # Track this download
                author_lower = author.lower()
                original_clean_file_name = original_full_file_name.removeprefix(f"{sound_id}__").removeprefix(
                    f"{author_lower}__")
                clean_file_name_base = os.path.splitext(original_clean_file_name)[0]
                new_sample_record = {
                    "full_name": original_full_file_name,
                    "base_name": clean_file_name_base,
                }
                downloaded_samples_map[file_id] = new_sample_record
                downloaded_filenames.add(original_full_file_name)
                downloaded_author_sound_id_pairs.add((sound_id, author_lower))

                downloaded_count += 1
                time.sleep(1)  # Be nice to the server

            page += 1
    finally:
        # Always save downloaded IDs, even if interrupted
        save_downloaded_samples_map(downloaded_samples_map)
        print(f"Saved {len(newly_downloaded)} new sample IDs")
        if failed_conversion_urls:
            print(f"Failed conversion URLs:")
            for url in failed_conversion_urls:
                print(url)


def main():
    scrape_freesound()


if __name__ == "__main__":
    main()
