"""Baseline berbasis regex, sebagai pembanding parser.

Sengaja naif: tidak paham komentar, string, maupun alias. Jangan diperbaiki;
tugasnya adalah menjadi pembanding dalam evaluasi (lihat README).
"""
import re

_NAME = r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)"
_PATTERNS = [
    (re.compile(r"\bINSERT\s+INTO\s+" + _NAME, re.I), "C"),
    (re.compile(r"\bFROM\s+" + _NAME, re.I), "R"),
    (re.compile(r"\bJOIN\s+" + _NAME, re.I), "R"),
    (re.compile(r"\bUPDATE\s+" + _NAME, re.I), "U"),
    (re.compile(r"\bDELETE\s+FROM\s+" + _NAME, re.I), "D"),
]
_START = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.I)


def extract(text: str) -> list[tuple[int, str, str]]:
    """Mengembalikan daftar (baris_statement, tabel, operasi)."""
    triples = set()
    offset = 0
    for chunk in text.split(";"):
        start = _START.search(chunk)
        if start:
            line = text.count("\n", 0, offset + start.start()) + 1
            for pattern, op in _PATTERNS:
                for m in pattern.finditer(chunk):
                    triples.add((line, m.group(1).lower(), op))
        offset += len(chunk) + 1
    return sorted(triples)
