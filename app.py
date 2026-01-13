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
# MIDDLEWARE - проверка первоначальной настройки
# =====================================================

@app.before_request
def check_setup():
    """Redirect to setup if user hasn't completed initial setup"""
    if current_user.is_authenticated:
        allowed_endpoints = ['setup', 'logout', 'static', 'api_sync_all']
        if request.endpoint and request.endpoint not in allowed_endpoints:
            if not current_user.is_setup_complete:
                return redirect(url_for('setup'))


# =====================================================
# AUTHENTICATION ROUTES
# =====================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if not current_user.is_setup_complete:
            return redirect(url_for('setup'))
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

            if not user.is_setup_complete:
                return redirect(url_for('setup'))

            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')
            return redirect(url_for('login'))

    return render_template('auth/login.html')

@app.route('/delete_account', methods=['GET', 'POST'])
@login_required
def delete_account():
    """Страница подтверждения и удаление аккаунта"""
    if request.method == 'POST':
        confirm_username = request.form.get('confirm_username', '').strip()

        # Требуем ввести логин для подтверждения
        if confirm_username != current_user.username:
            flash('Логин введён неверно. Аккаунт не удалён.', 'error')
            return redirect(url_for('delete_account'))

        try:
            # Сохраняем объект пользователя до logout
            user = current_user
            # Выходим из аккаунта (очищаем сессию)
            logout_user()
            # Удаляем пользователя (через каскад удалятся продукты, записи, рецепты, цели)
            db.session.delete(user)
            db.session.commit()
            flash('Аккаунт и все данные удалены без возможности восстановления.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Ошибка при удалении аккаунта. Попробуйте позже.', 'error')
            return redirect(url_for('settings'))

    # GET — просто показываем страницу подтверждения
    return render_template('auth/delete_account.html')


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

        user = User(username=username, is_setup_complete=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('setup'))

    return render_template('auth/register.html')


