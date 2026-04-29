#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

# Add skill path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.user_main import RatingUserSkill

# Create skill instance
skill = RatingUserSkill()

# Test data
user_id = 'ou_9b6700282aa925e38877623705a5c58e'
user_name = '林丰丰'

# Get default data
data = skill._get_default_data()
print('Data:', data)

# Calculate scores
scores = skill.auto_calculate_score(data)
print('Scores:', scores)

# Submit rating
success, msg = skill.submit_rating(user_id, user_name, data, scores)
print('Submit result:', success, msg)
