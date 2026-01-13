# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, date, timedelta
from config import Config
from models import db, User, Product, MealEntry, DailyGoal, Recipe, RecipeIngredient

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему'
login_manager.login_message_category = 'warning'

# Add timedelta to Jinja2 globals
app.jinja_env.globals['timedelta'] = timedelta


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


MEAL_TYPES = {
    'breakfast': 'Завтрак',
    'lunch': 'Обед',
    'dinner': 'Ужин',
    'snack': 'Перекус'
}


# =====================================================
# AUTHENTICATION ROUTES
# =====================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        if not username or not password:
            flash('Заполните все поля', 'error')
            return redirect(url_for('login'))

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Добро пожаловать, {user.username}!', 'success')

            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')
            return redirect(url_for('login'))

    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        if not username or not password:
            flash('Заполните все поля', 'error')
            return redirect(url_for('register'))

        if len(username) < 3:
            flash('Логин должен содержать минимум 3 символа', 'error')
            return redirect(url_for('register'))

        if len(password) < 4:
            flash('Пароль должен содержать минимум 4 символа', 'error')
            return redirect(url_for('register'))

        if password != password_confirm:
            flash('Пароли не совпадают', 'error')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Пользователь с таким логином уже существует', 'error')
            return redirect(url_for('register'))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Create default products for new user
        create_default_products(user.id)

        flash('Регистрация успешна! Теперь войдите в систему', 'success')
        return redirect(url_for('login'))

    return render_template('auth/register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def get_daily_summary(target_date, user_id):
    """Calculate daily nutritional summary for a user"""
    entries = MealEntry.query.filter_by(date=target_date, user_id=user_id).all()
    goals = DailyGoal.get_goals(user_id)

    totals = {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0}
    meals = {meal_type: [] for meal_type in MEAL_TYPES.keys()}
    meal_totals = {meal_type: {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0}
                   for meal_type in MEAL_TYPES.keys()}

    for entry in entries:
        nutrition = entry.nutrition
        meals[entry.meal_type].append({
            'id': entry.id,
            'product': entry.product,
            'weight': entry.weight,
            'nutrition': nutrition
        })

        for key in totals:
            totals[key] += nutrition[key]
            meal_totals[entry.meal_type][key] += nutrition[key]

    for key in totals:
        totals[key] = round(totals[key], 1)

    percentages = {
        'calories': round((totals['calories'] / goals.calories) * 100, 1) if goals.calories else 0,
        'protein': round((totals['protein'] / goals.protein) * 100, 1) if goals.protein else 0,
        'fat': round((totals['fat'] / goals.fat) * 100, 1) if goals.fat else 0,
        'carbs': round((totals['carbs'] / goals.carbs) * 100, 1) if goals.carbs else 0
    }

    total_macros = totals['protein'] + totals['fat'] + totals['carbs']
    if total_macros > 0:
        macro_breakdown = {
            'protein': round((totals['protein'] / total_macros) * 100, 1),
            'fat': round((totals['fat'] / total_macros) * 100, 1),
            'carbs': round((totals['carbs'] / total_macros) * 100, 1)
        }
    else:
        macro_breakdown = {'protein': 0, 'fat': 0, 'carbs': 0}

    calories_from_protein = totals['protein'] * 4
    calories_from_fat = totals['fat'] * 9
    calories_from_carbs = totals['carbs'] * 4
    total_calculated_calories = calories_from_protein + calories_from_fat + calories_from_carbs

    if total_calculated_calories > 0:
        calorie_breakdown = {
            'protein': round((calories_from_protein / total_calculated_calories) * 100, 1),
            'fat': round((calories_from_fat / total_calculated_calories) * 100, 1),
            'carbs': round((calories_from_carbs / total_calculated_calories) * 100, 1)
        }
    else:
        calorie_breakdown = {'protein': 0, 'fat': 0, 'carbs': 0}

    return {
        'date': target_date,
        'meals': meals,
        'meal_totals': meal_totals,
        'totals': totals,
        'goals': goals,
        'percentages': percentages,
        'macro_breakdown': macro_breakdown,
        'calorie_breakdown': calorie_breakdown,
        'remaining': {
            'calories': round(goals.calories - totals['calories'], 1),
            'protein': round(goals.protein - totals['protein'], 1),
            'fat': round(goals.fat - totals['fat'], 1),
            'carbs': round(goals.carbs - totals['carbs'], 1)
        }
    }


def create_default_products(user_id):
    """Create default products for a new user"""
    default_products = [
        ('Куриная грудка', 165, 31, 3.6, 0),
        ('Рис белый', 130, 2.7, 0.3, 28),
        ('Яйцо куриное', 155, 13, 11, 1.1),
        ('Овсянка', 68, 2.4, 1.4, 12),
        ('Банан', 89, 1.1, 0.3, 23),
        ('Творог 5%', 121, 17, 5, 1.8),
        ('Гречка', 110, 4.2, 1.1, 21),
        ('Молоко 2.5%', 52, 2.8, 2.5, 4.7),
        ('Хлеб белый', 265, 9, 3.2, 49),
        ('Яблоко', 52, 0.3, 0.2, 14),
        ('Говядина', 250, 26, 15, 0),
        ('Лосось', 208, 20, 13, 0),
        ('Картофель', 77, 2, 0.1, 17),
        ('Макароны', 131, 5, 1.1, 25),
        ('Сыр твердый', 402, 25, 33, 1.3),
    ]

    for name, cal, prot, fat, carbs in default_products:
        product = Product(
            user_id=user_id,
            name=name,
            calories=cal,
            protein=prot,
            fat=fat,
            carbs=carbs
        )
        db.session.add(product)

    db.session.commit()


# =====================================================
# MAIN ROUTES
# =====================================================

@app.route('/')
@login_required
def index():
    target_date = request.args.get('date')
    if target_date:
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    else:
        target_date = date.today()

    summary = get_daily_summary(target_date, current_user.id)
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.name).all()

    return render_template('index.html',
                           summary=summary,
                           meal_types=MEAL_TYPES,
                           products=products,
                           today=date.today())


