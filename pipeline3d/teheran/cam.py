# 테헤란로 판 카메라. 여의도 cam.py 와 같은 꼴(정사투영, 고도 35°, 방위 θ)이고 판 정의와 작업 px 만 다르다.
# 판 T: 방위 θ = −24° → 카메라가 남남서쪽에서 북북동쪽을 본다(화면 오른쪽 = 동남동). 테헤란로(방위 약 69°)와 강남 격자가 화면에서 45° 로 놓이고,
#   강남역이 왼쪽 아래, 삼성역·코엑스가 오른쪽 위에 온다. 테헤란로 북쪽 건물(위워크타워 등)의 큰길 쪽 면과 선정릉 숲이 카메라를 향한다.
# 화면 3440 × 2120 m 를 여의도와 같은 캔버스(그림 22016 × 13568 px, 지도 2752 × 1696 px)에 담는다 → 그림 15.625 cm/px, 지도 1.25 m/px.
import math, numpy as np
PX = 0.078125   # 작업 px(m): 그림 px 의 절반. gen_area.py 의 X0·Y0·판 W·H 단위
def axes(theta=-24.0, tilt=55.0):
    t, a = math.radians(theta), math.radians(tilt)
    Rz = np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    R = Rz @ Rx; return R[:, 0], R[:, 1], -R[:, 2]  # 화면 오른쪽, 화면 위, 시선
BOARDS = {'T': dict(theta=-24.0, SX0=-1930.0, SY1=1010.0, W=44032, H=27136)}   # 화면 u −1930~1510 m, v −1110~1010 m (원점 = 선릉역 근처, prep 의 P3D_ORG)
class Cam:
    def __init__(s, board):
        b = BOARDS[board] if isinstance(board, str) else board; s.b = b
        s.EX, s.EY, s.VD = axes(b['theta']); s.SX0, s.SY1, s.W, s.H = b['SX0'], b['SY1'], b['W'], b['H']
    def proj(s, p):  # 월드(m) → 작업 px
        p = np.asarray(p, float); return (p @ s.EX - s.SX0) / PX, (s.SY1 - p @ s.EY) / PX
    def unproj(s, X, Y, z=0.0):  # 작업 px + 높이 z → 월드 점
        u = s.SX0 + X * PX - s.EX[2] * z; v = s.SY1 - Y * PX - s.EY[2] * z
        x, y = np.linalg.solve(np.array([[s.EX[0], s.EX[1]], [s.EY[0], s.EY[1]]]), [u, v]); return (float(x), float(y), z)
