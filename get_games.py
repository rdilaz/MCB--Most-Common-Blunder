import requests
import json
import argparse
import time  # Add time import for performance tracking

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
    main_url = f"https://api.chess.com/pub/player/{username}/games/archives"
    headers = {"User-Agent": "MCB/1.0 (https://github.com/rdilaz/MCB--Most-Common-Blunder)"}

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
        file_name = f"{username}_last_{len(pgns)}_{type_for_filename}_{rated_filter}.pgn"
        
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