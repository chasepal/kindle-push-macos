"""Obsidian conveniences, with fenced/inline code left intact."""
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

IMAGE_TYPES = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}
CALLOUTS = {'note': '笔记', 'tip': '提示', 'hint': '提示', 'info': '信息',
            'warning': '注意', 'caution': '注意', 'danger': '警告', 'important': '重要',
            'quote': '引用', 'example': '示例', 'question': '问题', 'success': '完成',
            'todo': '待办', 'abstract': '摘要', 'summary': '摘要', 'failure': '失败', 'bug': '问题'}


def vault_root(source):
    for parent in source.parents:
        if (parent / '.obsidian').is_dir():
            return parent
    return source.parent


def prose_segments(text):
    """Yield (is_code, text) without modifying fenced blocks or code spans."""
    prose = []
    code = []
    fence = None
    for line in text.splitlines(keepends=True):
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line.rstrip('\r\n'))
        if fence:
            code.append(line)
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                yield True, ''.join(code)
                code, fence = [], None
        elif match:
            if prose:
                yield False, ''.join(prose)
                prose = []
            code, fence = [line], match[1]
        else:
            prose.append(line)
    if code:
        yield True, ''.join(code)
    if prose:
        yield False, ''.join(prose)


def transform_prose(text, transform):
    output = []
    for is_code, part in prose_segments(text):
        if is_code:
            output.append(part)
            continue
        # Match equal-length backtick delimiters, including multi-backtick spans.
        cursor = 0
        for match in re.finditer(r'(?<!`)(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)', part):
            output.extend([transform(part[cursor:match.start()]), match[0]])
            cursor = match.end()
        output.append(transform(part[cursor:]))
    return ''.join(output)


def resolve_file(target, source, root, note=False):
    target = unquote(target)
    if note and not Path(target).suffix:
        target += '.md'
    candidates = [source.parent / target, root / target]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    # Obsidian permits unique basename references, even inside its attachments folder.
    found = [p for p in root.rglob(Path(target).name)
             if p.is_file() and not any(part.startswith('.') for part in p.relative_to(root).parts)]
    if len(found) == 1:
        return found[0].resolve()
    raise ValueError('附件/嵌入笔记不存在或有重名，请使用明确路径：' + target)


def prepare_markdown(source):
    source = source.resolve()
    root = vault_root(source)
    warnings = []

    def expand(current, stack):
        if current in stack:
            raise ValueError('发现循环嵌入笔记：' + current.name)
        if len(stack) >= 5:
            raise ValueError('嵌入笔记超过 5 层，请简化后再发送。')
        text = current.read_text(encoding='utf-8-sig')
        if stack:
            text = re.sub(r'\A---\s*\n[\s\S]*?\n(?:---|\.\.\.)\s*(?:\n|$)', '', text, count=1)

        def transform(part):
            part = re.sub(r'%%[\s\S]*?%%', '', part)
            def wikilink(match):
                embedded, body = match.groups()
                body = body.replace('\\|', '|')
                target, _, alias = body.partition('|')
                if not embedded:
                    return alias or target
                suffix = Path(target.split('#')[0]).suffix.lower()
                if suffix in IMAGE_TYPES:
                    img = resolve_file(target.split('#')[0], current, root)
                    return '![](' + quote(str(img), safe='/') + ')'
                if suffix in {'', '.md', '.markdown'}:
                    if '#' in target:
                        raise ValueError('暂不支持按标题/块嵌入，请改为嵌入整篇笔记：' + target)
                    note = resolve_file(target, current, root, note=True)
                    return '\n\n' + expand(note, stack + [current]) + '\n\n'
                raise ValueError('不支持的嵌入附件：' + target + '；请移除或转换为图片。')

            def callout(match):
                prefix, kind, title = match.groups()
                name = title.strip() or CALLOUTS.get(kind.lower(), kind)
                return prefix + '**' + name + '**'
            part = re.sub(r'^(\s*>\s*)\[!([A-Za-z-]+)\][+-]?\s*(.*)$', callout, part, flags=re.M)
            # Resolve ordinary relative inline images before inserting nested notes.
            def image_path(match):
                lead, raw, tail = match.groups()
                raw = raw.strip('<>')
                if urlsplit(raw).scheme or raw.startswith('#'):
                    return match[0]
                path = current.parent / unquote(raw)
                if path.is_file():
                    return lead + '<' + quote(str(path.resolve()), safe='/') + '>' + tail
                return match[0]  # Pandoc reports missing resources; conversion stops.
            part = re.sub(r'(!\[[^\]\n]*\]\()(<[^>\n]+>|[^\s)]+)(\s+"[^"\n]*"\s*\)|\))', image_path, part)
            return re.sub(r'(!?)\[\[([^\]\n]+)\]\]', wikilink, part)

        for is_code, part in prose_segments(text):
            if is_code and re.match(r'\s*[`~]{3,}\s*(mermaid|dataview|dataviewjs)\b', part):
                warnings.append('图表/动态查询保留为代码，未运行：' + current.name)
        return transform_prose(text, transform)

    return expand(source, []), list(dict.fromkeys(warnings))
