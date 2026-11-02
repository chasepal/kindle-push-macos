import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import kindle_push as kp
from markdown_support import prepare_markdown


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / '.obsidian').mkdir()
        (self.root / '附件').mkdir()
        self.patch = patch.object(kp, 'OUT', self.root / 'output')
        self.patch.start()
        self.note = self.root / '原文件名.md'

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def image(self, path):
        path.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6N1sAAAAASUVORK5CYII='))

    def test_metadata_tables_tasks_footnotes_images_and_styles(self):
        self.image(self.root / '附件/图 片.png')
        self.note.write_text('''---
title: 我的阅读文章
author: 示例作者
lang: zh-CN
---
# 开始

这是一段**粗体**、*斜体*和~~删除线~~。[[其他笔记|链接文字]]

> [!tip] 阅读提示
> 这段需要保留。

| 名称 | 内容 |
| --- | --- |
| 中文 | 长一点的内容 |

- [x] 完成
- [ ] 待办

![[图 片.png|300]]

引用脚注[^1]。

[^1]: 脚注正文。
''')
        output = kp.convert(self.note)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            xhtml = '\n'.join(archive.read(n).decode() for n in names if n.endswith('.xhtml'))
            opf = '\n'.join(archive.read(n).decode() for n in names if n.endswith('.opf'))
            css = '\n'.join(archive.read(n).decode() for n in names if n.endswith('.css'))
            self.assertIn('我的阅读文章', opf)
            self.assertIn('示例作者', opf)
            self.assertIn('<table', xhtml)
            self.assertIn('<strong>粗体</strong>', xhtml)
            self.assertIn('脚注正文', xhtml)
            self.assertIn('阅读提示', xhtml)
            self.assertNotIn('[!tip]', xhtml)
            self.assertIn('链接文字', xhtml)
            self.assertTrue(any(n.endswith('.png') for n in names))
            self.assertIn('pre-wrap', css)
            self.assertIn('max-width: 100%', css)
            self.assertIsNone(archive.testzip())

    def test_multi_backtick_code_is_preserved(self):
        text = '# 代码\n\n````md\n```\n[[代码链接]]\n> [!tip] 不要改\n```\n````\n\n``[[行内]] ` test``\n\n[[普通|显示]]\n'
        self.note.write_text(text)
        converted, _ = prepare_markdown(self.note)
        self.assertIn('[[代码链接]]', converted)
        self.assertIn('> [!tip] 不要改', converted)
        self.assertIn('``[[行内]] ` test``', converted)
        self.assertTrue(converted.endswith('显示\n'))

    def test_nested_note_resolves_own_images_without_touching_code(self):
        nested = self.root / '子目录'; nested.mkdir()
        self.image(nested / '图.png')
        (nested / '被嵌入.md').write_text('---\ntitle: 子标题\n---\n## 内文\n\n![图](图.png)\n\n```md\n> [!tip] 原样保留\n```\n')
        self.note.write_text('# 主文章\n\n![[子目录/被嵌入]]\n')
        output = kp.convert(self.note)
        with zipfile.ZipFile(output) as archive:
            html = '\n'.join(archive.read(n).decode() for n in archive.namelist() if n.endswith('.xhtml'))
            self.assertIn('内文', html)
            self.assertIn('[!tip]', html)
            self.assertTrue(any(n.endswith('.png') for n in archive.namelist()))

    def test_cycle_is_reported(self):
        self.note.write_text('![[原文件名]]')
        with self.assertRaisesRegex(ValueError, '循环'):
            kp.convert(self.note)

    def test_ambiguous_images_are_reported(self):
        for folder in ['one', 'two']:
            (self.root / folder).mkdir(); self.image(self.root / folder / 'same.png')
        self.note.write_text('![[same.png]]')
        with self.assertRaisesRegex(ValueError, '重名'):
            kp.convert(self.note)

    def test_missing_image_does_not_replace_successful_output(self):
        self.note.write_text('# 成功\n\n原来的内容。')
        output = kp.convert(self.note); original = output.read_bytes()
        self.note.write_text('# 错误\n\n![图](missing.png)')
        with self.assertRaisesRegex(ValueError, '转换需处理'):
            kp.convert(self.note)
        self.assertEqual(output.read_bytes(), original)

    def test_fake_epub_is_rejected(self):
        fake = self.root / 'fake.epub'; fake.write_text('not a zip')
        with self.assertRaisesRegex(ValueError, '有效'):
            kp.convert(fake)

    def test_mermaid_is_preserved_and_warned(self):
        self.note.write_text('```mermaid\ngraph LR\nA-->B\n```')
        content, warnings = prepare_markdown(self.note)
        self.assertIn('A-->B', content)
        self.assertTrue(warnings)


if __name__ == '__main__':
    unittest.main()
