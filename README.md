# Freesound scraper

## Installation

Prerequisites: Python 3 and PIP.

Install dependencies:

```
pip install -r requirements.txt
```

## Setup

1. Add your auth tokens

- Log in to freesound.org
- Open your browser's developer console and go to the network tab.
- Click a download link for a sound and watch the network tab.
- Find a request with a 302 response (the file download) and look at the cookies sent for that request.
- Copy the values of the `sessionid` and the `csrftoken` cookies.
- Open the `.env` file in this project and place your own tokens in there:

```
SESSIONID=your_session_id
CSRFTOKEN=your_csrf_token
```

2. Create a search URL

- Make a search on freesound.org and apply any filters you want.
- Copy the URL (it contains your search options)
- Place the URL in the `.env` file:

```
SEARCH_URL=your_search_url
```

## Usage

```
python3 main.py
```

The scraper will create:
- `downloads/` - a directory where it saves the original audio files.
- `downloads/m4a/` - a directory with each file converted to M4A (web friendly) and given a UUIDv4 name.
- `downloads/downloaded_samples.json` - a tracking file which stores file names to prevent duplicate downloads.
