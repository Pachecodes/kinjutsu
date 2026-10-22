#!/usr/bin/env python
"""Build H3 prompts locally, without agents, tokens, media decoding or rendering."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prompting.renderer import PromptValidationError, render_prompt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='List template catalog JSON')
    parser.add_argument('--template', help='Template ID from --list')
    parser.add_argument('--input', type=Path, help='UTF-8 JSON form data file')
    parser.add_argument('--output', type=Path, help='UTF-8 prompt output; omit for stdout')
    args = parser.parse_args(argv)
    if args.list:
        print((ROOT / 'prompting/catalog.json').read_text(encoding='utf-8'))
        return 0
    if not args.template or args.input is None:
        parser.error('--template and --input are required unless using --list')
    try:
        data = json.loads(args.input.read_text(encoding='utf-8-sig'))
        result = render_prompt(args.template, data)
        if args.output:
            args.output.write_text(result, encoding='utf-8', newline='\n')
        else:
            sys.stdout.buffer.write(result.encode('utf-8'))
        return 0
    except (OSError, ValueError) as exc:
        print(f'Prompt error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
