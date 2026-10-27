"""Лицо с фотографии на текстуру головы 3D-модели.

Точки MediaPipe ищутся на виде модели спереди (front-render.mjs) и на фото; каждый тексель лица,
видимый спереди, переносится кусочно-аффинно по треугольникам этих точек. Тон всей кожи сводится
к тону фото, край лица мягкий, глаза модели остаются своими (на фото там глаза, а не кожа).
"""
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from scipy.spatial import Delaunay

S, W, H, YT = 2500., 560, 900, 1.8          # кадр front-render.mjs


def _landmarker(model_path):
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    opts = vision.FaceLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=str(model_path)),
                                        running_mode=vision.RunningMode.IMAGE, num_faces=1,
                                        min_face_detection_confidence=.2, min_face_presence_confidence=.2)
    lm = vision.FaceLandmarker.create_from_options(opts)

    def detect(im, box, face_px):
        w, h = im.size
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        s = face_px / (x1 - x0)
        crop = im.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.LANCZOS)
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.array(crop)))
        if not r.face_landmarks: return None
        cw, ch = crop.size
        return np.array([[x0 + p.x * cw / s, y0 + p.y * ch / s] for p in r.face_landmarks[0]])

    def points(im):
        """грубо по кадру, затем точно по области вокруг лица"""
        w, h = im.size
        P = detect(im, (0, 0, w, h), 1000)
        if P is None: raise SystemExit("лицо не найдено")
        (fx0, fy0), (fx1, fy1) = P.min(0), P.max(0)
        mx, my = (fx1 - fx0) * .6, (fy1 - fy0) * .6
        P2 = detect(im, (fx0 - mx, fy0 - my, fx1 + mx, fy1 + my), 1000)
        return P if P2 is None else P2
    return points, lm


def _loop(name):
    from mediapipe.tasks.python.vision import FaceLandmarksConnections as C
    es = [(c.start, c.end) for c in getattr(C, name)]
    nb = {}
    for a, b in es: nb.setdefault(a, []).append(b); nb.setdefault(b, []).append(a)
    out, prev = [es[0][0]], None
    while True:
        n = [v for v in nb[out[-1]] if v != prev]
        if not n or n[0] == out[0]: break
        prev = out[-1]; out.append(n[0])
    return out


def lin(c): return np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4)
def srgb(c): c = np.clip(c, 0, 1); return np.where(c <= .0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - .055)


