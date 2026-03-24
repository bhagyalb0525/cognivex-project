"""
COGNIVEX - Feature Extractor
Extracts 8 behavioral features from raw event data
"""

import numpy as np
from typing import Dict, List, Any

class FeatureExtractor:
    
    @staticmethod
    def extract(rawData: Dict[str, Any]) -> Dict[str, float]:
        """Extract 8 features from raw data"""
        
        keyEvents = rawData.get('key_events', [])
        mouseEvents = rawData.get('mouse_events', [])
        scrollEvents = rawData.get('scroll_events', [])
        
        features = {
            'typing_speed': FeatureExtractor.getTypingSpeed(keyEvents),
            'backspace_ratio': FeatureExtractor.getBackspaceRatio(keyEvents),
            'avg_keystroke_interval': FeatureExtractor.getKeystrokeInterval(keyEvents),
            'keystroke_variance': FeatureExtractor.getKeystrokeVariance(keyEvents),
            'avg_mouse_speed': FeatureExtractor.getMouseSpeed(mouseEvents),
            'mouse_move_variance': FeatureExtractor.getMouseVariance(mouseEvents),
            'scroll_frequency': FeatureExtractor.getScrollFrequency(scrollEvents),
            'idle_ratio': FeatureExtractor.getIdleRatio(keyEvents)
        }
        
        return features
    
    @staticmethod
    def getTypingSpeed(keyEvents: List[Dict]) -> float:
        """Feature 1: Typing speed (keys per second)"""
        if len(keyEvents) < 2:
            return 0
        
        keyups = [e for e in keyEvents if e.get('type') == 'keyup']
        if not keyups:
            return 0
            
        duration = (keyEvents[-1].get('timestamp', 0) - keyEvents[0].get('timestamp', 0)) / 1000
        
        if duration == 0:
            return 0
        return len(keyups) / duration
    
    @staticmethod
    def getBackspaceRatio(keyEvents: List[Dict]) -> float:
        """Feature 2: Backspace ratio"""
        if len(keyEvents) == 0:
            return 0
        
        backspaces = len([e for e in keyEvents if e.get('key') == 'Backspace'])
        return backspaces / len(keyEvents)
    
    @staticmethod
    def getKeystrokeInterval(keyEvents: List[Dict]) -> float:
        """Feature 3: Average keystroke interval (seconds)"""
        keyups = [e for e in keyEvents if e.get('type') == 'keyup']
        
        if len(keyups) < 2:
            return 0
        
        totalInterval = sum([keyups[i+1].get('timestamp', 0) - keyups[i].get('timestamp', 0) 
                            for i in range(len(keyups)-1)])
        
        return (totalInterval / (len(keyups) - 1)) / 1000
    
    @staticmethod
    def getKeystrokeVariance(keyEvents: List[Dict]) -> float:
        """Feature 4: Keystroke variance"""
        keyups = [e for e in keyEvents if e.get('type') == 'keyup']
        
        if len(keyups) < 2:
            return 0
        
        intervals = [keyups[i+1].get('timestamp', 0) - keyups[i].get('timestamp', 0) 
                    for i in range(len(keyups)-1)]
        
        mean = sum(intervals) / len(intervals)
        variance = sum([(x - mean)**2 for x in intervals]) / len(intervals)
        
        return np.sqrt(variance) / 1000
    
    @staticmethod
    def getMouseSpeed(mouseEvents: List[Dict]) -> float:
        """Feature 5: Average mouse speed (pixels per second)"""
        if len(mouseEvents) < 2:
            return 0
        
        totalDistance = 0
        for i in range(len(mouseEvents) - 1):
            current = mouseEvents[i]
            next_pos = mouseEvents[i+1]
            
            distance = np.sqrt(
                (next_pos.get('x', 0) - current.get('x', 0))**2 + 
                (next_pos.get('y', 0) - current.get('y', 0))**2
            )
            totalDistance += distance
        
        duration = (mouseEvents[-1].get('timestamp', 0) - mouseEvents[0].get('timestamp', 0)) / 1000
        
        if duration == 0:
            return 0
        return totalDistance / duration
    
    @staticmethod
    def getMouseVariance(mouseEvents: List[Dict]) -> float:
        """Feature 6: Mouse movement variance"""
        if len(mouseEvents) < 2:
            return 0
        
        speeds = []
        for i in range(len(mouseEvents) - 1):
            current = mouseEvents[i]
            next_pos = mouseEvents[i+1]
            
            distance = np.sqrt(
                (next_pos.get('x', 0) - current.get('x', 0))**2 + 
                (next_pos.get('y', 0) - current.get('y', 0))**2
            )
            timeDiff = (next_pos.get('timestamp', 0) - current.get('timestamp', 0)) / 1000
            
            if timeDiff > 0:
                speeds.append(distance / timeDiff)
        
        if len(speeds) == 0:
            return 0
        
        mean = sum(speeds) / len(speeds)
        variance = sum([(x - mean)**2 for x in speeds]) / len(speeds)
        
        return np.sqrt(variance)
    
    @staticmethod
    def getScrollFrequency(scrollEvents: List[Dict]) -> float:
        """Feature 7: Scroll frequency (scrolls per second)"""
        if len(scrollEvents) < 2:
            return 0
        
        duration = (scrollEvents[-1].get('timestamp', 0) - scrollEvents[0].get('timestamp', 0)) / 1000
        
        if duration == 0:
            return 0
        return len(scrollEvents) / duration
    
    @staticmethod
    def getIdleRatio(keyEvents: List[Dict]) -> float:
        """Feature 8: Idle ratio"""
        keyups = [e for e in keyEvents if e.get('type') == 'keyup']
        
        if len(keyups) < 2:
            return 0
        
        activeTime = sum([keyups[i+1].get('timestamp', 0) - keyups[i].get('timestamp', 0) 
                         for i in range(len(keyups)-1)])
        
        totalTime = keyups[-1].get('timestamp', 0) - keyups[0].get('timestamp', 0)
        
        if totalTime == 0:
            return 0
        
        return 1 - (activeTime / totalTime)
    
    @staticmethod
    def aggregateFeatures(snapshots: List[Dict]) -> Dict[str, float]:
        """Aggregate features from LOW-RISK snapshots only"""
        
        if len(snapshots) == 0:
            return FeatureExtractor.getDefaultFeatures()
        
        allFeatures = []
        for snapshot in snapshots:
            # Only use LOW risk snapshots for training data
            if snapshot.get('risk_level') != 'LOW':
                continue
            
            rawData = snapshot.get('raw_data') or snapshot
            features = FeatureExtractor.extract(rawData)
            allFeatures.append(features)
        
        if not allFeatures:
            # Fallback: use all snapshots if no LOW risk data
            for snapshot in snapshots:
                rawData = snapshot.get('raw_data') or snapshot
                features = FeatureExtractor.extract(rawData)
                allFeatures.append(features)
        
        # Average across all snapshots
        aggregated = {}
        featureNames = list(allFeatures[0].keys())
        
        for featureName in featureNames:
            values = [f[featureName] for f in allFeatures]
            avg = sum(values) / len(values)
            aggregated[featureName] = float(round(avg, 6))
        
        return aggregated
    
    @staticmethod
    def getDefaultFeatures() -> Dict[str, float]:
        """Get default zero features"""
        return {
            'typing_speed': 0,
            'backspace_ratio': 0,
            'avg_keystroke_interval': 0,
            'keystroke_variance': 0,
            'avg_mouse_speed': 0,
            'mouse_move_variance': 0,
            'scroll_frequency': 0,
            'idle_ratio': 0
        }