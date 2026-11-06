"""Membandingkan parser dan baseline regex terhadap ground truth.

    python evaluate.py                       # memakai data/ground_truth.csv
    python evaluate.py --truth path/lain.csv

Satuan yang dibandingkan adalah triple (file, baris, tabel, operasi).
Hanya file yang ada di ground truth yang dievaluasi.
"""
import argparse
import csv
from pathlib import Path

from baseline.regex_extractor import extract
from crud.pipeline import analyze_source

ROOT = Path(__file__).resolve().parent


def load_truth(path: Path) -> set:
    with path.open(encoding="utf-8") as fh:
        return {(r["file"], int(r["baris"]), r["tabel"], r["operasi"]) for r in csv.DictReader(fh)}


def parser_triples(name: str, text: str) -> set:
    res = analyze_source(text)
    return {(name, st.line, t, op) for st in res.statements for t, ops in st.tables.items() for op in ops}


def regex_triples(name: str, text: str) -> set:
    return {(name, line, t, op) for line, t, op in extract(text)}


def score(pred: set, truth: set) -> tuple[float, float, float]:
    tp = len(pred & truth)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", type=Path, default=ROOT / "data" / "ground_truth.csv")
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "sample")
    args = ap.parse_args()

    truth = load_truth(args.truth)
    labeled = sorted({t[0] for t in truth})
    unlabeled = sorted(p.name for p in args.data.glob("*.sql") if p.name not in labeled)
    if unlabeled:
        print("Belum berlabel (tidak dievaluasi):", ", ".join(unlabeled))

    pred_parser, pred_regex = set(), set()
    for name in labeled:
        text = (args.data / name).read_text(encoding="utf-8")
        pred_parser |= parser_triples(name, text)
        pred_regex |= regex_triples(name, text)

    print(f"\nDievaluasi: {', '.join(labeled)} ({len(truth)} triple)\n")
    print(f"{'Metode':<8} {'Precision':>9} {'Recall':>7} {'F1':>6}")
    for label, pred in (("parser", pred_parser), ("regex", pred_regex)):
        p, r, f = score(pred, truth)
        print(f"{label:<8} {p:>9.2f} {r:>7.2f} {f:>6.2f}")

    for label, pred in (("parser", pred_parser), ("regex", pred_regex)):
        fp, fn = sorted(pred - truth), sorted(truth - pred)
        if fp or fn:
            print(f"\n[{label}]")
            for t in fp:
                print("  salah ditemukan (FP):", t)
            for t in fn:
                print("  terlewat (FN):      ", t)


if __name__ == "__main__":
    main()