@app.route('/add_meal', methods=['GET', 'POST'])
@login_required
def add_meal():
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        meal_type = request.form.get('meal_type')
        weight = request.form.get('weight', 100)
        meal_date = request.form.get('date', date.today().isoformat())

        if not product_id or not meal_type:
            flash('Выберите продукт и тип приема пищи', 'error')
            return redirect(url_for('add_meal'))

        # Verify product belongs to user
        product = Product.query.filter_by(id=int(product_id), user_id=current_user.id).first()
        if not product:
            flash('Продукт не найден', 'error')
            return redirect(url_for('index'))

        entry = MealEntry(
            user_id=current_user.id,
            product_id=int(product_id),
            meal_type=meal_type,
            weight=float(weight),
            date=datetime.strptime(meal_date, '%Y-%m-%d').date()
        )
        db.session.add(entry)
        db.session.commit()

        flash('Продукт добавлен!', 'success')
        return redirect(url_for('index', date=meal_date))

    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.name).all()
    meal_date = request.args.get('date', date.today().isoformat())
    meal_type = request.args.get('meal_type', 'breakfast')

    return render_template('add_meal.html',
                           products=products,
                           meal_types=MEAL_TYPES,
                           selected_date=meal_date,
                           selected_meal_type=meal_type)


@app.route('/delete_meal/<int:entry_id>', methods=['POST'])
@login_required
def delete_meal(entry_id):
    entry = MealEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    meal_date = entry.date.isoformat()
    db.session.delete(entry)
    db.session.commit()
    flash('Запись удалена', 'success')
    return redirect(url_for('index', date=meal_date))


# =====================================================
# PRODUCTS ROUTES
# =====================================================

