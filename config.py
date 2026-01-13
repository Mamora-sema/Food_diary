# config.py
import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-super-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///meals.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Daily recommended values (defaults)
    DAILY_CALORIES = 2000
    DAILY_PROTEIN = 50
    DAILY_FAT = 65
    DAILY_CARBS = 300