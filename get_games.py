import requests
import json
import argparse
import time  # Add time import for performance tracking
from urllib.parse import quote
import asyncio
import httpx
from typing import List, Tuple, Optional

def fetch_user_games(username, num_games, selected_types, rated_filter):
    """
    Fetches a user's games from Chess.com API based on multiple criteria.
    Args:
        username (str): The username of the player to fetch games for.
        num_games (int): The number of games to fetch.
        selected_types (list): A list of game types to fetch.
        rated_filter (str): The filter to apply to the games.
    Returns:
        tuple: (pgn_filename, games_metadata) where games_metadata is a list of game info dicts
    """
    fetch_start = time.time()
    
    # Sanitize username for URL safety
    safe_username = quote(username, safe='')
    main_url = f"https://api.chess.com/pub/player/{safe_username}/games/archives"
    headers = {"User-Agent": "MCB/1.0"}

    # Improved print statement for clarity
    type_str = ", ".join(selected_types) if selected_types else "all"
    print(f"Config: Fetching last {num_games} games for '{username}' | Types: '{type_str}' | Filter: '{rated_filter}'")

    try:
        # Step 1: Get archives list
        archives_start = time.time()
        print(f"   [INFO] Fetching archives list...")
        response = requests.get(main_url, headers=headers)
        response.raise_for_status()
        archives_data = response.json()
        archive_urls = archives_data.get("archives", [])
        archives_time = time.time() - archives_start
        print(f"   [SUCCESS] Found {len(archive_urls)} monthly archives in {archives_time:.3f} seconds")

        pgns = []
        games_metadata = []
        archives_processed = 0
        
        # Step 2: Process each archive (starting from most recent)
        games_start = time.time()
        for archive_url in reversed(archive_urls):
            if len(pgns) >= num_games:
                break

            archives_processed += 1
            month_start = time.time()
            print(f"   [ARCHIVE] Processing archive {archives_processed}/{len(archive_urls)}...")
            
            monthly_response = requests.get(archive_url, headers=headers)
            monthly_response.raise_for_status()
            monthly_games_data = monthly_response.json()
            games_in_month = monthly_games_data.get("games", [])
            
            month_time = time.time() - month_start
            print(f"   [SUCCESS] Retrieved {len(games_in_month)} games from archive in {month_time:.3f} seconds")

            games_added_this_month = 0
            for game_data in reversed(games_in_month):
                if len(pgns) >= num_games:
                    break

                # Filter 1: Game Type
                current_game_type = game_data.get("time_class")
                # If the user selected specific types AND the current game's type isn't in their list, skip.
                if selected_types and current_game_type not in selected_types:
                    continue

                # Filter 2: Rated Status
                is_rated_game = game_data.get("rated", False)
                if rated_filter == "rated" and not is_rated_game:
                    continue
                if rated_filter == "unrated" and is_rated_game:
                    continue
                
                pgn_string = game_data.get("pgn")
                if pgn_string:
                    # Extract game metadata
                    white_player = game_data.get("white", {}).get("username", "Unknown")
                    black_player = game_data.get("black", {}).get("username", "Unknown")
                    game_url = game_data.get("url", "")
                    end_time = game_data.get("end_time", 0)
                    time_class = game_data.get("time_class", "unknown")
                    rated = game_data.get("rated", False)
                    
                    # Format end time
                    import datetime
                    try:
                        game_date = datetime.datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M")
                    except:
                        game_date = "Unknown date"
                    
                    # Store game metadata
                    game_info = {
                        "url": game_url,
                        "white": white_player,
                        "black": black_player,
                        "date": game_date,
                        "time_class": time_class,
                        "rated": rated,
                        "target_player": username  # Which player we're analyzing
                    }
                    
                    pgns.append(pgn_string)
                    games_metadata.append(game_info)
                    games_added_this_month += 1
            
            print(f"   [STATS] Added {games_added_this_month} games after filtering (Total: {len(pgns)}/{num_games})")

        games_time = time.time() - games_start
        print(f"[SUCCESS] Game collection completed in {games_time:.2f} seconds")
        print(f"Successfully fetched {len(pgns)} games.")

        # --- IMPROVED FILENAME LOGIC ---
        file_start = time.time()
        type_for_filename = type_str.replace(", ", "-") if selected_types else "all"
        base_filename = f"{username}_last_{len(pgns)}_{type_for_filename}_{rated_filter}.pgn"
        
        # Use safe file operations
        try:
            from utils import safe_file_operations
            file_name = safe_file_operations(base_filename)
        except ImportError:
            # Fallback if utils not available
            file_name = base_filename
        
        print(f"   [FILE] Writing PGN file '{file_name}'...")
        with open(file_name, "w", encoding="utf-8") as f:
            f.write("\n\n".join(pgns))
        
        file_time = time.time() - file_start
        total_time = time.time() - fetch_start
        print(f"   [SUCCESS] PGN file written in {file_time:.3f} seconds")
        print(f"[COMPLETE] Total fetch time: {total_time:.2f} seconds")
        print(f"PGN file saved as '{file_name}'")
        
        # Also save games metadata as JSON for debugging
        metadata_file = file_name.replace('.pgn', '_metadata.json')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(games_metadata, f, indent=2)
        print(f"Game metadata saved as '{metadata_file}'")
        
        return file_name, games_metadata
    
    except requests.exceptions.RequestException as e:
        print(f"API error occurred: {e}")
        return None, []


