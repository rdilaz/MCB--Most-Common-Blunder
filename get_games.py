# library for making HTTP requests
import requests

# library for parsing JSON data from the API
import json

# Define Chess.com username 
username = "roygbiv6"

# construct request URL, returns a list of monthly archive URLs for the user's games
# main_url is the URL that has the list of monthly archive URLs
main_url = f"https://api.chess.com/pub/player/{username}/games/archives"

# headers tell server who is making the request
headers = {"User-Agent": "MCB/1.0 (Most Common Blunder Project: Please contact at dilazzaroryo@gmail.com)"}

# send request to the API, using try except to handle errors
try:
    # request.get() sends get request to specified URL,header is passed here 
    response = requests.get(main_url, headers=headers)

    # check if request was successful (e.g. 200 OK status code)
    # will raise an exception for bad status codes so we can handle them
    response.raise_for_status()

    # API will return JSON (JavaScript Object Notation).
    # .json() will parse the text into a Python dictionary or list.
    archives_data = response.json()

    # the data for this endpoint is a dictionary with a single key, "archives"
    # the value is a list of URLS. Lets get that list.
    archive_urls = archives_data.get("archives", [])

    # # print the list of archive URLs to the console.
    # print(f"Found {len(archive_urls)} monthly archive URLs for '{username}':")

    # ========================================================================
    # logic for extracting games from archives. 
    # MCB will only anlayzie the last 50 games (for now) so 
    # we will go from most recent month and fill until 50 games are extracted.
    #=========================================================================

    # list for holding PGN data
    pgns = []
    games_needed = 50

    # starting from the most recent month, iterate over the archive URLs in reverse order (since they are posted earliest first).
    for archive_url in reversed(archive_urls):
        # once 50 games are extracted, break out of the for loop
        if len(pgns) >= games_needed:
            print(f"Extracted {len(pgns)} most recent games.")
            break

        # print the current archive URL
        print(f"Extracting games from monthly archive URL: {archive_url}")

        # make new request to archive URL
        monthly_response = requests.get(archive_url, headers=headers)
        monthly_response.raise_for_status()

        # new endpoint returns dictionary with "games" key, with a list of game objects.
        monthly_games_data = monthly_response.json()
        games_in_month = monthly_games_data.get("games", [])

        print(f"Found {len(games_in_month)} games in {archive_url}.")

        # games are also oldest to newest, so reverse and get most recent ones first
        for game_data in reversed(games_in_month):
            # each game has "pgn" key
            if "pgn" in game_data:
                pgns.append(game_data["pgn"])
                # stop once we have 50 games
                if len(pgns) >= games_needed:
                    break
    print(f"\nTotal games extracted: {len(pgns)}")

    # save the collected PGNS to a single file.
    # w mode will write to filem overwriting if it exists.
    # each pgn is seperated by 2 newlines for readability
    file_name = f"{username}_last_{len(pgns)}_games.pgn"
    with open(file_name, "w", encoding='utf-8') as f:
        # join method combines list of strings
        f.write("\n\n".join(pgns))

    print(f"PGNS saved to: {file_name}")
       

except requests.exceptions.RequestException as e:
    print(f"An error occured: {e}")
    print(f"Error details: {e.response.text}")