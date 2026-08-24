"""
解析 双流机场ppt草图.pptx → terminal_layout.json
使用 Python 内置库 zipfile + xml，无需第三方依赖
"""
import json
import zipfile
import xml.etree.ElementTree as ET
import os
import re
import sys

pptx_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'docs', '双流机场ppt草图.pptx')
out_path = os.path.join(os.path.dirname(pptx_path), 'terminal_layout.json')
# 同时输出到前端 public 目录
frontend_public = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'demo', 'public', 'terminal_layout.json')

# EMU → 像素 (96 dpi)
def emu_to_px(emu):
    return round(emu / 914400 * 96, 2) if emu is not None else 0

def parse_color(srgb_hex):
    """sRGB hex like 'FF0000' -> '#ff0000'"""
    if srgb_hex and len(srgb_hex) == 6:
        return '#' + srgb_hex.lower()
    return None

# PPTX 命名空间
NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
}

def get_fill(spPr):
    """提取填充色"""
    solid = spPr.find('.//a:solidFill/a:srgbClr', NS)
    if solid is not None:
        return parse_color(solid.get('val'))
    # 也可能在 a:schemeClr 里
    solid2 = spPr.find('.//a:solidFill/a:schemeClr', NS)
    if solid2 is not None:
        lum = solid2.find('a:lumMod', NS)
        clr_val = solid2.get('val', '')
        if clr_val == 'accent1': return '#4472C4'
        if clr_val == 'accent2': return '#ED7D31'
        if clr_val == 'accent3': return '#A5A5A5'
        if clr_val == 'accent4': return '#FFC000'
        if clr_val == 'accent5': return '#5B9BD5'
        if clr_val == 'accent6': return '#70AD47'
        if clr_val == 'dk1': return '#000000'
        if clr_val == 'dk2': return '#44546A'
        if clr_val == 'lt1': return '#FFFFFF'
        if clr_val == 'lt2': return '#E7E6E6'
        if clr_val == 'tx1': return '#000000'
        if clr_val == 'tx2': return '#44546A'
        if clr_val == 'bg1': return '#FFFFFF'
        if clr_val == 'bg2': return '#E7E6E6'
    return None

def get_line(spPr):
    """提取边框色"""
    ln = spPr.find('a:ln', NS)
    if ln is None:
        return None
    solid = ln.find('.//a:solidFill/a:srgbClr', NS)
    if solid is not None:
        return parse_color(solid.get('val'))
    return None

def get_text(shp, slide_rels):
    """从形状提取文本"""
    texts = []
    # 遍历 txBody
    txBody = shp.find('.//p:txBody', NS)
    if txBody is None:
        return ''
    for p_elem in txBody.findall('a:p', NS):
        line_parts = []
        for t_elem in p_elem.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
            if t_elem.text:
                line_parts.append(t_elem.text)
        if line_parts:
            texts.append(''.join(line_parts))
    return '\n'.join(texts).strip()

# 读取 PPTX (ZIP)
all_shapes = []

with zipfile.ZipFile(pptx_path, 'r') as zf:
    # 读取所有 slide
    slide_files = sorted([f for f in zf.namelist() if re.match(r'ppt/slides/slide\d+\.xml', f)])
    
    # 读取 slide 的关系文件（用于获取图片等 ）
    slide_rels = {}
    for sf in slide_files:
        slide_num = re.search(r'slide(\d+)', sf).group(1)
        rel_path = f'ppt/slides/_rels/slide{slide_num}.xml.rels'
        rels = {}
        if rel_path in zf.namelist():
            try:
                rel_xml = zf.read(rel_path)
                rel_root = ET.fromstring(rel_xml)
                for rel in rel_root:
                    rel_id = rel.get('Id')
                    target = rel.get('Target', '')
                    rel_type = rel.get('Type', '')
                    rels[rel_id] = {'target': target, 'type': rel_type}
            except:
                pass
        slide_rels[sf] = rels

    for sf in slide_files:
        xml_data = zf.read(sf)
        root = ET.fromstring(xml_data)
        
        # 所有形状在 p:spTree 下
        spTree = root.find('.//p:cSld/p:spTree', NS)
        if spTree is None:
            continue
        
        rels = slide_rels.get(sf, {})
        
        for shp in spTree:
            tag = shp.tag.split('}')[-1] if '}' in shp.tag else shp.tag
            
            if tag == 'sp':
                # 形状
                nvSpPr = shp.find('p:nvSpPr', NS)
                spPr = shp.find('p:spPr', NS)
                
                name = ''
                if nvSpPr is not None:
                    cNvPr = nvSpPr.find('p:cNvPr', NS)
                    if cNvPr is not None:
                        name = cNvPr.get('name', '')
                
                if spPr is None:
                    continue
                
                # 位置和大小
                xfrm = spPr.find('a:xfrm', NS)
                if xfrm is None:
                    continue
                
                off = xfrm.find('a:off', NS)
                ext = xfrm.find('a:ext', NS)
                
                left = emu_to_px(int(off.get('x', 0))) if off is not None else 0
                top = emu_to_px(int(off.get('y', 0))) if off is not None else 0
                w = emu_to_px(int(ext.get('cx', 0))) if ext is not None else 0
                h = emu_to_px(int(ext.get('cy', 0))) if ext is not None else 0
                
                # 旋转角度 (PPTX: 1/60000 度 → 度)
                rot_raw = xfrm.get('rot', '0')
                rot_deg = round(int(rot_raw) / 60000, 1) if rot_raw else 0
                
                # 如果有翻转 (flipH/flipV)
                flip_h = xfrm.get('flipH', '0') == '1'
                flip_v = xfrm.get('flipV', '0') == '1'
                
                # 形状类型
                prstGeom = spPr.find('a:prstGeom', NS)
                shape_type = prstGeom.get('prst', 'rect') if prstGeom is not None else 'rect'
                
                text = get_text(shp, rels)
                fill = get_fill(spPr)
                line = get_line(spPr)
                
                all_shapes.append({
                    'name': name,
                    'type': shape_type,
                    'x': left, 'y': top, 'w': w, 'h': h,
                    'rot': rot_deg,
                    'flipH': flip_h,
                    'flipV': flip_v,
                    'text': text,
                    'fill': fill,
                    'line': line,
                })
            
            elif tag in ('pic', 'cxnSp', 'grpSp'):
                # 图片、连接线、组合 — 简单提取位置
                pass

