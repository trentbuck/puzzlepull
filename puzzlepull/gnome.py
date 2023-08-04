import json
import logging
import pathlib
import sqlite3
import subprocess
import tempfile

import puzzlepull

sqlite3.register_converter('json', json.loads)
sqlite3.register_adapter(dict, json.dumps)

puzzle_fetchlist = {
    # NOTE: skiping the ~1 quick crossword from 1944.
    # https://www.theguardian.com/crosswords/quick/135
    # https://www.theguardian.com/crosswords/series/quick?page=376
    'Quick': range(9093, 1 + 16612),
    # NOTE: skipping the ~10 cryptic crosswords from 1932-1970:
    #       https://www.theguardian.com/crosswords/series/cryptic?page=314
    'Cryptic': range(21620, 1 + 29139),  # handful of older ones
    'Prize': range(12579, 1 + 29135),
    'Weekend': range(321, 1 + 655),
    'Quiptic': range(1, 1 + 1237),
    'Speedy': range(410, 1 + 1451),
    'Everyman': range(2965, 1 + 4006),
    # URL isn't determined entirely from ID number, so can't be done.
    # 'Azed': XXX,
}

# Actually download all the puzzles.
with sqlite3.connect('cache.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
    conn.execute('PRAGMA journal_mode = wal')
    conn.execute('CREATE TABLE IF NOT EXISTS puzzles(id INTEGER, kind TEXT, puzzle JSON NOT NULL, PRIMARY KEY (id, kind))')
    for kind, iterator in puzzle_fetchlist.items():
        for i in iterator:
            if bool(conn.execute('SELECT 1 FROM puzzles WHERE id = :id AND kind = :kind',
                                 {'id': i, 'kind': kind}).fetchall()):
                logging.debug('Already downloaded %s, so skipping', i)
                continue
            url = f'https://www.theguardian.com/crosswords/{kind.lower()}/{i}'
            try:
                conn.execute('INSERT INTO puzzles(id, kind, puzzle) VALUES (:id, :kind, :puzzle)',
                             {'id': i,
                              'kind': kind,
                              'puzzle': puzzlepull.get_guardian_puzzle(url, download=False)})
                conn.commit()
            except:
                logging.warning('Conversion problem for %s, skipping it', url)


# Assemble them into "The Guardian - Quick - 2002" collections.
for kind in puzzle_fetchlist:
    for year in range(1990, 2030):
        with sqlite3.connect('cache.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            conn.execute('PRAGMA journal_mode = wal')
            puzzles = conn.execute(
                "select puzzle from puzzles where kind LIKE :kind and json_extract(puzzle, '$.date') LIKE '__/__/' || :year",
                {'kind': kind,
                 'year': year}).fetchall()
        if not puzzles:
            logging.debug('No %s puzzles for year %s', kind, year)
            continue
        with tempfile.TemporaryDirectory() as td:
            td = pathlib.Path(td)
            root = td / f'theguardian-{kind.lower()}-{year}'
            root.mkdir()
            for puzzle_json, in puzzles:
                (root / puzzle_json['annotation']).write_text(json.dumps(puzzle_json))
            internal_manifest_path = root / 'puzzle.config'
            external_manifest_path = root.with_suffix('.gresource.xml')
            puzzle_paths = sorted(
                root / puzzle_json['annotation']
                for puzzle_json, in puzzles)
            internal_manifest_path.write_text('\n'.join(
                ['[Puzzle Set]',
                 f'ID={root.name}',
                 f'ShortName=Guardian {kind} {year}',
                 f'LongName=The Guardian’s {kind} Crossword Puzzles for the year {year}',
                 'Locale=en_US',
                 'Picker=list',
                 '[Picker List]',
                 f'Header=Guardian {kind} {year}',
                 'ShowProgress=true',
                 *(f"[Puzzle{i+1}]\nPuzzleName={path.relative_to(root)}"
                   for i, path in enumerate(puzzle_paths))]))
            external_manifest_path.write_text('\n'.join([
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<gresources>',
                '<gresource prefix="/org/gnome/Crosswords/puzzle-set/">',
                f'<file>{internal_manifest_path.relative_to(td)}</file>',
                *(f"<file>{path.relative_to(td)}</file>"
                  for path in puzzle_paths),
                '</gresource>',
                '</gresources>']))
            final_path = pathlib.Path.cwd() / root.with_suffix('.gresource').name
            subprocess.check_call(
                ['glib-compile-resources',
                 '--target', final_path,
                 external_manifest_path.relative_to(td)],
                cwd=td)
