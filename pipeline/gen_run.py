#!/usr/bin/env python3
"""생성 장비의 ComfyUI(127.0.0.1:8188)에 Qwen-Image-Edit-2511(Apache-2.0) 편집 작업을 보낸다.

  python3 gen_run.py jobs.json
jobs.json = [{"name": "t1", "image": "guide_color.png", "prompt": "...", "seed": 1, "steps": 8,
              "width": 1376, "height": 848,          # 출력 크기(생략 시 입력 크기)
              "init": "prev.png", "denoise": 0.6,    # 선택: img2img 초기 이미지
              "lora": "8",                             # "8" | "4" | "" (LoRA 없음 → steps/cfg 직접 지정)
              "ref": "photo.jpg"}]                     # 선택: 생김새 참조 사진(image2). 텍스트 인코더에만 보여 준다(구도는 image1 이 정한다)
입력은 in/, 출력은 out/<name>_*.png.
"""
import json, sys, time, urllib.request

URL = "http://127.0.0.1:8188"
LORA = {"8": "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors", "4": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"}

def graph(j):
    lora = j.get("lora", "8")
    g = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": j.get("unet", "qwen_image_edit_2511_fp8mixed.safetensors"), "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "img0": {"class_type": "LoadImage", "inputs": {"image": j["image"]}},
    }
    model = ["unet", 0]
    if lora:
        g["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model, "lora_name": LORA[lora], "strength_model": 1.0}}
        model = ["lora", 0]
    g["ms"] = {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": model, "shift": j.get("shift", 3.1)}}
    g["cn"] = {"class_type": "CFGNorm", "inputs": {"model": ["ms", 0], "strength": 1.0}}
    img = ["img0", 0]
    if "width" in j:
        g["scale"] = {"class_type": "ImageScale", "inputs": {"image": img, "upscale_method": j.get("resample", "lanczos"), "width": j["width"], "height": j["height"], "crop": "disabled"}}
        img = ["scale", 0]
    g["refl"] = {"class_type": "VAEEncode", "inputs": {"pixels": img, "vae": ["vae", 0]}}
    # 텍스트 인코더에는 이미지를 보여 주되(내부에서 축소됨), 참조 latent 는 원해상도로 따로 붙인다
    g["pos0"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "prompt": j["prompt"], "image1": img}}
    if j.get("ref"):
        g["img1"] = {"class_type": "LoadImage", "inputs": {"image": j["ref"]}}
        g["pos0"]["inputs"]["image2"] = ["img1", 0]
    g["pos"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["pos0", 0], "latent": ["refl", 0]}}
    g["neg0"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "prompt": j.get("negative", " "), "image1": img}}
    g["neg"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["neg0", 0], "latent": ["refl", 0]}}
    if j.get("init"):
        g["init0"] = {"class_type": "LoadImage", "inputs": {"image": j["init"]}}
        ii = ["init0", 0]
        if "width" in j:
            g["inits"] = {"class_type": "ImageScale", "inputs": {"image": ii, "upscale_method": "lanczos", "width": j["width"], "height": j["height"], "crop": "disabled"}}
            ii = ["inits", 0]
        g["lat"] = {"class_type": "VAEEncode", "inputs": {"pixels": ii, "vae": ["vae", 0]}}
        latent = ["lat", 0]
    else:
        latent = ["refl", 0]   # denoise 1.0 이면 크기만 쓰인다
    g["ks"] = {"class_type": "KSampler", "inputs": {"model": ["cn", 0], "seed": j.get("seed", 1), "steps": j.get("steps", 8 if lora != "4" else 4),
               "cfg": j.get("cfg", 1.0), "sampler_name": j.get("sampler", "euler"), "scheduler": "simple", "positive": ["pos", 0], "negative": ["neg", 0],
               "latent_image": latent, "denoise": j.get("denoise", 1.0)}}
    g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": j["name"]}}
    return g

def post(g):
    req = urllib.request.Request(URL + "/prompt", json.dumps({"prompt": g, "client_id": "iso-redraw"}).encode(), {"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req))["prompt_id"]
    except urllib.error.HTTPError as e:
        raise SystemExit("prompt rejected: " + e.read().decode()[:3000])

def wait(pid, t=3600):
    t0 = time.time()
    while time.time() - t0 < t:
        h = json.load(urllib.request.urlopen(f"{URL}/history/{pid}"))
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error": raise SystemExit(json.dumps(st)[:3000])
            if st.get("completed"): return h[pid]
        time.sleep(2)
    raise SystemExit("timeout " + pid)

jobs = json.load(open(sys.argv[1]))
ids = [(j["name"], post(graph(j)), time.time()) for j in jobs]
for name, pid, t0 in ids:
    h = wait(pid)
    files = [im["filename"] for o in h["outputs"].values() for im in o.get("images", [])]
    print(f"{name}: {files} ({time.time() - t0:.0f}s since submit)", flush=True)
