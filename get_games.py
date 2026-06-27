import json
import time  # Add time import for performance tracking
from urllib.parse import quote
import asyncio
import httpx
import tempfile
import os
from typing import List, Tuple, Optional

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

            return save_games_data(username, pgns, games_metadata, selected_types, rated_filter, fetch_start)

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

            pgn, metadata = process_game_data(game_data, username, selected_types, rated_filter)
            if pgn and metadata:
                pgns.append(pgn)
                games_metadata.append(metadata)

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


def process_game_data(game_data: dict, username: str, selected_types: List[str], rated_filter: str) -> Tuple[Optional[str], Optional[dict]]:
    """
    Process a single game data dict, apply filters, and extract metadata.
    Returns (pgn_string, game_metadata) if it passes filters, else (None, None).
    """
    current_game_type = game_data.get("time_class")
    if selected_types and current_game_type not in selected_types:
        return None, None

    is_rated_game = game_data.get("rated", False)
    if rated_filter == "rated" and not is_rated_game:
        return None, None
    if rated_filter == "unrated" and is_rated_game:
        return None, None

    pgn_string = game_data.get("pgn")
    if pgn_string:
        game_info = {
            "url": game_data.get("url", ""),
            "white": game_data.get("white", {}).get("username", "Unknown"),
            "black": game_data.get("black", {}).get("username", "Unknown"),
            "date": format_game_date(game_data.get("end_time", 0)),
            "time_class": current_game_type if current_game_type else "unknown",
            "rated": is_rated_game,
            "target_player": username
        }
        return pgn_string, game_info
        
    return None, None


def save_games_data(username: str, pgns: List[str], games_metadata: List[dict], selected_types: List[str], rated_filter: str, fetch_start: float) -> Tuple[str, List[dict]]:
    """
    Saves PGNs and metadata to files and logs performance timing.
    Returns (file_name, games_metadata)
    """
    file_start = time.time()
    type_str = ", ".join(selected_types) if selected_types else "all"
    type_for_filename = type_str.replace(", ", "-") if selected_types else "all"
    base_filename = f"{username}_last_{len(pgns)}_{type_for_filename}_{rated_filter}.pgn"
    
    file_name = os.path.join(tempfile.gettempdir(), base_filename)
    
    print(f"   [FILE] Writing PGN file '{file_name}'...")
    with open(file_name, "w", encoding="utf-8") as f:
        f.write("\n\n".join(pgns))
    
    file_time = time.time() - file_start
    total_time = time.time() - fetch_start
    print(f"   [SUCCESS] PGN file written in {file_time:.3f} seconds")
    print(f"[COMPLETE] Total fetch time: {total_time:.2f} seconds")
    print(f"PGN file saved as '{file_name}'")
    
    metadata_file = file_name.replace('.pgn', '_metadata.json')
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(games_metadata, f, indent=2)
    print(f"Game metadata saved as '{metadata_file}'")
    
    return file_name, games_metadata


def fetch_user_games(username: str, num_games: int, selected_types: List[str], rated_filter: str) -> Tuple[Optional[str], List[dict]]:
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