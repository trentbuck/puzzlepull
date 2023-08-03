import datetime
import json

import httpx
import lxml.html


# Create a session, so HTTP/2 connection pooling works.
# This dramatically reduces the overhead on the server.
_sess = httpx.Client(http2=True)


# make a blank puzzle
def make_blank_puzzle(width, height):
    puzzle = []
    for row in range(height):
        puzzle.append(["#"] * width)

    return puzzle


# get the solution from the entries
def get_solution(width, height, data):

    blank_puzzle = make_blank_puzzle(15, 15)

    # fill in across answers to solution
    for clue in data["entries"]:
        x = clue["position"]["x"]
        y = clue["position"]["y"]
        length = clue["length"]
        solution = clue["solution"]
        if clue["direction"] == "across":
            blank_puzzle[y][x:x + length] = list(solution)
        elif clue["direction"] == "down":
            for index, row in enumerate(range(y, y + length)):
                blank_puzzle[row][x] = solution[index]

    return blank_puzzle


# get the puzzle layout
def get_layout(width, height, data):
    blank_puzzle = make_blank_puzzle(15, 15)

    # fill in across answers to solution
    # across first
    for clue in data["entries"]:
        x = clue["position"]["x"]
        y = clue["position"]["y"]
        length = clue["length"]
        number = clue["number"]
        blank_puzzle[y][x] = number
        if clue["direction"] == "across":
            blank_puzzle[y][x + 1:x + length] = [0] * (length - 1)

    # down next
    for clue in data["entries"]:
        x = clue["position"]["x"]
        y = clue["position"]["y"]
        length = clue["length"]
        number = clue["number"]
        blank_puzzle[y][x] = number
        if clue["direction"] == "down":
            for index, row in enumerate(range(y + 1, y + length)):
                if blank_puzzle[row][x] == "#":
                    blank_puzzle[row][x] = 0

    return blank_puzzle


# get the clues from the entry
def get_clues(data):

    clues = dict()
    clues["Across"] = []
    clues["Down"] = []

    for clue in data["entries"]:

        number = clue["number"]
        text = clue["clue"]
        direction = clue["direction"]

        clues[direction.capitalize()].append([number, text])

    return clues


def get_guardian_puzzle(URL, filepath=None, download=True):

    resp = _sess.get(URL)
    if resp.status_code == 404:
        return False            # cheap hack
    if resp.status_code == 301 and resp.headers['location'] == 'https://www.theguardian.com/crosswords/':
        return False            # seen for https://www.theguardian.com/crosswords/quick/9245
    resp.raise_for_status()

    js_crossword, = lxml.html.fromstring(resp.text).xpath('//@data-crossword-data')
    data = json.loads(js_crossword)

    # get the datetime
    dt = datetime.datetime.fromtimestamp(data["date"] / 1000)
    width = data["dimensions"]["cols"]
    height = data["dimensions"]["rows"]

    puzzle = dict()
    puzzle["origin"] = "The Guardian"
    puzzle["version"] = "http://ipuz.org/v2"
    puzzle["kind"] = ["http://ipuz.org/crossword"]
    puzzle["copyright"] = f"{dt.year} Guardian News & Media Limited"

    try:
        puzzle["author"] = data["creator"]["name"]
    except KeyError:
        pass  # no author!

    puzzle["publisher"] = "The Guardian"
    puzzle["url"] = URL
    puzzle["title"] = data["name"]
    puzzle["date"] = dt.strftime("%m/%d/%Y")
    # puzzle["annotation"] = f"Puzzle type: {data['crosswordType']}"
    puzzle["dimensions"] = dict(width=width, height=height)

    puzzle["puzzle"] = get_layout(width, height, data)
    puzzle["clues"] = get_clues(data)
    puzzle["solution"] = get_solution(width, height, data)

    filename = f"Guardian_{data['crosswordType']}_{data['number']}.ipuz"
    puzzle["annotation"] = filename

    if not filepath:
        filepath = "."

    if download:
        with open(f"{filepath}/{filename}", "w") as outfile:
            json.dump(puzzle, outfile)

    return puzzle
