# library for making HTTP requests
import requests

# library for parsing JSON data from the API
import json

# Define Chess.com username 
username = "roygbiv6"

# construct request URL, uses f-string to insert username into the URL
url = f"https://api.chess.com/pub/player/{username}/games/archives"

# headers tell server who is making the request
headers = {"User-Agent": "MCB/1.0 (Most Common Blunder Project: Please contact at dilazzaroryo@gmail.com)"}

# send request to the API, using try except to handle errors
try:
    # request.get() sends get request to specified URL, pass headers here as well
    response = requests.get(url, headers=headers)

    # check if request was successful (e.g. 200 OK status code)
    # will raise an exception for bad status codes so we can handle them
    response.raise_for_status()

    # API will return JSON (JavaScript Object Notation).
    # .json() will parse the text into a Python dictionary or list.
    archives_data = response.json()

    # the data for this endpoint is a dictionary with a single key, "archives"
    # the value is a list of URLS. Lets get that list.
    archive_urls = archives_data.get("archives", [])

    # print the list of archive URLs to the console.
    print(f"Found {len(archive_urls)} monthly archive URLs for '{username}':")

    # use json.dumps() to pretty print the data, making it easier to read.
    # ident = 4 tell json.dumps to use 4 spaces for indentation
    print(json.dumps(archive_urls, indent=4))

except requests.exceptions.RequestException as e:
    print(f"An error occured: {e}")
    print(f"Error details: {e.response.text}")