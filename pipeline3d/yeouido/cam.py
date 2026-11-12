# 여의도 판 카메라: 정사투영, 고도 35°, 방위 θ(블렌더 카메라 z 회전). θ=135 → 카메라가 북동쪽에서 남서쪽을 본다.
import math, numpy as np
PX = 0.0625  # 작업 해상도 m/px (최종 0.5 m/px 의 1/8)
def axes(theta=135.0, tilt=55.0):
    t, a = math.radians(theta), math.radians(tilt)
    Rz = np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    R = Rz @ Rx; return R[:, 0], R[:, 1], -R[:, 2]  # 화면 오른쪽, 화면 위, 시선
# 판(board): 화면 좌표(m) 왼쪽 위 (SX0, SY1), 크기 W×H(6.25 cm px)
BOARDS = {
    'A': dict(theta=135.0, SX0=-330.0, SY1=860.0, W=30720, H=21760),   # 1920 m × 1360 m 화면, 0.5 m 판 3840×2720
    'B': dict(theta=135.0, SX0=-760.0, SY1=900.0, W=44032, H=27136),   # 2752 m × 1696 m 화면(상한), 0.5 m 판 5504×3392
    'C': dict(theta=135.0, SX0=-130.0, SY1=1060.0, W=44032, H=27136),   # [2차] 국회의사당~63빌딩: 화면 u −130~2622 m, v −636~1060 m(상한). 섬 동·서 끝 일부를 자름
    'D': dict(theta=135.0, SX0=-900.0, SY1=1060.0, W=57600, H=27136),  # [2차 대안] C + 동쪽 한강철교까지: 화면 3600 m — 6.25 cm 상한(44032) 초과 31%, 사용자 결정용 미리보기만
}
class Cam:
    def __init__(s, board):
        b = BOARDS[board] if isinstance(board, str) else board; s.b = b
        s.EX, s.EY, s.VD = axes(b['theta']); s.SX0, s.SY1, s.W, s.H = b['SX0'], b['SY1'], b['W'], b['H']
    def proj(s, p):  # 월드(m) → 6.25 cm 캔버스 px
        p = np.asarray(p, float); return (p @ s.EX - s.SX0) / PX, (s.SY1 - p @ s.EY) / PX
    def unproj(s, X, Y, z=0.0):  # 캔버스 px + 높이 z → 월드 점
        u = s.SX0 + X * PX - s.EX[2] * z; v = s.SY1 - Y * PX - s.EY[2] * z
        x, y = np.linalg.solve(np.array([[s.EX[0], s.EX[1]], [s.EY[0], s.EY[1]]]), [u, v]); return (float(x), float(y), z)

# [5차] 격자 도로가 화면 가로·세로로 놓이지 않게 방위를 45° 돌린 판. 중심은 C 판의 화면 중심이 가리키는 지면 점.
def _rot(theta, name):
    c = Cam('C'); w = np.array(c.unproj(c.W / 2, c.H / 2)); ex, ey, _ = axes(theta)
    BOARDS[name] = dict(theta=theta, SX0=float(w @ ex) - c.W * PX / 2, SY1=float(w @ ey) + c.H * PX / 2, W=c.W, H=c.H)
_rot(90.0, 'E'); _rot(180.0, 'F')
# [5차] F 를 화면 아래로 192 m 옮김(0.5 m 판 384 px): 밤섬 두 섬(옮기기 전 y 3019–3739 / 3392)이 판 안에 다 들어오게. 위쪽은 샛강 둑(y 71)·63 꼭대기(y 157)까지 남는다.
BOARDS['F']['SY1'] -= 192.0
