// 화면 갈무리. WebGL 은 한 턴이 끝나면 버퍼를 비우므로(preserveDrawingBuffer: false),
// draw() 가 돌아온 직후 같은 턴에 2D 캔버스로 옮기고 아래 띠에 출처를 적는다.
// 인앱 브라우저는 내려받기가 막혀 있어, 그때는 길게 눌러 저장하는 겹침을 띄운다.
const IN_APP = ['kakaotalk', 'instagram', 'fban', 'fbav', 'line/', 'naver(inapp', 'twitter', 'daumapps'];
const BAND = 'rgba(14,18,28,0.72)';
const INK = '#e9edf5';
const FLASH_MS = 1600;
const REVOKE_MS = 10000;

// ── 순수 로직(test/snap.test.js)

function clamp(n, lo, hi) {
  return Math.min(hi, Math.max(lo, n));
}

// 장치 픽셀 w×h 에서 아래 띠. 높이는 세로의 3.5%(22~64). 가로는 띠 크기에 안 쓴다.
export function stripLayout(w, h) {
  const bandH = clamp(Math.round(h * 0.035), 22, 64);
  return { bandH, font: Math.round(bandH * 0.5), pad: Math.round(bandH * 0.4) };
}

// 로컬 시각. seoul-miniature-YYYYMMDD-HHMMSS.png
export function snapName(date) {
  const p = (n) => String(n).padStart(2, '0');
  return `seoul-miniature-${date.getFullYear()}${p(date.getMonth() + 1)}${p(date.getDate())}-${p(date.getHours())}${p(date.getMinutes())}${p(date.getSeconds())}.png`;
}

// 카카오톡·인스타·페이스북(FBAN/FBAV)·라인·네이버·트위터·다음 인앱. 대소문자 무시, 부분 문자열.
export function isInApp(ua = navigator.userAgent) {
  const s = String(ua).toLowerCase();
  return IN_APP.some((k) => s.includes(k));
}

// ── 브라우저 쪽. 불러올 때는 document 를 건드리지 않는다.

// measureText 로 한 글자씩 줄여 maxW 안에 넣는다. 넘치면 끝에 '…'.
function ellipsize(g, text, maxW) {
  if (!text || maxW <= 0) return '';
  if (g.measureText(text).width <= maxW) return text;
  const ell = '…';
  if (g.measureText(ell).width > maxW) return '';
  let s = text;
  while (s.length && g.measureText(s + ell).width > maxW) s = s.slice(0, -1);
  return s + ell;
}

// 한 줄에 다 들어가면 알림(왼쪽)·사이트(오른쪽). 안 들어가면 알림을 ' · ' 경계에서 여러 줄로 나누고
// 사이트를 맨 아래 줄에 둔다 → 좁은 화면에서도 출처 표기가 잘리지 않는다(한 조각이 폭보다 길 때만 줄인다).
export function wrapParts(parts, fits) {
  const lines = [];
  let cur = '';
  for (const p of parts) {
    const next = cur ? `${cur} · ${p}` : p;
    if (cur && !fits(next)) { lines.push(cur); cur = p; } else cur = next;
  }
  if (cur) lines.push(cur);
  return lines;
}
function paintBand(g, w, h, opts) {
  const { bandH, font, pad } = stripLayout(w, h);
  g.font = `${font}px system-ui, sans-serif`;
  g.textBaseline = 'middle';
  g.direction = 'ltr';
  const inner = Math.max(0, w - pad * 2);
  const wd = (t) => g.measureText(t).width;
  const site = ellipsize(g, String(opts.site ?? ''), inner);
  const notice = String(opts.notice ?? '');
  const one = wd(notice) + (site ? wd(site) + pad : 0) <= inner;
  const lines = one ? [] : wrapParts(notice.split(' · ').filter(Boolean), (t) => wd(t) <= inner).map((t) => ellipsize(g, t, inner));
  if (!one && site) lines.push(site);
  const lineH = Math.round(font * 1.45);
  const H = one ? bandH : lines.length * lineH + Math.round(pad * 0.9);
  g.fillStyle = BAND;
  g.fillRect(0, h - H, w, H);
  g.fillStyle = INK;
  if (one) {
    const y = h - H / 2;
    if (notice) { g.textAlign = 'left'; g.fillText(notice, pad, y); }
    if (site) { g.textAlign = 'right'; g.fillText(site, w - pad, y); }
  } else {
    g.textAlign = 'left';
    const top = h - H + (H - lines.length * lineH) / 2;
    lines.forEach((t, i) => g.fillText(t, pad, top + lineH * (i + 0.5)));
  }
}

