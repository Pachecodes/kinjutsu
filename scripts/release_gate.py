"""Offline release privacy/inventory gate. Run after all sibling merges.
Default validates only; --write-inventory is an explicit final integration action.
Never deletes anything. No runtime service/model installation is performed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_DIRS={'.venv','venv','node_modules','__pycache__','.pytest_cache','.mypy_cache','uploads','outputs','thumbs'}
TEXT={'.py','.ts','.tsx','.js','.json','.md','.txt','.html','.css','.ps1','.vbs','.yaml','.yml'}

def check(root,terms=(),tracked=None):
    failures=[];files=[]
    candidates=(root/p for p in tracked) if tracked is not None else root.rglob('*')
    for p in candidates:
        if not p.resolve().is_relative_to(root.resolve()):
            failures.append('unsafe payload path');continue
        if '.git' in p.relative_to(root).parts:continue
        if not p.is_file():
            if tracked is not None:failures.append(p.relative_to(root).as_posix()+': tracked file missing')
            continue
        rel=p.relative_to(root).as_posix()
        if p.is_symlink():failures.append(rel+': symlink not transferable')
        if any(x in FORBIDDEN_DIRS for x in p.relative_to(root).parts):failures.append(rel+': runtime/cache directory')
        if p.name=='.env' or p.suffix in ('.sqlite','.sqlite3','.db','.mp4','.mov','.jpg','.jpeg','.webp','.pyc'):
            failures.append(rel+': private/runtime media or database')
        if rel.startswith(('runtime/logs/','runtime/state/','runtime/studio-data/','runtime/cache/','runtime/tools/')):
            failures.append(rel+': local installed state')
        if p.suffix in TEXT:
            text=p.read_text(encoding='utf-8-sig',errors='replace')
            for term in terms:
                if term.casefold() in text.casefold():failures.append(rel+': forbidden term '+term)
            if re.search(r'[A-Za-z]:[/\\]Users[/\\][A-Za-z0-9_.-]+[/\\]',text):failures.append(rel+': personal host path')
            if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:hf_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,})\b',text):failures.append(rel+': possible secret')
        if p.name!='SHA256SUMS.txt':files.append(p)
    return sorted(set(failures)),sorted(files)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--forbid-term',action='append',default=[])
    parser.add_argument('--write-inventory',action='store_true');parser.add_argument('--verify-inventory',action='store_true')
    parser.add_argument('--git-tracked',action='store_true',help='Inventory only staged/tracked source; exclude private gitignored local runtime')
    args=parser.parse_args();root=args.root.resolve()
    tracked=None
    if args.git_tracked:
        raw=subprocess.check_output(['git','-C',str(root),'ls-files','-z'])
        tracked=[name.decode('utf-8') for name in raw.split(b'\0') if name]
        if not tracked:raise ValueError('No tracked source files; stage source before creating inventory')
    failures,files=check(root,args.forbid_term,tracked)
    if failures:print(json.dumps({'privacy_failures':failures},indent=2));raise SystemExit(1)
    if args.write_inventory:
        rows=[]
        for p in files:
            with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            rows.append(digest+'  '+p.relative_to(root).as_posix())
        (root/'SHA256SUMS.txt').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    if args.verify_inventory:
        listed=set()
        for line in (root/'SHA256SUMS.txt').read_text().splitlines():
            digest,rel=line.split('  ',1);target=(root/rel).resolve()
            if not target.is_relative_to(root) or rel in listed:raise ValueError('unsafe/duplicate inventory target')
            listed.add(rel)
            with target.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
            if actual!=digest:raise ValueError('inventory mismatch: '+rel)
        if listed!={p.relative_to(root).as_posix() for p in files}:raise ValueError('inventory is incomplete or contains stale entries')
    print(json.dumps({'privacy':'passed','payload_files':len(files),'inventory_written':args.write_inventory,'inventory_verified':args.verify_inventory}))

if __name__=='__main__':main()
