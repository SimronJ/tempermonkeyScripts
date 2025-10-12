import os, sys
from dotenv import load_dotenv
from ultralytics import YOLO
import torch

def gpu_info():
    print("="*50)
    print("GPU CHECK")
    print("="*50)
    print(f"Python: {sys.version}")
    print(f"Torch: {torch.__version__}, CUDA compiled: {torch.version.cuda}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f} GB")

def ensure_dataset():
    load_dotenv()
    data_yaml = "./TlopoGame-2/data.yaml"
    if os.path.exists(data_yaml):
        print(f"Dataset found: {data_yaml}")
        return data_yaml
    api = os.getenv("ROBO_API")
    if not api:
        print("Missing ROBO_API; cannot download dataset.")
        sys.exit(1)
    try:
        import roboflow
        print("Downloading dataset from Roboflow...")
        rf = roboflow.Roboflow(api_key=api)
        project = rf.workspace("workspace1-7olpq").project("tlopogame-du372")
        ds = project.version(2).download("yolov8")
        data_yaml = f"{ds.location}/data.yaml"
        print(f"Dataset downloaded: {data_yaml}")
        return data_yaml
    except Exception as e:
        print(f"Dataset download error: {e}")
        sys.exit(1)

def build_model_name(family: str, variant: str) -> str:
    # family: 'yolov8' or 'yolo11'; variant: 'n','s','m','l','x'
    family = family.lower().strip()
    if family not in ("yolov8", "yolo11"):
        family = "yolov8"
    variant = variant.lower().strip()
    if variant not in ("n", "s", "m", "l", "x"):
        variant = "s"
    return f"{family}{variant}.pt"

def resolve_variants(preset: str, explicit_variant: str | None) -> list[str]:
    if explicit_variant:
        return [explicit_variant.lower()]
    p = (preset or "balanced").lower()
    if p == "accurate":
        return ["l", "m", "s"]   # try large, then step down
    if p == "fast":
        return ["n", "s", "m"]   # try nano/small first
    # balanced/default
    return ["s", "m", "l"]

def train(data_yaml):
    # Read settings from env
    load_dotenv()
    family = os.getenv("YOLO_FAMILY", "yolo11")  # yolo11 or yolov8
    preset = os.getenv("YOLO_PRESET", "balanced")  # accurate | balanced | fast
    variant_env = os.getenv("YOLO_VARIANT")  # optional explicit: n/s/m/l/x
    epochs = int(os.getenv("YOLO_EPOCHS", "150"))
    workers = int(os.getenv("YOLO_WORKERS", "0"))  # 0 on Windows to avoid spawn issues

    # Memory behavior
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Training family={family}, preset={preset}, device={device}, epochs={epochs}")

    # Image size/batch attempts (will try in order until one fits VRAM)
    tries = [
        (1280, -1),  # autobatch at high res first
        (1280, 16), (1280, 12),
        (1152, 16), (1152, 12),
        (1024, 16), (1024, 12),
        (960, 16),  (960, 12),
        (896, 16),  (896, 12),
        (832, 16),  (832, 12),
        (768, 16),  (768, 12),
        (640, 32),  (640, 24), (640, 16), (640, 12), (640, 8),
    ]

    last_err = None
    for variant in resolve_variants(preset, variant_env):
        model_name = build_model_name(family, variant)
        print(f"Loading model: {model_name}")
        model = YOLO(model_name)

        for imgsz, batch in tries:
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                print("="*50)
                print(f"TRY model={model_name} imgsz={imgsz} batch={batch} device={device} workers={workers}")
                r = model.train(
                    data=data_yaml,
                    epochs=epochs,
                    imgsz=imgsz,
                    batch=batch,
                    device=device,
                    workers=workers,                    # Windows-safe
                    cache="disk" if device == "cuda" else False,  # deterministic and VRAM-friendly
                    amp=(device == "cuda"),             # mixed precision on GPU
                    project="runs/detect",
                    name=f"tlopo_{family}_{variant}_s{imgsz}",
                    patience=30,
                    save_period=10,
                    plots=True,
                    verbose=True,
                )
                best = f"runs/detect/tlopo_{family}_{variant}_s{imgsz}/weights/best.pt"
                print("TRAINING COMPLETED")
                print(f"Best weights: {best}")
                return best
            except RuntimeError as e:
                last_err = e
                msg = str(e).lower()
                if "out of memory" in msg or "cublas" in msg:
                    print("OOM detected, retrying with smaller settings...")
                    continue
                raise
            except Exception as e:
                last_err = e
                print(f"Training failed with {model_name} at imgsz={imgsz}, batch={batch}: {e}")
                # Try next attempt
                continue

    print("Failed to train with available VRAM/settings.")
    if last_err:
        print(last_err)
    sys.exit(1)

def main():
    gpu_info()
    data_yaml = ensure_dataset()
    best = train(data_yaml)
    print("\nNEXT STEPS:")
    print(f"YOLO_MODEL_PATH=./{best}")
    print("YOLO_DEVICE=cuda")
    print("Set INFERENCE_MODE=local in .env to use the trained model.")

if __name__ == "__main__":
    main()