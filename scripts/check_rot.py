import zipfile
import xml.etree.ElementTree as ET
import re

pptx_path = 'docs/双流机场ppt草图.pptx'

NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
}

with zipfile.ZipFile(pptx_path, 'r') as zf:
    for sf in sorted([f for f in zf.namelist() if re.match(r'ppt/slides/slide\d+\.xml', f)]):
        xml_data = zf.read(sf)
        root = ET.fromstring(xml_data)
        spTree = root.find('.//p:cSld/p:spTree', NS)
        if spTree is None:
            continue
        
        for shp in spTree:
            tag = shp.tag.split('}')[-1]
            if tag != 'sp':
                continue
            
            nvSpPr = shp.find('p:nvSpPr', NS)
            name = ''
            if nvSpPr is not None:
                cNvPr = nvSpPr.find('p:cNvPr', NS)
                if cNvPr is not None:
                    name = cNvPr.get('name', '')
            
            spPr = shp.find('p:spPr', NS)
            if spPr is None:
                continue
            
            xfrm = spPr.find('a:xfrm', NS)
            if xfrm is None:
                continue
            
            rot = xfrm.get('rot', '0')
            flipH = xfrm.get('flipH', '0')
            flipV = xfrm.get('flipV', '0')
            
            # Only show shapes with rotation or flip
            if rot != '0' or flipH == '1' or flipV == '1':
                off = xfrm.find('a:off', NS)
                ext = xfrm.find('a:ext', NS)
                prstGeom = spPr.find('a:prstGeom', NS)
                shape_type = prstGeom.get('prst', '?') if prstGeom is not None else '?'
                print(f"{name}: rot={rot} ({int(rot)/60000:.1f}deg), flipH={flipH}, flipV={flipV}, type={shape_type}")
