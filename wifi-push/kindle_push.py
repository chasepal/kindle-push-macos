#!/opt/homebrew/bin/python3
"""Local Markdown → EPUB → key-authenticated Kindle transfer."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from markdown_support import prepare_markdown, vault_root
from urllib.parse import quote, unquote

DATA = Path.home() / 'Library/Application Support/KindlePush'
CONFIG = DATA / 'config.json'
OUT = Path.home() / 'Documents/Kindle推送/已转换'
PANDOC = next((p for p in ['/opt/homebrew/bin/pandoc', '/usr/local/bin/pandoc', shutil.which('pandoc')] if p and Path(p).is_file()), '/opt/homebrew/bin/pandoc')
CSS = Path(__file__).with_name('ebook.css')

def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def validate_epub(path):
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.read('mimetype').strip() != b'application/epub+zip' or 'META-INF/container.xml' not in archive.namelist() or archive.testzip():
                raise ValueError('EPUB 结构或内容校验失败：' + path.name)
    except (zipfile.BadZipFile, KeyError) as error:
        raise ValueError('不是有效的 EPUB 文件：' + path.name) from error


def convert(source):
    source = source.expanduser().resolve(strict=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == '.epub':
        validate_epub(source)
        content = source.read_bytes()
    elif source.suffix.lower() in {'.md', '.markdown'}:
        markdown, warnings = prepare_markdown(source)
        for warning in warnings:
            print('提示：' + warning)
        with tempfile.TemporaryDirectory(prefix='kindle-push-') as folder:
            draft = Path(folder) / 'article.md'
            epub = Path(folder) / 'article.epub'
            log = Path(folder) / 'pandoc.json'
            draft.write_text(markdown, encoding='utf-8')
            reader = 'markdown+task_lists+pipe_tables+strikeout+autolink_bare_uris'
            parsed = run([PANDOC, str(draft), '--from=' + reader, '--to=json'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            meta = json.loads(parsed.stdout)['meta']
            metadata = []
            if 'title' not in meta: metadata.append('--metadata=title:' + source.stem)
            if 'lang' not in meta: metadata.append('--metadata=lang:zh-CN')
            run([PANDOC, str(draft), '--from=' + reader, '--to=epub3',
                 '--resource-path=' + str(source.parent) + os.pathsep + str(vault_root(source)),
                 *metadata, '--css=' + str(CSS), '--toc', '--toc-depth=3', '--syntax-highlighting=none',
                 '--standalone', '--log=' + str(log), '--output=' + str(epub)],
                cwd=source.parent, stderr=subprocess.PIPE, timeout=120)
            messages = json.loads(log.read_text())
            problems = [entry for entry in messages if entry.get('verbosity') in {'WARNING', 'ERROR'}
                        and entry.get('type') not in {'CouldNotLoadTranslations', 'NoTranslation'}]
            if problems:
                raise ValueError('转换需处理：' + '; '.join(e.get('pretty', str(e)) for e in problems))
            validate_epub(epub)
            content = epub.read_bytes()
    else:
        raise ValueError('请选择 .md 或 .epub 文件：' + source.name)
    # Stable per-source name: repeated sends replace that article, without clutter.
    title = re.sub(r'[\x00-\x1f/\\:]', '-', source.stem).strip('. ')[:60] or '文章'
    identity = hashlib.sha256(str(source).encode()).hexdigest()[:8]
    output = OUT / f'{title}-{identity}.epub'
    if len(content) > 100 * 1024 * 1024:
        raise ValueError('文章超过 100 MB，请压缩图片后再发送。')
    with tempfile.NamedTemporaryFile(dir=OUT, suffix='.epub', delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output

def get_config(host=None):
    config = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    if host:
        address = ipaddress.ip_address(host.strip())
        if address.version != 4 or not address.is_private or address.is_loopback:
            raise ValueError('请输入 Kindle 在同一 Wi-Fi 下的局域网 IPv4 地址。')
        config['host'] = str(address)
        DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
        CONFIG.write_text(json.dumps(config, indent=2) + '\n')
    if not config.get('host'):
        raise ValueError('还没设置 Kindle IP。首次运行时输入 KOReader 网络信息里的 IP。')
    return config

def ssh(config, operation, content=b''):
    key = DATA / 'id_ed25519'
    if not key.exists():
        raise ValueError('USB 首次配置尚未完成。')
    result = run(['/usr/bin/ssh', '-F', '/dev/null', '-T', '-p', '2222', '-i', str(key),
        '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'HostKeyAlias=kindle-push',
        '-o', 'HostKeyAlgorithms=ssh-ed25519',
        '-o', 'UserKnownHostsFile="' + str(DATA / 'known_hosts') + '"',
        '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=10',
        '-o', 'ServerAliveCountMax=3', 'root@' + config['host'], operation],
        input=content, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    return result.stdout

def send(epub, config):
    content = epub.read_bytes()
    if ssh(config, 'ping').strip() != b'kindle-push-v1':
        raise ValueError('接收端未配置好。')
    filename = epub.name.encode('utf-8') + b'\n'
    response = ssh(config, 'put', filename + str(len(content)).encode() + b'\n' + content)
    if response.strip() != b'OK':
        raise ValueError('Kindle 没有确认接收。')
    received = ssh(config, 'get', filename)
    if hashlib.sha256(received).digest() != hashlib.sha256(content).digest():
        raise ValueError('传输校验未通过，请重试。')
    print('已发送并校验：' + epub.name)
    print('Kindle → 文件浏览器 → documents → 我的文章')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='*', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--convert-only', action='store_true')
    parser.add_argument('--interactive', action='store_true')
    args = parser.parse_args()
    if args.interactive:
        print('Kindle 推送：两台设备连接同一 Wi-Fi，Kindle 打开 KOReader。\n')
        if not args.files:
            raw = input('把文章 .md 文件拖进这个窗口，然后按回车：\n').strip()
            args.files = [Path(p) for p in shlex.split(raw)]
        previous = json.loads(CONFIG.read_text()).get('host', '') if CONFIG.exists() else ''
        args.host = input('Kindle IP' + (f'（回车沿用 {previous}）' if previous else '') + '：').strip() or previous
    if not args.files:
        parser.error('请指定至少一篇 .md 或 .epub 文件。')
    config = None if args.convert_only else get_config(args.host)
    for source in args.files:
        epub = convert(source)
        print('已转换：' + str(epub))
        if config:
            send(epub, config)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('\n未完成：' + str(error), file=sys.stderr)
        print('如连接失败：确认 Kindle 打开 KOReader、Wi-Fi 已开启，IP 地址正确。', file=sys.stderr)
        sys.exit(1)