@app.route('/products')
@login_required
def products():
    all_products = Product.query.filter_by(user_id=current_user.id).order_by(Product.name).all()
    return render_template('products.html', products=all_products)


@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        calories = request.form.get('calories')
        protein = request.form.get('protein')
        fat = request.form.get('fat')
        carbs = request.form.get('carbs')

        serving_type = request.form.get('serving_type', '100')
        custom_serving = request.form.get('custom_serving', '100')

        if not all([name, calories, protein, fat, carbs]):
            flash('Заполните все поля', 'error')
            return redirect(url_for('add_product'))

        calories = float(calories)
        protein = float(protein)
        fat = float(fat)
        carbs = float(carbs)

        if serving_type == 'custom':
            serving_size = float(custom_serving)
            if serving_size > 0:
                multiplier = 100 / serving_size
                calories = round(calories * multiplier, 1)
                protein = round(protein * multiplier, 1)
                fat = round(fat * multiplier, 1)
                carbs = round(carbs * multiplier, 1)

        product = Product(
            user_id=current_user.id,
            name=name,
            calories=calories,
            protein=protein,
            fat=fat,
            carbs=carbs
        )
        db.session.add(product)
        db.session.commit()

        flash(f'Продукт "{name}" добавлен!', 'success')
        return redirect(url_for('products'))

    return render_template('add_food.html')


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        name = request.form.get('name')
        calories = request.form.get('calories')
        protein = request.form.get('protein')
        fat = request.form.get('fat')
        carbs = request.form.get('carbs')

        serving_type = request.form.get('serving_type', '100')
        custom_serving = request.form.get('custom_serving', '100')

        calories = float(calories)
        protein = float(protein)
        fat = float(fat)
        carbs = float(carbs)

        if serving_type == 'custom':
            serving_size = float(custom_serving)
            if serving_size > 0:
                multiplier = 100 / serving_size
                calories = round(calories * multiplier, 1)
                protein = round(protein * multiplier, 1)
                fat = round(fat * multiplier, 1)
                carbs = round(carbs * multiplier, 1)

        product.name = name
        product.calories = calories
        product.protein = protein
        product.fat = fat
        product.carbs = carbs

        db.session.commit()
        flash('Продукт обновлен!', 'success')
        return redirect(url_for('products'))

    return render_template('add_food.html', product=product, edit=True)


@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
    db.session.delete(product)
    db.session.commit()
    flash('Продукт удален', 'success')
    return redirect(url_for('products'))


# =====================================================
# RECIPES ROUTES
# =====================================================

@app.route('/recipes')
@login_required
def recipes():
    all_recipes = Recipe.query.filter_by(user_id=current_user.id).order_by(Recipe.created_at.desc()).all()
    return render_template('recipes.html', recipes=all_recipes)


@app.route('/add_recipe', methods=['GET', 'POST'])
@login_required
def add_recipe():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')

        if not name:
            flash('Введите название рецепта', 'error')
            return redirect(url_for('add_recipe'))

        recipe = Recipe(user_id=current_user.id, name=name, description=description)
        db.session.add(recipe)
        db.session.flush()

        product_ids = request.form.getlist('product_id[]')
        weights = request.form.getlist('weight[]')

        if not product_ids or not any(product_ids):
            flash('Добавьте хотя бы один ингредиент', 'error')
            db.session.rollback()
            return redirect(url_for('add_recipe'))

        for product_id, weight in zip(product_ids, weights):
            if product_id and weight:
                ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    product_id=int(product_id),
                    weight=float(weight)
                )
                db.session.add(ingredient)

        db.session.flush()

        nutrition = recipe.nutrition_per_100g
        product = Product(
            user_id=current_user.id,
            name=f"{name}",
            calories=nutrition['calories'],
            protein=nutrition['protein'],
            fat=nutrition['fat'],
            carbs=nutrition['carbs'],
            is_recipe=True
        )
        db.session.add(product)
        db.session.flush()

        recipe.product_id = product.id
        db.session.commit()

        flash(f'Рецепт "{name}" создан и добавлен в продукты!', 'success')
        return redirect(url_for('recipes'))

    products = Product.query.filter_by(user_id=current_user.id, is_recipe=False).order_by(Product.name).all()
    return render_template('add_recipe.html', products=products)


