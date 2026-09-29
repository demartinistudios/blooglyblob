"""Remove only Bambu's account metadata, retaining all other project bytes.

XML byte offsets avoid reserializing model trees (and losing namespace declarations
or changing geometry text). Empty/missing fields are already public and stay intact.
"""
from pathlib import Path
from xml.parsers import expat
import zipfile


def private_metadata_spans(data):
    """Return nonempty DesignerUserId element spans; reject ambiguous XML."""
    if b'\x00' in data:
        raise ValueError('Project XML must use an ASCII-compatible encoding')
    parser = expat.ParserCreate(namespace_separator='}')
    spans, found, active = [], 0, None

    def start(name, attributes):
        nonlocal active, found
        if active is not None:
            raise ValueError('DesignerUserId must contain text only')
        if name.rsplit('}', 1)[-1] == 'metadata' and attributes.get('name') == 'DesignerUserId':
            found += 1
            if found > 1:
                raise ValueError('Duplicate DesignerUserId metadata')
            active = [parser.CurrentByteIndex, []]

    def characters(value):
        if active is not None:
            active[1].append(value)

    def end(name):
        nonlocal active
        if active is not None:
            if ''.join(active[1]).strip():
                # A nonempty text element has a closing tag at CurrentByteIndex.
                finish = data.index(b'>', parser.CurrentByteIndex) + 1
                spans.append((active[0], finish))
            active = None

    def reject_doctype(*args):
        raise ValueError('DTD declarations are not supported in project XML')

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = characters
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.Parse(data, True)
    return spans


def sanitize_metadata(data):
    """Remove nonempty account fields from XML without changing other bytes."""
    for start, end in reversed(private_metadata_spans(data)):
        data = data[:start] + data[end:]
    return data


def _xml_member(name, data):
    # Config files may be JSON or XML. Recognize XML byte-order marks so an
    # alternate encoding cannot bypass metadata checks; unsupported ones fail closed.
    prefix = data.removeprefix(b'\xef\xbb\xbf').lstrip()
    return name.lower().endswith(('.model', '.xml', '.rels')) or (
        name.lower().endswith('.config') and prefix.startswith((b'<', b'\xff\xfe', b'\xfe\xff', b'\x00')))


def _unique_members(project):
    names = project.namelist()
    if len(names) != len(set(names)):
        raise ValueError('Duplicate ZIP members in print project')


def check_project(path):
    """Reject nonempty account fields and ambiguous ZIP/XML; never print IDs."""
    with zipfile.ZipFile(path) as project:
        _unique_members(project)
        for info in project.infolist():
            data = project.read(info)
            if _xml_member(info.filename, data) and private_metadata_spans(data):
                raise ValueError(f'Nonempty DesignerUserId in {info.filename}')


def sanitize_project(src, dest, transform=None):
    """Write a separate public 3MF; optional transform(name, data) runs first."""
    if Path(src).resolve() == Path(dest).resolve() or (Path(dest).exists() and Path(src).samefile(dest)):
        raise ValueError('Public project output must differ from source')
    with zipfile.ZipFile(src) as zin:
        _unique_members(zin)
        with zipfile.ZipFile(dest, 'w') as zout:
            zout.comment = zin.comment
            for info in zin.infolist():
                data = zin.read(info)
                if transform is not None:
                    data = transform(info.filename, data)
                if _xml_member(info.filename, data):
                    data = sanitize_metadata(data)
                zout.writestr(info, data, compress_type=info.compress_type)
