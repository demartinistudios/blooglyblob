"""Every published page carries complete link-preview tags, the shared card and a touch icon."""
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
        self.tags, self.links = {}, {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and 'content' in attrs:
            key = attrs.get('property') or attrs.get('name')
            if key in self.tags:
                raise AssertionError(f'Duplicate meta tag: {key}')
            self.tags[key] = attrs['content']
        elif tag == 'link':
            self.links[attrs.get('rel')] = attrs.get('href')


def head(name):
    parser = Head()
    parser.feed((SRC / name).read_text())
    return parser


class SocialCardTests(unittest.TestCase):
    def test_images_are_pngs_of_the_declared_size(self):
        for name, size in [('social-card.png', (1200, 630)), ('apple-touch-icon.png', (180, 180))]:
            with self.subTest(image=name):
                data = (SRC / name).read_bytes()
                self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                self.assertEqual(struct.unpack('>II', data[16:24]), size)

    def test_pages_share_complete_absolute_tags(self):
        for name, path in PAGES.items():
            with self.subTest(page=name):
                page = head(name)
                self.assertFalse([key for key in REQUIRED if not page.tags.get(key)])
                self.assertEqual(page.tags['og:url'], SITE + path)
                self.assertEqual(page.links.get('canonical'), SITE + path)
                self.assertEqual(page.links.get('apple-touch-icon'), 'apple-touch-icon.png')
                self.assertEqual(page.tags['og:image'], SITE + 'social-card.png')
                self.assertEqual(page.tags['twitter:image'], page.tags['og:image'])
                self.assertEqual(page.tags['twitter:image:alt'], page.tags['og:image:alt'])
                self.assertEqual((page.tags['og:image:width'], page.tags['og:image:height']), ('1200', '630'))
                self.assertEqual(page.tags['twitter:card'], 'summary_large_image')
                self.assertEqual(page.tags['og:description'], page.tags['description'])


if __name__ == '__main__':
    unittest.main()
