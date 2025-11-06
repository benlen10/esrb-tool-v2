# ESRB Ratings Browser

Simple web app to browse and search ESRB video game ratings.

## Features

- Browse 30,000+ ESRB-rated games
- Search by title, filter by platform and rating
- Sort by game ID (newest first), title, platform, or rating
- Export filtered results to CSV
- Official ESRB rating icons
- Automatic scraper for latest ratings

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Visit http://localhost:5000

## Update Ratings

Click "Fetch New Data" in the UI or run:

```bash
python scrape.py
```

## Tech Stack

- Backend: Flask + SQLite
- Frontend: Vanilla JavaScript (no frameworks)
- Scraper: requests + BeautifulSoup