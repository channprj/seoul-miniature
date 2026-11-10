"""스텝 단위 작업 큐의 워커 쪽 노드. 작업 파일(JSON) 목록을 받아 하나씩 처리하고 결과를 공유 폴더에 쓴다(쓰기는 임시 파일 → rename).

작업 종류:
  enc: 창 그림(PNG)을 VAE 인코드하고 프롬프트와 함께 텍스트 인코드 → 조건(.pt). skip 창은 x0(.npy)만.
  den: 조건 + 잠재값 조각(.npy, 모델 공간) + sigma → 그 창의 x0 예측(.npy, 모델 공간). 모델을 한 번만 부른다.
  dec: 잠재값 조각(.npy, 모델 공간) → PNG
"""
import json
import os

import numpy as np
import torch
from PIL import Image

import comfy.samplers
import node_helpers
from comfy_extras.nodes_qwen import TextEncodeQwenImageEditPlus


def _np_save(path, arr):
    tmp = path + '.tmp.npy'
    np.save(tmp, arr); os.replace(tmp, path)


def _img(path):
    return torch.from_numpy(np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0)[None]


def _one(model, x, sigmas, extra_args=None, callback=None, disable=None):
    return model(x, sigmas[0] * x.new_ones([x.shape[0]]), **(extra_args or {}))


class IsoHDTasks:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"model": ("MODEL",), "clip": ("CLIP",), "vae": ("VAE",), "tasks": ("STRING", {"multiline": True})}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "run"
    CATEGORY = "iso-seoul"
    OUTPUT_NODE = True

    def run(self, model, clip, vae, tasks):
        done = []
        for p in json.loads(tasks):
            t = json.load(open(p))
            if os.path.exists(t['out']):
                done.append(t['out']); continue
            if t['type'] == 'enc':
                img = _img(t['image'])
                ref = vae.encode(img[:, :, :, :3])
                if t.get('skip'):
                    _np_save(t['out'], model.model.process_latent_in(ref).float().cpu().numpy())
                else:
                    img2 = _img(t['image2']) if t.get('image2') else None
                    cond = TextEncodeQwenImageEditPlus.execute(clip, t['prompt'], None, img, img2).result[0]
                    cond = node_helpers.conditioning_set_values(cond, {"reference_latents": [ref.cpu()]}, append=True)
                    cond = [[c[0].detach().half().cpu(), {k: (v.detach().cpu() if torch.is_tensor(v) else v) for k, v in c[1].items()}] for c in cond]
                    torch.save(cond, t['out'] + '.tmp'); os.replace(t['out'] + '.tmp', t['out'])
            elif t['type'] == 'den':
                cond = torch.load(t['cond'], weights_only=False)
                cond = [[c[0].float(), c[1]] for c in cond]
                x = torch.from_numpy(np.load(t['x'])).float()
                sigma = float(t['sigma'])
                g = comfy.samplers.CFGGuider(model)
                g.set_conds(cond, cond); g.set_cfg(1.0)
                # 잠재값을 그대로 넣는다: noise_scaling = sigma*noise + (1-sigma)*0 → x
                out = g.sample(x / sigma, torch.zeros_like(x), comfy.samplers.KSAMPLER(_one), torch.tensor([sigma, 0.0]), seed=0, disable_pbar=True)
                _np_save(t['out'], model.model.process_latent_in(out).float().cpu().numpy())
            elif t['type'] == 'dec':
                lat = torch.from_numpy(np.load(t['x'])).float()
                im = vae.decode(model.model.process_latent_out(lat))
                im = im.reshape(-1, im.shape[-3], im.shape[-2], im.shape[-1])[0]
                arr = (im.clamp(0, 1).cpu().numpy() * 255.0 + 0.5).astype(np.uint8)
                Image.fromarray(arr).save(t['out'] + '.tmp.png', compress_level=1); os.replace(t['out'] + '.tmp.png', t['out'])
            done.append(t['out'])
        return {"ui": {"text": [str(len(done))]}, "result": (json.dumps(done),)}


NODE_CLASS_MAPPINGS = {"IsoHDTasks": IsoHDTasks}
NODE_DISPLAY_NAME_MAPPINGS = {"IsoHDTasks": "Iso Seoul HD queue tasks"}
