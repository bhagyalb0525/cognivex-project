"""
COGNIVEX - Model Engine WITH PROPER FEATURE NORMALIZATION
Isolation Forest training, prediction, versioning
✅ FIXED: Added StandardScaler for proper anomaly detection
"""

import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import numpy as np
from typing import Dict, Optional, List
import io

class ModelEngine:
    
    # Risk thresholds (as per architecture)
    SCORE_LOW = -0.1
    SCORE_MEDIUM = -0.3
    
    def __init__(self, supabase):
        self.supabase = supabase
        self.model_cache = {}  # {user_id: {'model': model_obj, 'version': int, 'scaler': scaler_obj}}
        self.scaler_cache = {}  # {user_id: scaler_obj}
    
    def getModel(self, user_id: str) -> Optional[Dict]:
        """Get model from cache or load from DB"""
        
        if user_id in self.model_cache:
            return self.model_cache[user_id]
        
        modelBinary = self.supabase.get_model_data(user_id)
        scalerBinary = self.supabase.get_scaler_data(user_id)
        
        if not modelBinary or not scalerBinary:
            return None
        
        try:
            # ✅ Load model with BytesIO
            buffer = io.BytesIO(modelBinary)
            model = joblib.load(buffer)
            
            # ✅ Load scaler with BytesIO
            scaler_buffer = io.BytesIO(scalerBinary)
            scaler = joblib.load(scaler_buffer)
            
            metadata = self.supabase.get_model_metadata(user_id)
            
            result = {
                'model': model,
                'scaler': scaler,
                'model_version': metadata['model_version']
            }
            
            self.model_cache[user_id] = result
            self.scaler_cache[user_id] = scaler
            return result
        
        except Exception as e:
            print(f"❌ Error loading model/scaler: {e}")
            return None
    
    def predict(self, model: IsolationForest, scaler: StandardScaler, features: Dict[str, float]) -> float:
        """Score features with model - NOW WITH NORMALIZATION"""
        
        # Create feature array in correct order
        featureArray = np.array([
            features['typing_speed'],
            features['backspace_ratio'],
            features['avg_keystroke_interval'],
            features['keystroke_variance'],
            features['avg_mouse_speed'],
            features['mouse_move_variance'],
            features['scroll_frequency'],
            features['idle_ratio']
        ]).reshape(1, -1)
        
        # ✅ NORMALIZE features before scoring!
        featureArray_normalized = scaler.transform(featureArray)
        
        # Score with normalized features
        score = model.decision_function(featureArray_normalized)[0]
        return score
    
    def scoreToRiskLevel(self, score: float) -> str:
        """Convert score to risk level"""
        
        if score > self.SCORE_LOW:
            return 'LOW'
        elif score > self.SCORE_MEDIUM:
            return 'MEDIUM'
        else:
            return 'HIGH'
    
    def trainModelV1(self, user_id: str) -> Dict:
        """Train first model on 15 sessions (PHASE 2) WITH NORMALIZATION"""
        
        print(f"\n{'='*70}")
        print(f"🤖 Training Model v1 for user {user_id}")
        print(f"{'='*70}")
        
        sessions = self.supabase.get_latest_sessions(user_id, 15)
        
        if len(sessions) < 15:
            raise Exception(f"Not enough sessions: {len(sessions)} < 15")
        
        # Extract features
        featureMatrix = []
        for session in sessions:
            features = [
                session['typing_speed'],
                session['backspace_ratio'],
                session['avg_keystroke_interval'],
                session['keystroke_variance'],
                session['avg_mouse_speed'],
                session['mouse_move_variance'],
                session['scroll_frequency'],
                session['idle_ratio']
            ]
            featureMatrix.append(features)
        
        featureMatrix = np.array(featureMatrix)
        
        print(f"   Training on {len(sessions)} sessions")
        print(f"   Feature matrix shape: {featureMatrix.shape}")
        print(f"   Feature ranges (BEFORE normalization):")
        print(f"      typing_speed: {featureMatrix[:, 0].min():.2f} - {featureMatrix[:, 0].max():.2f}")
        print(f"      backspace_ratio: {featureMatrix[:, 1].min():.4f} - {featureMatrix[:, 1].max():.4f}")
        print(f"      avg_keystroke_interval: {featureMatrix[:, 2].min():.4f} - {featureMatrix[:, 2].max():.4f}")
        print(f"      keystroke_variance: {featureMatrix[:, 3].min():.4f} - {featureMatrix[:, 3].max():.4f}")
        print(f"      avg_mouse_speed: {featureMatrix[:, 4].min():.2f} - {featureMatrix[:, 4].max():.2f}")
        print(f"      mouse_move_variance: {featureMatrix[:, 5].min():.2f} - {featureMatrix[:, 5].max():.2f}")
        print(f"      scroll_frequency: {featureMatrix[:, 6].min():.2f} - {featureMatrix[:, 6].max():.2f}")
        print(f"      idle_ratio: {featureMatrix[:, 7].min():.4f} - {featureMatrix[:, 7].max():.4f}")
        
        # ✅ NORMALIZE features!
        print(f"\n   ✅ Normalizing features with StandardScaler...")
        scaler = StandardScaler()
        featureMatrix_normalized = scaler.fit_transform(featureMatrix)
        print(f"   ✅ Normalized feature ranges:")
        print(f"      All features: {featureMatrix_normalized.min():.2f} - {featureMatrix_normalized.max():.2f}")
        
        # Train Isolation Forest ON NORMALIZED DATA
        print(f"\n   Training Isolation Forest on normalized data...")
        model = IsolationForest(
            contamination=0.05,
            random_state=42,
            n_estimators=100
        )
        model.fit(featureMatrix_normalized)
        
        print(f"   ✅ Model trained (contamination=0.05, trees=100)")
        
        # ✅ Save model to database
        buffer = io.BytesIO()
        joblib.dump(model, buffer)
        modelBinary = buffer.getvalue()
        
        # ✅ Save scaler to database
        scaler_buffer = io.BytesIO()
        joblib.dump(scaler, scaler_buffer)
        scalerBinary = scaler_buffer.getvalue()
        
        self.supabase.save_model(user_id, modelBinary, model_version=1, total_sessions=15)
        self.supabase.save_scaler(user_id, scalerBinary)
        
        # Clear cache
        if user_id in self.model_cache:
            del self.model_cache[user_id]
        if user_id in self.scaler_cache:
            del self.scaler_cache[user_id]
        
        print(f"   ✅ Model and Scaler saved to database\n")
        
        return {'model_version': 1, 'total_sessions': 15}
    
    def retrainModel(self, user_id: str, totalSessions: int) -> Dict:
        """Retrain model on latest 15 sessions (PHASE 2) WITH NORMALIZATION"""
        
        print(f"\n{'='*70}")
        print(f"🤖 Retraining Model for user {user_id}")
        print(f"{'='*70}")
        
        sessions = self.supabase.get_latest_sessions(user_id, 15)
        
        # Extract features
        featureMatrix = []
        for session in sessions:
            features = [
                session['typing_speed'],
                session['backspace_ratio'],
                session['avg_keystroke_interval'],
                session['keystroke_variance'],
                session['avg_mouse_speed'],
                session['mouse_move_variance'],
                session['scroll_frequency'],
                session['idle_ratio']
            ]
            featureMatrix.append(features)
        
        featureMatrix = np.array(featureMatrix)
        
        print(f"   Retraining on latest {len(sessions)} sessions")
        
        # Get current version
        metadata = self.supabase.get_model_metadata(user_id)
        newVersion = metadata['model_version'] + 1
        
        # ✅ Normalize features!
        print(f"   ✅ Normalizing features with StandardScaler...")
        scaler = StandardScaler()
        featureMatrix_normalized = scaler.fit_transform(featureMatrix)
        
        # Train on normalized data
        print(f"   Training Isolation Forest on normalized data...")
        model = IsolationForest(
            contamination=0.05,
            random_state=42,
            n_estimators=100
        )
        model.fit(featureMatrix_normalized)
        
        print(f"   ✅ Model retrained (v{newVersion})")
        
        # ✅ Save model
        buffer = io.BytesIO()
        joblib.dump(model, buffer)
        modelBinary = buffer.getvalue()
        
        # ✅ Save scaler
        scaler_buffer = io.BytesIO()
        joblib.dump(scaler, scaler_buffer)
        scalerBinary = scaler_buffer.getvalue()
        
        self.supabase.save_model(user_id, modelBinary, model_version=newVersion, total_sessions=totalSessions)
        self.supabase.save_scaler(user_id, scalerBinary)
        
        # Clear cache
        if user_id in self.model_cache:
            del self.model_cache[user_id]
        if user_id in self.scaler_cache:
            del self.scaler_cache[user_id]
        
        print(f"   ✅ Model v{newVersion} and Scaler saved\n")
        
        return {'model_version': newVersion, 'total_sessions': totalSessions}
    
    def getModelMetadata(self, user_id: str) -> Dict:
        """Get model metadata"""
        return self.supabase.get_model_metadata(user_id)