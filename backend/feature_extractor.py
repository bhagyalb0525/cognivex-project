"""
COGNIVEX - Feature Extractor
Extracts 8 behavioral features from raw event data.
"""

import numpy as np
from typing import Dict, List, Any


class FeatureExtractor:

    @staticmethod
    def extract(raw_data: Dict[str, Any]) -> Dict[str, float]:
        key_events    = raw_data.get('key_events', [])
        mouse_events  = raw_data.get('mouse_events', [])
        scroll_events = raw_data.get('scroll_events', [])

        return {
            'typing_speed':           FeatureExtractor._typing_speed(key_events),
            'backspace_ratio':        FeatureExtractor._backspace_ratio(key_events),
            'avg_keystroke_interval': FeatureExtractor._keystroke_interval(key_events),
            'keystroke_variance':     FeatureExtractor._keystroke_variance(key_events),
            'avg_mouse_speed':        FeatureExtractor._mouse_speed(mouse_events),
            'mouse_move_variance':    FeatureExtractor._mouse_variance(mouse_events),
            'scroll_frequency':       FeatureExtractor._scroll_frequency(scroll_events),
            'idle_ratio':             FeatureExtractor._idle_ratio(key_events),
        }

    # ── Feature helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _keyups(key_events):
        return [e for e in key_events if e.get('type') == 'keyup']

    @staticmethod
    def _typing_speed(key_events):
        if len(key_events) < 2:
            return 0.0
        keyups    = FeatureExtractor._keyups(key_events)
        duration  = (key_events[-1]['timestamp'] - key_events[0]['timestamp']) / 1000
        return len(keyups) / duration if duration > 0 else 0.0

    @staticmethod
    def _backspace_ratio(key_events):
        if not key_events:
            return 0.0
        return len([e for e in key_events if e.get('key') == 'Backspace']) / len(key_events)

    @staticmethod
    def _keystroke_interval(key_events):
        keyups = FeatureExtractor._keyups(key_events)
        if len(keyups) < 2:
            return 0.0
        intervals = [keyups[i+1]['timestamp'] - keyups[i]['timestamp']
                     for i in range(len(keyups) - 1)]
        return (sum(intervals) / len(intervals)) / 1000

    @staticmethod
    def _keystroke_variance(key_events):
        keyups = FeatureExtractor._keyups(key_events)
        if len(keyups) < 2:
            return 0.0
        intervals = [keyups[i+1]['timestamp'] - keyups[i]['timestamp']
                     for i in range(len(keyups) - 1)]
        return float(np.std(intervals) / 1000)

    @staticmethod
    def _mouse_speed(mouse_events):
        if len(mouse_events) < 2:
            return 0.0
        dist = sum(
            np.sqrt((mouse_events[i+1]['x'] - mouse_events[i]['x'])**2 +
                    (mouse_events[i+1]['y'] - mouse_events[i]['y'])**2)
            for i in range(len(mouse_events) - 1)
        )
        duration = (mouse_events[-1]['timestamp'] - mouse_events[0]['timestamp']) / 1000
        return dist / duration if duration > 0 else 0.0

    @staticmethod
    def _mouse_variance(mouse_events):
        if len(mouse_events) < 2:
            return 0.0
        speeds = []
        for i in range(len(mouse_events) - 1):
            dx = mouse_events[i+1]['x'] - mouse_events[i]['x']
            dy = mouse_events[i+1]['y'] - mouse_events[i]['y']
            dt = (mouse_events[i+1]['timestamp'] - mouse_events[i]['timestamp']) / 1000
            if dt > 0:
                speeds.append(np.sqrt(dx**2 + dy**2) / dt)
        return float(np.std(speeds)) if speeds else 0.0

    @staticmethod
    def _scroll_frequency(scroll_events):
        if len(scroll_events) < 2:
            return 0.0
        duration = (scroll_events[-1]['timestamp'] - scroll_events[0]['timestamp']) / 1000
        return len(scroll_events) / duration if duration > 0 else 0.0

    @staticmethod
    def _idle_ratio(key_events):
        keyups = FeatureExtractor._keyups(key_events)
        if len(keyups) < 2:
            return 0.0
        active    = sum(keyups[i+1]['timestamp'] - keyups[i]['timestamp']
                        for i in range(len(keyups) - 1))
        total     = keyups[-1]['timestamp'] - keyups[0]['timestamp']
        return 1.0 - (active / total) if total > 0 else 0.0

    # ── Aggregation ─────────────────────────────────────────────────────────

    @staticmethod
    def aggregateFeatures(snapshots: List[Dict]) -> Dict[str, float]:
        """
        Average features across LOW-risk snapshots.
        Snapshots are already filtered to LOW by the DB query — no need to re-filter.
        """
        if not snapshots:
            return FeatureExtractor._defaults()

        all_features = [FeatureExtractor.extract(s.get('raw_data') or s)
                        for s in snapshots]

        keys = list(all_features[0].keys())
        return {k: round(sum(f[k] for f in all_features) / len(all_features), 6)
                for k in keys}

    @staticmethod
    def _defaults() -> Dict[str, float]:
        return {k: 0.0 for k in [
            'typing_speed', 'backspace_ratio', 'avg_keystroke_interval',
            'keystroke_variance', 'avg_mouse_speed', 'mouse_move_variance',
            'scroll_frequency', 'idle_ratio'
        ]}