@app.route('/view_recipe/<int:recipe_id>')
@login_required
def view_recipe(recipe_id):
    recipe = Recipe.query.filter_by(id=recipe_id, user_id=current_user.id).first_or_404()
    return render_template('view_recipe.html', recipe=recipe)


@app.route('/edit_recipe/<int:recipe_id>', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.filter_by(id=recipe_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')

        if not name:
            flash('Введите название рецепта', 'error')
            return redirect(url_for('edit_recipe', recipe_id=recipe_id))

        recipe.name = name
        recipe.description = description

        RecipeIngredient.query.filter_by(recipe_id=recipe.id).delete()

        product_ids = request.form.getlist('product_id[]')
        weights = request.form.getlist('weight[]')

        for product_id, weight in zip(product_ids, weights):
            if product_id and weight:
                ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    product_id=int(product_id),
                    weight=float(weight)
                )
                db.session.add(ingredient)

        if recipe.product:
            nutrition = recipe.nutrition_per_100g
            recipe.product.name = name
            recipe.product.calories = nutrition['calories']
            recipe.product.protein = nutrition['protein']
            recipe.product.fat = nutrition['fat']
            recipe.product.carbs = nutrition['carbs']

        db.session.commit()
        flash('Рецепт обновлен!', 'success')
        return redirect(url_for('recipes'))

    products = Product.query.filter_by(user_id=current_user.id, is_recipe=False).order_by(Product.name).all()
    return render_template('add_recipe.html', recipe=recipe, products=products, edit=True)


@app.route('/delete_recipe/<int:recipe_id>', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    recipe = Recipe.query.filter_by(id=recipe_id, user_id=current_user.id).first_or_404()

    if recipe.product:
        db.session.delete(recipe.product)

    db.session.delete(recipe)
    db.session.commit()

    flash('Рецепт удален', 'success')
    return redirect(url_for('recipes'))


# =====================================================
# SUMMARY & SETTINGS ROUTES
# =====================================================

@app.route('/daily_summary')
@login_required
def daily_summary():
    target_date = request.args.get('date')
    if target_date:
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    else:
        target_date = date.today()

    summary = get_daily_summary(target_date, current_user.id)

    return render_template('daily_summary.html',
                           summary=summary,
                           meal_types=MEAL_TYPES)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    goals = DailyGoal.get_goals(current_user.id)

    if request.method == 'POST':
        goals.calories = float(request.form.get('calories', 2000))
        goals.protein = float(request.form.get('protein', 50))
        goals.fat = float(request.form.get('fat', 65))
        goals.carbs = float(request.form.get('carbs', 300))

        db.session.commit()
        flash('Настройки сохранены!', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', goals=goals)


# =====================================================
# API ROUTES
# =====================================================

@app.route('/api/product/<int:product_id>')
@login_required
def api_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
    weight = request.args.get('weight', 100, type=float)
    nutrition = product.get_nutrition_for_weight(weight)

    return jsonify({
        'id': product.id,
        'name': product.name,
        'weight': weight,
        'nutrition': nutrition
    })


@app.route('/api/search_products')
@login_required
def api_search_products():
    query = request.args.get('q', '')
    products = Product.query.filter(
        Product.user_id == current_user.id,
        Product.name.ilike(f'%{query}%')
    ).limit(10).all()

    return jsonify([{
        'id': p.id,
        'name': p.name,
        'calories': p.calories,
        'protein': p.protein,
        'fat': p.fat,
        'carbs': p.carbs
    } for p in products])


# =====================================================
# INITIALIZE DATABASE
# =====================================================

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    print(f"Starting server on http://localhost:{port}")
    app.run(debug=True, port=port, host='0.0.0.0')