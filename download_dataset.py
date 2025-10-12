# download_dataset.py
import roboflow
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment
api_key = os.getenv("ROBO_API")

if not api_key:
    print("Error: ROBO_API not found in .env file")
    exit(1)

try:
    rf = roboflow.Roboflow(api_key=api_key)
    project = rf.workspace("workspace1-7olpq").project("tlopogame-du372")
    version = project.version(2)
    
    print("Downloading dataset...")
    dataset = version.download("yolov8")
    
    print(f"Dataset downloaded to: {dataset.location}")
    print("Dataset download completed successfully!")
    
    # Print the actual folder name for reference
    dataset_folder = os.path.basename(dataset.location)
    print(f"Dataset folder name: {dataset_folder}")
    print(f"data.yaml path: {dataset.location}/data.yaml")
    
except Exception as e:
    print(f"Error downloading dataset: {e}")

# train_model.py
from ultralytics import YOLO

# Load a pre-trained model
model = YOLO('yolov8n.pt')  # nano version for speed

# Train the model
model.train(
    data='./TlopoGame-2/data.yaml',
    epochs=100,
    imgsz=640,
    batch=16
)
