"""Every published page carries complete link-preview tags for the shared card image."""
from html.parser import HTMLParser
from pathlib import Path
import struct
import unittest

SRC = Path(__file__).resolve().parents[2] / 'build-guide/src'
SITE = 'https://demartinistudios.github.io/blooglyblob/'
PAGES = {'index.html': '', 'references.html': 'references.html', 'repeat-build.html': 'repeat-build.html'}
REQUIRED = ('og:type', 'og:site_name', 'og:title', 'og:description', 'og:url', 'og:image',
            'og:image:width', 'og:image:height', 'og:image:alt', 'twitter:card', 'twitter:image',
            'twitter:image:alt', 'description')


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.canonical = {}, None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and 'content' in attrs:
            key = attrs.get('property') or attrs.get('name')
            if key in self.tags:
                raise AssertionError(f'Duplicate meta tag: {key}')
            self.tags[key] = attrs['content']
        elif tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical = attrs.get('href')


def head(name):
    parser = Head()
    parser.feed((SRC / name).read_text())
    return parser


class SocialCardTests(unittest.TestCase):
    def test_image_is_a_1200_by_630_png(self):
        data = (SRC / 'social-card.png').read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', data[16:24]), (1200, 630))

    def test_pages_share_complete_absolute_tags(self):
        for name, path in PAGES.items():
            with self.subTest(page=name):
                page = head(name)
                self.assertFalse([key for key in REQUIRED if not page.tags.get(key)])
                self.assertEqual(page.tags['og:url'], SITE + path)
                self.assertEqual(page.canonical, SITE + path)
                self.assertEqual(page.tags['og:image'], SITE + 'social-card.png')
                self.assertEqual(page.tags['twitter:image'], page.tags['og:image'])
                self.assertEqual(page.tags['twitter:image:alt'], page.tags['og:image:alt'])
                self.assertEqual((page.tags['og:image:width'], page.tags['og:image:height']), ('1200', '630'))
                self.assertEqual(page.tags['twitter:card'], 'summary_large_image')
                self.assertEqual(page.tags['og:description'], page.tags['description'])


if __name__ == '__main__':
    unittest.main()
