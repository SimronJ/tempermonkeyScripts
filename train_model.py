from ultralytics import YOLO
import os

# The actual dataset folder name from your download
dataset_folder = "TlopoGame-2"  # This is what was downloaded
data_yaml_path = f"./{dataset_folder}/data.yaml"

print(f"Looking for data.yaml at: {data_yaml_path}")

if not os.path.exists(data_yaml_path):
    print(f"Error: data.yaml not found at {data_yaml_path}")
    print("Available folders:")
    for item in os.listdir("."):
        if os.path.isdir(item):
            print(f"  - {item}")
    exit(1)

try:
    # Load a pre-trained model
    model = YOLO('yolov8n.pt')  # nano version for speed
    
    print("Starting training...")
    # Train the model
    results = model.train(
        data=data_yaml_path,  # Correct path: ./TlopoGame-2/data.yaml
        epochs=100,
        imgsz=640,
        batch=16,
        name='tlopo_game_model'
    )
    
    print("Training completed!")
    print(f"Best model saved at: runs/detect/tlopo_game_model/weights/best.pt")
    
except Exception as e:
    print(f"Training error: {e}")