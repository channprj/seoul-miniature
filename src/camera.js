// 팬·줌 카메라. 포인터 중심 연속(소수 배율) 줌, 드래그 관성, 핀치, 경계 처리.
// 내부 상태: 화면 중심의 지도 좌표(cx, cy)와 zoom(CSS px / 지도 px).
export function createCamera(canvas, W, H) {
  const cam = {
    cx: W / 2, cy: H / 2, zoom: 1, dpr: 1, onUserInput: null,
    _tz: 1, _ax: 0, _ay: 0, _amx: 0, _amy: 0, _zooming: false, _vx: 0, _vy: 0, _locked: false, _fly: null, _minZ: 0.2, _maxZ: 9,
    // 휴대폰 경로에서 main 이 정한다. maxScale = 최대 배율(기기 px / 지도 px), tapSteps = 터치 더블탭이 멈추는 배율들(오름차순)
    maxScale: 0, tapSteps: null,
  };
  let cssW = 1, cssH = 1;

  cam.resize = () => {
    cam.dpr = Math.min(2, window.devicePixelRatio || 1);
    cssW = canvas.clientWidth; cssH = canvas.clientHeight;
    canvas.width = Math.round(cssW * cam.dpr); canvas.height = Math.round(cssH * cam.dpr);
    cam._minZ = Math.min(cssW / W, cssH / H) * 0.82;
    if (cam.maxScale) cam._maxZ = Math.max(cam._minZ, cam.maxScale / cam.dpr);
    cam._tz = Math.min(cam._maxZ, cam._tz); cam.zoom = Math.min(cam._maxZ, cam.zoom);
    cam._tz = Math.max(cam._minZ, cam._tz); cam.zoom = Math.max(cam._minZ, cam.zoom);
  };
  // vh = 화면 세로에 들어오는 지도 px 수
  cam.set = (x, y, vh) => { cam.cx = x; cam.cy = y; cam.zoom = cam._tz = Math.min(cam._maxZ, cssH / vh); cam._vx = cam._vy = 0; cam._zooming = false; };
  cam.lock = (on) => { cam._locked = on; cam._fly = null; };
  cam.flyTo = (x, y, vh, dur = 1.6) => {
    cam._fly = { t: 0, dur, x0: cam.cx, y0: cam.cy, z0: Math.log(cam.zoom), x1: x, y1: y, z1: Math.log(Math.min(cam._maxZ, cssH / vh)) };
    cam._vx = cam._vy = 0; cam._zooming = false;
  };
  cam.view = () => {
    const scale = cam.zoom * cam.dpr;
    return { scale, originX: cam.cx - canvas.width / 2 / scale, originY: cam.cy - canvas.height / 2 / scale };
  };
  const toMap = (sx, sy) => [cam.cx + (sx - cssW / 2) / cam.zoom, cam.cy + (sy - cssH / 2) / cam.zoom];
  const clamp = () => { cam.cx = Math.min(W, Math.max(0, cam.cx)); cam.cy = Math.min(H, Math.max(0, cam.cy)); };

  cam.update = (dt) => {
    if (cam._fly) {
      const f = cam._fly; f.t += dt;
      const u = Math.min(1, f.t / f.dur), e = u * u * u * (u * (u * 6 - 15) + 10);
      // 멀리 날아갈 때는 중간에 살짝 물러난다
      const dist = Math.hypot(f.x1 - f.x0, f.y1 - f.y0);
      const lift = Math.sin(Math.PI * u) * Math.min(0.9, dist / 2200);
      cam.cx = f.x0 + (f.x1 - f.x0) * e; cam.cy = f.y0 + (f.y1 - f.y0) * e;
      cam.zoom = cam._tz = Math.exp(f.z0 + (f.z1 - f.z0) * e - lift);
      if (u >= 1) cam._fly = null;
      return;
    }
    if (cam._zooming) {
      const k = 1 - Math.exp(-dt * 16);
      const z = Math.exp(Math.log(cam.zoom) + (Math.log(cam._tz) - Math.log(cam.zoom)) * k);
      cam.zoom = z;
      // 기준점(포인터 아래 지도 좌표)이 같은 화면 위치에 남도록 중심을 옮긴다
      cam.cx = cam._amx - (cam._ax - cssW / 2) / z; cam.cy = cam._amy - (cam._ay - cssH / 2) / z;
      if (Math.abs(Math.log(cam._tz / z)) < 1e-4) { cam.zoom = cam._tz; cam._zooming = false; }
    }
    if (!dragging && (cam._vx || cam._vy)) {
      cam.cx += cam._vx * dt; cam.cy += cam._vy * dt;
      const d = Math.exp(-dt * 4.5); cam._vx *= d; cam._vy *= d;
      if (Math.hypot(cam._vx, cam._vy) * cam.zoom < 4) cam._vx = cam._vy = 0;
    }
    clamp();
  };

  // 터치 더블탭 확대 폭: tapSteps 가 있으면 지금보다 15 % 이상 큰 다음 단계까지(한 번에 최대 3배).
  // 단계를 정수 배율로 두면 원본 텍셀이 기기 px 정수배에 멈춰 픽셀 크기가 고르다. 없으면 1.8배.
  const tapFactor = () => {
    const st = cam.tapSteps;
    if (!st) return 1.8;
    const s = cam._tz * cam.dpr, next = st.find((v) => v > s * 1.15);
    return next ? Math.min(3, next / s) : 1;
  };
  const input = () => { cam._fly = null; cam.onUserInput?.(); };
  const zoomAt = (sx, sy, factor) => {
    if (cam._locked) { input(); if (cam._locked) return; }
    input();
    const [mx, my] = toMap(sx, sy);
    cam._ax = sx; cam._ay = sy; cam._amx = mx; cam._amy = my;
    cam._tz = Math.min(cam._maxZ, Math.max(cam._minZ, cam._tz * factor));
    cam._zooming = true; cam._vx = cam._vy = 0;
  };
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const unit = e.deltaMode === 1 ? 16 : 1;
    const k = e.ctrlKey ? 0.012 : 0.0022;         // ctrlKey = 트랙패드 핀치
    zoomAt(e.clientX, e.clientY, Math.exp(-e.deltaY * unit * k));
  }, { passive: false });

  // 포인터: 1개 = 드래그, 2개 = 핀치(두 손가락 중점 기준). 이동 거리로 탭과 드래그를 가른다.
  // 탭은 cam.onTap(x, y, 포인터 종류) 로 알리고, 터치 더블탭은 그 자리를 확대한다(iOS 는 dblclick 을 안 준다).
  const pts = new Map();
  let dragging = false, lastT = 0, pinch0 = 0;
  let down = null, lastTap = null, lastType = 'mouse';
  const TAP_PX = 10, TAP_MS = 350;
  const mid = () => { const [a, b] = [...pts.values()]; return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.hypot(a[0] - b[0], a[1] - b[1])]; };
  canvas.addEventListener('pointerdown', (e) => {
    try { canvas.setPointerCapture(e.pointerId); } catch { /* 합성 이벤트 */ }
    pts.set(e.pointerId, [e.clientX, e.clientY]);
    lastType = e.pointerType || 'mouse';
    // 두 번째 손가락이 닿으면 탭 후보는 버린다
    down = pts.size === 1 ? { x: e.clientX, y: e.clientY, t: performance.now(), moved: 0 } : null;
    input();
    if (cam._locked) return;
    dragging = true; cam._vx = cam._vy = 0; cam._zooming = false; cam._tz = cam.zoom; lastT = performance.now();
    canvas.classList.add('drag');
    if (pts.size === 2) pinch0 = mid()[2];
  });
  canvas.addEventListener('pointermove', (e) => {
    const p = pts.get(e.pointerId);
    if (!p) return;
    const dx = e.clientX - p[0], dy = e.clientY - p[1];
    if (down) down.moved = Math.max(down.moved, Math.hypot(e.clientX - down.x, e.clientY - down.y));
    if (cam._locked) { p[0] = e.clientX; p[1] = e.clientY; return; }
    if (pts.size === 1) {
      p[0] = e.clientX; p[1] = e.clientY;
      cam.cx -= dx / cam.zoom; cam.cy -= dy / cam.zoom;
      const now = performance.now(), dt = Math.max(1, now - lastT) / 1000; lastT = now;
      // 관성용 속도(지수 평활)
      cam._vx = cam._vx * 0.6 + (-dx / cam.zoom / dt) * 0.4; cam._vy = cam._vy * 0.6 + (-dy / cam.zoom / dt) * 0.4;
    } else if (pts.size === 2) {
      // 움직이기 전 중점 아래의 지도 점을 새 중점·새 배율에서도 같은 자리에 둔다(이동 + 확대가 한 번에)
      const [m0x, m0y] = mid();
      const [wx, wy] = toMap(m0x, m0y);
      p[0] = e.clientX; p[1] = e.clientY;
      const [mx, my, dist] = mid();
      if (pinch0 > 0) {
        const z = Math.min(cam._maxZ, Math.max(cam._minZ, cam.zoom * dist / pinch0));
        cam.zoom = cam._tz = z;
      }
      cam.cx = wx - (mx - cssW / 2) / cam.zoom; cam.cy = wy - (my - cssH / 2) / cam.zoom;
      pinch0 = dist; cam._vx = cam._vy = 0;
    } else { p[0] = e.clientX; p[1] = e.clientY; }
    clamp();
  });
  const up = (e) => {
    const had = pts.delete(e.pointerId);
    if (pts.size === 0) {
      dragging = false; canvas.classList.remove('drag');
      if (performance.now() - lastT > 80) cam._vx = cam._vy = 0;   // 멈췄다 뗀 경우 관성 없음
      const now = performance.now();
      if (had && down && e.type === 'pointerup' && down.moved < TAP_PX && now - down.t < TAP_MS) {
        cam._vx = cam._vy = 0;
        const touch = (e.pointerType || lastType) !== 'mouse';
        if (touch && lastTap && now - lastTap.t < 320 && Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) < 30) {
          lastTap = null; zoomAt(e.clientX, e.clientY, tapFactor());
        } else {
          lastTap = { x: e.clientX, y: e.clientY, t: now };
          cam.onTap?.(e.clientX, e.clientY, e.pointerType || lastType);
        }
      }
      down = null;
    } else if (pts.size === 1) { cam._vx = cam._vy = 0; lastT = performance.now(); down = null; }
  };
  canvas.addEventListener('pointerup', up);
  canvas.addEventListener('pointercancel', up);
  // 마우스 더블클릭만. 터치는 위의 더블탭이 처리한다(안드로이드 크롬이 dblclick 도 주면 두 번 확대되므로)
  canvas.addEventListener('dblclick', (e) => { if (lastType === 'mouse') zoomAt(e.clientX, e.clientY, 1.8); });
  return cam;
}
