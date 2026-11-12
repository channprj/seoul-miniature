// 지도 고유 값 파일(map.json) → 앱이 쓰는 장면 모양(scene.json 과 같은 키).
// 경로 좌표 = 장면 지역 좌표(m, z 위). 규격이 바뀌면 여기만 고친다.
//   camera {theta, elev, SX0, SY1, cam_ref, view_dir}, depth {D0, step}, map_px, map_m_per_px,
//   landmarks {key: {name, px:[x, y](지도 px)}}, lanes [{highway, pts:[[x,y,z]]}], walk_paths [{pts}]
import { hash01 } from './geom.js';

// truck = 소형 화물차(앞 운전칸 + 뒤 짐칸 상자). 글자·로고 없음.
const SPECS = { sedan: [4.7, 1.85, 1.45], suv: [4.8, 1.95, 1.75], taxi: [4.7, 1.8, 1.5], bus: [11.0, 2.5, 3.2], van: [5.2, 1.95, 2.0], truck: [6.2, 2.05, 2.6] };
const COLORS = { sedan: ['#f4f4f0', '#c9ccd0', '#2a2c30', '#7d838a', '#33507a', '#a8322c'], suv: ['#2a2c30', '#f4f4f0', '#7d838a'], taxi: ['#f08a24', '#c9ccd0'], bus: ['#3a7bd5', '#4caf50', '#e53935'], van: ['#f4f4f0', '#8a9098'], truck: ['#2f5fa8', '#f4f4f0', '#3a8a5a'] };
const SHIRTS = ['#e8e4da', '#3b4a66', '#a8322c', '#4f7f5a', '#d9a441', '#6c5a8e', '#2f2f35', '#c7d3e0'], PANTS = ['#3b4a66', '#1e1e22', '#6b6258'], HAIR = ['#141210', '#3a2a20', '#7a5a40'];

export function sceneFromMap(m) {
  const c = m.camera, t = c.theta * Math.PI / 180, a = (90 - c.elev) * Math.PI / 180;
  // 여의도 판 카메라(정사투영, 방위 θ, 고도 elev): R = Rz(θ)·Rx(90° − elev). 화면 오른쪽, 화면 위, 시선
  const ex = [Math.cos(t), Math.sin(t), 0];
  const ey = [-Math.sin(t) * Math.cos(a), Math.cos(t) * Math.cos(a), Math.sin(a)];
  const vd = c.view_dir || [-Math.sin(t) * Math.sin(a), Math.cos(t) * Math.sin(a), -Math.cos(a)];
  const [W, H] = m.map_px, mpp = m.map_m_per_px;
  const pts3 = (p) => p.map((q) => [q[0], q[1], q[2] || 0]);
  const len = (p) => { let L = 0; for (let i = 1; i < p.length; i++) L += Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]); return L; };
  const lanes = (m.lanes || []).map((l, i) => { const pts = pts3(l.pts); return { id: 'L' + i, name: l.name || '', highway: l.highway || 'secondary', lane_k: 0, length: len(pts), pts }; });
  const palette = [];
  for (const s of SHIRTS) for (const p of PANTS) for (const h of HAIR) palette.push([s, p, h]);
  // 보행로마다 길이에 비례해 걷는 사람을 둔다(약 45 m 에 한 명, 경로당 최대 6)
  const walkers = [], pal = [];
  (m.walk_paths || []).forEach((w, i) => {
    const pts = pts3(w.pts), L = len(pts);
    const n = Math.min(6, Math.max(1, Math.round(L / 45)));
    for (let k = 0; k < n; k++) { walkers.push({ id: `W${i}-${k}`, speed_mps: 1.1 + 0.3 * hash01(i * 31 + k), length_m: L, pts }); pal.push(Math.floor(hash01(i * 97 + k * 13) * palette.length)); }
  });
  const frames = [];
  for (const k of Object.keys(COLORS)) for (const col of COLORS[k]) frames.push({ kind: k, color: col });
  const anchors = {};
  // anchors_ground = 그 랜드마크가 땅에 닿는 자리(타워는 ground_px). 사람·장면 자리 찾기에 쓴다(바로가기·둘러보기는 anchors).
  const anchorsGround = {};
  for (const [k, v] of Object.entries(m.landmarks || {})) if (v && v.px) { anchors[k] = v.px; anchorsGround[k] = v.ground_px || v.px; }
  return {
    schema: 'map-json', name: m.name,
    camera: { res: [W, H], m_per_px_screen: mpp, cx: c.SX0 + W * mpp / 2, cy: c.SY1 - H * mpp / 2, cam_location: c.cam_ref, view_dir: vd, screen_x_axis: ex, screen_y_axis: ey },
    occlusion: { D0_m: m.depth.D0, step_m: m.depth.step },
    sun: m.sun || { euler_deg: [50, 0, c.theta - 73], shadow_tint: [0.6, 0.64, 0.74] },
    lanes, walkers, walker_palette: palette, walker_pal_idx: pal, standing: [],
    vehicle_specs: SPECS, vehicle_atlas: { headings: 32, frames },
    anchors, anchors_ground: anchorsGround,
  };
}
