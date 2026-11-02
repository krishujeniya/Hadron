"""Validate Hadron's source layout, moved paths, and frontend module references."""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'frontend/src'


def main() -> int:
    errors = []
    manifest = json.loads((ROOT / 'docs/verification/structure-moves-2026-11-02.json').read_text())
    for move in manifest['moves']:
        if (ROOT / move['from']).exists():
            errors.append(f"Old path still exists: {move['from']}")
        if not (ROOT / move['to']).is_file():
            errors.append(f"Missing moved file: {move['to']}")
    for path in [*SOURCE.rglob('*.ts'), *SOURCE.rglob('*.tsx')]:
        text = path.read_text()
        specs = re.findall(r'''(?:from\s*|import\s*\()\s*["'](@/[^"']+)["']''', text)
        for spec in specs:
            module = SOURCE / spec[2:]
            if not any(candidate.is_file() for candidate in [module, module.with_suffix('.ts'), module.with_suffix('.tsx'), module / 'index.ts', module / 'index.tsx']):
                errors.append(f'{path.relative_to(ROOT)}: unresolved {spec}')
            if path.is_relative_to(SOURCE / 'components/ui') or path.is_relative_to(SOURCE / 'components/brand'):
                if spec.startswith('@/features/'):
                    errors.append(f'{path.relative_to(ROOT)}: shared presentation imports product feature {spec}')
    if list((ROOT / 'tests').glob('test_*.py')):
        errors.append('Python tests must live in a named test domain, not the tests root')
    if list((SOURCE / 'components').glob('*.tsx')):
        errors.append('Shared components must belong to brand, layout, or ui')
    if errors:
        print('\n'.join(errors))
        print('VERDICT: FAIL')
        return 1
    print(f"Validated {len(manifest['moves'])} moves, frontend imports and shared component boundaries.")
    print('VERDICT: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
