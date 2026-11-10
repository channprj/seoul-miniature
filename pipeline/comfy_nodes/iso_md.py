"""이음매 없는 타일 생성용 ComfyUI 노드(Qwen-Image-Edit, flow matching).

하나의 큰 latent 를 공유하고, 매 스텝마다 겹치는 창(window)별로 모델을 따로 돌린 뒤 x0 예측을 가중 평균한다(MultiDiffusion).
창마다 자기 영역의 밑그림을 참조 latent 와 텍스트 인코더 입력으로 쓴다. 스텝마다 다른 격자를 쓸 수 있다(step_grids).
이미 끝난 이웃을 고정하려면 init(LATENT, noise_mask 포함)을 주면 된다(ComfyUI 의 인페인트 경로를 그대로 탄다).

spec(JSON 문자열):
  {"win": [1408, 1024],                       # 창 크기(px). 16 의 배수
   "windows": [{"x": 0, "y": 0, "prompt": "...", "grid": 0, "skip": false}, ...],   # x, y 는 8 의 배수
   "step_grids": [0, 1, 0, 1, 0, 0, 0, 0],    # 스텝별로 쓸 격자 번호
   "ramp": 16, "pow": 1.0,                    # 창 가장자리에서 가중치가 0→1 로 오르는 폭(latent px)과 지수
   "dump": "/path/prefix"}                    # 선택: 스텝마다 x0 latent 를 저장
"""
import json

import torch

import comfy.model_management
import comfy.sample
import comfy.sampler_helpers
import comfy.samplers
import comfy.utils
import latent_preview
import node_helpers
from comfy_extras.nodes_qwen import TextEncodeQwenImageEditPlus


class _Guider(comfy.samplers.CFGGuider):
    def setup(self, wins, lw, lh, step_grids, sigmas, ramp, power, dump):
        self.wins, self.lw, self.lh = wins, lw, lh
        self.step_grids, self.sig = step_grids, [float(s) for s in sigmas]
        self.ramp, self.power, self.dump = ramp, power, dump
        self.masks = {}

    def mask(self, w, H, W, device):
        """창 가장자리로 갈수록 작아지는 가중치. 캔버스 가장자리에 닿은 변은 줄이지 않는다."""
        key = (w['lx'], w['ly'])
        if key not in self.masks:
            def axis(n, at_start, at_end):
                d = torch.arange(n, dtype=torch.float32)
                a = torch.ones(n)
                r = ((d + 0.5) / self.ramp).clamp(max=1.0) ** self.power
                if not at_start: a = torch.minimum(a, r)
                if not at_end: a = torch.minimum(a, r.flip(0))
                return a.clamp(min=1e-4)
            my = axis(self.lh, w['ly'] == 0, w['ly'] + self.lh >= H)
            mx = axis(self.lw, w['lx'] == 0, w['lx'] + self.lw >= W)
            self.masks[key] = (my[:, None] * mx[None, :]).to(device)
        return self.masks[key]

    def predict_noise(self, x, timestep, model_options={}, seed=None):
        s = float(timestep.flatten()[0])
        step = min(range(len(self.sig)), key=lambda i: abs(self.sig[i] - s))
        grid = self.step_grids[min(step, len(self.step_grids) - 1)]
        H, W = x.shape[-2], x.shape[-1]
        acc = torch.zeros_like(x)
        wsum = torch.zeros((H, W), device=x.device, dtype=x.dtype)
        for w in self.wins:
            if w['grid'] != grid:
                continue
            ys, xs = slice(w['ly'], w['ly'] + self.lh), slice(w['lx'], w['lx'] + self.lw)
            xc = x[..., ys, xs]
            if w.get('skip'):
                den = w['ref_model'].to(x.device, x.dtype)
            else:
                if 'pc' not in w:
                    conds = {"positive": comfy.sampler_helpers.convert_cond(w['cond'])}
                    w['pc'] = comfy.samplers.process_conds(self.inner_model, xc, conds, x.device, latent_shapes=[xc.shape])["positive"]
                self.inner_model.latent_shapes = [xc.shape]
                den = comfy.samplers.sampling_function(self.inner_model, xc, timestep, None, w['pc'], 1.0, model_options=model_options, seed=seed)
            m = self.mask(w, H, W, x.device)
            acc[..., ys, xs] += den * m
            wsum[ys, xs] += m
            comfy.model_management.throw_exception_if_processing_interrupted()
        if float(wsum.min()) <= 0:
            raise RuntimeError(f"grid {grid} does not cover the canvas")
        out = acc / wsum
        if self.dump:
            torch.save(out.detach().float().cpu(), f"{self.dump}_x0_step{step}.pt")
        return out

    def outer_sample(self, noise, latent_image, sampler, sigmas, denoise_mask=None, callback=None, disable_pbar=False, seed=None, latent_shapes=None):
        # 메모리 추정은 캔버스 전체가 아니라 창 하나 크기로 한다(모델은 창 단위로만 돈다)
        shape = list(noise.shape[:-2]) + [self.lh, self.lw]
        self.inner_model, self.conds, self.loaded_models = comfy.sampler_helpers.prepare_sampling(self.model_patcher, shape, self.conds, self.model_options)
        device = self.model_patcher.load_device
        try:
            noise = noise.to(device=device, dtype=torch.float32)
            latent_image = latent_image.to(device=device, dtype=torch.float32)
            sigmas = sigmas.to(device)
            comfy.samplers.cast_to_load_options(self.model_options, device=device, dtype=self.model_patcher.model_dtype())
            self.model_patcher.pre_run()
            output = self.inner_sample(noise, latent_image, device, sampler, sigmas, denoise_mask, callback, disable_pbar, seed, latent_shapes=latent_shapes)
        finally:
            self.model_patcher.cleanup()
        comfy.sampler_helpers.cleanup_models(self.conds, self.loaded_models)
        del self.inner_model
        del self.loaded_models
        return output


