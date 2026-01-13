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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    products = db.relationship('Product', backref='user', lazy=True)
    meal_entries = db.relationship('MealEntry', backref='user', lazy=True)
    recipes = db.relationship('Recipe', backref='user', lazy=True)
    daily_goal = db.relationship('DailyGoal', backref='user', uselist=False, lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


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

    def __repr__(self):
        return f'<Product {self.name}>'

    def get_nutrition_for_weight(self, weight):
        """Calculate nutrition for given weight in grams"""
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

    def __repr__(self):
        return f'<Recipe {self.name}>'

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

    def __repr__(self):
        return f'<RecipeIngredient {self.product.name} {self.weight}g>'

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

    def __repr__(self):
        return f'<MealEntry {self.product.name} - {self.meal_type}>'

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

    @classmethod
    def get_goals(cls, user_id):
        goal = cls.query.filter_by(user_id=user_id).first()
        if not goal:
            goal = cls(user_id=user_id)
            db.session.add(goal)
            db.session.commit()
        return goal