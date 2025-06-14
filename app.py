import os
from flask import Flask, jsonify
from flask_cors import CORS
from get_games import fetch_user_games
from analyze_games import find_blunders

app = Flask(__name__)
CORS(app)

#--- Configuration ---
STOCKFISH_PATH = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
GAMES_TO_FETCH = 1
BLUNDER_THRESHOLD = 10
ENGINE_THINK_TIME = 1.0
#--- End Configuration ---

@app.route("/api/analyze/<string:username>")
def analyze_player(username):
    """
    Main API endpoint to fetch games, analyze them, and return blunders.
    """
    print(f"Received request to analyze player: {username}")

    # 1. Fetch the user's games. For now, we'll use some default filters.
    pgn_filename = fetch_user_games(
        username=username, 
        num_games=GAMES_TO_FETCH, 
        selected_types=[], # Empty list = "all" types
        rated_filter="rated"
    )

    if pgn_filename is None:
        return jsonify({"error": "Could not fetch games from Chess.com API."}), 500

    # 2. Analyze the PGN file for blunders.
    blunders_list = find_blunders(
        pgn_filename=pgn_filename,
        stockfish_path=STOCKFISH_PATH,
        player_name=username,
        threshold=BLUNDER_THRESHOLD,
        think_time=ENGINE_THINK_TIME
    )

    if blunders_list is None:
        return jsonify({"error": "Could not find or analyze the PGN file."}), 404

    print(f"Analysis complete. Found {len(blunders_list)} blunders for {username}.")
    
    # 3. Return the successful result as JSON.
    return jsonify(blunders_list)

if __name__ == '__main__':
    # Make sure to install Flask-Cors: pip install Flask-Cors
    app.run(debug=True, port=5000)