async def fetch_user_games_async(username: str, num_games: int, selected_types: List[str], rated_filter: str) -> Tuple[Optional[str], List[dict]]:
    """
    Async version of fetch_user_games with concurrent API calls for better performance.
    
    Args:
        username (str): The username of the player to fetch games for.
        num_games (int): The number of games to fetch.
        selected_types (List[str]): A list of game types to fetch.
        rated_filter (str): The filter to apply to the games.
        
    Returns:
        Tuple[Optional[str], List[dict]]: (pgn_filename, games_metadata) where games_metadata is a list of game info dicts
    """
    fetch_start = time.time()
    
    # Sanitize username for URL safety
    safe_username = quote(username, safe='')
    main_url = f"https://api.chess.com/pub/player/{safe_username}/games/archives"
    headers = {"User-Agent": "MCB/1.0"}

    type_str = ", ".join(selected_types) if selected_types else "all"
    print(f"Config: Fetching last {num_games} games for '{username}' | Types: '{type_str}' | Filter: '{rated_filter}'")

    try:
        async with httpx.AsyncClient(headers=headers) as client:
            # Step 1: Get archives list
            archives_start = time.time()
            print(f"   [INFO] Fetching archives list...")

            response = await client.get(main_url)
            response.raise_for_status()
            archives_data = response.json()
            archive_urls = archives_data.get("archives", [])

            archives_time = time.time() - archives_start
            print(f"   [SUCCESS] Found {len(archive_urls)} monthly archives in {archives_time:.3f} seconds")

            # Step 2: Fetch multiple archives concurrently
            pgns = []
            games_metadata = []

            # Process archives in batches to avoid overwhelming the API
            batch_size = 3
            for i in range(0, len(archive_urls), batch_size):
                batch = list(reversed(archive_urls))[i:i+batch_size]

                print(f"   [BATCH] Processing batch {i//batch_size + 1} with {len(batch)} archives...")
                
                # Fetch batch concurrently
                tasks = [fetch_archive_games(client, url, username, num_games, selected_types, rated_filter) for url in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in batch_results:
                    if isinstance(result, Exception):
                        print(f"   [ERROR] Archive fetch failed: {result}")
                        continue

                    batch_pgns, batch_metadata = result
                    pgns.extend(batch_pgns)
                    games_metadata.extend(batch_metadata)

                    if len(pgns) >= num_games:
                        break

                if len(pgns) >= num_games:
                    break

            # Trim to requested number
            pgns = pgns[:num_games]
            games_metadata = games_metadata[:num_games]

            print(f"[SUCCESS] Async game collection completed. Found {len(pgns)} games.")

            # --- IMPROVED FILENAME LOGIC ---
            file_start = time.time()
            type_for_filename = type_str.replace(", ", "-") if selected_types else "all"
            base_filename = f"{username}_last_{len(pgns)}_{type_for_filename}_{rated_filter}.pgn"
            
            # Use safe file operations
            try:
                from utils import safe_file_operations
                file_name = safe_file_operations(base_filename)
            except ImportError:
                # Fallback if utils not available
                file_name = base_filename
            
            print(f"   [FILE] Writing PGN file '{file_name}'...")
            with open(file_name, "w", encoding="utf-8") as f:
                f.write("\n\n".join(pgns))
            
            file_time = time.time() - file_start
            total_time = time.time() - fetch_start
            print(f"   [SUCCESS] PGN file written in {file_time:.3f} seconds")
            print(f"[COMPLETE] Total async fetch time: {total_time:.2f} seconds")
            print(f"PGN file saved as '{file_name}'")
            
            # Also save games metadata as JSON for debugging
            metadata_file = file_name.replace('.pgn', '_metadata.json')
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(games_metadata, f, indent=2)
            print(f"Game metadata saved as '{metadata_file}'")
            
            return file_name, games_metadata

    except Exception as e:
        print(f"Async API error occurred: {e}")
        return None, []


async def fetch_archive_games(client: httpx.AsyncClient, archive_url: str, username: str, num_games: int, selected_types: List[str], rated_filter: str) -> Tuple[List[str], List[dict]]:
    """
    Fetch games from a single archive asynchronously.
    
    Args:
        client: httpx AsyncClient for making requests
        archive_url: URL of the archive to fetch
        username: Username for target player identification
        num_games: Maximum number of games to fetch
        selected_types: List of game types to filter
        rated_filter: Filter for rated/unrated games
        
    Returns:
        Tuple[List[str], List[dict]]: (pgn_strings, games_metadata)
    """
    try:
        response = await client.get(archive_url)
        response.raise_for_status()
        monthly_games_data = response.json()
        games_in_month = monthly_games_data.get("games", [])

        pgns = []
        games_metadata = []

        for game_data in reversed(games_in_month):
            if len(pgns) >= num_games:
                break

            # Apply filters (same logic as original)
            current_game_type = game_data.get("time_class")
            if selected_types and current_game_type not in selected_types:
                continue

            is_rated_game = game_data.get("rated", False)
            if rated_filter == "rated" and not is_rated_game:
                continue
            if rated_filter == "unrated" and is_rated_game:
                continue

            pgn_string = game_data.get("pgn")
            if pgn_string:
                # Extract metadata (same as original)
                game_info = {
                    "url": game_data.get("url", ""),
                    "white": game_data.get("white", {}).get("username", "Unknown"),
                    "black": game_data.get("black", {}).get("username", "Unknown"),
                    "date": format_game_date(game_data.get("end_time", 0)),
                    "time_class": game_data.get("time_class", "unknown"),
                    "rated": game_data.get("rated", False),
                    "target_player": username
                }

                pgns.append(pgn_string)
                games_metadata.append(game_info)

        return pgns, games_metadata

    except Exception as e:
        print(f"Error fetching archive {archive_url}: {e}")
        return [], []


def format_game_date(end_time: int) -> str:
    """Format game end time to readable date"""
    try:
        import datetime
        return datetime.datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M")
    except:
        return "Unknown date"


def fetch_user_games_with_async(username: str, num_games: int, selected_types: List[str], rated_filter: str) -> Tuple[Optional[str], List[dict]]:
    """
    Synchronous wrapper for async function - provides backwards compatibility.
    
    This function uses the async implementation internally but provides a synchronous interface
    for existing code that depends on the original fetch_user_games function.
    
    Args:
        username (str): The username of the player to fetch games for.
        num_games (int): The number of games to fetch.
        selected_types (List[str]): A list of game types to fetch.
        rated_filter (str): The filter to apply to the games.
        
    Returns:
        Tuple[Optional[str], List[dict]]: (pgn_filename, games_metadata)
    """
    try:
        # Check if there's already a running event loop
        loop = asyncio.get_running_loop()
        # If there is, we need to run in a new thread to avoid conflicts
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, fetch_user_games_async(username, num_games, selected_types, rated_filter))
            return future.result()
    except RuntimeError:
        # No running event loop, safe to use asyncio.run
        return asyncio.run(fetch_user_games_async(username, num_games, selected_types, rated_filter))

