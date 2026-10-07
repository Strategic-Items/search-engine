"""Paired bootstrap of every 43단계 arm against its baseline, per mode and metric.

An arm differs from the baseline by a handful of questions, so the 95% interval over resampled
questions shows whether any change is distinguishable from zero.
Run: .venv/bin/python scripts/law/bootstrap_embedding_fields.py
"""
import argparse
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paired_bootstrap import interval

METRICS = {
    'chunk_recall': lambda r: float(r['rank'] is not None),
    'mrr': lambda r: 1 / r['rank'] if r['rank'] else 0.0,
    'chunk_precision': lambda r: r['gold_precision'],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', type=Path, default=Path('data/generated/embedding-fields-2026-10-06'))
    parser.add_argument('--seed', type=int, default=44)
    args = parser.parse_args()
    arms = {p.stem: json.loads(p.read_text()) for p in (args.dir / 'arms').glob('*.json')}
    base = arms.pop('baseline')['outcomes']
    out = {}
    for name in sorted(arms):
        out[name] = {}
        for mode in ('dense', 'splade', 'hybrid'):
            before, after = base[mode]['results'], arms[name]['outcomes'][mode]['results']
            if [r['qid'] for r in before] != [r['qid'] for r in after]:
                raise ValueError('qid mismatch')
            out[name][mode] = {}
            for metric, fn in METRICS.items():
                deltas = [fn(b) - fn(a) for a, b in zip(before, after)]
                low, high = interval(deltas, random.Random(args.seed))
                mean = sum(deltas) / len(deltas)
                out[name][mode][metric] = {'delta': mean, 'low': low, 'high': high, 'excludes_zero': low > 0 or high < 0}
    (args.dir / 'bootstrap.json').write_text(json.dumps(out, indent=2) + '\n')
    for name, modes in out.items():
        cells = []
        for mode, ms in modes.items():
            cells.append(mode + ' ' + ' '.join(f"{k[:4]}{v['delta']:+.3f}[{v['low']:+.3f},{v['high']:+.3f}]{'*' if v['excludes_zero'] else ''}" for k, v in ms.items()))
        print(name, '|', ' | '.join(cells))
    print('arms with any interval excluding 0:', [n for n, m in out.items() if any(v['excludes_zero'] for ms in m.values() for v in ms.values())])


if __name__ == '__main__':
    main()