# ===== 从所有形状中识别关键布局 =====
rects = [s for s in all_shapes if s['w'] > 0 and s['h'] > 0]

if not rects:
    print("ERROR: No shapes found!")
    sys.exit(1)

min_x = min(s['x'] for s in rects)
min_y = min(s['y'] for s in rects)
max_x = max(s['x'] + s['w'] for s in rects)
max_y = max(s['y'] + s['h'] for s in rects)

rects_sorted = sorted(rects, key=lambda r: r['w'] * r['h'], reverse=True)

# 按语义分类
terminals = []   # 航站楼主体（有"航站楼"文字）
runways = []     # 跑道（有"跑道"文字）
arrow_gates = [] # 箭头登机口
rect_gates = []  # 矩形登机口
piers = []       # 延伸廊
others = []

for r in rects_sorted:
    text = r.get('text', '')
    s_type = r.get('type', '')
    area = r['w'] * r['h']
    
    # 1. 航站楼主体
    if '航站楼' in text:
        r['terminal_name'] = text.strip()
        terminals.append(r)
    # 2. 跑道
    elif '跑道' in text:
        runways.append(r)
    # 3. 箭头 → 登机口标识
    elif s_type in ('upArrow', 'downArrow'):
        r['gate_dir'] = 'exit' if s_type == 'upArrow' else 'entry'
        arrow_gates.append(r)
    # 4. 小矩形 → 登机口 (w ~31, h ~5)
    elif area < 5000 and r['w'] < 50 and r['h'] < 15:
        r['gate_dir'] = 'unknown'
        rect_gates.append(r)
    # 5. 延伸廊：中等矩形 (窄长竖矩形或扁横矩形 + 没有特殊文字)
    elif (r['w'] <= 250 and r['h'] >= 50) or (r['w'] >= 80 and r['h'] <= 25):
        piers.append(r)
    else:
        others.append(r)

# 合并所有 gates
all_gates = arrow_gates + rect_gates

# gates → 归属到最近的 terminal 或 pier
def find_attach(g, candidates):
    gcx = g['x'] + g['w'] / 2
    gcy = g['y'] + g['h'] / 2
    best = None
    best_dist = 9999
    
    for obj, ref_name in candidates:
        tx, ty, tw, th = obj['x'], obj['y'], obj['w'], obj['h']
        sides = [
            ('top',    ty - (gcy + g['h']),     gcx, ty),
            ('bottom', gcy - (ty + th),          gcx, ty + th),
            ('left',   tx - (gcx + g['w']),     tx, gcy),
            ('right',  gcx - (tx + tw),          tx + tw, gcy),
        ]
        for sd_name, sd_dist, sx, sy in sides:
            h_range = gcx > tx - 60 and gcx < tx + tw + 60
            v_range = gcy > ty - 60 and gcy < ty + th + 60
            valid = (sd_name in ('top', 'bottom') and h_range) or (sd_name in ('left', 'right') and v_range)
            if valid and abs(sd_dist) < abs(best_dist):
                best_dist = abs(sd_dist)
                best = {'ref': ref_name, 'side': sd_name, 'dist': round(sd_dist, 1)}
    return best

for g in all_gates:
    candidates = []
    for term in terminals:
        candidates.append((term, term.get('terminal_name', term.get('name', ''))))
    for pier in piers:
        candidates.append((pier, pier.get('text', '') or pier.get('name', '')))
    g['attach'] = find_attach(g, candidates)

# 标记每个 gate 的方向：基于箭头类型
# upArrow 指向 terminal → entry（登机入口）
# downArrow 背离 terminal → exit（下客出口）
for g in arrow_gates:
    if g.get('gate_dir') == 'exit':
        pass  # 已经是 exit
    elif g.get('gate_dir') == 'entry':
        pass  # 已经是 entry

result = {
    'meta': {
        'bounds': {'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y,
                   'width': max_x - min_x, 'height': max_y - min_y},
        'total_shapes': len(all_shapes),
    },
    'terminals': terminals,
    'piers': piers,
    'gates': all_gates,
    'runways': runways,
    'others': others,
    'all_shapes': all_shapes,
}

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
with open(frontend_public, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('Done! Output:', out_path)
print('       Also:', frontend_public)
print(f'  total_shapes={len(all_shapes)}')
print(f'  terminals={len(terminals)}')
print(f'  piers={len(piers)}')
print(f'  gates={len(all_gates)} (arrows={len(arrow_gates)}, rects={len(rect_gates)})')
print(f'  runways={len(runways)}')
print(f'  others={len(others)}')