# argparse for debugging
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch recent games for a Chess.com user.",
        formatter_class=argparse.RawTextHelpFormatter # Improves help message formatting
    )

    parser.add_argument("--username", type=str, required=True, help="Chess.com username.")
    parser.add_argument("--num_games", type=int, default=50, help="Number of games to fetch. Default is 50.")
    parser.add_argument("--filter", type=str, default="rated", choices=["rated", "unrated", "both"],
                        help="Filter by rated status: 'rated' (default), 'unrated', or 'both'.")
    
    # NEW: Replaced --game_type with individual flags for each category
    parser.add_argument("--rapid", action="store_true", help="Include rapid games.")
    parser.add_argument("--blitz", action="store_true", help="Include blitz games.")
    parser.add_argument("--bullet", action="store_true", help="Include bullet games.")
    parser.add_argument("--daily", action="store_true", help="Include daily games.")
    
    args = parser.parse_args()

    # Build a list of the game types the user selected.
    selected_types = []
    if args.rapid:
        selected_types.append("rapid")
    if args.blitz:
        selected_types.append("blitz")
    if args.bullet:
        selected_types.append("bullet")
    if args.daily:
        selected_types.append("daily")
    
    # If the user provides no flags, the list remains empty, which we'll treat as "all".

    print("\n--- Running in standalone test mode ---")
    pgn_file, games_metadata = fetch_user_games(
        username=args.username,
        num_games=args.num_games,
        selected_types=selected_types, # Pass the list to our function
        rated_filter=args.filter
    )
    
    if pgn_file and games_metadata:
        print(f"\n[GAMES] Games analyzed:")
        for i, game in enumerate(games_metadata, 1):
            print(f"  {i}. {game['white']} vs {game['black']} ({game['time_class']}) - {game['date']}")
            print(f"     [LINK] {game['url']}")