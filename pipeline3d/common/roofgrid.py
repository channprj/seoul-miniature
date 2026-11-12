# 높이장 지붕(gen.py roof())을 메시 대신 "그림 두 장 + 지오메트리 노드"로 둔다(--save-blend 때만).
#   메시로 두면 지붕 하나가 수만~수십만 정점이라 경복궁 한 구역 .blend 가 수 GB 가 된다. 같은 격자를 Blender 가 열 때 다시 만든다.
#   - 높이: 16비트 회색 PNG, z = z0 + v/65535·zs (zs = 그 지붕의 높이 범위, 양자화 오차 ≤ zs/131070 m).
#   - 색·안팎: 8비트 RGBA PNG(sRGB). 알파 0 = 처마 밖(그 점과 닿는 면을 지운다 — 원래 메시도 네 꼭짓점이 모두 안일 때만 면을 만들었다).
#   - 노드 그룹 P3D_RoofGrid: Grid(nx×ny, 간격 G) → 위치 이동 + 높이 → 색 속성 'col'(점) → 밖 점 지우기 → 재질.
#   그림의 아래 행이 격자의 첫 y 행이다(Blender 이미지 원점 = 왼쪽 아래).
import os, io, numpy as np, bpy
from PIL import Image

_NG = None
_N = [0]

