import io
import os
import zipfile
from xml.etree import ElementTree as ET

SRC = os.path.join('practices', 'practice_03', 'output.pptx')
DST = os.path.join('practices', 'practice_03', 'output_first2.pptx')


NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

ET.register_namespace('p', NS['p'])
ET.register_namespace('r', NS['r'])


def get_keep_slides(z: zipfile.ZipFile):
    pres_xml = ET.fromstring(z.read('ppt/presentation.xml'))
    sldIdLst = pres_xml.find('p:sldIdLst', NS)
    if sldIdLst is None:
        raise RuntimeError('No slide ID list found')
    # Collect first two r:id values in order
    sldIds = sldIdLst.findall('p:sldId', NS)
    if len(sldIds) < 2:
        raise RuntimeError('Presentation has fewer than 2 slides')
    keep_ids = [sldIds[0].attrib[f"{{{NS['r']}}}id"], sldIds[1].attrib[f"{{{NS['r']}}}id"]]
    # Map relationships to slide targets
    rels_xml = ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))
    slide_targets = {}
    for rel in rels_xml.findall('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
        rid = rel.attrib.get('Id')
        target = rel.attrib.get('Target')
        rtype = rel.attrib.get('Type')
        if rtype and rtype.endswith('/slide'):
            slide_targets[rid] = target  # e.g., 'slides/slide1.xml'
    keep_targets = [slide_targets[rid] for rid in keep_ids]
    return keep_ids, keep_targets


def build_modified_presentation(z: zipfile.ZipFile, keep_ids):
    pres_xml = ET.fromstring(z.read('ppt/presentation.xml'))
    sldIdLst = pres_xml.find('p:sldIdLst', NS)
    # Remove all children except first two
    sldIds = sldIdLst.findall('p:sldId', NS)
    for elem in sldIds[2:]:
        sldIdLst.remove(elem)
    # Write back
    buf = io.BytesIO()
    ET.ElementTree(pres_xml).write(buf, encoding='utf-8', xml_declaration=True)
    return buf.getvalue()


def build_modified_presentation_rels(z: zipfile.ZipFile, keep_ids):
    rels_xml = ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))
    for rel in list(rels_xml):
        rid = rel.attrib.get('Id')
        rtype = rel.attrib.get('Type')
        if rtype and rtype.endswith('/slide') and rid not in keep_ids:
            rels_xml.remove(rel)
    buf = io.BytesIO()
    ET.ElementTree(rels_xml).write(buf, encoding='utf-8', xml_declaration=True)
    return buf.getvalue()


def build_modified_content_types(z: zipfile.ZipFile, keep_targets):
    ct_xml = ET.fromstring(z.read('[Content_Types].xml'))
    # Keep Overrides for slides in keep_targets; remove others
    for ov in list(ct_xml):
        if ov.tag.endswith('Override'):
            part = ov.attrib.get('PartName', '')
            # PartName is like '/ppt/slides/slide1.xml'
            if part.startswith('/ppt/slides/') and (part.split('/')[-1] not in [t.split('/')[-1] for t in keep_targets]):
                ct_xml.remove(ov)
    buf = io.BytesIO()
    ET.ElementTree(ct_xml).write(buf, encoding='utf-8', xml_declaration=True)
    return buf.getvalue()


def main():
    with zipfile.ZipFile(SRC, 'r') as z:
        keep_ids, keep_targets = get_keep_slides(z)
        pres_mod = build_modified_presentation(z, keep_ids)
        rels_mod = build_modified_presentation_rels(z, keep_ids)
        ct_mod = build_modified_content_types(z, keep_targets)

        # Build new zip
        with zipfile.ZipFile(DST, 'w', compression=zipfile.ZIP_DEFLATED) as out:
            names = z.namelist()
            for name in names:
                data = z.read(name)
                if name == 'ppt/presentation.xml':
                    out.writestr(name, pres_mod)
                    continue
                if name == 'ppt/_rels/presentation.xml.rels':
                    out.writestr(name, rels_mod)
                    continue
                if name == '[Content_Types].xml':
                    out.writestr(name, ct_mod)
                    continue
                # Include only kept slides and their rels; include all non-slide parts
                if name.startswith('ppt/slides/'):
                    base = name.split('/')[-1]
                    if base in [t.split('/')[-1] for t in keep_targets]:
                        out.writestr(name, data)
                    else:
                        continue
                elif name.startswith('ppt/slides/_rels/'):
                    base = name.split('/')[-1]
                    # Map slide rel name convention: slideN.xml.rels
                    keep_rels = [t.split('/')[-1] + '.rels' for t in keep_targets]
                    if base in keep_rels:
                        out.writestr(name, data)
                    else:
                        continue
                else:
                    out.writestr(name, data)
    print('Wrote', DST)


if __name__ == '__main__':
    main()
