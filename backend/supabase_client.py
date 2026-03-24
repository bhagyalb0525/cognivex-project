"""
COGNIVEX - Supabase Client WITH SCALER STORAGE
All database operations including StandardScaler storage for feature normalization
"""

import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import json
import base64

load_dotenv()

class SupabaseClient:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not self.url or not self.key:
            print("❌ Missing Supabase credentials in .env")
            exit(1)
        
        self.client = create_client(self.url, self.key)
        print("✅ Supabase connected")
    
    # ===== BEHAVIOR_LOGS =====
    
    def store_snapshot(self, user_id: str, session_id: str, raw_data: dict) -> str:
        """Store 30-sec snapshot to behavior_logs"""
        try:
            response = self.client.table('behavior_logs').insert({
                'user_id': user_id,
                'session_id': session_id,
                'key_events': raw_data.get('key_events'),
                'mouse_events': raw_data.get('mouse_events'),
                'scroll_events': raw_data.get('scroll_events'),
                'summary': raw_data.get('summary'),
                'risk_level': 'PENDING',
                'model_version': 0
            }).execute()
            
            return response.data[0]['id']
        except Exception as e:
            print(f"❌ Error storing snapshot: {e}")
            raise
    
    def update_snapshot_risk(self, snapshot_id: str, risk_level: str, model_version: int):
        """Update risk level after scoring"""
        try:
            self.client.table('behavior_logs').update({
                'risk_level': risk_level,
                'model_version': model_version
            }).eq('id', snapshot_id).execute()
        except Exception as e:
            print(f"❌ Error updating snapshot: {e}")
            raise
    
    def get_low_risk_snapshots(self, user_id: str, session_id: str) -> list:
        """Get all LOW-risk snapshots"""
        try:
            response = self.client.table('behavior_logs').select('*').eq(
                'user_id', user_id
            ).eq('session_id', session_id).eq('risk_level', 'LOW').execute()
            return response.data
        except Exception as e:
            print(f"❌ Error fetching snapshots: {e}")
            raise
    
    # ===== BEHAVIOR_FEATURES =====
    
    def store_session_features(self, user_id: str, session_id: str, features: dict):
        """Store aggregated session features"""
        try:
            print(f"   📝 Storing features for user {user_id}")
            print(f"      Session: {session_id}")
            
            # Ensure all values are floats
            clean_features = {
                'user_id': user_id,
                'session_id': session_id,
                'typing_speed': float(features.get('typing_speed', 0)),
                'backspace_ratio': float(features.get('backspace_ratio', 0)),
                'avg_keystroke_interval': float(features.get('avg_keystroke_interval', 0)),
                'keystroke_variance': float(features.get('keystroke_variance', 0)),
                'avg_mouse_speed': float(features.get('avg_mouse_speed', 0)),
                'mouse_move_variance': float(features.get('mouse_move_variance', 0)),
                'scroll_frequency': float(features.get('scroll_frequency', 0)),
                'idle_ratio': float(features.get('idle_ratio', 0))
            }
            
            response = self.client.table('behavior_features').insert(clean_features).execute()
            print(f"      ✅ Features stored")
            return response.data[0]['id']
        except Exception as e:
            print(f"❌ Error storing features: {e}")
            raise
    
    def get_latest_sessions(self, user_id: str, limit: int) -> list:
        """Get latest N sessions' features ordered by creation date"""
        try:
            response = self.client.table('behavior_features').select('*').eq(
                'user_id', user_id
            ).order('created_at', desc=True).limit(limit).execute()
            
            # Reverse to get chronological order (oldest to newest)
            return list(reversed(response.data))
        except Exception as e:
            print(f"❌ Error fetching sessions: {e}")
            raise
    
    def get_total_sessions(self, user_id: str) -> int:
        """Count total stored sessions for a user"""
        try:
            response = self.client.table('behavior_features').select(
                'id', count='exact'
            ).eq('user_id', user_id).execute()
            return response.count
        except Exception as e:
            print(f"❌ Error counting sessions: {e}")
            raise
    
    # ===== MODEL_METADATA =====
    
    def save_model(self, user_id: str, modelBinary: bytes, model_version: int, total_sessions: int):
        """Save trained model"""
        try:
            # Convert to base64 for storage
            modelB64 = base64.b64encode(modelBinary).decode()
            
            # Check if metadata exists
            existing = self.client.table('model_metadata').select('*').eq(
                'user_id', user_id
            ).execute()
            
            if existing.data:
                # Update
                self.client.table('model_metadata').update({
                    'model_data': modelB64,
                    'model_version': model_version,
                    'total_sessions': total_sessions,
                    'last_trained_at': datetime.now(timezone.utc).isoformat(),
                    'last_trained_count': total_sessions
                }).eq('user_id', user_id).execute()
            else:
                # Insert
                self.client.table('model_metadata').insert({
                    'user_id': user_id,
                    'model_data': modelB64,
                    'model_version': model_version,
                    'total_sessions': total_sessions,
                    'last_trained_at': datetime.now(timezone.utc).isoformat(),
                    'last_trained_count': total_sessions
                }).execute()
        except Exception as e:
            print(f"❌ Error saving model: {e}")
            raise
    
    def get_model_data(self, user_id: str) -> bytes:
        """Get model binary data"""
        try:
            response = self.client.table('model_metadata').select('model_data').eq(
                'user_id', user_id
            ).execute()
            
            if not response.data:
                return None
            
            modelB64 = response.data[0]['model_data']
            return base64.b64decode(modelB64)
        except Exception as e:
            print(f"❌ Error fetching model: {e}")
            return None
    
    def get_model_metadata(self, user_id: str) -> dict:
        """Get model metadata"""
        try:
            response = self.client.table('model_metadata').select('*').eq(
                'user_id', user_id
            ).execute()
            
            if not response.data:
                return {'model_version': 0, 'total_sessions': 0}
            
            return response.data[0]
        except Exception as e:
            print(f"❌ Error fetching metadata: {e}")
            return {'model_version': 0, 'total_sessions': 0}
    
    # ===== SCALER STORAGE (NEW) =====
    
    def save_scaler(self, user_id: str, scalerBinary: bytes):
        """✅ NEW: Save StandardScaler for feature normalization"""
        try:
            # Convert to base64 for storage
            scalerB64 = base64.b64encode(scalerBinary).decode()
            
            # Check if scaler exists
            existing = self.client.table('model_metadata').select('*').eq(
                'user_id', user_id
            ).execute()
            
            if existing.data:
                # Update - add scaler to existing metadata row
                self.client.table('model_metadata').update({
                    'scaler_data': scalerB64
                }).eq('user_id', user_id).execute()
            else:
                # Insert new row with scaler
                self.client.table('model_metadata').insert({
                    'user_id': user_id,
                    'scaler_data': scalerB64
                }).execute()
        except Exception as e:
            print(f"❌ Error saving scaler: {e}")
            raise
    
    def get_scaler_data(self, user_id: str) -> bytes:
        """✅ NEW: Get StandardScaler binary data"""
        try:
            response = self.client.table('model_metadata').select('scaler_data').eq(
                'user_id', user_id
            ).execute()
            
            if not response.data or not response.data[0].get('scaler_data'):
                return None
            
            scalerB64 = response.data[0]['scaler_data']
            return base64.b64decode(scalerB64)
        except Exception as e:
            print(f"❌ Error fetching scaler: {e}")
            return None
    
    # ===== OTP_CHALLENGES =====
    
    def store_otp(self, user_id: str, session_id: str, otp_code: str, ip_address: str):
        """Store OTP challenge"""
        try:
            expiry_time = datetime.now(timezone.utc) + timedelta(minutes=2)
            
            response = self.client.table('otp_challenges').insert({
                'user_id': user_id,
                'session_id': session_id,
                'otp_code': otp_code,
                'ip_address': ip_address,
                'is_verified': False,
                'expires_at': expiry_time.isoformat()
            }).execute()
            
            return response.data[0]['id']
        except Exception as e:
            print(f"❌ Error storing OTP: {e}")
            raise
    
    def get_active_otp(self, user_id: str, session_id: str) -> dict:
        """Get active OTP for session"""
        try:
            now = datetime.now(timezone.utc)
            
            response = self.client.table('otp_challenges').select('*').eq(
                'user_id', user_id
            ).eq('session_id', session_id).eq(
                'is_verified', False
            ).gt('expires_at', now.isoformat()).execute()
            
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ Error fetching OTP: {e}")
            return None
    
    def verify_otp(self, otp_id: str):
        """Mark OTP as verified"""
        try:
            self.client.table('otp_challenges').update({
                'is_verified': True,
                'verified_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', otp_id).execute()
        except Exception as e:
            print(f"❌ Error verifying OTP: {e}")
            raise