export function captureCanvas(canvas, draw, opts) {
  const out = document.createElement('canvas');
  draw();                                         // 이 호출과 drawImage 사이에 await·rAF 를 넣지 않는다
  out.width = canvas.width;                       // 크기를 바꾸면 2D 상태가 리셋되므로, 컨텍스트는 그 다음에 얻는다
  out.height = canvas.height;
  const g = out.getContext('2d');
  g.drawImage(canvas, 0, 0);
  paintBand(g, out.width, out.height, opts || {});
  return out;
}

function blobFromDataUrl(url) {
  const comma = url.indexOf(',');
  const meta = url.slice(0, comma);
  const data = url.slice(comma + 1);
  const mime = (meta.match(/^data:([^;,]*)/) || [])[1] || 'image/png';
  const bin = atob(data);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

// toBlob 은 콜백이라 Promise 로 감싼다. null 이거나 없으면 dataURL 로 만든다.
function pngBlob(cnv) {
  return new Promise((resolve, reject) => {
    const viaUrl = () => {
      try { resolve(blobFromDataUrl(cnv.toDataURL('image/png'))); }
      catch (e) { reject(e); }
    };
    if (typeof cnv.toBlob !== 'function') { viaUrl(); return; }
    cnv.toBlob((b) => { if (b) resolve(b); else viaUrl(); }, 'image/png');
  });
}

function triggerDownload(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), REVOKE_MS);
}

let overlayUrl = '';

function dismissOverlay() {
  const prev = document.getElementById('snap-view');
  if (!prev) return;
  prev.remove();
  if (overlayUrl) { URL.revokeObjectURL(overlayUrl); overlayUrl = ''; }
}

export function showOverlay(url) {
  dismissOverlay();
  overlayUrl = url;
  const root = document.createElement('div');
  root.id = 'snap-view';
  // body 가 -webkit-touch-callout:none 이라(style.css), 그림만 길게 누르기가 되게 인라인으로 되돌린다.
  root.style.cssText = 'position:fixed;left:0;top:0;right:0;bottom:0;z-index:50;background:rgba(6,8,14,0.88);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:16px;box-sizing:border-box;overflow:auto';
  const img = document.createElement('img');
  img.alt = '서울 미니어처';
  img.style.cssText = 'max-width:92vw;max-height:80vh;object-fit:contain;-webkit-touch-callout:default';
  img.src = url;
  const hint = document.createElement('p');
  hint.textContent = '이미지를 길게 눌러 저장하세요';
  hint.style.cssText = 'margin:0;color:#e9edf5;font:14px system-ui,sans-serif;text-align:center';
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.textContent = '닫기';
  btn.style.cssText = 'font:600 14px system-ui,sans-serif;color:#2a1a05;background:#ffb454;border:0;border-radius:11px;padding:8px 16px;min-height:40px;cursor:pointer';
  const close = () => {
    if (root.isConnected) root.remove();
    if (overlayUrl === url) { URL.revokeObjectURL(url); overlayUrl = ''; }
  };
  root.addEventListener('click', (e) => { if (e.target === root) close(); });
  btn.addEventListener('click', close);
  root.appendChild(img);
  root.appendChild(hint);
  root.appendChild(btn);
  document.body.appendChild(root);
}

export async function shareOrSave(cnv, opts = {}) {
  const blob = await pngBlob(cnv);
  const name = opts.fileName || snapName(new Date());
  // File·canShare 가 던지면 공유를 건너뛰고 저장으로 간다. share() 의 AbortError 만 취소.
  try {
    const file = new File([blob], name, { type: 'image/png' });
    // 공유 시트는 터치 기기에서만(데스크톱은 바로 내려받는 편이 낫다)
    const touch = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
    if (touch && navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: '서울 미니어처' });
        return 'shared';
      } catch (e) {
        if (e && e.name === 'AbortError') return 'cancelled';
      }
    }
  } catch { /* 이 브라우저는 파일 공유를 못 한다 */ }
  if (!isInApp()) {
    triggerDownload(blob, name);
    return 'saved';
  }
  showOverlay(URL.createObjectURL(blob));
  return 'shown';
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

export function initSnap(button, canvas, draw, opts) {
  const label = button.textContent;
  let busy = false;
  button.onclick = async () => {
    if (busy) return;
    busy = true;
    button.disabled = true;
    try {
      const shot = captureCanvas(canvas, draw, opts);   // 클릭 턴 안에서 동기 호출(사용자 제스처·WebGL 버퍼)
      const how = await shareOrSave(shot, opts);
      if (how === 'shared' || how === 'saved' || how === 'shown') {
        if (how !== 'shown') { button.textContent = how === 'shared' ? '공유됨' : '저장됨'; await wait(FLASH_MS); }
      }
    } catch (e) {
      console.warn(e);
    } finally {
      button.textContent = label;
      button.disabled = false;
      busy = false;
    }
  };
}