class IsoSeamlessSample:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"model": ("MODEL",), "clip": ("CLIP",), "vae": ("VAE",), "image": ("IMAGE",),
                             "spec": ("STRING", {"multiline": True}), "seed": ("INT", {"default": 1, "min": 0, "max": 2 ** 63}),
                             "steps": ("INT", {"default": 8, "min": 1, "max": 100}),
                             "sampler_name": (comfy.samplers.KSAMPLER_NAMES,), "scheduler": (comfy.samplers.SCHEDULER_NAMES,)},
                "optional": {"init": ("LATENT",)}}

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "run"
    CATEGORY = "iso-seoul"

    def run(self, model, clip, vae, image, spec, seed, steps, sampler_name, scheduler, init=None):
        spec = json.loads(spec)
        ww, wh = spec["win"]
        lw, lh = ww // 8, wh // 8
        Hp, Wp = image.shape[1], image.shape[2]
        wins = spec["windows"]
        first = None
        for i, w in enumerate(wins):
            crop = image[:, w["y"]:w["y"] + wh, w["x"]:w["x"] + ww, :3]
            assert crop.shape[1] == wh and crop.shape[2] == ww, f"window {i} leaves the canvas"
            ref = vae.encode(crop)
            w["lx"], w["ly"] = w["x"] // 8, w["y"] // 8
            if first is None:
                first = ref
                print(f"[iso_md] canvas {Wp}x{Hp}px, window latent {tuple(ref.shape)}, {len(wins)} windows", flush=True)
            if w.get("skip"):
                w["ref_model"] = model.model.process_latent_in(ref)
            else:
                cond = TextEncodeQwenImageEditPlus.execute(clip, w["prompt"], None, crop).result[0]
                w["cond"] = node_helpers.conditioning_set_values(cond, {"reference_latents": [ref]}, append=True)
            comfy.model_management.throw_exception_if_processing_interrupted()
        shape = list(first.shape[:-2]) + [Hp // 8, Wp // 8]
        mask = None
        if init is not None:
            latent = init["samples"]
            assert list(latent.shape) == shape, f"init {tuple(latent.shape)} != canvas {shape}"
            mask = init.get("noise_mask")
        else:
            latent = torch.zeros(shape)
        noise = comfy.sample.prepare_noise(latent, seed)
        g = _Guider(model)
        any_cond = next(w["cond"] for w in wins if "cond" in w)
        g.set_conds(any_cond, any_cond)
        g.set_cfg(1.0)
        sigmas = comfy.samplers.calculate_sigmas(model.get_model_object("model_sampling"), scheduler, steps)
        g.setup(wins, lw, lh, spec.get("step_grids", [0] * steps), sigmas, spec.get("ramp", 16), spec.get("pow", 1.0), spec.get("dump"))
        cb = latent_preview.prepare_callback(model, steps)
        out = g.sample(noise, latent, comfy.samplers.sampler_object(sampler_name), sigmas, denoise_mask=mask, callback=cb, seed=seed)
        return ({"samples": out.cpu()},)


NODE_CLASS_MAPPINGS = {"IsoSeamlessSample": IsoSeamlessSample}
NODE_DISPLAY_NAME_MAPPINGS = {"IsoSeamlessSample": "Iso Seoul seamless window sampler"}