@app.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    """Initial setup - set weight and daily goals"""
    if current_user.is_setup_complete:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Получаем вес
        weight = float(request.form.get('weight', 70))
        activity = request.form.get('activity', 'moderate')

        # Сохраняем вес пользователя
        current_user.weight = weight

        # Получаем БЖУ
        use_calculated = request.form.get('use_calculated', 'true') == 'true'

        if use_calculated:
            recommended = DailyGoal.calculate_recommended(weight, activity)
            protein = recommended['protein']
            fat = recommended['fat']
            carbs = recommended['carbs']
        else:
            protein = float(request.form.get('protein', 50))
            fat = float(request.form.get('fat', 65))
            carbs = float(request.form.get('carbs', 300))

        calories = DailyGoal.calculate_calories(protein, fat, carbs)

        goal = DailyGoal.query.filter_by(user_id=current_user.id).first()
        if not goal:
            goal = DailyGoal(user_id=current_user.id)
            db.session.add(goal)

        goal.protein = protein
        goal.fat = fat
        goal.carbs = carbs
        goal.calories = calories

        create_default_products(current_user.id)

        current_user.is_setup_complete = True
        db.session.commit()

        flash(f'Настройка завершена! Ваша норма: {int(calories)} ккал/день', 'success')
        return redirect(url_for('index'))

    return render_template('auth/setup.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


# =====================================================
# API - СИНХРОНИЗАЦИЯ
# =====================================================

@app.route('/api/sync', methods=['GET', 'POST'])
@login_required
def api_sync_all():
    if request.method == 'GET':
        products = Product.query.filter_by(user_id=current_user.id).all()
        recipes = Recipe.query.filter_by(user_id=current_user.id).all()
        goals = DailyGoal.get_goals(current_user.id)

        start_date = date.today() - timedelta(days=30)
        entries = MealEntry.query.filter(
            MealEntry.user_id == current_user.id,
            MealEntry.date >= start_date
        ).all()

        return jsonify({
            'success': True,
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'user': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'weight': current_user.weight,
                    'is_setup_complete': current_user.is_setup_complete
                },
                'products': [p.to_dict() for p in products],
                'recipes': [r.to_dict() for r in recipes],
                'goals': goals.to_dict(),
                'entries': [e.to_dict() for e in entries],
                'meal_types': MEAL_TYPES
            }
        })

    elif request.method == 'POST':
        try:
            data = request.get_json()

            if 'user_weight' in data:
                current_user.weight = float(data['user_weight'])

            new_entries = data.get('new_entries', [])
            for entry_data in new_entries:
                entry = MealEntry(
                    user_id=current_user.id,
                    product_id=entry_data['product_id'],
                    meal_type=entry_data['meal_type'],
                    weight=entry_data['weight'],
                    date=datetime.strptime(entry_data['date'], '%Y-%m-%d').date()
                )
                db.session.add(entry)

            deleted_entries = data.get('deleted_entries', [])
            for entry_id in deleted_entries:
                entry = MealEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()
                if entry:
                    db.session.delete(entry)

            new_products = data.get('new_products', [])
            created_products = []
            for prod_data in new_products:
                product = Product(
                    user_id=current_user.id,
                    name=prod_data['name'],
                    calories=prod_data['calories'],
                    protein=prod_data['protein'],
                    fat=prod_data['fat'],
                    carbs=prod_data['carbs'],
                    is_recipe=prod_data.get('is_recipe', False)
                )
                db.session.add(product)
                db.session.flush()
                created_products.append(product.to_dict())

            deleted_products = data.get('deleted_products', [])
            for prod_id in deleted_products:
                product = Product.query.filter_by(id=prod_id, user_id=current_user.id).first()
                if product:
                    db.session.delete(product)

            if 'goals' in data:
                goals = DailyGoal.get_goals(current_user.id)
                goals.protein = data['goals']['protein']
                goals.fat = data['goals']['fat']
                goals.carbs = data['goals']['carbs']
                goals.calories = DailyGoal.calculate_calories(
                    data['goals']['protein'],
                    data['goals']['fat'],
                    data['goals']['carbs']
                )

            db.session.commit()

            return jsonify({
                'success': True,
                'created_products': created_products,
                'message': 'Синхронизация успешна'
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/add_entry', methods=['POST'])
@login_required
def api_add_entry():
    try:
        data = request.get_json()
        entry = MealEntry(
            user_id=current_user.id,
            product_id=data['product_id'],
            meal_type=data['meal_type'],
            weight=data['weight'],
            date=datetime.strptime(data['date'], '%Y-%m-%d').date()
        )
        db.session.add(entry)
        db.session.commit()

        return jsonify({
            'success': True,
            'entry': entry.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/delete_entry/<int:entry_id>', methods=['DELETE'])
@login_required
def api_delete_entry(entry_id):
    try:
        entry = MealEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()
        if entry:
            db.session.delete(entry)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Not found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/add_product', methods=['POST'])
@login_required
def api_add_product():
    try:
        data = request.get_json()

        protein = float(data['protein'])
        fat = float(data['fat'])
        carbs = float(data['carbs'])
        calories = DailyGoal.calculate_calories(protein, fat, carbs)

        product = Product(
            user_id=current_user.id,
            name=data['name'],
            calories=calories,
            protein=protein,
            fat=fat,
            carbs=carbs,
            is_recipe=data.get('is_recipe', False)
        )
        db.session.add(product)
        db.session.commit()

        return jsonify({
            'success': True,
            'product': product.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


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

    return render_template('index.html',
                           target_date=target_date,
                           meal_types=MEAL_TYPES,
                           today=date.today())


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
        protein = float(request.form.get('protein', 0))
        fat = float(request.form.get('fat', 0))
        carbs = float(request.form.get('carbs', 0))

        serving_type = request.form.get('serving_type', '100')
        custom_serving = float(request.form.get('custom_serving', 100))

        if serving_type == 'custom' and custom_serving > 0:
            multiplier = 100 / custom_serving
            protein = round(protein * multiplier, 1)
            fat = round(fat * multiplier, 1)
            carbs = round(carbs * multiplier, 1)

        calories = DailyGoal.calculate_calories(protein, fat, carbs)

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

        flash(f'Продукт "{name}" добавлен! ({int(calories)} ккал/100г)', 'success')
        return redirect(url_for('products'))

    return render_template('add_food.html')


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        protein = float(request.form.get('protein', 0))
        fat = float(request.form.get('fat', 0))
        carbs = float(request.form.get('carbs', 0))

        serving_type = request.form.get('serving_type', '100')
        custom_serving = float(request.form.get('custom_serving', 100))

        if serving_type == 'custom' and custom_serving > 0:
            multiplier = 100 / custom_serving
            protein = round(protein * multiplier, 1)
            fat = round(fat * multiplier, 1)
            carbs = round(carbs * multiplier, 1)

        product.name = request.form.get('name')
        product.protein = protein
        product.fat = fat
        product.carbs = carbs
        product.calories = DailyGoal.calculate_calories(protein, fat, carbs)

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
            name=name,
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

        flash(f'Рецепт "{name}" создан!', 'success')
        return redirect(url_for('recipes'))

    products_list = Product.query.filter_by(user_id=current_user.id, is_recipe=False).order_by(Product.name).all()
    return render_template('add_recipe.html', products=products_list)


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

        db.session.flush()

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

    products_list = Product.query.filter_by(user_id=current_user.id, is_recipe=False).order_by(Product.name).all()
    return render_template('add_recipe.html', recipe=recipe, products=products_list, edit=True)


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
# SUMMARY & SETTINGS
# =====================================================

@app.route('/daily_summary')
@login_required
def daily_summary():
    target_date = request.args.get('date')
    if target_date:
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    else:
        target_date = date.today()

    return render_template('daily_summary.html',
                           target_date=target_date,
                           meal_types=MEAL_TYPES)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    goals = DailyGoal.get_goals(current_user.id)

    if request.method == 'POST':
        weight = float(request.form.get('weight', current_user.weight))
        current_user.weight = weight

        protein = float(request.form.get('protein', 50))
        fat = float(request.form.get('fat', 65))
        carbs = float(request.form.get('carbs', 300))

        goals.protein = protein
        goals.fat = fat
        goals.carbs = carbs
        goals.calories = DailyGoal.calculate_calories(protein, fat, carbs)

        db.session.commit()
        flash(f'Настройки сохранены! Норма: {int(goals.calories)} ккал/день', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', goals=goals)


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(current_password):
            flash('Текущий пароль введен неверно', 'error')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('Новые пароли не совпадают', 'error')
            return redirect(url_for('change_password'))

        if len(new_password) < 4:
            flash('Пароль должен быть не менее 4 символов', 'error')
            return redirect(url_for('change_password'))

        current_user.set_password(new_password)
        db.session.commit()
        flash('Пароль успешно изменен!', 'success')
        return redirect(url_for('settings'))

    return render_template('auth/change_password.html')


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def create_default_products(user_id):
    """Create default products for a new user"""
    default_products = [
        ('Куриная грудка', 31, 3.6, 0),
        ('Рис белый', 2.7, 0.3, 28),
        ('Яйцо куриное', 13, 11, 1.1),
        ('Овсянка', 2.4, 1.4, 12),
        ('Банан', 1.1, 0.3, 23),
        ('Творог 5%', 17, 5, 1.8),
        ('Гречка', 4.2, 1.1, 21),
        ('Молоко 2.5%', 2.8, 2.5, 4.7),
        ('Хлеб белый', 9, 3.2, 49),
        ('Яблоко', 0.3, 0.2, 14),
        ('Говядина', 26, 15, 0),
        ('Лосось', 20, 13, 0),
        ('Картофель', 2, 0.1, 17),
        ('Макароны', 5, 1.1, 25),
        ('Сыр твердый', 25, 33, 1.3),
    ]

    for name, protein, fat, carbs in default_products:
        calories = DailyGoal.calculate_calories(protein, fat, carbs)
        product = Product(
            user_id=user_id,
            name=name,
            calories=calories,
            protein=protein,
            fat=fat,
            carbs=carbs
        )
        db.session.add(product)

    db.session.commit()


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