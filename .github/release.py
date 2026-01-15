"""
Release script for parsing commit messages and generating release notes.

Expected commit message format:
    v{version}: {description}

Example:
    v0.0.2: Add new feature; Fix bug; Improve performance

The description can use semicolons to separate multiple points,
which will be formatted as a numbered list in the release notes.
"""

import os
import sys
import re


def add_output(k, v):
    """Add output to GitHub Actions environment."""
    cmd = f'echo "{k}={v}" >> $GITHUB_OUTPUT'
    print(cmd, os.system(cmd))


def parse_body(body):
    """
    Parse release body from commit message.
    
    If the body contains semicolons, split it into numbered points.
    Otherwise, return the body as-is.
    """
    if ';' not in body:
        return body

    parts = body.split(";")
    points = []
    for i, e in enumerate(parts):
        e: str = e.strip()
        if e == '':
            continue
        points.append(f'{i + 1}. {e}')

    return '\n'.join(points)


def get_tag_and_body():
    """Extract tag and body from commit message."""
    msg = sys.argv[1]
    print(f'msg: {msg}')
    p = re.compile('(.*?): ?(.*)')
    match = p.search(msg)
    assert match is not None, f'commit message format is wrong: {msg}'
    tag, body = match[1], match[2]
    return body, tag


def main():
    body, tag = get_tag_and_body()

    add_output('tag', tag)

    with open('release_body.txt', 'w', encoding='utf-8') as f:
        f.write(parse_body(body))


if __name__ == '__main__':
    main()
