"""glTF 1.0 GLB → glTF 2.0 GLB 转换器

把旧版（Blender 老导出器）生成的 GLB v1 二进制模型转换为标准 GLB v2，
使新版 Three.js GLTFLoader 可以直接加载。

转换要点：
- buffer 数据原样复用（accessors 均无 byteStride，紧凑排布）
- bufferView 名字 → 索引；accessor 引用同步重映射
- 丢弃 shaders/programs/techniques/animations/cameras/skins
- effect 材质 → PBR 材质（diffuse 颜色或贴图、透明度、双面标志）
- 内嵌图片（KHR_binary_glTF bufferView）提取为独立 image + texture

用法: python scripts/convert_glb_v1_to_v2.py <input.glb> <output.glb>
"""

import json
import os
import struct
import sys

# glTF 1.0 材质里的技术（technique）状态：
# enable 列表出现 2884 (CULL_FACE) => 背面剔除开启（非双面）
_CULL_FACE = 2884
_BLEND = 3042


def read_glb(path):
    """读取 GLB，返回 (version, json_obj, binary_bytes)"""
    with open(path, 'rb') as f:
        data = f.read()
    magic, version, length = struct.unpack('<III', data[:12])
    assert magic == 0x46546C67, 'not a glTF binary'
    if version == 1:
        clen = struct.unpack('<I', data[12:16])[0]
        json_bytes = data[20:20 + clen]
        bin_start = 20 + clen
        if bin_start % 4:
            bin_start += 4 - (bin_start % 4)
        bin_bytes = data[bin_start:]
    else:
        clen = struct.unpack('<I', data[12:16])[0]
        json_bytes = data[20:20 + clen]
        bin_start = 20 + clen
        blen = struct.unpack('<I', data[bin_start:bin_start + 4])[0] if len(data) > bin_start + 4 else 0
        bin_bytes = data[bin_start + 8: bin_start + 8 + blen]
    if json_bytes[:3] == b'\xef\xbb\xbf':
        json_bytes = json_bytes[3:]
    return version, json.loads(json_bytes.decode('utf-8')), bin_bytes


def write_glb(path, gltf, bin_bytes):
    """写出标准 GLB v2"""
    json_bytes = json.dumps(gltf, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    # JSON chunk 4 字节对齐（用空格填充）
    if len(json_bytes) % 4:
        json_bytes += b' ' * (4 - len(json_bytes) % 4)
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, total))
        f.write(struct.pack('<I', len(json_bytes)))
        f.write(b'JSON')
        f.write(json_bytes)
        f.write(struct.pack('<I', len(bin_bytes)))
        f.write(b'BIN\x00')
        f.write(bin_bytes)


def extract_image_bytes(j, bin_bytes, image):
    """从 glTF 1.0 image 中提取图片字节（KHR_binary_glTF bufferView 或 data uri）"""
    ext = image.get('extensions', {}).get('KHR_binary_glTF', {})
    if 'bufferView' in ext:
        bv = j['bufferViews'][ext['bufferView']]
        buf = j['buffers'][bv['buffer']]
        # 找到二进制 buffer（GLB v1 的 uri 是 "data:," 或 "data:"）
        offset = bv.get('byteOffset', 0)
        return bin_bytes[offset:offset + bv['byteLength']], ext.get('mimeType')
    uri = image.get('uri', '')
    if uri.startswith('data:'):
        import base64
        head, _, b64 = uri.partition(',')
        mime = head.split(';')[0].replace('data:', '')
        return base64.b64decode(b64), mime
    return None, None


def material_to_pbr(j, mat_name, mat, tech, texture_info):
    """把 glTF 1.0 effect 材质转为 glTF 2.0 PBR 材质描述"""
    values = mat.get('values', {})
    base_color = [1.0, 1.0, 1.0, 1.0]
    base_color_tex = None

    diffuse = values.get('diffuse')
    if isinstance(diffuse, (list, tuple)):
        base_color = [float(x) for x in diffuse[:4]]
        if len(base_color) == 3:
            base_color.append(1.0)
    elif isinstance(diffuse, str) and texture_info:
        base_color_tex = {'index': texture_info['texture_index']}

    emissive = values.get('emissive')
    emissive_factor = [0.0, 0.0, 0.0]
    if isinstance(emissive, (list, tuple)):
        emissive_factor = [float(x) for x in emissive[:3]]

    # 透明度
    alpha = values.get('transparency', 1.0)
    alpha = float(alpha)
    if alpha > 1.0:
        alpha = 1.0
    base_color[3] = alpha

    # 技术状态：是否双面 / 是否混合
    double_sided = True
    has_blend = False
    if tech:
        states = tech.get('states', {})
        enabled = states.get('enable', [])
        double_sided = _CULL_FACE not in enabled
        has_blend = _BLEND in enabled
    alpha_mode = 'BLEND' if (has_blend or alpha < 1.0) else 'OPAQUE'

    pbr = {
        'baseColorFactor': base_color,
        'metallicFactor': 0.0,
        'roughnessFactor': 0.9,
    }
    if base_color_tex:
        pbr['baseColorTexture'] = base_color_tex

    out = {
        'name': mat.get('name', mat_name),
        'pbrMetallicRoughness': pbr,
        'alphaMode': alpha_mode,
        'doubleSided': double_sided,
    }
    if emissive_factor != [0.0, 0.0, 0.0]:
        out['emissiveFactor'] = emissive_factor
    return out


