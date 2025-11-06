"""
ESRB Ratings Scraper
Scrapes latest rated games from ESRB.org and stores them in SQLite database.
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
from time import sleep
import re

DB_PATH = 'esrb_ratings.db'
BASE_URL = 'https://www.esrb.org/search/'

def extract_game_id(url):
    """Extract the game ID from an ESRB URL"""
    if not url:
        return None
    match = re.search(r'/ratings/(\d+)/', url)
    if match:
        return int(match.group(1))
    return None

def game_exists(conn, game_id):
    """Check if a game with this ID already exists"""
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM ratings WHERE game_id = ?', (game_id,))
    return cursor.fetchone()[0] > 0

def insert_game(conn, game_data):
    """Insert a new game into the database"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ratings (game_id, game_title, platform, rating, descriptors, url, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', game_data)
    conn.commit()

def parse_game_item(item):
    """Extract game data from a game div element"""
    try:
        # Title and URL
        title_elem = item.find('h2')
        if not title_elem:
            return None

        link = title_elem.find('a')
        if not link:
            return None

        title = link.get_text(strip=True)
        url = link.get('href', '')
        game_id = extract_game_id(url)

        if not game_id:
            return None

        # Platform
        platform_elem = item.find('div', class_='platforms')
        platform = platform_elem.get_text(strip=True) if platform_elem else ''

        # Rating (from image alt attribute)
        rating_img = item.find('img', alt=True)
        rating = rating_img.get('alt', '') if rating_img else ''

        # Find table data
        table = item.find('table')
        descriptors = ''
        summary = ''

        if table:
            rows = table.find_all('tr')
            if len(rows) > 1:
                cells = rows[1].find_all('td')

                # Content descriptors (column 2)
                if len(cells) > 1:
                    desc_cell = cells[1]
                    # Get text and clean up - HTML has commas already, just replace line breaks
                    descriptors = desc_cell.get_text(separator=' ', strip=True)
                    # Clean up any double commas or spaces
                    descriptors = descriptors.replace(',,', ',').replace('  ', ' ').strip()

                # Rating Summary/Synopsis (column 4)
                if len(cells) > 3:
                    synopsis_div = cells[3].find('div', class_='synopsis')
                    if synopsis_div:
                        summary = synopsis_div.get_text(strip=True)

        return (game_id, title, platform, rating, descriptors, url, summary)

    except Exception as e:
        print(f"Error parsing game item: {e}")
        return None

def scrape_page(page):
    """Scrape a single search results page"""
    conn = sqlite3.connect(DB_PATH)
    new_count = 0
    skipped_count = 0

    # Construct URL with pagination
    url = f"{BASE_URL}?searchKeyword=&searchType=LatestRatings&pg={page}"

    # Headers to mimic browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Safari/605.1.15',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all game items
        games = soup.find_all('div', class_='game')

        if not games:
            print(f"  No more results on page {page}")
            conn.close()
            return new_count, skipped_count, False

        print(f"  Processing page {page} ({len(games)} games)...")

        for game in games:
            game_data = parse_game_item(game)

            if game_data and game_data[0]:  # Has game_id
                game_id, title, platform, rating, descriptors = game_data[0], game_data[1], game_data[2], game_data[3], game_data[4]

                if game_exists(conn, game_id):
                    skipped_count += 1
                    print(f"    ⊘ SKIPPED: {title}")
                    print(f"      ID: {game_id} | Platform: {platform}")
                    # Stop when we hit an existing game (since we're scraping latest first)
                    conn.close()
                    return new_count, skipped_count, False
                else:
                    insert_game(conn, game_data)
                    new_count += 1
                    print(f"    ✓ ADDED: {title}")
                    print(f"      ID: {game_id} | Platform: {platform}")
                    print(f"      Rating: {rating} | Descriptors: {descriptors[:50]}...")

        sleep(1)  # Be respectful to the server

    except Exception as e:
        print(f"  Error fetching page {page}: {e}")
        conn.close()
        return new_count, skipped_count, False

    conn.close()
    return new_count, skipped_count, True

def log_scrape_run(games_added, games_skipped):
    """Log the scrape run to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO scrape_log (games_added, games_skipped) VALUES (?, ?)',
                   (games_added, games_skipped))
    conn.commit()
    conn.close()

def main():
    """Main scraper function"""
    print(f"=== ESRB Ratings Scraper ===")
    print(f"Scraping latest rated games...\n")

    total_new = 0
    total_skipped = 0
    page = 1
    max_pages = 50  # Safety limit

    while page <= max_pages:
        new, skipped, has_more = scrape_page(page)
        total_new += new
        total_skipped += skipped

        if not has_more:
            break

        page += 1

    # Log the scrape run
    log_scrape_run(total_new, total_skipped)

    print(f"\n=== Scrape Complete ===")
    print(f"New games added: {total_new}")
    print(f"Existing games skipped: {total_skipped}")

if __name__ == '__main__':
    main()
