"""
COGNIVEX - FastAPI Server
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

from supabase_client import SupabaseClient
from model_engine import ModelEngine
from feature_extractor import FeatureExtractor
from otp_controller import OTPController

app = FastAPI()
supabase        = SupabaseClient()
modelEngine     = ModelEngine(supabase)
featureExtractor = FeatureExtractor()
otpController   = OTPController()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request Models ──────────────────────────────────────────────────────────

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

# ── Endpoints ───────────────────────────────────────────────────────────────

@app.post("/session/snapshot")
async def handle_snapshot(req: SnapshotRequest):
    """Phase 1: Real-time 30-sec monitoring."""
    print(f"\n📤 [SNAPSHOT] User {req.user_id}, Session {req.session_id}")
    try:
        # 1. Store raw snapshot
        snapshot_id = supabase.store_snapshot(req.user_id, req.session_id, req.raw_data)
        print(f"   Stored snapshot: {snapshot_id}")

        # 2. Try to load model
        model_dict = modelEngine.getModel(req.user_id)

        if not model_dict:
            supabase.update_snapshot_risk(snapshot_id, 'LOW', 0)
            print(f"   No model yet — marking LOW (baseline collection)")
            return {'status': 'OK', 'risk_level': 'LOW',
                    'message': 'Collecting baseline data', 'model_version': 0}

        # 3. Extract + score
        features = featureExtractor.extract(req.raw_data)
        print(f"   typing_speed={features['typing_speed']:.2f}  "
              f"mouse_speed={features['avg_mouse_speed']:.2f}  "
              f"keystroke_interval={features['avg_keystroke_interval']:.4f}")

        score, src = modelEngine.predict(model_dict['model'], model_dict['scaler'], features, stats=model_dict.get('stats'))
        risk  = modelEngine.scoreToRiskLevel(score)
        print(f"   Score: {score:.4f}  [{src}]  →  {risk}")

        supabase.update_snapshot_risk(snapshot_id, risk, model_dict['model_version'])

        # 4. Act on risk
        if risk == 'HIGH':
            return {'status': 'SESSION_TERMINATED', 'risk_level': 'HIGH',
                    'message': '🚨 High risk — session terminated',
                    'model_version': model_dict['model_version']}

        if risk == 'MEDIUM':
            # ✅ Cooldown check — don't spam OTP every 30 sec
            if otpController.isCoolingDown(req.user_id, req.session_id):
                print(f"   ⏳ MEDIUM but cooldown active — treating as LOW")
                return {'status': 'OK', 'risk_level': 'LOW',
                        'message': '⏳ Cooldown active — monitoring continues',
                        'model_version': model_dict['model_version']}
            otp = otpController.generateOTP()
            otpController.storeOTP(req.user_id, req.session_id, otp)
            print(f"   ⚠️  OTP: {otp}")
            return {'status': 'OTP_REQUIRED', 'risk_level': 'MEDIUM',
                    'message': f'⚠️ Unusual behavior detected. OTP: {otp}',
                    'model_version': model_dict['model_version']}

        return {'status': 'OK', 'risk_level': 'LOW',
                'message': '✅ Normal behavior',
                'model_version': model_dict['model_version']}

    except Exception as e:
        import traceback; traceback.print_exc()
        return {'status': 'ERROR', 'message': str(e)}


@app.post("/session/end")
async def handle_session_end(req: SessionEndRequest):
    """Phase 2: Aggregate features, persist, trigger training if needed."""
    print(f"\n🏁 [SESSION END] User {req.user_id}, Session {req.session_id}")
    try:
        # 1. Fetch LOW-risk snapshots
        snapshots = supabase.get_low_risk_snapshots(req.user_id, req.session_id)
        print(f"   LOW-risk snapshots: {len(snapshots)}")

        if not snapshots:
            print(f"   ⚠️ No LOW-risk snapshots — skipping feature storage")
            return {'status': 'NO_LOW_RISK_DATA',
                    'message': 'No low-risk snapshots to aggregate'}

        # 2. Aggregate + persist
        features = featureExtractor.aggregateFeatures(snapshots)
        supabase.store_session_features(req.user_id, req.session_id, features)
        print(f"   ✅ Features stored")

        # 3. Check training trigger
        total = supabase.get_total_sessions(req.user_id)
        print(f"   Total sessions: {total}")

        # ✅ FIX 4: Explicit returns so we never fall through to COLLECTING_DATA after training
        if total == 15:
            print(f"   🎯 Session 15 — training first model...")
            modelEngine.trainModelV1(req.user_id)
            return {'status': 'MODEL_TRAINED', 'model_version': 1,
                    'message': 'Model v1 trained successfully'}

        if total > 15:
            meta = supabase.get_model_metadata(req.user_id)
            sessions_since = total - meta.get('last_trained_count', 15)
            print(f"   Sessions since last train: {sessions_since}")
            if sessions_since >= 20:
                print(f"   🎯 Retraining model...")
                result = modelEngine.retrainModel(req.user_id, total)
                return {'status': 'MODEL_RETRAINED',
                        'model_version': result['model_version'],
                        'message': f"Model v{result['model_version']} retrained"}
            return {'status': 'SESSION_STORED',
                    'message': f'Session stored ({total} total)'}

        # total < 15
        needed = 15 - total
        return {'status': 'COLLECTING_DATA',
                'sessions_collected': total,
                'sessions_needed': needed,
                'message': f'{total}/15 sessions collected'}

    except Exception as e:
        import traceback; traceback.print_exc()
        return {'status': 'ERROR', 'message': str(e)}


@app.post("/verify-otp")
async def verify_otp(req: VerifyOTPRequest):
    print(f"\n🔐 [OTP VERIFY] User {req.user_id}  OTP entered: {req.otp_code}")
    try:
        result = otpController.verifyOTP(req.user_id, req.session_id, req.otp_code)
        if result['valid']:
            print(f"   ✅ OTP verified")
            return {'status': 'OTP_VERIFIED', 'message': '✅ Verified — session continues'}
        print(f"   ❌ {result['reason']}")
        return {'status': 'OTP_INVALID', 'message': result['reason']}
    except Exception as e:
        return {'status': 'ERROR', 'message': str(e)}


@app.get("/health")
async def health():
    return {'status': 'healthy', 'message': 'COGNIVEX running'}


@app.get("/status/{user_id}")
async def status(user_id: str):
    meta = supabase.get_model_metadata(user_id)
    total = supabase.get_total_sessions(user_id)
    return {'model_version': meta.get('model_version', 0), 'total_sessions': total}


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 COGNIVEX — Behavioral Biometrics Anomaly Detection")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=5000)