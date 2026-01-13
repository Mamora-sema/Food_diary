# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model for authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    weight = db.Column(db.Float, default=70.0)  # Вес пользователя в кг
    is_setup_complete = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    products = db.relationship('Product', backref='user', lazy=True, cascade='all, delete-orphan')
    meal_entries = db.relationship('MealEntry', backref='user', lazy=True, cascade='all, delete-orphan')
    recipes = db.relationship('Recipe', backref='user', lazy=True, cascade='all, delete-orphan')
    daily_goal = db.relationship('DailyGoal', backref='user', uselist=False, lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'weight': self.weight,
            'is_setup_complete': self.is_setup_complete
        }


class Product(db.Model):
    """Food products with nutritional information per 100g"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    calories = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, nullable=False)
    fat = db.Column(db.Float, nullable=False)
    carbs = db.Column(db.Float, nullable=False)
    is_recipe = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'calories': self.calories,
            'protein': self.protein,
            'fat': self.fat,
            'carbs': self.carbs,
            'is_recipe': self.is_recipe
        }

    def get_nutrition_for_weight(self, weight):
        multiplier = weight / 100
        return {
            'calories': round(self.calories * multiplier, 1),
            'protein': round(self.protein * multiplier, 1),
            'fat': round(self.fat * multiplier, 1),
            'carbs': round(self.carbs * multiplier, 1)
        }


class Recipe(db.Model):
    """Recipe that combines multiple products"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ingredients = db.relationship('RecipeIngredient', backref='recipe', lazy=True, cascade='all, delete-orphan')
    product = db.relationship('Product', backref='recipe_source', foreign_keys=[product_id])

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'product_id': self.product_id,
            'ingredients': [ing.to_dict() for ing in self.ingredients],
            'total_weight': self.total_weight,
            'total_nutrition': self.total_nutrition,
            'nutrition_per_100g': self.nutrition_per_100g
        }

    @property
    def total_weight(self):
        return sum(ing.weight for ing in self.ingredients)

    @property
    def total_nutrition(self):
        totals = {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0}
        for ing in self.ingredients:
            nutrition = ing.product.get_nutrition_for_weight(ing.weight)
            for key in totals:
                totals[key] += nutrition[key]
        return {k: round(v, 1) for k, v in totals.items()}

    @property
    def nutrition_per_100g(self):
        total_weight = self.total_weight
        if total_weight == 0:
            return {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0}

        total = self.total_nutrition
        multiplier = 100 / total_weight
        return {
            'calories': round(total['calories'] * multiplier, 1),
            'protein': round(total['protein'] * multiplier, 1),
            'fat': round(total['fat'] * multiplier, 1),
            'carbs': round(total['carbs'] * multiplier, 1)
        }


class RecipeIngredient(db.Model):
    """Ingredient in a recipe"""
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    weight = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='recipe_ingredients', foreign_keys=[product_id])

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'weight': self.weight,
            'nutrition': self.nutrition
        }

    @property
    def nutrition(self):
        return self.product.get_nutrition_for_weight(self.weight)


class MealEntry(db.Model):
    """Individual meal entries"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref=db.backref('entries', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'product_is_recipe': self.product.is_recipe if self.product else False,
            'meal_type': self.meal_type,
            'weight': self.weight,
            'date': self.date.isoformat(),
            'nutrition': self.nutrition
        }

    @property
    def nutrition(self):
        return self.product.get_nutrition_for_weight(self.weight)


class DailyGoal(db.Model):
    """User's daily nutritional goals"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    calories = db.Column(db.Float, default=2000)
    protein = db.Column(db.Float, default=50)
    fat = db.Column(db.Float, default=65)
    carbs = db.Column(db.Float, default=300)

    def to_dict(self):
        return {
            'calories': self.calories,
            'protein': self.protein,
            'fat': self.fat,
            'carbs': self.carbs
        }

    @classmethod
    def get_goals(cls, user_id):
        goal = cls.query.filter_by(user_id=user_id).first()
        if not goal:
            goal = cls(user_id=user_id)
            db.session.add(goal)
            db.session.commit()
        return goal

    @staticmethod
    def calculate_calories(protein, fat, carbs):
        """Calculate calories from macros: P*4 + F*9 + C*4"""
        return round((protein * 4) + (fat * 9) + (carbs * 4), 1)

    @staticmethod
    def calculate_recommended(weight, activity_level='moderate'):
        """
        Рассчитать рекомендуемые БЖУ на основе веса
        activity_level: low, moderate, high, athlete
        """
        # Белки: 1.5-2г на кг веса
        # Жиры: 0.8-1г на кг веса
        # Углеводы: остаток калорий

        activity_multipliers = {
            'low': {'protein': 1.2, 'fat': 0.8, 'carbs': 3},
            'moderate': {'protein': 1.5, 'fat': 1.0, 'carbs': 4},
            'high': {'protein': 1.8, 'fat': 1.0, 'carbs': 5},
            'athlete': {'protein': 2.2, 'fat': 1.2, 'carbs': 6}
        }

        mult = activity_multipliers.get(activity_level, activity_multipliers['moderate'])

        protein = round(weight * mult['protein'])
        fat = round(weight * mult['fat'])
        carbs = round(weight * mult['carbs'])
        calories = DailyGoal.calculate_calories(protein, fat, carbs)

        return {
            'protein': protein,
            'fat': fat,
            'carbs': carbs,
            'calories': calories
        }