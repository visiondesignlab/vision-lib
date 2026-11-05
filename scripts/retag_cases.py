"""Preview or apply tag curation to the current local store without changing publishing state."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import store
from case_tags import suggested_tags


def run(apply=False):
    with store.locked():
        cases = store.load_cases()
        before = json.dumps(cases, ensure_ascii=False)
        old, new = Counter(), Counter()
        changed = 0
        for case in cases:
            old.update(case.get('tags') or [])
            tags = suggested_tags(case)
            modified = tags != case.get('tags', [])
            revision = case.get('revision')
            if revision:
                revised = suggested_tags({**case, **revision})
                if revised != revision.get('tags', tags):
                    revision['tags'] = revised
                    modified = True
            new.update(tags)
            if modified:
                case['tags'] = tags
                case['_version'] = case.get('_version', 0) + 1
                changed += 1
        backup = None
        if apply and changed:
            folder = Path(store.DATA) / 'backups'
            folder.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', prefix='before-retag-', suffix='.json',
                                             dir=folder, delete=False, encoding='utf-8') as f:
                f.write(before)
                backup = f.name
            store.save_cases(cases)
        return dict(records=len(cases), changed=changed, old_tags=len(old), new_tags=len(new), backup=backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    print(json.dumps(run(parser.parse_args().apply), ensure_ascii=False))
