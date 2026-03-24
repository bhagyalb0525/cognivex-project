"""
COGNIVEX - FastAPI Server WITH PROPER FEATURE NORMALIZATION
✅ FIXED: Using StandardScaler for proper anomaly detection
✅ FIXED: OTP generateOTP method
✅ FIXED: Session counter logic
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

# Import our modules
from supabase_client import SupabaseClient
from model_engine import ModelEngine
from feature_extractor import FeatureExtractor
from otp_controller import OTPController

# ===== INITIALIZATION =====
app = FastAPI()
supabase = SupabaseClient()
modelEngine = ModelEngine(supabase)
featureExtractor = FeatureExtractor()
otpController = OTPController(supabase)

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== REQUEST MODELS =====

class SnapshotRequest(BaseModel):
    user_id: str
    session_id: str
    raw_data: dict

class SessionEndRequest(BaseModel):
    user_id: str
    session_id: str

class VerifyOTPRequest(BaseModel):
    user_id: str
    session_id: str
    otp_code: str

# ===== ENDPOINTS =====

@app.post("/session/snapshot")
async def handle_snapshot(request: SnapshotRequest):
    """
    Phase 1: Real-time monitoring endpoint
    - Store snapshot to behavior_logs
    - Extract features from snapshot
    - If model exists: Score with model → return risk level
    - If no model: Mark as LOW risk (collecting baseline)
    """
    
    print(f"\n📤 [SNAPSHOT] User {request.user_id}, Session {request.session_id}")
    
    try:
        # Step 1: Store raw data to behavior_logs
        print(f"   Step 1: Storing raw data to behavior_logs...")
        snapshot_id = supabase.store_snapshot(
            request.user_id,
            request.session_id,
            request.raw_data
        )
        print(f"   ✅ Stored snapshot ID: {snapshot_id}")
        
        # Step 2: Check if model exists
        print(f"   Step 2: Checking if model exists...")
        model_dict = modelEngine.getModel(request.user_id)
        
        if not model_dict:
            # No model yet - collecting baseline data
            print(f"   Step 3: No model yet. Mark as LOW (collecting baseline)...")
            supabase.update_snapshot_risk(snapshot_id, 'LOW', 0)
            return {
                'status': 'OK',
                'risk_level': 'LOW',
                'message': '✅ Baseline data collected',
                'model_version': 0
            }
        
        # Step 3: Extract features from this snapshot
        print(f"   Step 3: Extracting features (in-memory)...")
        features_dict = featureExtractor.extract(request.raw_data)
        print(f"   Features:")
        print(f"      typing_speed: {features_dict['typing_speed']:.2f}")
        print(f"      mouse_speed: {features_dict['avg_mouse_speed']:.2f}")
        print(f"      keystroke_interval: {features_dict['avg_keystroke_interval']:.4f}")
        
        # Step 4: Score with model using NORMALIZED features
        print(f"   Step 4: Scoring with model v{model_dict['model_version']}...")
        model = model_dict['model']
        scaler = model_dict['scaler']  # ✅ Get scaler!
        
        score = modelEngine.predict(model, scaler, features_dict)  # ✅ Pass scaler!
        print(f"   Score: {score:.4f}")
        
        risk_level = modelEngine.scoreToRiskLevel(score)
        print(f"   Risk Level: {risk_level}")
        
        # Step 5: Update snapshot with risk level
        supabase.update_snapshot_risk(snapshot_id, risk_level, model_dict['model_version'])
        
        # Step 6: Handle by risk level
        if risk_level == 'HIGH':
            print(f"   ✅ HIGH risk - Session will terminate on logout")
            return {
                'status': 'SESSION_TERMINATED',
                'risk_level': 'HIGH',
                'message': '🚨 HIGH RISK DETECTED: Session will be terminated',
                'model_version': model_dict['model_version']
            }
        
        elif risk_level == 'MEDIUM':
            print(f"   ✅ MEDIUM risk - Generating OTP...")
            otp_code = otpController.generateOTP()  # ✅ FIXED METHOD NAME!
            otpController.storeOTP(request.user_id, request.session_id, otp_code, '127.0.0.1')
            
            print(f"   ⚠️ OTP: {otp_code}")
            
            return {
                'status': 'OTP_REQUIRED',
                'risk_level': 'MEDIUM',
                'message': f'⚠️ Unusual behavior. OTP: {otp_code}',
                'model_version': model_dict['model_version']
            }
        
        else:  # LOW
            print(f"   ✅ LOW risk - Behavior is normal")
            return {
                'status': 'OK',
                'risk_level': 'LOW',
                'message': '✅ Normal behavior detected',
                'model_version': model_dict['model_version']
            }
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'ERROR', 'message': str(e)}


@app.post("/session/end")
async def handle_session_end(request: SessionEndRequest):
    """
    Phase 2: Session aggregation and model training
    - Fetch all LOW-risk snapshots from session
    - Aggregate features to single row in behavior_features
    - Check if training trigger (session 15, 35, 55, etc.)
    - Train/retrain model if needed
    """
    
    print(f"\n🏁 [SESSION END] User {request.user_id}, Session {request.session_id}")
    
    try:
        # Step 1: Get LOW-risk snapshots
        print(f"   Step 1: Fetching LOW-risk snapshots...")
        snapshots = supabase.get_low_risk_snapshots(request.user_id, request.session_id)
        print(f"   Found: {len(snapshots)} LOW-risk snapshots")
        
        if len(snapshots) == 0:
            print(f"   ⚠️ WARNING: No LOW-risk snapshots found!")
            print(f"   This is normal for sessions with HIGH/MEDIUM risk")
            return {
                'status': 'NO_LOW_RISK_DATA',
                'message': 'No LOW-risk snapshots to aggregate'
            }
        
        # Step 2: Aggregate features
        print(f"   Step 2: Aggregating features from snapshots...")
        try:
            aggregated_features = featureExtractor.aggregateFeatures(snapshots)
            print(f"   ✅ Features aggregated:")
            print(f"      typing_speed: {aggregated_features.get('typing_speed', 0):.2f}")
            print(f"      mouse_speed: {aggregated_features.get('avg_mouse_speed', 0):.2f}")
        except Exception as agg_err:
            print(f"   ❌ Error aggregating: {agg_err}")
            raise agg_err
        
        # Step 3: Store aggregated features
        print(f"   Step 3: Storing aggregated features...")
        try:
            supabase.store_session_features(request.user_id, request.session_id, aggregated_features)
            print(f"   ✅ Features stored to behavior_features table!")
        except Exception as store_err:
            print(f"   ❌ Error storing features: {store_err}")
            raise store_err
        
        # Step 4: Get total sessions and check training trigger
        print(f"   Step 4: Checking training trigger...")
        try:
            totalSessions = supabase.get_total_sessions(request.user_id)
            print(f"   Total sessions so far: {totalSessions}")
        except Exception as count_err:
            print(f"   ❌ Error getting session count: {count_err}")
            raise count_err
        
        # TRAINING LOGIC
        if totalSessions == 15:
            print(f"\n   🎯 SESSION 15 REACHED! Training first model...")
            try:
                modelEngine.trainModelV1(request.user_id)
                print(f"   ✅ Model v1 TRAINED!")
                return {
                    'status': 'MODEL_TRAINED',
                    'message': 'Model trained successfully',
                    'model_version': 1
                }
            except Exception as train_err:
                print(f"   ❌ Error training model: {train_err}")
                raise train_err
        
        elif totalSessions > 15:
            print(f"   Checking if retraining needed...")
            try:
                metadata = modelEngine.getModelMetadata(request.user_id)
                lastTrained = metadata.get('last_trained_count', 15)
                sessionsSinceTrain = totalSessions - lastTrained
                print(f"   Sessions since training: {sessionsSinceTrain}")
                
                if sessionsSinceTrain >= 20:
                    print(f"\n   🎯 20 SESSIONS SINCE TRAINING ({sessionsSinceTrain})! Retraining...")
                    modelEngine.retrainModel(request.user_id, totalSessions)
                    print(f"   ✅ Model RETRAINED!")
                    return {
                        'status': 'MODEL_RETRAINED',
                        'message': 'Model retrained successfully',
                        'model_version': metadata['model_version'] + 1
                    }
            except Exception as retrain_err:
                print(f"   ❌ Error checking retraining: {retrain_err}")
        
        # Still collecting data - FIXED COUNTER LOGIC
        sessionsNeeded = max(0, 15 - totalSessions)
        print(f"   ✅ Session {totalSessions} saved. Need {sessionsNeeded} more for training")
        return {
            'status': 'COLLECTING_DATA',
            'message': f'Data collected ({totalSessions}/15 sessions for training)',
            'sessions_collected': totalSessions,
            'sessions_needed': sessionsNeeded
        }
    
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'ERROR', 'message': str(e)}


@app.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest):
    """
    OTP verification endpoint
    """
    
    print(f"\n🔐 [OTP VERIFY] User {request.user_id}, Session {request.session_id}")
    print(f"   OTP Entered: {request.otp_code}")
    
    try:
        # Verify OTP
        result = otpController.verifyOTP(request.user_id, request.session_id, request.otp_code)
        
        if result['valid']:
            print(f"   ✅ OTP VERIFIED!")
            return {
                'status': 'OTP_VERIFIED',
                'message': '✅ OTP verified! Session continues.'
            }
        else:
            print(f"   ❌ OTP INVALID: {result['reason']}")
            return {
                'status': 'SESSION_TERMINATED',
                'message': f'❌ OTP verification failed: {result["reason"]}. Session terminated.'
            }
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'ERROR', 'message': str(e)}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {'status': 'healthy', 'message': 'COGNIVEX v2.0 running'}


# ===== STARTUP =====
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 COGNIVEX v2.0 - Behavioral Biometrics Anomaly Detection")
    print("="*70)
    print("✅ Feature Normalization: ENABLED")
    print("✅ Isolation Forest with StandardScaler: ACTIVE")
    print("✅ OTP Controller: FIXED")
    print("✅ Session Counter: FIXED")
    print("\nStarting FastAPI server on http://localhost:5000")
    print("="*70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=5000)