def project(skin, A, front_png, front_z, photo_path, model_path):
    """skin: текстура тела (N,N,3) 0..1; A: карта развёртки тела в метрах (uvmap.mjs ... world) -> новая текстура"""
    N = skin.shape[0]
    cov = A[..., 6] == 1
    photo = np.asarray(Image.open(photo_path).convert("RGB"), np.float32) / 255
    front = np.asarray(Image.open(front_png).convert("RGB"), np.float32) / 255
    zb = np.fromfile(front_z, dtype=np.float32).reshape(H, W)
    points, lm = _landmarker(model_path)
    Lm = points(Image.open(front_png).convert("RGB"))
    Lp = points(Image.open(photo_path).convert("RGB"))
    lm.close()
    oval = _loop("FACE_LANDMARKS_FACE_OVAL")

    # контур чуть уже лица: по краям на фото пряди и тени от волос, там остаётся кожа модели в её тоне
    cO = Lm[oval].mean(0); OV = Lm[oval] - cO
    OV[:, 0] *= .88; OV[:, 1] *= np.where(OV[:, 1] < 0, .93, .99)
    m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).polygon([tuple(v) for v in OV + cO], fill=255)
    edge = ndi.distance_transform_edt(np.asarray(m) > 0)

    # на фото: глаза (у модели свои глазные яблоки) и тёмные пряди у края лица не переносим
    ph, pw = photo.shape[:2]
    em = Image.new("L", (pw, ph), 0); d = ImageDraw.Draw(em)
    for n in ("FACE_LANDMARKS_LEFT_EYE", "FACE_LANDMARKS_RIGHT_EYE"):
        d.polygon([tuple(Lp[i]) for i in _loop(n)], fill=255)
    eyes = ndi.gaussian_filter(ndi.binary_dilation(np.asarray(em) > 0, iterations=2).astype(np.float32), 1.2)
    pm = Image.new("L", (pw, ph), 0); ImageDraw.Draw(pm).polygon([tuple(Lp[i]) for i in oval], fill=255)
    pin = np.asarray(pm) > 0
    pedge = ndi.distance_transform_edt(pin)
    luma = np.array([.299, .587, .114], np.float32)
    rlum = np.median(photo[pin & (pedge > 25)].reshape(-1, 3), 0) @ luma
    dark = np.clip((rlum * .82 - photo @ luma) / (rlum * .2), 0, 1)
    hair = ndi.gaussian_filter(dark * np.clip(1 - (pedge - 10) / 18, 0, 1), 1.5)

    # тексели головы, видимые спереди
    x, y, z, nz = A[..., 0], A[..., 1], A[..., 2], A[..., 5]
    px = np.nan_to_num(x * S + W / 2, nan=-1); py = np.nan_to_num((YT - y) * S, nan=-1)
    ix = np.clip(np.round(px).astype(int), 0, W - 1); iy = np.clip(np.round(py).astype(int), 0, H - 1)
    vis = cov & (y > 1.45) & (nz > .05) & (z >= zb[iy, ix] - .004) & (px >= 0) & (px < W) & (py >= 0) & (py < H)
    tri = Delaunay(Lm)
    pts = np.stack([px[vis], py[vis]], 1)
    s = tri.find_simplex(pts); ok = s >= 0; pts = pts[ok]; s = s[ok]

    def to_photo(p, s):
        T = tri.transform[s]; bc = np.einsum("nij,nj->ni", T[:, :2], p - T[:, 2])
        return np.einsum("ni,nij->nj", np.c_[bc, 1 - bc.sum(1)], Lp[tri.simplices[s]])

    def sample(img, q, order=1):
        if img.ndim == 2: return ndi.map_coordinates(img, [q[:, 1], q[:, 0]], order=order, mode="nearest")
        return np.stack([ndi.map_coordinates(img[..., c], [q[:, 1], q[:, 0]], order=order, mode="nearest") for c in range(3)], 1)

    q = to_photo(pts, s)
    # правая сторона лица на фото закрыта прядью: её внешнюю часть берём зеркально с левой стороны
    pm2 = pts.copy(); pm2[:, 0] = W - pm2[:, 0]
    s2 = tri.find_simplex(pm2); s2[s2 < 0] = s[s2 < 0]
    qm = to_photo(pm2, s2)
    half = (Lm[oval, 0].max() - Lm[oval, 0].min()) / 2
    mw = np.clip(((W / 2 - pts[:, 0]) / half - .3) / .25, 0, 1)[:, None]
    col = sample(photo, q) * (1 - mw) + sample(photo, qm) * mw
    q = q * (1 - mw) + qm * mw
    w = (np.clip(edge[np.round(pts[:, 1]).astype(int), np.round(pts[:, 0]).astype(int)] / 24, 0, 1) ** 1.5
         * np.clip((nz[vis][ok] - .1) / .3, 0, 1) * (1 - np.clip(sample(eyes, q) * 1.5, 0, 1)) * (1 - np.clip(sample(hair, q) * 1.6, 0, 1)))

    # тон: щёки и лоб фото против модели, сводим навстречу друг другу
    def mean_at(img, P, r):
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        return lin(np.concatenate([img[np.clip((cy + yy).astype(int), 0, img.shape[0] - 1),
                                       np.clip((cx + xx).astype(int), 0, img.shape[1] - 1)].reshape(-1, 3)
                                   for cx, cy in P[[50, 280, 101, 330, 151, 9]]])).mean(0)
    gain = mean_at(photo, Lp, 3) / mean_at(front, Lm, 7)
    out = srgb(lin(skin) * gain ** .5)
    col = srgb(lin(col) * gain ** -.5)
    t = np.argwhere(vis)[ok]
    out[t[:, 0], t[:, 1]] = out[t[:, 0], t[:, 1]] * (1 - w[:, None]) + col * w[:, None]
    return out
