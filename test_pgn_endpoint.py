import requests
import tempfile
import os

def test_pgn_endpoint():
    """Test the PGN analysis endpoint"""
    
    # Sample PGN from game3.pgn
    sample_pgn = """[Event "Live Chess"]
[Site "Chess.com"]
[Date "2025.07.19"]
[Round "-"]
[White "roygbiv6"]
[Black "VidnyGorod"]
[Result "0-1"]

1. d4 e5 2. e3 $6 exd4 3. Qxd4 Qe7 4. Bd3 Nc6 5. Qc3 Nf6 6. Nf3 d6 7. O-O Bg4 8. Nd4 Ne5 $6 9. Bd2 $2 Bd7 $2 10. Na3 $9 a6 $2 11. Nc4 $9 Neg4 $9 12. Qa5 $9 c5 $4 13. Nf3 Bc6 14. Qb6 $2 Nd7 15. Qa5 b6 $2 16. Qa3 $4 b5 $6 17. Na5 Bd5 $2 18. Qc3 $4 Nge5 $9 19. Nxe5 dxe5 $2 20. e4 $4 b4 $1 21. Bb5 $2 bxc3 22. Nc6 Bxc6 23. Bxc6 Rc8 24. bxc3 $6 Rxc6 25. Bh6 gxh6 0-1"""
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pgn', delete=False) as temp_file:
        temp_file.write(sample_pgn)
        temp_file_path = temp_file.name
    
    try:
        # Prepare the request
        url = 'http://localhost:5000/api/analyze-pgn'
        
        with open(temp_file_path, 'rb') as f:
            files = {'pgn_file': ('test_game.pgn', f, 'text/plain')}
            data = {
                'username': 'roygbiv6',
                'blunder_threshold': '10',
                'engine_think_time': '0.15',
                'debug': 'true'
            }
            
            print("Testing PGN analysis endpoint...")
            response = requests.post(url, files=files, data=data)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✅ Success! Found {result.get('total_blunders', 0)} blunders")
                for blunder in result.get('blunders', []):
                    print(f"  Move {blunder.get('move_number')}: {blunder.get('category')} - {blunder.get('description')}")
            else:
                print(f"❌ Error: {response.text}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        # Clean up
        try:
            os.unlink(temp_file_path)
        except:
            pass

if __name__ == "__main__":
    test_pgn_endpoint() 