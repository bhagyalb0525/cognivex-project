/**
 * COGNIVEX - Behavior Monitor
 * Frontend JavaScript for capturing behavioral events
 * FIXED: Corrected startSnapshotTimer() method name
 * UPDATED: OTP Modal UI instead of prompt
 */

class BehaviorMonitor {
    constructor(userId, sessionId) {
        this.userId = userId;
        this.sessionId = sessionId;
        this.keyEvents = [];
        this.mouseEvents = [];
        this.scrollEvents = [];
        this.startTime = Date.now();
        
        console.log('📊 BehaviorMonitor initialized');
        console.log(`   User ID: ${userId}`);
        console.log(`   Session ID: ${sessionId}`);
        
        this.setupListeners();
        this.startSnapshotTimer();
    }
    
    setupListeners() {
        console.log('⚙️ Setting up event listeners...');
        
        // Capture keyboard events
        document.addEventListener('keydown', (e) => {
            this.keyEvents.push({
                type: 'keydown',
                key: e.key,
                timestamp: Date.now() - this.startTime
            });
        });
        
        document.addEventListener('keyup', (e) => {
            this.keyEvents.push({
                type: 'keyup',
                key: e.key,
                timestamp: Date.now() - this.startTime
            });
        });
        
        // Capture mouse events
        document.addEventListener('mousemove', (e) => {
            this.mouseEvents.push({
                x: e.clientX,
                y: e.clientY,
                timestamp: Date.now() - this.startTime
            });
        });
        
        // Capture scroll events
        window.addEventListener('scroll', () => {
            this.scrollEvents.push({
                timestamp: Date.now() - this.startTime
            });
        });
        
        console.log('✅ Event listeners attached');
    }
    
    startSnapshotTimer() {
        console.log('⏱️ Starting snapshot timer (30 seconds)');
        
        // Send snapshot every 30 seconds
        this.snapshotInterval = setInterval(() => {
            this.sendSnapshot();
        }, 30000);
    }
    
    async sendSnapshot() {
        console.log('\n📤 Sending behavioral snapshot...');
        
        // Prepare raw data
        const rawData = {
            key_events: this.keyEvents,
            mouse_events: this.mouseEvents,
            scroll_events: this.scrollEvents,
            summary: {
                captured_at: new Date().toISOString(),
                key_count: this.keyEvents.length,
                mouse_count: this.mouseEvents.length,
                scroll_count: this.scrollEvents.length
            }
        };
        
        console.log(`   Key events: ${this.keyEvents.length}`);
        console.log(`   Mouse events: ${this.mouseEvents.length}`);
        console.log(`   Scroll events: ${this.scrollEvents.length}`);
        
        try {
            const response = await fetch('http://localhost:5000/session/snapshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.userId,
                    session_id: this.sessionId,
                    raw_data: rawData
                })
            });
            
            const data = await response.json();
            console.log('📥 Snapshot Response:', data);
            
            // Update UI with risk level
            this.updateRiskIndicator(data.risk_level);
            
            // Handle based on status
            if (data.status === 'SESSION_TERMINATED') {
                console.error('🚨 HIGH RISK DETECTED - SESSION TERMINATED');
                alert(data.message);
                this.endSession();
                window.location.href = 'index.html';
                return;
            }
            
            if (data.status === 'OTP_REQUIRED') {
                console.warn('⚠️ OTP REQUIRED FOR MEDIUM RISK');
                showOTPModal(this.sessionId, data.message, this.userId);
                return;
            }
            
            if (data.status === 'OK') {
                console.log('✅ LOW RISK - Activity normal');
            }
            
            // Reset for next snapshot
            this.keyEvents = [];
            this.mouseEvents = [];
            this.scrollEvents = [];
            this.startTime = Date.now();
            
        } catch (error) {
            console.error('❌ Error sending snapshot:', error);
        }
    }
    
    async verifyOTP(otpCode) {
        console.log('🔐 Verifying OTP code...');
        
        try {
            const response = await fetch('http://localhost:5000/verify-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.userId,
                    session_id: this.sessionId,
                    otp_code: otpCode
                })
            });
            
            const data = await response.json();
            console.log('🔐 OTP Response:', data);
            
            if (data.status === 'SESSION_TERMINATED') {
                console.error('❌ OTP verification failed - SESSION TERMINATED');
                alert(data.message);
                this.endSession();
                window.location.href = 'index.html';
            } else if (data.status === 'OTP_VERIFIED') {
                console.log('✅ OTP verified successfully!');
                alert('✅ OTP verified! Your session continues.');
            }
        } catch (error) {
            console.error('❌ Error verifying OTP:', error);
        }
    }
    
    updateRiskIndicator(riskLevel) {
        // Update header security status
        if (typeof window.updateHeaderSecurityStatus === 'function') {
            window.updateHeaderSecurityStatus(riskLevel);
        }
    }
    
    async endSession() {
        console.log('🏁 Ending session...');
        
        try {
            const response = await fetch('http://localhost:5000/session/end', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.userId,
                    session_id: this.sessionId
                })
            });
            
            const data = await response.json();
            console.log('🏁 Session End Response:', data);
            
        } catch (error) {
            console.error('❌ Error ending session:', error);
        }
    }
    
    stopMonitoring() {
        console.log('⏹️ Stopping behavioral monitoring');
        
        if (this.snapshotInterval) {
            clearInterval(this.snapshotInterval);
        }
    }
}