def _group():
    global _NG
    if _NG is not None: return _NG
    ng = bpy.data.node_groups.new('P3D_RoofGrid', 'GeometryNodeTree'); it = ng.interface
    it.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for nm, ty in (('Height', 'NodeSocketImage'), ('Color', 'NodeSocketImage'), ('NX', 'NodeSocketInt'), ('NY', 'NodeSocketInt'), ('G', 'NodeSocketFloat'),
                   ('X0', 'NodeSocketFloat'), ('Y0', 'NodeSocketFloat'), ('Z0', 'NodeSocketFloat'), ('ZS', 'NodeSocketFloat'), ('Material', 'NodeSocketMaterial')):
        it.new_socket(nm, in_out='INPUT', socket_type=ty)
    it.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    def math(op, a, b=None):
        n = N.new('ShaderNodeMath'); n.operation = op
        for k, s in enumerate((a, b)):
            if s is None: continue
            if isinstance(s, (int, float)): n.inputs[k].default_value = s
            else: L.new(s, n.inputs[k])
        return n.outputs[0]
    def toF(s): return math('ADD', s, 0.0)
    nx, ny, G = toF(gi.outputs['NX']), toF(gi.outputs['NY']), gi.outputs['G']
    # Step: 격자 칸을 몇 개씩 건너뛸지(1 = 원래 격자). 그룹 안의 정수 노드 하나라서 이 값을 바꾸면 모든 지붕에 한 번에 적용된다
    # (그룹 입력 소켓으로 두면 수정자마다 값이 따로 저장돼 기본값을 바꿔도 반영되지 않는다). 메모리가 모자랄 때 2–4.
    sn = N.new('FunctionNodeInputInt'); sn.name = sn.label = 'Step'; sn.integer = 1
    stp = math('MAXIMUM', toF(sn.outputs[0]), 1.0); GS = math('MULTIPLY', G, stp)
    vx = math('ADD', math('FLOOR', math('DIVIDE', math('SUBTRACT', nx, 1.0), stp)), 1.0)   # 건너뛴 격자의 꼭짓점 수
    vy = math('ADD', math('FLOOR', math('DIVIDE', math('SUBTRACT', ny, 1.0), stp)), 1.0)
    grid = N.new('GeometryNodeMeshGrid')
    L.new(math('MULTIPLY', math('SUBTRACT', vx, 1.0), GS), grid.inputs['Size X']); L.new(math('MULTIPLY', math('SUBTRACT', vy, 1.0), GS), grid.inputs['Size Y'])
    L.new(vx, grid.inputs['Vertices X']); L.new(vy, grid.inputs['Vertices Y'])
    # 1) x,y 를 지도 좌표로: 원점 = (X0 + (vx-1)·G·Step/2, Y0 + (vy-1)·G·Step/2)
    off = N.new('ShaderNodeCombineXYZ')
    L.new(math('ADD', gi.outputs['X0'], math('MULTIPLY', math('SUBTRACT', vx, 1.0), math('MULTIPLY', GS, 0.5))), off.inputs[0])
    L.new(math('ADD', gi.outputs['Y0'], math('MULTIPLY', math('SUBTRACT', vy, 1.0), math('MULTIPLY', GS, 0.5))), off.inputs[1])
    sp1 = N.new('GeometryNodeSetPosition'); L.new(grid.outputs['Mesh'], sp1.inputs['Geometry']); L.new(off.outputs[0], sp1.inputs['Offset'])
    # 2) 격자 번호 → 화소 중심 UV
    pos = N.new('GeometryNodeInputPosition'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(pos.outputs[0], sep.inputs[0])
    ii = math('ROUND', math('DIVIDE', math('SUBTRACT', sep.outputs[0], gi.outputs['X0']), G))
    jj = math('ROUND', math('DIVIDE', math('SUBTRACT', sep.outputs[1], gi.outputs['Y0']), G))
    uv = N.new('ShaderNodeCombineXYZ'); L.new(math('DIVIDE', math('ADD', ii, 0.5), nx), uv.inputs[0]); L.new(math('DIVIDE', math('ADD', jj, 0.5), ny), uv.inputs[1])
    def tex(sock):
        t = N.new('GeometryNodeImageTexture'); t.interpolation = 'Closest'; t.extension = 'EXTEND'
        L.new(sock, t.inputs['Image']); L.new(uv.outputs[0], t.inputs['Vector']); return t
    th, tc = tex(gi.outputs['Height']), tex(gi.outputs['Color'])
    hs = N.new('FunctionNodeSeparateColor'); L.new(th.outputs['Color'], hs.inputs[0])
    ma = N.new('ShaderNodeMath'); ma.operation = 'MULTIPLY_ADD'  # z = R·ZS + Z0
    L.new(hs.outputs[0], ma.inputs[0]); L.new(gi.outputs['ZS'], ma.inputs[1]); L.new(gi.outputs['Z0'], ma.inputs[2])
    zc = N.new('ShaderNodeCombineXYZ'); L.new(ma.outputs[0], zc.inputs[2])
    sp2 = N.new('GeometryNodeSetPosition'); L.new(sp1.outputs[0], sp2.inputs['Geometry']); L.new(zc.outputs[0], sp2.inputs['Offset'])
    st = N.new('GeometryNodeStoreNamedAttribute'); st.data_type = 'FLOAT_COLOR'; st.domain = 'POINT'
    L.new(sp2.outputs[0], st.inputs['Geometry']); st.inputs['Name'].default_value = 'col'; L.new(tc.outputs['Color'], st.inputs['Value'])
    out = math('LESS_THAN', tc.outputs['Alpha'], 0.5)
    dl = N.new('GeometryNodeDeleteGeometry'); dl.domain = 'POINT'; L.new(st.outputs[0], dl.inputs['Geometry']); L.new(out, dl.inputs['Selection'])
    sm = N.new('GeometryNodeSetMaterial'); L.new(dl.outputs[0], sm.inputs['Geometry']); L.new(gi.outputs['Material'], sm.inputs['Material'])
    ss = N.new('GeometryNodeSetShadeSmooth'); L.new(sm.outputs[0], ss.inputs['Geometry'])
    for k in ('Shade Smooth', 'Smooth'):
        if k in ss.inputs: ss.inputs[k].default_value = False
    L.new(ss.outputs[0], go.inputs[0])
    _NG = ng; return ng

def _srgb8(c):
    c = np.clip(c, 0, 1); s = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    return np.round(s * 255).astype(np.uint8)

def _packed(nm, pim):
    """PNG 를 디스크를 거치지 않고 메모리에서 바로 .blend 에 넣는다(임시 폴더 경로가 파일 바이트에 남지 않게)."""
    b = io.BytesIO(); pim.save(b, 'PNG'); data = b.getvalue()
    img = bpy.data.images.new(nm, *pim.size); img.pack(data=data, data_len=len(data))
    img.source = 'FILE'; img.filepath_raw = '//textures/' + nm
    for pf in img.packed_files: pf.filepath = '//textures/' + nm
    return img

def build(name, idx, xs, ys, z, colv, inside, mat, texdir, link):
    """xs(nx), ys(ny), z·inside (ny,nx), colv (ny,nx,4) 선형 색. 원래 메시와 같은 정점·면을 만드는 오브젝트를 돌려준다."""
    ng = _group(); _N[0] += 1; k = _N[0]
    ny, nx = inside.shape; zi = z[inside]; z0 = float(zi.min()); zs = float(max(zi.max() - z0, 1e-3))
    hv = np.zeros((ny, nx), np.uint16); hv[inside] = np.round((z[inside] - z0) / zs * 65535).astype(np.uint16)
    rgba = np.zeros((ny, nx, 4), np.uint8); rgba[..., :3] = _srgb8(colv[..., :3]); rgba[..., 3] = np.where(inside, 255, 0)
    ih = _packed('roofh_%05d.png' % k, Image.fromarray(hv[::-1].copy())); ih.colorspace_settings.name = 'Non-Color'; ih.reload()
    ic = _packed('roofc_%05d.png' % k, Image.fromarray(rgba[::-1].copy(), 'RGBA')); ic.alpha_mode = 'CHANNEL_PACKED'; ic.reload()
    me = bpy.data.meshes.new(name); me.materials.append(mat)
    o = bpy.data.objects.new(name, me); o.pass_index = idx; link(o)
    md = o.modifiers.new('RoofGrid', 'NODES'); md.node_group = ng
    vals = dict(Height=ih, Color=ic, NX=nx, NY=ny, G=float(xs[1] - xs[0]), X0=float(xs[0]), Y0=float(ys[0]), Z0=z0, ZS=zs, Material=mat)
    for it in ng.interface.items_tree:
        if getattr(it, 'in_out', '') == 'INPUT' and it.name in vals: md[it.identifier] = vals[it.name]
    return o
