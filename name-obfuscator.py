"""
sas_name_replacer.py

Obfuscate and restore identifiers that contain underscores in any plain-text file.
Originally designed for SAS dataset/variable names; restore works on any file type
(SAS, Python, SQL, CSV, …).

Usage:
    Obfuscate:  python sas_name_replacer.py obfuscate input.sas  output.sas  key.csv [--prefix PREFIX]
    Restore:    python sas_name_replacer.py restore  input.txt   output.txt  key.csv

Options:
    --prefix PREFIX   Use PREFIX1, PREFIX2, … as replacements instead of random strings.
                      PREFIX must not contain underscores.

Rules:
    - Obfuscate targets words matching [a-zA-Z][a-zA-Z0-9_]*_[a-zA-Z0-9_]*
      (identifiers that start with a letter and contain at least one underscore)
    - Replacements contain no underscores, so they are never re-matched or double-replaced
    - Restore finds each replacement even when it is embedded inside a larger identifier
      (e.g. sum_v6 → sum_blood_pressure); works on any plain-text file
    - The CSV key maps original -> replacement and is used to reverse the process
"""

import argparse
import re
import csv
import random
import string
import sys

# Pattern: word starting with a letter, containing at least one underscore,
# made up of letters/digits/underscores.
PATTERN = re.compile(r'\b([a-zA-Z][a-zA-Z0-9_]*_[a-zA-Z0-9_]*)\b')

RANDOM_LENGTH = 10  # length of generated replacement names


def random_name(used: set) -> str:
    """Generate a unique random lowercase identifier with no underscores."""
    while True:
        name = random.choice(string.ascii_lowercase) + \
               ''.join(random.choices(string.ascii_lowercase + string.digits, k=RANDOM_LENGTH - 1))
        if name not in used:
            return name


def obfuscate(input_file: str, output_file: str, key_file: str, prefix: str | None = None) -> None:
    if prefix is not None and '_' in prefix:
        sys.exit("Error: --prefix may not contain underscores (replacements would re-match the pattern).")

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Collect all unique matching names, preserving first-seen order
    seen_order = []
    seen_set = set()
    for m in PATTERN.finditer(content):
        word = m.group(1)
        if word not in seen_set:
            seen_set.add(word)
            seen_order.append(word)

    # Build original -> replacement mapping
    mapping: dict[str, str] = {}
    if prefix is not None:
        for i, word in enumerate(seen_order, start=1):
            mapping[word] = f"{prefix}{i}"
    else:
        used_replacements: set = set()
        for word in seen_order:
            mapping[word] = random_name(used_replacements)
            used_replacements.add(mapping[word])

    # Replace all occurrences in content
    result = PATTERN.sub(lambda m: mapping[m.group(1)], content)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)

    with open(key_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['original', 'replacement'])
        for orig in seen_order:
            writer.writerow([orig, mapping[orig]])

    print(f"Obfuscated {len(mapping)} unique name(s).")
    print(f"  Output:  {output_file}")
    print(f"  Key CSV: {key_file}")


def restore(input_file: str, output_file: str, key_file: str) -> None:
    # Load key: replacement -> original
    reverse: dict[str, str] = {}
    with open(key_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            reverse[row['replacement']] = row['original']

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Build a single pattern that matches any replacement name as a whole word.
    # Sort longest-first to avoid partial-match issues if one name is a prefix of another.
    escaped = sorted(
        (re.escape(r) for r in reverse),
        key=len,
        reverse=True
    )
    if not escaped:
        print("Key file is empty — nothing to restore.")
        return

    # Use lookahead/lookbehind instead of \b so replacements embedded after '_'
    # (e.g. sum_v6) are matched. Underscore is \w so \b wouldn't fire there.
    restore_pattern = re.compile(r'(?<![a-zA-Z0-9])(' + '|'.join(escaped) + r')(?![a-zA-Z0-9])')
    result = restore_pattern.sub(lambda m: reverse[m.group(1)], content)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"Restored {len(reverse)} unique name(s).")
    print(f"  Output: {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Obfuscate and restore SAS dataset/variable names that contain underscores.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    obf = subparsers.add_parser('obfuscate', help='Replace underscore-containing identifiers with obfuscated names.')
    obf.add_argument('input_file', help='Source file to obfuscate (any plain-text format).')
    obf.add_argument('output_file', help='Destination file for obfuscated content.')
    obf.add_argument('key_file', help='CSV file to write the original→replacement mapping.')
    obf.add_argument('--prefix', default=None,
                     help='Use PREFIX1, PREFIX2, … as replacements instead of random strings. Must not contain underscores.')

    res = subparsers.add_parser('restore', help='Reverse a previous obfuscation using the key CSV. Works on any plain-text file.')
    res.add_argument('input_file', help='Obfuscated file to restore (any plain-text format: .sas, .py, .sql, …).')
    res.add_argument('output_file', help='Destination file for restored content.')
    res.add_argument('key_file', help='CSV mapping file produced by obfuscate.')

    args = parser.parse_args()

    if args.command == 'obfuscate':
        obfuscate(args.input_file, args.output_file, args.key_file, prefix=args.prefix)
    else:
        restore(args.input_file, args.output_file, args.key_file)


if __name__ == '__main__':
    main()