// ========== OTP MODAL FUNCTIONS ==========

function showOTPModal(sessionId, message, userId) {
    console.log('Showing OTP modal. Message:', message);
    
    // Extract OTP code from message (format: "⚠️ Unusual behavior. OTP: 1234")
    // But DON'T display it in the modal - only in terminal!
    const otpMatch = message.match(/OTP: (\d+)/);
    const otpCode = otpMatch ? otpMatch[1] : '';
    
    console.log('⚠️ OTP Code:', otpCode);
    console.log('⚠️ User must check terminal to see OTP!');
    
    // Show the modal
    const modal = document.getElementById('otpModal');
    // DON'T set otpDisplayCode - we're not showing it!
    document.getElementById('otpSessionId').value = sessionId;
    document.getElementById('otpUserId').value = userId;
    modal.style.display = 'flex';
    
    // Hide any previous error messages
    document.getElementById('otpError').style.display = 'none';
    
    // Focus on input field
    document.getElementById('otpVerifyInput').focus();
}

async function closeOTPModal() {
    const modal = document.getElementById('otpModal');
    modal.style.display = 'none';
    document.getElementById('otpVerifyInput').value = '';
    document.getElementById('otpError').style.display = 'none';

    // Stop monitoring + notify backend
    if (window.behaviorMonitor) {
        window.behaviorMonitor.stopMonitoring();
        await window.behaviorMonitor.endSession();
    }

    // ✅ FIX: Must call authHandler.logout() to clear the Supabase auth session.
    // Without this, index.html's checkSession() sees an active session and
    // immediately redirects back to dashboard.html — so logout appeared broken.
    if (window.authHandler) {
        try {
            await window.authHandler.logout(); // handles redirect internally
        } catch (_) {
            window.location.href = 'index.html';
        }
    } else {
        window.location.href = 'index.html';
    }
}

function submitOTP() {
    const otpCode = document.getElementById('otpVerifyInput').value;
    const sessionId = document.getElementById('otpSessionId').value;
    const userId = document.getElementById('otpUserId').value;
    
    console.log('Submitting OTP:', otpCode);
    
    if (otpCode.length !== 4) {
        showOTPError('Please enter a 4-digit code');
        return;
    }
    
    // Send OTP verification to backend
    fetch('http://localhost:5000/verify-otp', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: userId,
            session_id: sessionId,
            otp_code: otpCode
        })
    })
    .then(res => res.json())
    .then(data => {
        console.log('OTP Verification Response:', data);
        
        if (data.status === 'OTP_VERIFIED') {
            console.log('✅ OTP verified! Session continues.');
            
            // Close modal and hide error
            const modal = document.getElementById('otpModal');
            modal.style.display = 'none';
            document.getElementById('otpError').style.display = 'none';
            
            // Update UI - show success message
            if (typeof window.updateHeaderSecurityStatus === 'function') {
                window.updateHeaderSecurityStatus('LOW');
            }
            
            // Clear input
            document.getElementById('otpVerifyInput').value = '';
        } else {
            showOTPError('❌ Invalid or expired OTP');
            document.getElementById('otpVerifyInput').value = '';
            document.getElementById('otpVerifyInput').focus();
        }
    })
    .catch(error => {
        console.error('Error verifying OTP:', error);
        showOTPError('Error verifying OTP. Try again.');
    });
}

function showOTPError(message) {
    const errorDiv = document.getElementById('otpError');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

// Allow Enter key to submit OTP
document.addEventListener('DOMContentLoaded', function() {
    const otpInput = document.getElementById('otpVerifyInput');
    if (otpInput) {
        otpInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                submitOTP();
            }
        });
    }
});

// Export for use in other scripts
window.BehaviorMonitor = BehaviorMonitor;

// Global function to initialize behavior monitoring
window.initializeSession = function(userId) {
    console.log('\n' + '='*70);
    console.log('🚀 COGNIVEX - BEHAVIORAL MONITORING INITIALIZED');
    console.log('='*70 + '\n');
    
    const sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    
    window.behaviorMonitor = new BehaviorMonitor(userId, sessionId);
    
    // End session when user leaves
    window.addEventListener('beforeunload', () => {
        window.behaviorMonitor.endSession();
        window.behaviorMonitor.stopMonitoring();
    });
    
    console.log(`\n📍 Monitoring active on session: ${sessionId}\n`);
};