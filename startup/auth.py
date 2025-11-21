# auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import create_user, verify_password, get_user_by_id
from models import User

# Создаем blueprint для аутентификации
auth_bp = Blueprint('auth', __name__)

# Инициализация LoginManager будет в app.py
login_manager = LoginManager()

# В auth.py - обновите функцию load_user
@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(user_id)
    if user_data:
        return User(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            password_hash=user_data['password_hash'],
            created_at=user_data['created_at'],
            menu_position=user_data['menu_position']  # ДОБАВИТЬ ЭТУ СТРОКУ
        )
    return None
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not email or not password:
            flash('Все поля обязательны для заполнения')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Пароли не совпадают')
            return render_template('register.html')
        
        user_id = create_user(username, email, password)
        if user_id:
            user_data = get_user_by_id(user_id)
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                password_hash=user_data['password_hash']
            )
            login_user(user)
            flash('Регистрация успешна!')
            return redirect(url_for('index'))
        else:
            flash('Пользователь с таким именем или email уже существует')
    
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_data = verify_password(username, password)
        if user_data:
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                password_hash=user_data['password_hash']
            )
            login_user(user)
            flash('Вход выполнен успешно!')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль')
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы')
    return redirect(url_for('auth.login'))