def convert(src, dst):
    version, j, bin_bytes = read_glb(src)
    if version == 2:
        print(f'{src} 已是 GLB v2，跳过')
        return

    # ---- bufferViews / accessors 名字 → 索引 ----
    bv_names = list(j.get('bufferViews', {}).keys())
    bv_index = {n: i for i, n in enumerate(bv_names)}
    acc_names = list(j.get('accessors', {}).keys())
    acc_index = {n: i for i, n in enumerate(acc_names)}
    mesh_names = list(j.get('meshes', {}).keys())
    mesh_index = {n: i for i, n in enumerate(mesh_names)}
    node_names = list(j.get('nodes', {}).keys())
    node_index = {n: i for i, n in enumerate(node_names)}

    # ---- accessors 重映射（保持数据不变） ----
    new_accessors = []
    for name in acc_names:
        a = dict(j['accessors'][name])
        if 'bufferView' in a:
            a['bufferView'] = bv_index[a['bufferView']]
        a.pop('byteStride', None)  # v1 的 accessor 级 stride 在 v2 中无意义（本项目均为 0）
        new_accessors.append(a)

    # ---- bufferViews（全部保留，含 shader 缓冲；index 顺序不变） ----
    new_buffer_views = []
    for name in bv_names:
        bv = dict(j['bufferViews'][name])
        bv['buffer'] = 0
        new_buffer_views.append(bv)

    # ---- images / textures / samplers ----
    new_images = []
    new_samplers = []
    new_textures = []
    texture_info = None
    img_map = {}
    for name, img in j.get('images', {}).items():
        data_bytes, mime = extract_image_bytes(j, bin_bytes, img)
        if data_bytes is None:
            continue
        new_images.append({'bufferView': None, 'mimeType': mime or 'image/jpeg'})
        img_map[name] = len(new_images) - 1
        # 图片 bufferView 独立放入 bufferViews 末尾
        offset = len(bin_bytes)
        # 4 字节对齐
        if offset % 4:
            pad = b'\x00' * (4 - offset % 4)
            bin_bytes += pad
            offset = len(bin_bytes)
        new_images[-1]['bufferView'] = len(new_buffer_views)
        new_buffer_views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(data_bytes)})
        bin_bytes += data_bytes

    # sampler / texture
    for sname, s in j.get('samplers', {}).items():
        new_samplers.append({
            'magFilter': s.get('magFilter', 9729),
            'minFilter': s.get('minFilter', 9729),
            'wrapS': s.get('wrapS', 10497),
            'wrapT': s.get('wrapT', 10497),
        })
    for tname, t in j.get('textures', {}).items():
        src_img = t.get('source')
        if src_img not in img_map:
            continue
        new_textures.append({
            'sampler': 0,
            'source': img_map[src_img],
            'name': tname,
        })
    if new_textures:
        texture_info = {'texture_index': 0}

    # ---- materials：effect → PBR ----
    techniques = j.get('techniques', {})
    new_materials = []
    mat_index = {}
    for mname, m in j.get('materials', {}).items():
        tech = techniques.get(m.get('technique', ''), None)
        new_materials.append(material_to_pbr(j, mname, m, tech, texture_info))
        mat_index[mname] = len(new_materials) - 1

    # ---- meshes ----
    new_meshes = []
    for name in mesh_names:
        mesh = j['meshes'][name]
        prims = []
        for p in mesh.get('primitives', []):
            attrs = {}
            for akey, aname in p.get('attributes', {}).items():
                attrs[akey] = acc_index[aname]
            prim = {
                'attributes': attrs,
            }
            if 'indices' in p:
                prim['indices'] = acc_index[p['indices']]
            if 'material' in p and p['material'] in mat_index:
                prim['material'] = mat_index[p['material']]
            if 'mode' in p:
                prim['mode'] = p['mode']
            prims.append(prim)
        new_meshes.append({'name': name, 'primitives': prims})

    # ---- nodes（保留 matrix / children / meshes） ----
    new_nodes = []
    for name in node_names:
        n = j['nodes'][name]
        node = {'name': n.get('name', name)}
        if 'matrix' in n:
            node['matrix'] = n['matrix']
        if n.get('children'):
            node['children'] = [node_index[c] for c in n['children']]
        if n.get('meshes'):
            node['mesh'] = mesh_index[n['meshes'][0]]
        new_nodes.append(node)

    # ---- scenes ----
    new_scenes = []
    scene_index = {}
    for sname, s in j.get('scenes', {}).items():
        new_scenes.append({'name': sname, 'nodes': [node_index[n] for n in s.get('nodes', [])]})
        scene_index[sname] = len(new_scenes) - 1

    gltf = {
        'asset': {'version': '2.0', 'generator': 'glb-v1-to-v2-converter'},
        'scene': scene_index.get(j.get('scene', 'defaultScene'), 0),
        'scenes': new_scenes,
        'nodes': new_nodes,
        'meshes': new_meshes,
        'accessors': new_accessors,
        'bufferViews': new_buffer_views,
        'buffers': [{'byteLength': len(bin_bytes)}],
    }
    if new_materials:
        gltf['materials'] = new_materials
    if new_samplers:
        gltf['samplers'] = new_samplers
    if new_textures:
        gltf['textures'] = new_textures
    if new_images:
        gltf['images'] = new_images

    write_glb(dst, gltf, bin_bytes)
    print(f'converted {src} -> {dst} ({len(bin_bytes)} bytes bin, '
          f'{len(new_nodes)} nodes, {len(new_meshes)} meshes, {len(new_materials)} materials)')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('usage: python scripts/convert_glb_v1_to_v2.py <input.glb> <output.glb>')
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
