#!/usr/bin/env python3
"""Backfill paragraph fields for existing entries.

Historical full paragraphs were not stored previously. For backward compatibility,
this script sets:
- lead_paragraph = lead_sentence
- paragraph_hash = sentence_hash
- paragraph_length = sentence_length

This ensures the site can render paragraphs immediately and the paragraph-based
change detector behaves identically for the historical dataset until new entries
are collected.

No dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path

ENTRIES_DIR = Path('_entries')


def set_key(txt: str, key: str, value_yaml: str) -> str:
    if re.search(rf'^{re.escape(key)}:\s*.*$', txt, flags=re.M):
        return re.sub(rf'^{re.escape(key)}:\s*.*$', f'{key}: {value_yaml}', txt, flags=re.M)
    if not txt.startswith('---'):
        return txt
    parts = txt.split('---', 2)
    if len(parts) < 3:
        return txt
    head = '---\n' + parts[1].lstrip('\n')
    tail = '---' + parts[2]
    if not head.endswith('\n'):
        head += '\n'
    head += f'{key}: {value_yaml}\n'
    return head + tail


def main():
    changed = 0
    for ep in ENTRIES_DIR.glob('*.md'):
        txt = ep.read_text(encoding='utf-8')
        # pull values
        fm_block = txt.split('---', 2)[1]
        def get(k):
            m = re.search(rf'^{re.escape(k)}:\s*(.*)$', fm_block, flags=re.M)
            if not m:
                return None
            v = m.group(1).strip()
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            return v

        lead_sentence = get('lead_sentence') or ''
        sentence_hash = get('sentence_hash') or ''
        sentence_length = get('sentence_length') or ''

        txt2 = txt
        if lead_sentence:
            txt2 = set_key(txt2, 'lead_paragraph', '"' + lead_sentence.replace('\\','\\\\').replace('"','\\"') + '"')
        if sentence_hash:
            txt2 = set_key(txt2, 'paragraph_hash', '"' + sentence_hash + '"')
        if sentence_length:
            txt2 = set_key(txt2, 'paragraph_length', str(sentence_length))

        if txt2 != txt:
            ep.write_text(txt2, encoding='utf-8')
            changed += 1

    print('backfilled', changed)


if __name__ == '__main__':
    main()
