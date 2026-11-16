"""Train/evaluate the reproducible synthetic baseline models and print metrics."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.prediction.model import MODEL
print(json.dumps({'dataset':'Synthetic generated dataset (1,600 rows)','split':'Chronological 80/20','selected_model':MODEL.best_name,'metrics':MODEL.metrics},indent=2))
