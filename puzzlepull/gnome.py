import json
import logging
import pathlib
import sqlite3
import subprocess
import tempfile

import puzzlepull

sqlite3.register_converter('json', json.loads)
sqlite3.register_adapter(dict, json.dumps)


# Actually download all the puzzles.
with sqlite3.connect('cache.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
    conn.execute('PRAGMA journal_mode = wal')
    conn.execute('CREATE TABLE IF NOT EXISTS quick(id INTEGER PRIMARY KEY, puzzle JSON NOT NULL)')
    for i in range(100, 100000, 1000):
        if bool(conn.execute('SELECT 1 FROM quick WHERE id = :id', {'id': i}).fetchall()):
            logging.debug('Already downloaded %s, so skipping', i)
            continue
        conn.execute('INSERT INTO quick(id, puzzle) VALUES (:id, :puzzle)',
                     {'id': i,
                      'puzzle': puzzlepull.get_guardian_puzzle(
                          f'https://www.theguardian.com/crosswords/quick/{i}',
                          download=False)})
        conn.commit()


# Assemble them into "The Guardian - Quick - 2002" collections.
for year in range(1990, 2030):
    with sqlite3.connect('cache.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        conn.execute('PRAGMA journal_mode = wal')
        puzzles = conn.execute(
            "select puzzle from quick where json_extract(puzzle, '$.date') LIKE '__/__/' || :year",
            {'year': year}).fetchall()
    if not puzzles:
        logging.debug('No quick puzzles for year %s', year)
        continue
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        root = td / f'theguardian-quick-{year}'
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
             f'ShortName=Guardian Quick {year}',
             f'LongName=The Guardian’s Quick Crossword Puzzles for the year {year}',
             'Locale=en_US',
             'Picker=list',
             '[Picker List]',
             f'Header=Guardian Quick {year}',
             'ShowProgress=true',
             *(f"[Puzzle{i}]\nPuzzleName={path.relative_to(root)}"
               for path in puzzle_paths)]))
        external_manifest_path.write_text('\n'.join([
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gresources>',
            '<gresource prefix="/org/gnome/Crosswords/puzzle-set/">',
            f'<file>{internal_manifest_path}</file>',
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
