"""
COGNIVEX - OTP Controller
In-memory OTP generation and verification
OTP codes printed to terminal for testing
"""

import random
import string
from datetime import datetime, timedelta

class OTPController:
    
    def __init__(self, supabase):
        self.supabase = supabase
        self.otp_storage = {}  # {session_id: {'code': 'XXXX', 'expires_at': time}}
    
    def generateOTP(self, user_id: str = None, session_id: str = None) -> str:
        """Generate OTP in memory and print to terminal"""
        
        print(f"   Creating OTP challenge...")
        
        # Generate random 4-digit OTP
        otpCode = ''.join(random.choices(string.digits, k=4))
        
        # Store in memory
        expires_at = datetime.now() + timedelta(minutes=2)
        
        if session_id:
            self.otp_storage[session_id] = {
                'user_id': user_id,
                'code': otpCode,
                'expires_at': expires_at
            }
        
        # PRINT TO TERMINAL FOR TESTING
        print(f"\n" + "="*70)
        print(f"   🔐 OTP GENERATED (MEDIUM RISK DETECTED)")
        print(f"   {'='*70}")
        print(f"   📧 OTP Code: {otpCode}")
        print(f"   Expires at: {expires_at.strftime('%H:%M:%S')}")
        if session_id:
            print(f"   Session ID: {session_id}")
        print(f"   {'='*70}\n")
        
        return otpCode
    
    def createOTP(self, user_id: str, session_id: str) -> str:
        """Alias for generateOTP for backward compatibility"""
        return self.generateOTP(user_id, session_id)
    
    def storeOTP(self, user_id: str, session_id: str, otp_code: str, ip_address: str) -> str:
        """Store OTP to database"""
        try:
            return self.supabase.store_otp(user_id, session_id, otp_code, ip_address)
        except Exception as e:
            print(f"   ⚠️ Error storing OTP to database: {e}")
            return None
    
    def verifyOTP(self, user_id: str, session_id: str, provided_code: str) -> dict:
        """Verify OTP from memory"""
        
        print(f"   Verifying OTP...")
        
        # Check if OTP exists for this session
        if session_id not in self.otp_storage:
            print(f"   ❌ No OTP generated for this session")
            return {
                'valid': False,
                'reason': 'No OTP generated for this session'
            }
        
        otp_data = self.otp_storage[session_id]
        stored_code = otp_data['code']
        expires_at = otp_data['expires_at']
        
        print(f"   Provided code: {provided_code}")
        print(f"   Stored code: {stored_code}")
        
        # Check expiry
        if datetime.now() > expires_at:
            print(f"   ⏰ OTP expired")
            del self.otp_storage[session_id]
            return {
                'valid': False,
                'reason': 'OTP expired'
            }
        
        # Check code
        if str(stored_code) == str(provided_code).strip():
            print(f"   ✅ OTP VERIFIED!")
            del self.otp_storage[session_id]
            return {
                'valid': True,
                'reason': 'OTP verified successfully'
            }
        else:
            print(f"   ❌ OTP does not match")
            return {
                'valid': False,
                'reason': 'OTP does not match'
            }
    
    def checkCooldown(self, user_id: str, session_id: str) -> bool:
        """Check if in cooldown (placeholder for now)"""
        return False
    
    def getOTPStorage(self):
        """Debug: see what's in memory"""
        return self.otp_storage