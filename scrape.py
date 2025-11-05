import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from time import sleep

DB_PATH = 'esrb_ratings.db'
BASE_URL = 'https://www.esrb.org/search/'

def game_exists(conn, game_title, platform):
    """Check if a game with this title and platform already exists"""
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM ratings WHERE game_title = ? AND platform = ?', (game_title, platform))
    return cursor.fetchone()[0] > 0

def insert_game(conn, game_data):
    """Insert a new game into the database"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ratings (game_title, platform, rating, descriptors, interactive_elements, release_date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', game_data)
    conn.commit()

def parse_game_item(item):
    """Extract game data from an HTML item"""
    try:
        # Title
        title_elem = item.find('h3')
        title = title_elem.text.strip() if title_elem else ''

        # Platform
        platform_elem = item.find('div', class_='platform')
        platform = platform_elem.text.strip() if platform_elem else ''

        # Rating
        rating_elem = item.find('div', class_='rating')
        rating = rating_elem.text.strip() if rating_elem else ''

        # Descriptors
        descriptors_elem = item.find('div', class_='content-descriptors')
        descriptors = descriptors_elem.text.strip() if descriptors_elem else ''

        # Interactive elements
        interactive_elem = item.find('div', class_='interactive-elements')
        interactive = interactive_elem.text.strip() if interactive_elem else ''

        # Release date
        date_elem = item.find('div', class_='release-date')
        release_date = date_elem.text.strip() if date_elem else ''

        return (title, platform, rating, descriptors, interactive, release_date)

    except Exception as e:
        print(f"Error parsing game item: {e}")
        return None

def scrape_search_page(search_term='', rating_filter='', page=1):
    """Scrape a single search results page"""
    conn = sqlite3.connect(DB_PATH)
    new_count = 0
    skipped_count = 0

    print(f"Scraping page {page}...")

    try:
        # Build search URL with parameters
        params = {
            'searchKeyword': search_term,
            'rating': rating_filter,
            'page': page
        }

        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all game items (adjust selector based on actual ESRB website structure)
        items = soup.find_all('div', class_='search-result-item')

        if not items:
            print(f"  No results found on page {page}")
            conn.close()
            return new_count, skipped_count, False

        print(f"  Processing {len(items)} games...")

        for item in items:
            game_data = parse_game_item(item)

            if game_data and game_data[0]:  # Has title
                title, platform, rating, descriptors, interactive, release_date = game_data

                if game_exists(conn, title, platform):
                    skipped_count += 1
                    print(f"    ⊘ SKIPPED: {title} ({platform})")
                else:
                    insert_game(conn, game_data)
                    new_count += 1
                    print(f"    ✓ ADDED: {title} ({platform})")
                    print(f"      Rating: {rating}")

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

    total_new = 0
    total_skipped = 0

    # Scrape multiple pages (adjust as needed)
    max_pages = 10
    for page in range(1, max_pages + 1):
        new, skipped, has_more = scrape_search_page(page=page)
        total_new += new
        total_skipped += skipped

        if not has_more:
            break

    # Log the scrape run
    log_scrape_run(total_new, total_skipped)

    print(f"\n=== Scrape Complete ===")
    print(f"New games added: {total_new}")
    print(f"Existing games skipped: {total_skipped}")

if __name__ == '__main__':
    main()
