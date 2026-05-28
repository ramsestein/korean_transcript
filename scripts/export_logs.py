#!/usr/bin/env python3
"""
Exportador de logs de /app/logs.

Soporta:
- modo local: empaquetar un directorio local (`--path`)
- modo docker: copiar desde un contenedor (`--docker --container --container-path`)
- opcional: anonimizar campos comunes en JSON
- opcional: excluir archivos de audio

Ejemplo de uso (host):
  python scripts/export_logs.py --path ./data --output ./exports/logs.zip --anonymize

Ejemplo de uso (docker):
  docker compose exec backend python /app/scripts/export_logs.py --path /app/logs --output /app/exports/logs.zip --anonymize

"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


AUDIO_EXTS = {'.wav', '.mp3', '.flac', '.m4a', '.ogg', '.webm'}
JSON_KEYS_TO_ANON = {'session_id', 'user_id', 'user', 'email', 'name'}


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def anonymize_json_file(src_path: Path, dst_path: Path):
    try:
        with src_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        # if cannot parse, copy as-is
        shutil.copy2(src_path, dst_path)
        return

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if k in JSON_KEYS_TO_ANON and isinstance(v, str):
                    obj[k] = sha256_hex(v)[:16]
                else:
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)

    with dst_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def gather_local_path(src_path: str) -> Path:
    p = Path(src_path)
    if not p.exists():
        raise FileNotFoundError(f"Path not found: {src_path}")
    return p


def gather_from_docker(container: str, container_path: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix='logs_copy_'))
    dest = tmp / 'logs'
    dest.mkdir()
    # use docker cp
    src_spec = f"{container}:{container_path}"
    try:
        subprocess.check_call(['docker', 'cp', src_spec, str(dest)])
    except subprocess.CalledProcessError as e:
        shutil.rmtree(tmp)
        raise RuntimeError(f"docker cp failed: {e}")
    return dest


def create_zip(src_dir: Path, output: Path, anonymize: bool = False, remove_audio: bool = False):
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src_dir):
            root_path = Path(root)
            for fname in files:
                fpath = root_path / fname
                rel = fpath.relative_to(src_dir)
                if remove_audio and fpath.suffix.lower() in AUDIO_EXTS:
                    continue

                if anonymize and fpath.suffix.lower() == '.json':
                    # create temp anonymized copy
                    with tempfile.NamedTemporaryFile('w+b', delete=False) as tf:
                        tmpf = Path(tf.name)
                    try:
                        anonymize_json_file(fpath, tmpf)
                        z.write(tmpf, arcname=str(rel))
                    finally:
                        try:
                            tmpf.unlink()
                        except Exception:
                            pass
                else:
                    z.write(fpath, arcname=str(rel))


def main():
    parser = argparse.ArgumentParser(description='Export and optionally anonymize logs')
    parser.add_argument('--path', help='Local path to logs directory (if running inside container or host)',)
    parser.add_argument('--docker', action='store_true', help='Copy logs from a running docker container')
    parser.add_argument('--container', help='Docker container name or id (required with --docker)')
    parser.add_argument('--container-path', default='/app/logs', help='Path inside container to copy (default /app/logs)')
    parser.add_argument('--output', help='Output zip file path', default=None)
    parser.add_argument('--anonymize', action='store_true', help='Anonymize common PII fields in JSON files')
    parser.add_argument('--remove-audio', action='store_true', help='Exclude audio files from export')
    args = parser.parse_args()

    tmpdir = None
    try:
        if args.docker:
            if not args.container:
                parser.error('--container is required when --docker is set')
            src = gather_from_docker(args.container, args.container_path)
            tmpdir = src.parent
        else:
            if not args.path:
                parser.error('--path is required when not using --docker')
            src = gather_local_path(args.path)

        if not args.output:
            ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            out = Path('exports') / f'logs_{ts}.zip'
        else:
            out = Path(args.output)

        print(f"Creating archive {out} from {src} (anonymize={args.anonymize}, remove_audio={args.remove_audio})")
        create_zip(src, out, anonymize=args.anonymize, remove_audio=args.remove_audio)
        print(f"Done: {out}")
    finally:
        if tmpdir and tmpdir.exists():
            # only remove temp copy if it looks like ours
            try:
                shutil.rmtree(tmpdir)
            except Exception:
                pass


if __name__ == '__main__':
    main()
