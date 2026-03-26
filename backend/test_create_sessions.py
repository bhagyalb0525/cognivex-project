"""
COGNIVEX - One-time retrain script
Reads existing rows from behavior_features, trains model v1,
saves model + scaler+stats bundle to model_metadata.

Run ONCE after deleting the old model_metadata row:
  DELETE FROM model_metadata WHERE user_id = 'your-user-id';
  python retrain_from_db.py
"""

import os, io, base64, joblib, numpy as np
from dotenv import load_dotenv
from supabase import create_client
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timezone

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
client = create_client(SUPABASE_URL, SUPABASE_KEY)

FEATURE_ORDER = [
    'typing_speed', 'backspace_ratio', 'avg_keystroke_interval',
    'keystroke_variance', 'avg_mouse_speed', 'mouse_move_variance',
    'scroll_frequency'
    # idle_ratio excluded — zero variance, useless
]

# ── 1. Fetch user ───────────────────────────────────────────────────────────
users = client.auth.admin.list_users()
user_list = users.users if hasattr(users, 'users') else users
user  = user_list[0]
uid   = user.id
print(f"User: {user.email} ({uid})")

# ── 2. Fetch behavior_features rows ────────────────────────────────────────
resp = client.table('behavior_features').select('*').eq(
    'user_id', uid
).order('created_at', desc=False).execute()

rows = resp.data
print(f"Found {len(rows)} sessions in behavior_features")

if len(rows) < 5:
    print("❌ Need at least 5 sessions. Exiting.")
    exit(1)

# Use up to latest 15
rows = rows[-15:]
print(f"Training on {len(rows)} sessions")

# ── 3. Build feature matrix ─────────────────────────────────────────────────
X = np.array([[r[f] for f in FEATURE_ORDER] for r in rows])
print("\nFeature ranges:")
for i, n in enumerate(FEATURE_ORDER):
    print(f"  {n}: {X[:,i].min():.4f} – {X[:,i].max():.4f}  mean={X[:,i].mean():.4f}")

# ── 4. Train ────────────────────────────────────────────────────────────────
means  = X.mean(axis=0).tolist()
stds   = X.std(axis=0).tolist()
stats  = {'means': means, 'stds': stds}

scaler = StandardScaler()
X_norm = scaler.fit_transform(X)
model  = IsolationForest(contamination=0.1, n_estimators=200, random_state=42)
model.fit(X_norm)

scores = model.decision_function(X_norm)
print(f"\nTraining scores: min={scores.min():.4f}  max={scores.max():.4f}")

# ── 5. Serialize ────────────────────────────────────────────────────────────
def to_b64(obj):
    buf = io.BytesIO(); joblib.dump(obj, buf)
    return base64.b64encode(buf.getvalue()).decode()

model_b64  = to_b64(model)
# scaler_data column stores scaler + stats together as a bundle
scaler_b64 = to_b64({'scaler': scaler, 'stats': stats})

# ── 6. Save to model_metadata ───────────────────────────────────────────────
total = len(resp.data)  # total sessions in DB (not just training slice)

existing = client.table('model_metadata').select('id').eq('user_id', uid).execute()

payload = {
    'user_id':           uid,
    'model_data':        model_b64,
    'scaler_data':       scaler_b64,
    'model_version':     1,
    'total_sessions':    total,
    'last_trained_count': total,
    'last_trained_at':   datetime.now(timezone.utc).isoformat(),
}

if existing.data:
    client.table('model_metadata').update(payload).eq('user_id', uid).execute()
    print("✅ Updated existing model_metadata row")
else:
    client.table('model_metadata').insert(payload).execute()
    print("✅ Inserted new model_metadata row")

print(f"\n🎉 Done! Model v1 trained on {len(rows)} sessions, total={total}")
print("Restart main.py — anomaly detection is live from the next session.")