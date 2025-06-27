import os
import chess
import chess.pgn
import chess.engine
from collections import Counter
from flask import Flask, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
from get_games import fetch_user_games
from analyze_games import analyze_game

app = Flask(__name__)
CORS(app)

#--- Configuration ---
STOCKFISH_PATH = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
GAMES_TO_FETCH = 1
BLUNDER_THRESHOLD = 10
ENGINE_THINK_TIME = 1.0
#--- End Configuration ---

@app.route("/")
def home():
    """
    Serve the main HTML page.
    """
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return "index.html not found", 404

@app.route("/styles.css")
def serve_css():
    """
    Serve the CSS file.
    """
    return send_from_directory('.', 'styles.css')

@app.route("/main.js")
def serve_js():
    """
    Serve the JavaScript file.
    """
    return send_from_directory('.', 'main.js')

def analyze_multiple_games(pgn_file_path, username, stockfish_path, blunder_threshold, engine_think_time):
    """
    Wrapper function that processes multiple games from a PGN file and aggregates blunder data.
    
    Args:
        pgn_file_path (str): Path to the PGN file
        username (str): Username to analyze blunders for
        stockfish_path (str): Path to Stockfish engine
        blunder_threshold (float): Win probability drop threshold for blunder detection
        engine_think_time (float): Engine analysis time per move
    
    Returns:
        dict: Structured summary with blunder statistics and detailed list
    """
    # Initialize Stockfish engine
    try:
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    except Exception as e:
        return {"error": f"Could not initialize Stockfish engine: {str(e)}"}

    # Process games and collect blunders
    all_blunders = []
    games_analyzed = 0
    
    try:
        with open(pgn_file_path, 'r', encoding='utf-8') as pgn_file:
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break
                
                games_analyzed += 1
                print(f"Analyzing game #{games_analyzed}")
                
                # Analyze this game for blunders
                blunders = analyze_game(
                    game=game,
                    engine=engine,
                    target_user=username,
                    blunder_threshold=blunder_threshold,
                    engine_think_time=engine_think_time,
                    debug_mode=False
                )
                
                all_blunders.extend(blunders)
                
    except FileNotFoundError:
        engine.quit()
        return {"error": f"Could not find PGN file: {pgn_file_path}"}
    except Exception as e:
        engine.quit()
        return {"error": f"Error processing games: {str(e)}"}
    finally:
        # Always close the engine
        engine.quit()

    # Aggregate blunder statistics
    if not all_blunders:
        return {
            "success": True,
            "username": username,
            "games_analyzed": games_analyzed,
            "summary": {
                "total_blunders": 0,
                "most_common_blunder": None,
                "message": "No blunders detected in the analyzed games!"
            },
            "blunders": []
        }

    # Count blunder categories
    blunder_categories = [blunder['category'] for blunder in all_blunders]
    category_counts = Counter(blunder_categories)
    
    # Find most common blunder
    most_common = category_counts.most_common(1)[0]
    most_common_category = most_common[0]
    most_common_count = most_common[1]
    most_common_percentage = round((most_common_count / len(all_blunders)) * 100, 1)
    
    # Find an example of the most common blunder
    example_blunder = next(
        (blunder for blunder in all_blunders if blunder['category'] == most_common_category), 
        None
    )
    
    # Create structured summary
    summary = {
        "total_blunders": len(all_blunders),
        "most_common_blunder": {
            "category": most_common_category,
            "count": most_common_count,
            "percentage": most_common_percentage,
            "example": example_blunder['description'] if example_blunder else None
        },
        "category_breakdown": dict(category_counts)
    }
    
    return {
        "success": True,
        "username": username,
        "games_analyzed": games_analyzed,
        "summary": summary,
        "blunders": all_blunders
    }

@app.route("/api/analyze/<string:username>")
def analyze_player(username):
    """
    Main API endpoint to fetch games, analyze them, and return blunders.
    """
    print(f"Received request to analyze player: {username}")

    # 1. Fetch the user's games
    pgn_filename = fetch_user_games(
        username=username, 
        num_games=GAMES_TO_FETCH, 
        selected_types=[], # Empty list = "all" types
        rated_filter="rated"
    )

    if pgn_filename is None:
        return jsonify({"error": "Could not fetch games from Chess.com API."}), 500

    # 2. Analyze all games using our wrapper function
    result = analyze_multiple_games(
        pgn_file_path=pgn_filename,
        username=username,
        stockfish_path=STOCKFISH_PATH,
        blunder_threshold=BLUNDER_THRESHOLD,
        engine_think_time=ENGINE_THINK_TIME
    )
    
    # 3. Handle errors from the analysis
    if "error" in result:
        return jsonify(result), 500

    print(f"Analysis complete. Found {result['summary']['total_blunders']} blunders across {result['games_analyzed']} games for {username}.")
    
    # 4. Return the successful result as JSON
    return jsonify(result)

if __name__ == '__main__':
    # Make sure to install Flask-Cors: pip install Flask-Cors
    app.run(debug=True, port=5000)
