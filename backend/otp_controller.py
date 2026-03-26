"""
COGNIVEX - OTP Controller
In-memory OTP with:
  - 2-minute expiry per OTP code
  - 5-minute cooldown between OTP challenges per session
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Optional


class OTPController:

    OTP_EXPIRY_MINUTES = 2
    COOLDOWN_MINUTES   = 5   # min gap between two OTP challenges in same session

    def __init__(self, supabase=None):
        # {user_id: {session_id: {code, expires_at, attempts, last_issued_at}}}
        self.otp_store: Dict[str, Dict[str, Dict]] = {}

    def _get(self, user_id: str, session_id: str) -> Optional[Dict]:
        return self.otp_store.get(user_id, {}).get(session_id)

    def isCoolingDown(self, user_id: str, session_id: str) -> bool:
        """Returns True if cooldown is still active — skip OTP challenge."""
        record = self._get(user_id, session_id)
        if not record:
            return False
        last = record.get('last_issued_at')
        if not last:
            return False
        return datetime.now() < last + timedelta(minutes=self.COOLDOWN_MINUTES)

    def generateOTP(self) -> str:
        return str(random.randint(1000, 9999))

    def storeOTP(self, user_id: str, session_id: str, otp_code: str, ip_address: str = None):
        if user_id not in self.otp_store:
            self.otp_store[user_id] = {}

        now = datetime.now()
        self.otp_store[user_id][session_id] = {
            'code':           otp_code,
            'expires_at':     now + timedelta(minutes=self.OTP_EXPIRY_MINUTES),
            'last_issued_at': None,  # set only after successful verification
            'attempts':       0,
        }
        print(f"   OTP stored — expires {self.OTP_EXPIRY_MINUTES} min, "
              f"cooldown {self.COOLDOWN_MINUTES} min")

    def verifyOTP(self, user_id: str, session_id: str, otp_code: str) -> Dict:
        record = self._get(user_id, session_id)

        if not record:
            return {'valid': False, 'reason': 'No OTP generated for this session'}

        if datetime.now() > record['expires_at']:
            del self.otp_store[user_id][session_id]
            return {'valid': False, 'reason': 'OTP expired'}

        if record['attempts'] >= 3:
            del self.otp_store[user_id][session_id]
            return {'valid': False, 'reason': 'Too many attempts'}

        if record['code'] != otp_code:
            record['attempts'] += 1
            remaining = 3 - record['attempts']
            return {'valid': False,
                    'reason': f'Invalid OTP — {remaining} attempt(s) remaining'}

        # Valid — now activate cooldown
        record['code']           = None
        record['expires_at']     = datetime.now()
        record['last_issued_at'] = datetime.now()
        return {'valid': True, 'reason': 'OTP verified successfully'}