from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, current_user, login_required
import sqlite3
import os
from datetime import datetime, timedelta
from database import update_user_profile, update_user_password, verify_current_password, update_user_menu_position
from flask import flash

# Импортируем из auth.py
from auth import auth_bp, login_manager

app = Flask(__name__)
import os
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(24).hex()  # Замените на случайный ключ!

def check_project_access(project_id, user_id):
    """Проверяет доступ пользователя к проекту (владелец или участник)"""
    conn = get_db_connection()
    project = conn.execute('''
        SELECT p.* FROM projects p 
        LEFT JOIN project_members pm ON p.id = pm.project_id AND pm.user_id = ?
        WHERE p.id = ? AND (p.user_id = ? OR pm.user_id = ?)
    ''', (user_id, project_id, user_id, user_id)).fetchone()
    conn.close()
    return project

# Инициализация LoginManager
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Регистрируем blueprint аутентификации
app.register_blueprint(auth_bp)

# Настройки базы данных
DATABASE = 'instance/app.db'

def get_db_connection():
    os.makedirs('instance', exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ОСТАВЛЯЕМ оригинальную функцию init_db, но упрощаем её
def init_db():
    from database import init_db as db_init
    db_init()

# Инициализация БД при старте
# Инициализация БД при старте (только если не существует)
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
        # Можно продолжить работу, если БД уже существует

# ДОБАВЛЯЕМ ЭТУ ФУНКЦИЮ В app.py
def check_task_dependencies(task_id):
    """
    Проверяет, все ли зависимости задачи выполнены
    Возвращает True если задача может быть начата, False если есть незавершенные зависимости
    """
    conn = get_db_connection()
    
    try:
        task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not task:
            return True
        
        # Проверяем СТАРЫЕ зависимости (FS)
        if task['dependencies']:
            dependencies = task['dependencies'].split(',')
            for dep_id in dependencies:
                if dep_id.strip():
                    dep_task = conn.execute('SELECT status FROM tasks WHERE id = ?', (int(dep_id),)).fetchone()
                    if dep_task and dep_task['status'] != 'completed':
                        return False
        
        # Проверяем НОВЫЕ зависимости из task_dependencies
        dependencies = conn.execute('''
            SELECT td.dependency_type, t.status as predecessor_status 
            FROM task_dependencies td 
            JOIN tasks t ON td.predecessor_id = t.id 
            WHERE td.task_id = ?
        ''', (task_id,)).fetchall()
        
        for dep in dependencies:
            dependency_type = dep['dependency_type']
            predecessor_status = dep['predecessor_status']
            
            # Для FS зависимостей предшественник должен быть завершен
            if dependency_type == 'FS' and predecessor_status != 'completed':
                return False
            
            # Для SS зависимостей предшественник должен быть в работе или завершен
            if dependency_type == 'SS' and predecessor_status == 'planned':
                return False
            
            # Для FF зависимостей - не блокируем начало задачи
            # FF влияет только на завершение, а не на начало
        
        return True
        
    except Exception as e:
        print(f"Ошибка при проверке зависимостей: {e}")
        return True
    finally:
        conn.close()

# Главная страница с боковым меню
@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    projects = conn.execute('''
        SELECT p.* FROM projects p 
        LEFT JOIN project_members pm ON p.id = pm.project_id AND pm.user_id = ?
        WHERE p.user_id = ? OR pm.user_id = ?
        GROUP BY p.id
        ORDER BY p.name
    ''', (current_user.id, current_user.id, current_user.id)).fetchall()
    
    conn.close()
    return render_template('index.html', projects=projects, active_tab='projects', current_user=current_user)

# app.py - ДОБАВЛЯЕМ НОВЫЕ МАРШРУТЫ ДЛЯ УПРАВЛЕНИЯ КОМАНДОЙ ПРОЕКТА

# Страница команды проекта
# project_team
@app.route('/project/<int:project_id>/team')
@login_required
def project_team(project_id):
    project = check_project_access(project_id, current_user.id)
    
    if not project:
        return "Проект не найден", 404
    
    conn = get_db_connection()
    
    # Получаем участников проекта
    members = conn.execute('''
        SELECT pm.*, u.username, u.email 
        FROM project_members pm 
        JOIN users u ON pm.user_id = u.id 
        WHERE pm.project_id = ?
        ORDER BY 
            CASE pm.role 
                WHEN 'owner' THEN 1
                WHEN 'admin' THEN 2
                WHEN 'member' THEN 3
            END,
            u.username
    ''', (project_id,)).fetchall()
    
    # Получаем всех пользователей для добавления в команду
    all_users = conn.execute(
        'SELECT id, username, email FROM users WHERE id != ? ORDER BY username',
        (current_user.id,)
    ).fetchall()
    
    conn.close()
    
    return render_template('project_team.html', 
                         project=project, 
                         members=members,
                         all_users=all_users,
                         active_tab='team',
                         current_user=current_user)

# API: Добавить участника в проект
@app.route('/api/project/<int:project_id>/team', methods=['POST'])
@login_required
def api_add_project_member(project_id):
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        role = data.get('role', 'member')
        
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
        
        conn = get_db_connection()
        
        # Проверяем права доступа (только владелец проекта может добавлять участников)
        project = conn.execute(
            'SELECT * FROM projects WHERE id = ? AND user_id = ?', 
            (project_id, current_user.id)
        ).fetchone()
        
        if not project:
            conn.close()
            return jsonify({'error': 'Project not found or access denied'}), 404
        
        # Проверяем существует ли пользователь
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Проверяем не добавлен ли уже пользователь
        existing_member = conn.execute(
            'SELECT * FROM project_members WHERE project_id = ? AND user_id = ?', 
            (project_id, user_id)
        ).fetchone()
        
        if existing_member:
            conn.close()
            return jsonify({'error': 'User is already a member of this project'}), 400
        
        # Добавляем участника
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO project_members (project_id, user_id, role)
            VALUES (?, ?, ?)
        ''', (project_id, user_id, role))
        
        member_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'member_id': member_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Удалить участника из проекта
@app.route('/api/project/<int:project_id>/team/<int:user_id>', methods=['DELETE'])
@login_required
def api_remove_project_member(project_id, user_id):
    try:
        conn = get_db_connection()
        
        # Проверяем права доступа
        project = conn.execute(
            'SELECT * FROM projects WHERE id = ? AND user_id = ?', 
            (project_id, current_user.id)
        ).fetchone()
        
        if not project:
            conn.close()
            return jsonify({'error': 'Project not found or access denied'}), 404
        
        # Удаляем участника
        conn.execute(
            'DELETE FROM project_members WHERE project_id = ? AND user_id = ?', 
            (project_id, user_id)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Обновить роль участника
@app.route('/api/project/<int:project_id>/team/<int:user_id>/role', methods=['PUT'])
@login_required
def api_update_member_role(project_id, user_id):
    try:
        data = request.get_json()
        new_role = data.get('role')
        
        if not new_role or new_role not in ['owner', 'admin', 'member']:
            return jsonify({'error': 'Valid role is required'}), 400
        
        conn = get_db_connection()
        
        # Проверяем права доступа
        project = conn.execute(
            'SELECT * FROM projects WHERE id = ? AND user_id = ?', 
            (project_id, current_user.id)
        ).fetchone()
        
        if not project:
            conn.close()
            return jsonify({'error': 'Project not found or access denied'}), 404
        
        # Обновляем роль
        conn.execute(
            'UPDATE project_members SET role = ? WHERE project_id = ? AND user_id = ?', 
            (new_role, project_id, user_id)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Получить все персональные задачи
@app.route('/api/personal/tasks', methods=['GET'])
@login_required
def api_get_personal_tasks():
    conn = get_db_connection()
    tasks = conn.execute('''
        SELECT * FROM personal_tasks 
        WHERE user_id = ?
        ORDER BY 
            CASE status 
                WHEN 'planned' THEN 1 
                WHEN 'in_progress' THEN 2 
                WHEN 'completed' THEN 3 
            END,
            position ASC
    ''', (current_user.id,)).fetchall()
    conn.close()
    
    tasks_list = []
    for task in tasks:
        tasks_list.append({
            'id': task['id'],
            'title': task['title'],
            'description': task['description'],
            'status': task['status'],
            'position': task['position'],
            'duration': task['duration'],
            'start_date': task['start_date'],
            'end_date': task['end_date'],
            'created_at': task['created_at']
        })
    
    return jsonify(tasks_list)

# API: Создать персональную задачу
@app.route('/api/personal/task', methods=['POST'])
@login_required
def api_create_personal_task():
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description', '')
        duration = data.get('duration', 1)
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        priority = data.get('priority', 'medium')  # ← ДОБАВЬТЕ
        
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if start_date is None:
            start_date = datetime.now().date().isoformat()
        if end_date is None:
            end_date = (datetime.now().date() + timedelta(days=duration-1)).isoformat()
        
        cursor.execute('''
            INSERT INTO personal_tasks (title, description, duration, start_date, end_date, user_id, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, duration, start_date, end_date, current_user.id, priority))  # ← И ЭТУ
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Обновить статус персональной задачи
@app.route('/api/personal/task/<int:task_id>/status', methods=['POST'])
@login_required
def api_update_personal_task_status(task_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        new_position = data.get('position', 0)
        
        conn = get_db_connection()
        conn.execute('UPDATE personal_tasks SET status = ?, position = ? WHERE id = ?',
                    (new_status, new_position, task_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Обновить персональную задачу
@app.route('/api/personal/task/<int:task_id>', methods=['PUT'])
@login_required
def api_update_personal_task(task_id):
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description', '')
        
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        conn = get_db_connection()
        conn.execute('UPDATE personal_tasks SET title = ?, description = ? WHERE id = ?',
                    (title, description, task_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Обновить даты персональной задачи
@app.route('/api/personal/task/<int:task_id>/dates', methods=['POST'])
@login_required
def api_update_personal_task_dates(task_id):
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        duration = data.get('duration')
        
        conn = get_db_connection()
        
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            new_duration = (end_dt - start_dt).days + 1
            conn.execute('UPDATE personal_tasks SET start_date = ?, end_date = ?, duration = ? WHERE id = ?',
                        (start_date, end_date, new_duration, task_id))
        elif start_date and duration:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            new_end_date = (start_dt + timedelta(days=int(duration)-1)).strftime('%Y-%m-%d')
            conn.execute('UPDATE personal_tasks SET start_date = ?, end_date = ?, duration = ? WHERE id = ?',
                        (start_date, new_end_date, duration, task_id))
        elif end_date and duration:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            new_start_date = (end_dt - timedelta(days=int(duration)-1)).strftime('%Y-%m-%d')
            conn.execute('UPDATE personal_tasks SET start_date = ?, end_date = ?, duration = ? WHERE id = ?',
                        (new_start_date, end_date, duration, task_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Удалить персональную задачу
@app.route('/api/personal/task/<int:task_id>', methods=['DELETE'])
@login_required
def api_delete_personal_task(task_id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM personal_tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Задача удалена'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Мои задачи
@app.route('/my-tasks')
@login_required
def my_tasks():
    conn = get_db_connection()
    # Получаем только персональные задачи текущего пользователя
    tasks = conn.execute('''
        SELECT * FROM personal_tasks 
        WHERE user_id = ?
        ORDER BY 
            CASE status 
                WHEN 'planned' THEN 1 
                WHEN 'in_progress' THEN 2 
                WHEN 'completed' THEN 3 
            END,
            position ASC
    ''', (current_user.id,)).fetchall()
    conn.close()
    return render_template('my_tasks.html', tasks=tasks, active_tab='my_tasks', current_user=current_user)

# app.py - ОБНОВЛЯЕМ СУЩЕСТВУЮЩИЙ МАРШРУТ /team

# Команда (все проекты пользователя)
@app.route('/team')
@login_required
def team():
    conn = get_db_connection()
    
    # Получаем проекты где пользователь является владельцем или участником
    projects_with_teams = conn.execute('''
        SELECT p.*, pm.role 
        FROM projects p 
        LEFT JOIN project_members pm ON p.id = pm.project_id AND pm.user_id = ?
        WHERE p.user_id = ? OR pm.user_id = ?
        GROUP BY p.id
        ORDER BY p.name
    ''', (current_user.id, current_user.id, current_user.id)).fetchall()
    
    # Для каждого проекта получаем участников
    projects_data = []
    for project in projects_with_teams:
        members = conn.execute('''
            SELECT pm.*, u.username, u.email 
            FROM project_members pm 
            JOIN users u ON pm.user_id = u.id 
            WHERE pm.project_id = ?
            ORDER BY 
                CASE pm.role 
                    WHEN 'owner' THEN 1
                    WHEN 'admin' THEN 2
                    WHEN 'member' THEN 3
                END,
                u.username
        ''', (project['id'],)).fetchall()
        
        projects_data.append({
            'project': project,
            'members': members
        })
    
    conn.close()
    
    return render_template('team.html', 
                         projects_with_teams=projects_data,
                         active_tab='team',  # Убедитесь, что это есть
                         current_user=current_user)

# Добавьте эти endpoints в app.py после существующих API endpoints

# API: Получить исполнителей задачи
@app.route('/api/task/<int:task_id>/assignees', methods=['GET'])
@login_required
def api_get_task_assignees(task_id):
    conn = get_db_connection()
    
    # Получаем исполнителей задачи
    assignees = conn.execute('''
        SELECT u.id, u.username, u.email 
        FROM task_assignees ta 
        JOIN users u ON ta.user_id = u.id 
        WHERE ta.task_id = ?
    ''', (task_id,)).fetchall()
    
    conn.close()
    
    assignees_list = []
    for assignee in assignees:
        assignees_list.append({
            'id': assignee['id'],
            'username': assignee['username'],
            'email': assignee['email']
        })
    
    return jsonify(assignees_list)

# API: Добавить исполнителя к задаче
@app.route('/api/task/<int:task_id>/assignees', methods=['POST'])
@login_required
def api_add_task_assignee(task_id):
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
        
        conn = get_db_connection()
        
        # Проверяем существование задачи
        task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not task:
            conn.close()
            return jsonify({'error': 'Task not found'}), 404
        
        # Проверяем существование пользователя
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Проверяем, не добавлен ли уже пользователь
        existing = conn.execute(
            'SELECT * FROM task_assignees WHERE task_id = ? AND user_id = ?', 
            (task_id, user_id)
        ).fetchone()
        
        if existing:
            conn.close()
            return jsonify({'error': 'User is already assigned to this task'}), 400
        
        # Добавляем исполнителя
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO task_assignees (task_id, user_id) VALUES (?, ?)',
            (task_id, user_id)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Удалить исполнителя из задачи
@app.route('/api/task/<int:task_id>/assignees/<int:user_id>', methods=['DELETE'])
@login_required
def api_remove_task_assignee(task_id, user_id):
    try:
        conn = get_db_connection()
        
        # Удаляем исполнителя
        conn.execute(
            'DELETE FROM task_assignees WHERE task_id = ? AND user_id = ?',
            (task_id, user_id)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Получить доступных пользователей для назначения (участники проекта)
@app.route('/api/project/<int:project_id>/available_assignees', methods=['GET'])
@login_required
def api_get_available_assignees(project_id):
    conn = get_db_connection()
    
    # Получаем всех участников проекта (включая владельца)
    members = conn.execute('''
        SELECT u.id, u.username, u.email 
        FROM project_members pm 
        JOIN users u ON pm.user_id = u.id 
        WHERE pm.project_id = ?
        UNION
        SELECT u.id, u.username, u.email 
        FROM projects p 
        JOIN users u ON p.user_id = u.id 
        WHERE p.id = ? AND p.user_id = ?
    ''', (project_id, project_id, current_user.id)).fetchall()
    
    conn.close()
    
    members_list = []
    for member in members:
        members_list.append({
            'id': member['id'],
            'username': member['username'],
            'email': member['email']
        })
    
    return jsonify(members_list)

# Настройки
# В app.py - НАЙДИТЕ существующий маршрут settings и ОБНОВИТЕ его:
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # Определяем тип операции
        operation = request.form.get('operation')
        
        if operation == 'update_profile':
            # Обработка обновления профиля
            username = request.form.get('username')
            email = request.form.get('email')
            
            if username and email:
                success = update_user_profile(current_user.id, username, email)
                if success:
                    flash('Профиль успешно обновлен', 'success')
                    # Обновляем данные в текущей сессии
                    current_user.username = username
                    current_user.email = email
                else:
                    flash('Пользователь с таким именем или email уже существует', 'error')
            else:
                flash('Все поля обязательны для заполнения', 'error')
                
        elif operation == 'change_password':
            # Обработка смены пароля
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not current_password or not new_password or not confirm_password:
                flash('Все поля пароля обязательны для заполнения', 'error')
            elif new_password != confirm_password:
                flash('Новые пароли не совпадают', 'error')
            elif len(new_password) < 6:
                flash('Пароль должен содержать минимум 6 символов', 'error')
            elif not verify_current_password(current_user.id, current_password):
                flash('Текущий пароль неверен', 'error')
            else:
                update_user_password(current_user.id, new_password)
                flash('Пароль успешно изменен', 'success')
        
        # ДОБАВЛЯЕМ ОБРАБОТКУ НАСТРОЙКИ МЕНЮ
        elif operation == 'update_menu_position':
            menu_position = request.form.get('menu_position')
            if menu_position in ['side', 'top']:
                success = update_user_menu_position(current_user.id, menu_position)
                if success:
                    flash('Расположение меню успешно обновлено', 'success')
                    current_user.menu_position = menu_position
                else:
                    flash('Ошибка при обновлении расположения меню', 'error')
    
    # Получаем актуальные данные пользователя
    conn = get_db_connection()
    user_data = conn.execute(
        'SELECT * FROM users WHERE id = ?', (current_user.id,)
    ).fetchone()
    conn.close()
    
    return render_template('settings.html', 
                         active_tab='settings', 
                         current_user=current_user,
                         user_data=user_data)

# Создание проекта
@app.route('/project/create', methods=['GET', 'POST'])
@login_required
def create_project():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO projects (name, description, user_id) VALUES (?, ?, ?)', 
            (name, description, current_user.id)
        )
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return redirect(f'/project/{project_id}/kanban')
    
    return render_template('create_project.html', current_user=current_user)

# Канбан доска
@app.route('/project/<int:project_id>/kanban')
@login_required
def kanban(project_id):
    conn = get_db_connection()
    project = check_project_access(project_id, current_user.id)
    
    if not project:
        return "Проект не найден", 404
        
    conn = get_db_connection()
    tasks = conn.execute(
        'SELECT * FROM tasks WHERE project_id = ? ORDER BY position ASC', 
        (project_id,)
    ).fetchall()
    conn.close()
        
    return render_template('kanban.html', project=project, tasks=tasks, active_tab='kanban', current_user=current_user)

# Страница сетевого графика
@app.route('/project/<int:project_id>/network')
@login_required
def network_graph(project_id):
    try:
        project = check_project_access(project_id, current_user.id)
        
        if not project:
            return "Проект не найден", 404
            
        conn = get_db_connection()
        tasks = conn.execute('SELECT * FROM tasks WHERE project_id = ?', (project_id,)).fetchall()
        conn.close()
        
        tasks_list = []
        for task in tasks:
            tasks_list.append(dict(task))
            
        return render_template('network.html', project=dict(project), tasks=tasks_list, active_tab='network', current_user=current_user)
        
    except Exception as e:
        print(f"Ошибка в network_graph: {str(e)}")
        return f"Внутренняя ошибка сервера: {str(e)}", 500

# API: Получить все проекты
@app.route('/api/project/<int:project_id>/tasks', methods=['GET'])
@login_required
def api_get_tasks(project_id):
    """Получить задачи проекта (для канбан-доски)"""
    conn = get_db_connection()
    
    # Проверяем доступ к проекту
    project = check_project_access(project_id, current_user.id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    # Получаем задачи проекта
    tasks = conn.execute('''
        SELECT t.*, 
               GROUP_CONCAT(DISTINCT u.id) as assignee_ids,
               GROUP_CONCAT(DISTINCT u.username) as assignee_names
        FROM tasks t
        LEFT JOIN task_assignees ta ON t.id = ta.task_id
        LEFT JOIN users u ON ta.user_id = u.id
        WHERE t.project_id = ?
        GROUP BY t.id
        ORDER BY t.position ASC
    ''', (project_id,)).fetchall()
    
    conn.close()
    
    tasks_list = []
    for task in tasks:
        assignees = []
        if task['assignee_ids']:
            assignee_ids = task['assignee_ids'].split(',')
            assignee_names = task['assignee_names'].split(',')
            for i, user_id in enumerate(assignee_ids):
                if user_id and i < len(assignee_names):
                    assignees.append({
                        'id': int(user_id),
                        'username': assignee_names[i]
                    })
        
        tasks_list.append({
            'id': task['id'],
            'title': task['title'],
            'description': task['description'],
            'status': task['status'],
            'duration': task['duration'],
            'start_date': task['start_date'],
            'end_date': task['end_date'],
            'dependencies': task['dependencies'],
            'assignees': assignees
        })
    
    return jsonify(tasks_list)

# API: Создать задачу
# ОБНОВЛЯЕМ ENDPOINT СОЗДАНИЯ ЗАДАЧИ
# В API создания задачи
@app.route('/api/project/<int:project_id>/task', methods=['POST'])
def api_create_task(project_id):
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description', '')
        duration = data.get('duration', 1)
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        priority = data.get('priority', 'medium')  # ← ДОБАВЬТЕ ЭТУ СТРОЧКУ
        
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if start_date is None:
            start_date = datetime.now().date().isoformat()
        if end_date is None:
            end_date = (datetime.now().date() + timedelta(days=duration-1)).isoformat()
        
        cursor.execute('''
            INSERT INTO tasks (project_id, title, description, status, duration, start_date, end_date, priority)
            VALUES (?, ?, ?, 'planned', ?, ?, ?, ?)
        ''', (project_id, title, description, duration, start_date, end_date, priority))  # ← И ЭТУ
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ДОБАВЛЯЕМ ENDPOINT ДЛЯ ПРОВЕРКИ ВОЗМОЖНОСТИ НАЧАЛА ЗАДАЧИ
@app.route('/api/task/<int:task_id>/can_start', methods=['GET'])
def api_can_task_start(task_id):
    """
    Проверяет, может ли задача быть начата (все зависимости выполнены)
    """
    can_start = check_task_dependencies(task_id)
    return jsonify({'can_start': can_start})

# API: Получить задачу
@app.route('/api/task/<int:task_id>', methods=['GET'])
@login_required
def api_get_task(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
        
    return jsonify({
        'id': task['id'],
        'title': task['title'],
        'description': task['description'],
        'status': task['status'],
        'duration': task['duration'],
        'start_date': task['start_date'],
        'end_date': task['end_date'],
        'priority': task['priority']  # ← ДОБАВЬТЕ ЭТУ СТРОЧКУ
    })

# API: Обновить статус
@app.route('/api/task/<int:task_id>/status', methods=['POST'])
@login_required
def api_update_task_status(task_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        new_position = data.get('position', 0)
        
        conn = get_db_connection()
        conn.execute('UPDATE tasks SET status = ?, position = ? WHERE id = ?',
                    (new_status, new_position, task_id))
        conn.commit()
        conn.close()
        
        # ВЫЗЫВАЕМ ФУНКЦИЮ ДЛЯ ОБНОВЛЕНИЯ ЗАВИСИМЫХ ЗАДАЧ
        update_dependent_tasks_status(task_id, new_status)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Обновить задачу
@app.route('/api/task/<int:task_id>', methods=['PUT'])
def api_update_task(task_id):
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')  # ← ДОБАВЬТЕ
        
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        conn = get_db_connection()
        conn.execute('UPDATE tasks SET title = ?, description = ?, priority = ? WHERE id = ?',
                    (title, description, priority, task_id))  # ← ОБНОВИТЕ ЭТУ СТРОЧКУ
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Обновить даты
@app.route('/api/task/<int:task_id>/dates', methods=['POST'])
def api_update_task_dates(task_id):
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        duration = data.get('duration')
        
        conn = get_db_connection()
        
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            new_duration = (end_dt - start_dt).days + 1
            conn.execute('UPDATE tasks SET start_date = ?, end_date = ?, duration = ? WHERE id = ?',
                        (start_date, end_date, new_duration, task_id))
        elif start_date and duration:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            new_end_date = (start_dt + timedelta(days=int(duration)-1)).strftime('%Y-%m-%d')
            conn.execute('UPDATE tasks SET start_date = ?, end_date = ?, duration = ? WHERE id = ?',
                        (start_date, new_end_date, duration, task_id))
        elif end_date and duration:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            new_start_date = (end_dt - timedelta(days=int(duration)-1)).strftime('%Y-%m-%d')
            conn.execute('UPDATE tasks SET start_date = ?, end_date = ?, duration = ? WHERE id = ?',
                        (new_start_date, end_date, duration, task_id))
        
        conn.commit()
        conn.close()
        
        # ВЫЗЫВАЕМ КАСКАДНЫЙ ПЕРЕСЧЕТ ДАТ
        cascade_recalculate_dates(task_id)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Удалить задачу
@app.route('/api/task/<int:task_id>', methods=['DELETE'])
def api_delete_task(task_id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Задача удалена'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Установить зависимости задач
@app.route('/api/task/<int:task_id>/dependencies', methods=['POST'])
def api_set_dependencies(task_id):
    try:
        data = request.get_json()
        dependencies = data.get('dependencies', [])
        
        # Преобразуем список ID в строку через запятую
        dependencies_str = ','.join(map(str, dependencies))
        
        conn = get_db_connection()
        conn.execute('UPDATE tasks SET dependencies = ? WHERE id = ?', 
                    (dependencies_str, task_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Функция для расчета дат проекта
def calculate_project_dates(project_id):
    conn = get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks WHERE project_id = ?', (project_id,)).fetchall()
    conn.close()
    
    if not tasks:
        return None, None
    
    start_dates = []
    end_dates = []
    
    for task in tasks:
        if task['start_date']:
            start_dates.append(datetime.strptime(task['start_date'], '%Y-%m-%d'))
        if task['end_date']:
            end_dates.append(datetime.strptime(task['end_date'], '%Y-%m-%d'))
    
    project_start = min(start_dates) if start_dates else None
    project_end = max(end_dates) if end_dates else None
    
    return project_start, project_end

# API: Получить статистику проекта
@app.route('/api/project/<int:project_id>/stats')
def api_get_project_stats(project_id):
    conn = get_db_connection()
    
    # Общее количество задач
    total_tasks = conn.execute('SELECT COUNT(*) FROM tasks WHERE project_id = ?', 
                              (project_id,)).fetchone()[0]
    
    # Задачи по статусам
    status_stats = conn.execute('''
        SELECT status, COUNT(*) as count 
        FROM tasks 
        WHERE project_id = ? 
        GROUP BY status
    ''', (project_id,)).fetchall()
    
    # Даты проекта
    project_start, project_end = calculate_project_dates(project_id)
    
    conn.close()
    
    stats = {
        'total_tasks': total_tasks,
        'status_stats': {row['status']: row['count'] for row in status_stats},
        'project_start': project_start.strftime('%Y-%m-%d') if project_start else None,
        'project_end': project_end.strftime('%Y-%m-%d') if project_end else None
    }
    
    return jsonify(stats)

# Обработчик ошибок
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# API: Получить вехи проекта
@app.route('/api/project/<int:project_id>/milestones', methods=['GET'])
def api_get_milestones(project_id):
    conn = get_db_connection()
    milestones = conn.execute('SELECT * FROM milestones WHERE project_id = ?', (project_id,)).fetchall()
    conn.close()
    
    milestones_list = []
    for milestone in milestones:
        milestones_list.append({
            'id': milestone['id'],
            'title': milestone['title'],
            'description': milestone['description'],
            'date': milestone['date'],
            'color': milestone['color']
        })
    
    return jsonify(milestones_list)

# API: Создать веху
@app.route('/api/project/<int:project_id>/milestone', methods=['POST'])
def api_create_milestone(project_id):
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description', '')
        date = data.get('date')
        color = data.get('color', '#FFD700')
        
        if not title or not date:
            return jsonify({'error': 'Title and date are required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO milestones (project_id, title, description, date, color)
            VALUES (?, ?, ?, ?, ?)
        ''', (project_id, title, description, date, color))
        
        milestone_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'milestone_id': milestone_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Обновить веху
@app.route('/api/milestone/<int:milestone_id>', methods=['PUT'])
def api_update_milestone(milestone_id):
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description', '')
        date = data.get('date')
        color = data.get('color', '#FFD700')
        
        if not title or not date:
            return jsonify({'error': 'Title and date are required'}), 400
        
        conn = get_db_connection()
        conn.execute('''
            UPDATE milestones SET title = ?, description = ?, date = ?, color = ?
            WHERE id = ?
        ''', (title, description, date, color, milestone_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Удалить веху
@app.route('/api/milestone/<int:milestone_id>', methods=['DELETE'])
def api_delete_milestone(milestone_id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM milestones WHERE id = ?', (milestone_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Веха удалена'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Получить зависимости проекта
@app.route('/api/project/<int:project_id>/dependencies', methods=['GET'])
def api_get_dependencies(project_id):
    conn = get_db_connection()
    dependencies = conn.execute('''
        SELECT td.*, t1.title as task_title, t2.title as predecessor_title
        FROM task_dependencies td
        JOIN tasks t1 ON td.task_id = t1.id
        JOIN tasks t2 ON td.predecessor_id = t2.id
        WHERE t1.project_id = ? AND t2.project_id = ?
    ''', (project_id, project_id)).fetchall()
    conn.close()
    
    dependencies_list = []
    for dep in dependencies:
        dependencies_list.append({
            'id': dep['id'],
            'task_id': dep['task_id'],
            'predecessor_id': dep['predecessor_id'],
            'dependency_type': dep['dependency_type'],
            'lag': dep['lag'],
            'task_title': dep['task_title'],
            'predecessor_title': dep['predecessor_title']
        })
    
    return jsonify(dependencies_list)

# API: Добавить зависимость
# Заменить существующий endpoint или добавить новый
@app.route('/api/task/<int:task_id>/dependency', methods=['POST'])
@login_required
def api_add_dependency_with_recalculation(task_id):
    try:
        data = request.get_json()
        predecessor_id = data.get('predecessor_id')
        dependency_type = data.get('dependency_type', 'FS')
        lag = data.get('lag', 0)
        
        if not predecessor_id:
            return jsonify({'error': 'Predecessor ID is required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Создаем зависимость
        cursor.execute('''
            INSERT INTO task_dependencies (task_id, predecessor_id, dependency_type, lag)
            VALUES (?, ?, ?, ?)
        ''', (task_id, predecessor_id, dependency_type, lag))
        
        dependency_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Автоматически пересчитываем даты
        recalculate_task_dates(task_id, dependency_type, lag)
        
        return jsonify({'success': True, 'dependency_id': dependency_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Удалить зависимость
@app.route('/api/dependency/<int:dependency_id>', methods=['DELETE'])
def api_delete_dependency(dependency_id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM task_dependencies WHERE id = ?', (dependency_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# app.py - ДОБАВЛЯЕМ ПОСЛЕ СУЩЕСТВУЮЩИХ ИМПОРТОВ

# ЗАМЕНИТЕ существующую функцию update_dependent_tasks_status в app.py на эту:

def update_dependent_tasks_status(task_id, new_status):
    """
    Автоматически обновляет статусы зависимых задач при изменении статуса текущей задачи
    Обрабатывает все типы зависимостей: FS, SS, FF, SF
    """
    conn = get_db_connection()
    
    try:
        # Получаем текущую задачу
        task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not task:
            return
        
        print(f"Обновление зависимостей: задача {task_id} -> статус {new_status}")
        
        # Получаем ВСЕ зависимости где текущая задача является предшественником
        dependencies = conn.execute('''
            SELECT td.*, t.status as dependent_task_status, t.title as dependent_task_title
            FROM task_dependencies td 
            JOIN tasks t ON td.task_id = t.id 
            WHERE td.predecessor_id = ?
        ''', (task_id,)).fetchall()
        
        for dep in dependencies:
            dependent_task_id = dep['task_id']
            dependency_type = dep['dependency_type']
            dependent_task_status = dep['dependent_task_status']
            dependent_task_title = dep['dependent_task_title']
            
            print(f"Обработка зависимости: {dependency_type} -> задача {dependent_task_id} ({dependent_task_title})")
            
            # Обрабатываем разные типы зависимостей
            if dependency_type == 'FS' and new_status == 'completed':
                # F-S: Когда задача завершена, следующая задача может начаться
                if dependent_task_status == 'planned':
                    conn.execute('UPDATE tasks SET status = "in_progress" WHERE id = ?', 
                               (dependent_task_id,))
                    print(f"FS: Задача '{dependent_task_title}' ({dependent_task_id}) переведена в 'В работе'")
            
            elif dependency_type == 'SS':
                # S-S: Когда задача начинается, следующая задача тоже начинается
                if new_status == 'in_progress' and dependent_task_status == 'planned':
                    conn.execute('UPDATE tasks SET status = "in_progress" WHERE id = ?', 
                               (dependent_task_id,))
                    print(f"SS: Задача '{dependent_task_title}' ({dependent_task_id}) переведена в 'В работе'")
                
                # S-S: Если текущая задача возвращается в planned, зависимая тоже должна вернуться
                elif new_status == 'planned' and dependent_task_status == 'in_progress':
                    # Проверяем, есть ли другие активные SS зависимости
                    other_active_deps = conn.execute('''
                        SELECT COUNT(*) as count FROM task_dependencies td
                        JOIN tasks t ON td.predecessor_id = t.id
                        WHERE td.task_id = ? AND td.dependency_type = 'SS' AND t.status = 'in_progress'
                    ''', (dependent_task_id,)).fetchone()['count']
                    
                    if other_active_deps == 0:
                        conn.execute('UPDATE tasks SET status = "planned" WHERE id = ?', 
                                   (dependent_task_id,))
                        print(f"SS: Задача '{dependent_task_title}' ({dependent_task_id}) возвращена в 'Запланировано'")
            
            elif dependency_type == 'FF':
                # F-F: Когда задача завершена, следующая задача тоже завершается
                if new_status == 'completed' and dependent_task_status == 'in_progress':
                    conn.execute('UPDATE tasks SET status = "completed" WHERE id = ?', 
                               (dependent_task_id,))
                    print(f"FF: Задача '{dependent_task_title}' ({dependent_task_id}) переведена в 'Завершено'")
                
                # F-F: Если текущая задача возвращается из completed, зависимая тоже должна вернуться
                elif new_status == 'in_progress' and dependent_task_status == 'completed':
                    # Проверяем, есть ли другие завершенные FF зависимости
                    other_completed_deps = conn.execute('''
                        SELECT COUNT(*) as count FROM task_dependencies td
                        JOIN tasks t ON td.predecessor_id = t.id
                        WHERE td.task_id = ? AND td.dependency_type = 'FF' AND t.status = 'completed'
                    ''', (dependent_task_id,)).fetchone()['count']
                    
                    if other_completed_deps == 0:
                        conn.execute('UPDATE tasks SET status = "in_progress" WHERE id = ?', 
                                   (dependent_task_id,))
                        print(f"FF: Задача '{dependent_task_title}' ({dependent_task_id}) возвращена в 'В работе'")
            
            elif dependency_type == 'SF' and new_status == 'in_progress':
                # S-F: Когда задача начинается, следующая задача завершается
                if dependent_task_status == 'in_progress':
                    conn.execute('UPDATE tasks SET status = "completed" WHERE id = ?', 
                               (dependent_task_id,))
                    print(f"SF: Задача '{dependent_task_title}' ({dependent_task_id}) переведена в 'Завершено'")
        
        # Также обрабатываем СТАРЫЕ зависимости (из поля dependencies) как FS связи
        all_tasks = conn.execute('SELECT * FROM tasks WHERE project_id = ?', (task['project_id'],)).fetchall()
        
        for dependent_task in all_tasks:
            if dependent_task['dependencies']:
                dependencies_old = dependent_task['dependencies'].split(',')
                if str(task_id) in dependencies_old and new_status == 'completed':
                    # Для старых зависимостей считаем их FS связями
                    if dependent_task['status'] == 'planned':
                        conn.execute('UPDATE tasks SET status = "in_progress" WHERE id = ?', 
                                   (dependent_task['id'],))
                        print(f"Старая FS: Задача {dependent_task['id']} переведена в 'В работе'")
        
        conn.commit()
        
    except Exception as e:
        print(f"Ошибка при обновлении зависимых задач: {e}")
    finally:
        conn.close()

# ДОБАВЬТЕ этот endpoint в app.py для отладки:

@app.route('/api/debug/dependencies/<int:task_id>', methods=['GET'])
def api_debug_dependencies(task_id):
    """
    Отладочный endpoint для проверки зависимостей задачи
    """
    conn = get_db_connection()
    
    # Получаем задачу
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    
    # Получаем зависимости где задача является предшественником
    outgoing_deps = conn.execute('''
        SELECT td.*, t.title as dependent_task_title, t.status as dependent_task_status
        FROM task_dependencies td 
        JOIN tasks t ON td.task_id = t.id 
        WHERE td.predecessor_id = ?
    ''', (task_id,)).fetchall()
    
    # Получаем зависимости где задача является приемником
    incoming_deps = conn.execute('''
        SELECT td.*, t.title as predecessor_task_title, t.status as predecessor_task_status
        FROM task_dependencies td 
        JOIN tasks t ON td.predecessor_id = t.id 
        WHERE td.task_id = ?
    ''', (task_id,)).fetchall()
    
    conn.close()
    
    result = {
        'task': dict(task) if task else None,
        'outgoing_dependencies': [dict(dep) for dep in outgoing_deps],
        'incoming_dependencies': [dict(dep) for dep in incoming_deps],
        'can_start': check_task_dependencies(task_id)
    }
    
    return jsonify(result)

# временный для отладки
@app.route('/debug/routes')
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': str(rule)
        })
    return jsonify(routes)

@app.errorhandler(500)
def internal_error_handler(error):
    import traceback
    error_traceback = traceback.format_exc()
    print("Internal Server Error:")
    print(error_traceback)
    return jsonify({
        'error': 'Internal server error',
        'traceback': error_traceback
    }), 500

# График Ганта
@app.route('/project/<int:project_id>/gantt')
@login_required
def gantt_chart(project_id):
    project = check_project_access(project_id, current_user.id)
    
    if not project:
        return "Проект не найден", 404
        
    conn = get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks WHERE project_id = ?', (project_id,)).fetchall()
    milestones = conn.execute('SELECT * FROM milestones WHERE project_id = ?', (project_id,)).fetchall()
    conn.close()
        
    return render_template('gantt.html', project=dict(project), tasks=tasks, milestones=milestones, active_tab='gantt', current_user=current_user)

# API: Получить данные для графика Ганта
def calculate_task_progress(task):
    """Рассчитывает прогресс задачи на основе статуса"""
    if task['status'] == 'completed':
        return 100
    elif task['status'] == 'in_progress':
        return 50
    else:
        return 0

# API: Получить данные для графика Ганта
# api_get_gantt_data
@app.route('/api/project/<int:project_id>/gantt/data', methods=['GET'])
@login_required
def api_get_gantt_data(project_id):
    # Проверяем доступ к проекту
    project = check_project_access(project_id, current_user.id)
    
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    conn = get_db_connection()
    
    # Получаем задачи
    tasks = conn.execute('''
        SELECT id, title, start_date, end_date, duration, status, dependencies 
        FROM tasks WHERE project_id = ? ORDER BY start_date
    ''', (project_id,)).fetchall()
    
    # Получаем вехи
    milestones = conn.execute('''
        SELECT id, title, date, color 
        FROM milestones WHERE project_id = ? ORDER BY date
    ''', (project_id,)).fetchall()
    
    conn.close()
    
    # Формируем данные для Ганта
    gantt_data = {
        'tasks': [],
        'milestones': []
    }
    
    for task in tasks:
        gantt_data['tasks'].append({
            'id': task['id'],
            'name': task['title'],
            'start': task['start_date'],
            'end': task['end_date'],
            'duration': task['duration'],
            'progress': calculate_task_progress(task),
            'status': task['status'],
            'dependencies': task['dependencies'] if task['dependencies'] else ''
        })
    
    for milestone in milestones:
        gantt_data['milestones'].append({
            'id': milestone['id'],
            'name': milestone['title'],
            'date': milestone['date'],
            'color': milestone['color']
        })
    
    return jsonify(gantt_data)

# Добавить в app.py после существующих API endpoints
@app.route('/api/user/<int:user_id>', methods=['GET'])
@login_required
def api_get_user(user_id):
    """Получить информацию о пользователе по ID"""
    try:
        conn = get_db_connection()
        
        user = conn.execute(
            'SELECT id, username, email FROM users WHERE id = ?', 
            (user_id,)
        ).fetchone()
        
        conn.close()
        
        if user:
            return jsonify({
                'success': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email']
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Пользователь не найден'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API: Получить задачи, назначенные текущему пользователю
@app.route('/api/my/assigned-tasks', methods=['GET'])
@login_required
def api_get_my_assigned_tasks():
    """Получить все задачи, где текущий пользователь является исполнителем"""
    try:
        print(f"DEBUG: Запрос назначенных задач для пользователя {current_user.id}")
        
        conn = get_db_connection()
        
        # Получаем задачи, где пользователь назначен исполнителем
        tasks = conn.execute('''
            SELECT DISTINCT 
                t.id, t.title, t.description, t.status, 
                t.duration, t.start_date, t.end_date,
                p.name as project_name, p.id as project_id
            FROM tasks t
            JOIN task_assignees ta ON t.id = ta.task_id
            JOIN projects p ON t.project_id = p.id
            LEFT JOIN project_members pm ON p.id = pm.project_id AND pm.user_id = ?
            WHERE ta.user_id = ? 
            AND (p.user_id = ? OR pm.user_id IS NOT NULL)
            ORDER BY 
                CASE t.status 
                    WHEN 'planned' THEN 1 
                    WHEN 'in_progress' THEN 2 
                    WHEN 'completed' THEN 3 
                END,
                t.start_date ASC
        ''', (current_user.id, current_user.id, current_user.id)).fetchall()
        
        print(f"DEBUG: Найдено задач для пользователя {current_user.id}: {len(tasks)}")
        
        # Выведем информацию о найденных задачах для отладки
        for task in tasks:
            print(f"DEBUG: Задача {task['id']} - {task['title']} (проект: {task['project_name']})")
        
        conn.close()
        
        tasks_list = []
        for task in tasks:
            tasks_list.append({
                'id': task['id'],
                'title': task['title'],
                'description': task['description'],
                'status': task['status'],
                'duration': task['duration'],
                'start_date': task['start_date'],
                'end_date': task['end_date'],
                'project_id': task['project_id'],
                'project_name': task['project_name'],
                'type': 'project_task'
            })
        
        return jsonify(tasks_list)
        
    except Exception as e:
        print(f"ERROR: Ошибка при получении назначенных задач: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
# Отладочный endpoint для проверки базы данных
@app.route('/api/debug/database')
@login_required
def api_debug_database():
    """Отладочный endpoint для проверки состояния базы данных"""
    conn = get_db_connection()
    
    # Проверяем таблицы
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables_info = []
    
    for table in tables:
        table_name = table['name']
        count = conn.execute(f'SELECT COUNT(*) as count FROM {table_name}').fetchone()['count']
        tables_info.append({
            'table': table_name,
            'count': count
        })
    
    # Проверяем task_assignees
    task_assignees = conn.execute('''
        SELECT ta.*, u.username, t.title as task_title, p.name as project_name
        FROM task_assignees ta
        JOIN users u ON ta.user_id = u.id
        JOIN tasks t ON ta.task_id = t.id
        JOIN projects p ON t.project_id = p.id
    ''').fetchall()
    
    # Проверяем текущего пользователя
    current_user_info = conn.execute(
        'SELECT id, username, email FROM users WHERE id = ?', 
        (current_user.id,)
    ).fetchone()
    
    conn.close()
    
    return jsonify({
        'tables': tables_info,
        'current_user': dict(current_user_info) if current_user_info else None,
        'task_assignees': [dict(row) for row in task_assignees]
    })

@app.route('/api/debug/task-assignees')
@login_required
def api_debug_task_assignees():
    """Отладочный endpoint для проверки назначений задач"""
    conn = get_db_connection()
    
    # Проверяем все назначения
    all_assignments = conn.execute('''
        SELECT ta.*, u.username, t.title as task_title, p.name as project_name
        FROM task_assignees ta
        JOIN users u ON ta.user_id = u.id
        JOIN tasks t ON ta.task_id = t.id
        JOIN projects p ON t.project_id = p.id
    ''').fetchall()
    
    # Проверяем назначения текущего пользователя
    my_assignments = conn.execute('''
        SELECT ta.*, u.username, t.title as task_title, p.name as project_name
        FROM task_assignees ta
        JOIN users u ON ta.user_id = u.id
        JOIN tasks t ON ta.task_id = t.id
        JOIN projects p ON t.project_id = p.id
        WHERE ta.user_id = ?
    ''', (current_user.id,)).fetchall()
    
    conn.close()
    
    return jsonify({
        'all_assignments': [dict(row) for row in all_assignments],
        'my_assignments': [dict(row) for row in my_assignments],
        'current_user_id': current_user.id
    })

# Добавить в app.py после существующих функций
def recalculate_task_dates(task_id, dependency_type='FS', lag=0, visited=None):
    """
    Автоматически пересчитывает даты задачи на основе зависимостей
    visited - множество для отслеживания посещенных задач (предотвращение циклов)
    """
    if visited is None:
        visited = set()
    
    if task_id in visited:
        return  # Предотвращаем бесконечную рекурсию при циклических зависимостях
    
    visited.add(task_id)
    
    conn = get_db_connection()
    
    try:
        task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not task:
            return
        
        # Получаем все зависимости задачи
        dependencies = conn.execute('''
            SELECT td.*, t.end_date as predecessor_end, t.start_date as predecessor_start
            FROM task_dependencies td
            JOIN tasks t ON td.predecessor_id = t.id
            WHERE td.task_id = ?
        ''', (task_id,)).fetchall()
        
        if not dependencies:
            return
        
        earliest_start_date = None
        
        # Для FS зависимостей находим самую позднюю дату окончания предшественников
        for dep in dependencies:
            if dep['dependency_type'] == 'FS':  # Finish-to-Start
                if dep['predecessor_end']:
                    lag_days = dep['lag'] or 0
                    dep_start_date = datetime.strptime(dep['predecessor_end'], '%Y-%m-%d') + timedelta(days=1 + lag_days)
                    
                    if earliest_start_date is None or dep_start_date > earliest_start_date:
                        earliest_start_date = dep_start_date
        
        if earliest_start_date:
            new_end_date = earliest_start_date + timedelta(days=task['duration'] - 1)
            
            conn.execute('''
                UPDATE tasks SET start_date = ?, end_date = ? 
                WHERE id = ?
            ''', (earliest_start_date.strftime('%Y-%m-%d'), 
                  new_end_date.strftime('%Y-%m-%d'), 
                  task_id))
            
            conn.commit()
        
    except Exception as e:
        print(f"Ошибка при пересчете дат задачи {task_id}: {e}")
    finally:
        conn.close()


def cascade_recalculate_dates(changed_task_id):
    """
    Пересчитывает даты всех задач, которые зависят от измененной задачи
    """
    conn = get_db_connection()
    
    try:
        # Находим все задачи, которые зависят от измененной задачи
        dependent_tasks = conn.execute('''
            SELECT td.task_id, td.dependency_type, td.lag
            FROM task_dependencies td
            WHERE td.predecessor_id = ?
        ''', (changed_task_id,)).fetchall()
        
        # Пересчитываем даты для каждой зависимой задачи
        for dep_task in dependent_tasks:
            recalculate_task_dates(dep_task['task_id'], dep_task['dependency_type'], dep_task['lag'])
            
            # Рекурсивно пересчитываем задачи, зависящие от этой задачи (каскад)
            cascade_recalculate_dates(dep_task['task_id'])
            
    except Exception as e:
        print(f"Ошибка при каскадном пересчете дат: {e}")
    finally:
        conn.close()

# Календарь в главном меню
@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html', active_tab='calendar', current_user=current_user)

# API: Получить все события календаря (включая задачи, вехи и кастомные события)
@app.route('/api/calendar/events', methods=['GET'])
@login_required
def api_get_calendar_events():
    """Получить только те события, которые относятся к текущему пользователю"""
    try:
        conn = get_db_connection()
        
        print(f"DEBUG: Загрузка событий для пользователя {current_user.id}")
        
        # Задачи из проектов (только назначенные текущему пользователю)
        project_tasks = conn.execute('''
            SELECT 
                t.id, t.title, t.description, t.status,
                t.start_date, t.end_date, t.duration,
                p.name as project_name, p.id as project_id,
                'project_task' as event_type
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            JOIN task_assignees ta ON t.id = ta.task_id
            LEFT JOIN project_members pm ON p.id = pm.project_id AND pm.user_id = ?
            WHERE ta.user_id = ?  -- ТОЛЬКО задачи, назначенные текущему пользователю
            AND (p.user_id = ? OR pm.user_id IS NOT NULL)
            AND t.start_date IS NOT NULL AND t.end_date IS NOT NULL
        ''', (current_user.id, current_user.id, current_user.id)).fetchall()
        
        print(f"DEBUG: Найдено проектных задач для пользователя: {len(project_tasks)}")
        
        # Персональные задачи (только текущего пользователя)
        personal_tasks = conn.execute('''
            SELECT 
                id, title, description, status,
                start_date, end_date, duration,
                'Персональные задачи' as project_name,
                NULL as project_id,
                'personal_task' as event_type
            FROM personal_tasks 
            WHERE user_id = ?
            AND start_date IS NOT NULL AND end_date IS NOT NULL
        ''', (current_user.id,)).fetchall()
        
        print(f"DEBUG: Найдено персональных задач: {len(personal_tasks)}")
        
        # Вехи проектов (где пользователь участник)
        milestones = conn.execute('''
            SELECT 
                m.id, m.title, m.description, m.date,
                m.color, p.name as project_name, p.id as project_id,
                'milestone' as event_type
            FROM milestones m
            JOIN projects p ON m.project_id = p.id
            LEFT JOIN project_members pm ON p.id = pm.project_id AND pm.user_id = ?
            WHERE (p.user_id = ? OR pm.user_id IS NOT NULL)
            AND m.date IS NOT NULL
        ''', (current_user.id, current_user.id)).fetchall()
        
        print(f"DEBUG: Найдено вех: {len(milestones)}")
        
        # Кастомные события календаря (только текущего пользователя)
        custom_events = conn.execute('''
            SELECT 
                id, title, description, start_date, start_time,
                end_date, end_time, duration_minutes, all_day,
                event_type, color, created_at
            FROM calendar_events 
            WHERE user_id = ?
        ''', (current_user.id,)).fetchall()
        
        print(f"DEBUG: Найдено кастомных событий: {len(custom_events)}")
        
        conn.close()
        
        # Объединяем события
        all_events = []
        
        # Добавляем задачи проектов (только назначенные)
        for task in project_tasks:
            event_data = {
                'id': f"task_{task['id']}",
                'title': task['title'],
                'description': task['description'],
                'start': task['start_date'],
                'end': task['end_date'],
                'extendedProps': {
                    'event_type': 'task',
                    'type': task['event_type'],
                    'status': task['status'],
                    'project_name': task['project_name'],
                    'project_id': task['project_id'],
                    'duration': task['duration'],
                    'assigned_to_me': True  # Флаг что задача назначена текущему пользователю
                },
                'color': get_task_color(task['status'], task['event_type'])
            }
            all_events.append(event_data)
            print(f"DEBUG: Добавлена проектная задача (назначенная): {task['title']}")
        
        # Добавляем персональные задачи
        for task in personal_tasks:
            event_data = {
                'id': f"personal_{task['id']}",
                'title': task['title'],
                'description': task['description'],
                'start': task['start_date'],
                'end': task['end_date'],
                'extendedProps': {
                    'event_type': 'task',
                    'type': task['event_type'],
                    'status': task['status'],
                    'project_name': task['project_name'],
                    'project_id': task['project_id'],
                    'duration': task['duration']
                },
                'color': get_task_color(task['status'], task['event_type'])
            }
            all_events.append(event_data)
            print(f"DEBUG: Добавлена персональная задача: {task['title']}")
        
        # Добавляем вехи
        for milestone in milestones:
            event_data = {
                'id': f"milestone_{milestone['id']}",
                'title': milestone['title'],
                'description': milestone['description'],
                'start': milestone['date'],
                'end': milestone['date'],
                'extendedProps': {
                    'event_type': 'milestone',
                    'project_name': milestone['project_name'],
                    'project_id': milestone['project_id']
                },
                'color': milestone['color'] or '#FFD700',
                'allDay': True
            }
            all_events.append(event_data)
            print(f"DEBUG: Добавлена веха: {milestone['title']}")
        
        # Добавляем кастомные события
        for event in custom_events:
            start_datetime = event['start_date']
            if event['start_time'] and not event['all_day']:
                start_datetime = f"{event['start_date']}T{event['start_time']}"
            
            end_datetime = None
            if event['end_date']:
                end_datetime = event['end_date']
                if event['end_time'] and not event['all_day']:
                    end_datetime = f"{event['end_date']}T{event['end_time']}"
            elif event['duration_minutes'] and event['start_time'] and not event['all_day']:
                start_dt = datetime.strptime(f"{event['start_date']} {event['start_time']}", '%Y-%m-%d %H:%M')
                end_dt = start_dt + timedelta(minutes=event['duration_minutes'])
                end_datetime = end_dt.strftime('%Y-%m-%dT%H:%M')
            
            event_data = {
                'id': f"custom_{event['id']}",
                'title': event['title'],
                'description': event['description'],
                'start': start_datetime,
                'end': end_datetime,
                'allDay': bool(event['all_day']),
                'color': event['color'],
                'extendedProps': {
                    'event_type': 'custom',
                    'custom_type': event['event_type'],
                    'source': 'custom'
                }
            }
            all_events.append(event_data)
            print(f"DEBUG: Добавлено кастомное событие: {event['title']}")
        
        print(f"DEBUG: Всего событий для календаря пользователя {current_user.id}: {len(all_events)}")
        return jsonify(all_events)
        
    except Exception as e:
        print(f"ERROR: Ошибка при загрузке событий календаря: {str(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# API: Создать новое событие календаря
@app.route('/api/calendar/event', methods=['POST'])
@login_required
def api_create_calendar_event():
    """Создать новое событие календаря"""
    try:
        data = request.get_json()
        
        title = data.get('title')
        description = data.get('description', '')
        start_date = data.get('start_date')
        start_time = data.get('start_time')
        end_date = data.get('end_date')
        end_time = data.get('end_time')
        duration_minutes = data.get('duration_minutes')
        all_day = data.get('all_day', False)
        event_type = data.get('event_type', 'custom')
        color = data.get('color', '#3498db')
        
        if not title or not start_date:
            return jsonify({'error': 'Title and start date are required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO calendar_events 
            (user_id, title, description, start_date, start_time, end_date, end_time, 
             duration_minutes, all_day, event_type, color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (current_user.id, title, description, start_date, start_time, end_date, 
              end_time, duration_minutes, all_day, event_type, color))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'event_id': event_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Обновить событие календаря
@app.route('/api/calendar/event/<int:event_id>', methods=['PUT'])
@login_required
def api_update_calendar_event(event_id):
    """Обновить событие календаря"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        
        # Проверяем принадлежность события пользователю
        event = conn.execute(
            'SELECT * FROM calendar_events WHERE id = ? AND user_id = ?',
            (event_id, current_user.id)
        ).fetchone()
        
        if not event:
            conn.close()
            return jsonify({'error': 'Event not found'}), 404
        
        # Обновляем поля
        update_fields = []
        update_values = []
        
        field_mapping = {
            'title': data.get('title'),
            'description': data.get('description'),
            'start_date': data.get('start_date'),
            'start_time': data.get('start_time'),
            'end_date': data.get('end_date'),
            'end_time': data.get('end_time'),
            'duration_minutes': data.get('duration_minutes'),
            'all_day': data.get('all_day'),
            'event_type': data.get('event_type'),
            'color': data.get('color')
        }
        
        for field, value in field_mapping.items():
            if value is not None:
                update_fields.append(f"{field} = ?")
                update_values.append(value)
        
        if update_fields:
            update_values.extend([event_id, current_user.id])
            conn.execute(f'''
                UPDATE calendar_events 
                SET {', '.join(update_fields)}
                WHERE id = ? AND user_id = ?
            ''', update_values)
            
            conn.commit()
        
        conn.close()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Удалить событие календаря
@app.route('/api/calendar/event/<int:event_id>', methods=['DELETE'])
@login_required
def api_delete_calendar_event(event_id):
    """Удалить событие календаря"""
    try:
        conn = get_db_connection()
        
        # Проверяем принадлежность события пользователю
        event = conn.execute(
            'SELECT * FROM calendar_events WHERE id = ? AND user_id = ?',
            (event_id, current_user.id)
        ).fetchone()
        
        if not event:
            conn.close()
            return jsonify({'error': 'Event not found'}), 404
        
        conn.execute(
            'DELETE FROM calendar_events WHERE id = ? AND user_id = ?',
            (event_id, current_user.id)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Получить конкретное событие календаря
@app.route('/api/calendar/event/<int:event_id>', methods=['GET'])
@login_required
def api_get_calendar_event(event_id):
    """Получить конкретное событие календаря"""
    try:
        conn = get_db_connection()
        
        event = conn.execute(
            'SELECT * FROM calendar_events WHERE id = ? AND user_id = ?',
            (event_id, current_user.id)
        ).fetchone()
        
        conn.close()
        
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        event_data = {
            'id': event['id'],
            'title': event['title'],
            'description': event['description'],
            'start_date': event['start_date'],
            'start_time': event['start_time'],
            'end_date': event['end_date'],
            'end_time': event['end_time'],
            'duration_minutes': event['duration_minutes'],
            'all_day': bool(event['all_day']),
            'event_type': event['event_type'],
            'color': event['color'],
            'created_at': event['created_at']
        }
        
        return jsonify(event_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Вспомогательная функция для определения цвета
def get_task_color(status, task_type):
    """Определяет цвет задачи для календаря"""
    if task_type == 'personal_task':
        return '#6c757d'  # Серый для персональных задач
    
    color_map = {
        'planned': '#3498db',    # Синий
        'in_progress': '#f39c12', # Оранжевый
        'completed': '#27ae60'    # Зеленый
    }
    return color_map.get(status, '#95a5a6')

# API: Удалить кастомное событие календаря
@app.route('/api/calendar/event/<string:event_id>', methods=['DELETE'])
@login_required
def api_delete_calendar_event_full(event_id):
    """Удалить событие календаря (полная реализация)"""
    try:
        print(f"DEBUG: Deleting calendar event: {event_id}")
        
        # Разбираем ID события (формат: "type_id")
        if event_id.startswith('custom_'):
            # Удаляем кастомное событие
            custom_event_id = event_id.replace('custom_', '')
            conn = get_db_connection()
            
            # Проверяем принадлежность события пользователю
            event = conn.execute(
                'SELECT * FROM calendar_events WHERE id = ? AND user_id = ?',
                (custom_event_id, current_user.id)
            ).fetchone()
            
            if not event:
                conn.close()
                return jsonify({'error': 'Event not found'}), 404
            
            conn.execute(
                'DELETE FROM calendar_events WHERE id = ? AND user_id = ?',
                (custom_event_id, current_user.id)
            )
            conn.commit()
            conn.close()
            
            return jsonify({'success': True})
            
        elif event_id.startswith('personal_'):
            # Удаляем персональную задачу
            task_id = event_id.replace('personal_', '')
            conn = get_db_connection()
            conn.execute('DELETE FROM personal_tasks WHERE id = ? AND user_id = ?', 
                        (task_id, current_user.id))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
            
        elif event_id.startswith('task_'):
            # Для проектных задач показываем сообщение
            return jsonify({'error': 'Проектные задачи удаляются в канбан-доске проекта'}), 400
            
        elif event_id.startswith('milestone_'):
            # Для вех показываем сообщение  
            return jsonify({'error': 'Вехи удаляются в диаграмме Ганта проекта'}), 400
            
        else:
            return jsonify({'error': 'Unknown event type'}), 400
            
    except Exception as e:
        print(f"ERROR: Error deleting calendar event: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
    # Получаем актуальные данные пользователя
    conn = get_db_connection()
    user_data = conn.execute(
        'SELECT * FROM users WHERE id = ?', (current_user.id,)
    ).fetchone()
    conn.close()
    
    return render_template('settings.html', 
                         active_tab='settings', 
                         current_user=current_user,
                         user_data=user_data)

# Добавить в app.py после существующих API endpoints

# API: Получить задачи команды с статистикой
# В app.py - ОБНОВИТЬ api_get_team_tasks
@app.route('/api/project/<int:project_id>/team/tasks', methods=['GET'])
@login_required
def api_get_team_tasks(project_id):
    """Получить все задачи команды с группировкой по исполнителям"""
    try:
        conn = get_db_connection()
        
        # Проверяем доступ к проекту
        project = check_project_access(project_id, current_user.id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Получаем всех участников проекта
        members = conn.execute('''
            SELECT pm.user_id, u.username, u.email, pm.role 
            FROM project_members pm 
            JOIN users u ON pm.user_id = u.id 
            WHERE pm.project_id = ?
            UNION
            SELECT p.user_id as user_id, u.username, u.email, 'owner' as role
            FROM projects p 
            JOIN users u ON p.user_id = u.id 
            WHERE p.id = ?
        ''', (project_id, project_id)).fetchall()
        
        # Получаем ВСЕ задачи проекта с исполнителями
        tasks = conn.execute('''
            SELECT 
                t.id, t.title, t.description, t.status,
                t.duration, t.start_date, t.end_date,
                t.project_id,
                GROUP_CONCAT(ta.user_id) as assignee_ids,
                GROUP_CONCAT(u.username) as assignee_names
            FROM tasks t
            LEFT JOIN task_assignees ta ON t.id = ta.task_id
            LEFT JOIN users u ON ta.user_id = u.id
            WHERE t.project_id = ?
            GROUP BY t.id
            ORDER BY t.status, t.start_date
        ''', (project_id,)).fetchall()
        
        # Форматируем задачи
        formatted_tasks = []
        for task in tasks:
            assignees = []
            if task['assignee_ids']:
                assignee_ids = task['assignee_ids'].split(',')
                assignee_names = task['assignee_names'].split(',')
                for i, user_id in enumerate(assignee_ids):
                    if user_id and i < len(assignee_names):
                        assignees.append({
                            'id': int(user_id),
                            'username': assignee_names[i]
                        })
            
            formatted_tasks.append({
                'id': task['id'],
                'title': task['title'],
                'description': task['description'],
                'status': task['status'],
                'duration': task['duration'],
                'start_date': task['start_date'],
                'end_date': task['end_date'],
                'project_id': task['project_id'],
                'assignees': assignees
            })
        
        # Статистика
        stats = {
            'total': len(tasks),
            'planned': len([t for t in tasks if t['status'] == 'planned']),
            'in_progress': len([t for t in tasks if t['status'] == 'in_progress']),
            'completed': len([t for t in tasks if t['status'] == 'completed'])
        }
        
        conn.close()
        
        return jsonify({
            'success': True,
            'tasks': formatted_tasks,
            'stats': stats,
            'members': [dict(member) for member in members]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Создать и назначить задачу
@app.route('/api/project/<int:project_id>/team/task', methods=['POST'])
@login_required
def api_create_team_task(project_id):
    """Создать задачу и назначить исполнителя"""
    try:
        data = request.get_json()
        
        title = data.get('title')
        description = data.get('description', '')
        assignee_id = data.get('assignee_id')
        duration = data.get('duration', 3)
        start_date = data.get('start_date')
        priority = data.get('priority', 'medium')
        
        if not title or not assignee_id:
            return jsonify({'error': 'Title and assignee are required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем доступ к проекту
        project = check_project_access(project_id, current_user.id)
        if not project:
            conn.close()
            return jsonify({'error': 'Project not found'}), 404
        
        # Проверяем что исполнитель является участником проекта
        is_member = conn.execute('''
            SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?
            UNION
            SELECT 1 FROM projects WHERE id = ? AND user_id = ?
        ''', (project_id, assignee_id, project_id, assignee_id)).fetchone()
        
        if not is_member:
            conn.close()
            return jsonify({'error': 'Assignee is not a project member'}), 400
        
        # Устанавливаем даты по умолчанию
        if not start_date:
            start_date = datetime.now().date().isoformat()
        
        end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=duration-1)).strftime('%Y-%m-%d')
        
        # Создаем задачу
        cursor.execute('''
            INSERT INTO tasks (project_id, title, description, status, duration, start_date, end_date)
            VALUES (?, ?, ?, 'planned', ?, ?, ?)
        ''', (project_id, title, description, duration, start_date, end_date))
        
        task_id = cursor.lastrowid
        
        # Назначаем исполнителя
        cursor.execute('''
            INSERT INTO task_assignees (task_id, user_id)
            VALUES (?, ?)
        ''', (task_id, assignee_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Получить задачи конкретного участника
@app.route('/api/project/<int:project_id>/member/<int:user_id>/tasks', methods=['GET'])
@login_required
def api_get_member_tasks(project_id, user_id):
    """Получить задачи конкретного участника проекта"""
    try:
        conn = get_db_connection()
        
        tasks = conn.execute('''
            SELECT t.*, p.name as project_name
            FROM tasks t
            JOIN task_assignees ta ON t.id = ta.task_id
            JOIN projects p ON t.project_id = p.id
            WHERE t.project_id = ? AND ta.user_id = ?
            ORDER BY 
                CASE t.status 
                    WHEN 'planned' THEN 1 
                    WHEN 'in_progress' THEN 2 
                    WHEN 'completed' THEN 3 
                END,
                t.start_date ASC
        ''', (project_id, user_id)).fetchall()
        
        conn.close()
        
        tasks_list = []
        for task in tasks:
            tasks_list.append({
                'id': task['id'],
                'title': task['title'],
                'description': task['description'],
                'status': task['status'],
                'duration': task['duration'],
                'start_date': task['start_date'],
                'end_date': task['end_date'],
                'project_name': task['project_name']
            })
        
        return jsonify(tasks_list)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Страница "Задачи команды" проекта
@app.route('/project/<int:project_id>/team-tasks')
@login_required
def team_tasks(project_id):
    project = check_project_access(project_id, current_user.id)
    
    if not project:
        return "Проект не найден", 404
    
    conn = get_db_connection()
    
    # Получаем участников проекта
    members = conn.execute('''
        SELECT pm.user_id, u.username, u.email, pm.role 
        FROM project_members pm 
        JOIN users u ON pm.user_id = u.id 
        WHERE pm.project_id = ?
        UNION
        SELECT p.user_id as user_id, u.username, u.email, 'owner' as role
        FROM projects p 
        JOIN users u ON p.user_id = u.id 
        WHERE p.id = ?
        ORDER BY role, username
    ''', (project_id, project_id)).fetchall()
    
    conn.close()
    
    return render_template('team_tasks.html', 
                         project=project, 
                         members=members,
                         active_tab='team_tasks',
                         current_user=current_user)

# В app.py - ДОБАВИТЬ новый endpoint для административного просмотра
@app.route('/api/project/<int:project_id>/all-tasks', methods=['GET'])
@login_required
def api_get_all_project_tasks(project_id):
    """Получить ВСЕ задачи проекта (для страницы 'Задачи команды')"""
    try:
        conn = get_db_connection()
        
        # Проверяем права доступа - только участники проекта могут видеть все задачи
        project = check_project_access(project_id, current_user.id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Получаем ВСЕ задачи проекта с исполнителями
        tasks = conn.execute('''
            SELECT 
                t.id, t.title, t.description, t.status,
                t.duration, t.start_date, t.end_date,
                GROUP_CONCAT(ta.user_id) as assignee_ids,
                GROUP_CONCAT(u.username) as assignee_names
            FROM tasks t
            LEFT JOIN task_assignees ta ON t.id = ta.task_id
            LEFT JOIN users u ON ta.user_id = u.id
            WHERE t.project_id = ?
            GROUP BY t.id
            ORDER BY t.status, t.start_date
        ''', (project_id,)).fetchall()
        
        conn.close()
        
        formatted_tasks = []
        for task in tasks:
            assignees = []
            if task['assignee_ids']:
                assignee_ids = task['assignee_ids'].split(',')
                assignee_names = task['assignee_names'].split(',')
                for i, user_id in enumerate(assignee_ids):
                    if user_id and i < len(assignee_names):
                        assignees.append({
                            'id': int(user_id),
                            'username': assignee_names[i]
                        })
            
            formatted_tasks.append({
                'id': task['id'],
                'title': task['title'],
                'description': task['description'],
                'status': task['status'],
                'duration': task['duration'],
                'start_date': task['start_date'],
                'end_date': task['end_date'],
                'assignees': assignees
            })
        
        return jsonify({
            'success': True,
            'tasks': formatted_tasks
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Аналитика проекта
@app.route('/project/<int:project_id>/analytics')
@login_required
def project_analytics(project_id):
    project = check_project_access(project_id, current_user.id)
    
    if not project:
        return "Проект не найден", 404
        
    return render_template('analytics.html', project=project, active_tab='analytics', current_user=current_user)

# API: Получить данные для аналитики
@app.route('/api/project/<int:project_id>/analytics/workload')
@login_required
def api_get_workload_analytics(project_id):
    """Получить данные о загрузке участников"""
    try:
        conn = get_db_connection()
        
        # Проверяем доступ к проекту
        project = check_project_access(project_id, current_user.id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Получаем участников проекта
        members = conn.execute('''
            SELECT pm.user_id, u.username, u.email, pm.role 
            FROM project_members pm 
            JOIN users u ON pm.user_id = u.id 
            WHERE pm.project_id = ?
            UNION
            SELECT p.user_id as user_id, u.username, u.email, 'owner' as role
            FROM projects p 
            JOIN users u ON p.user_id = u.id 
            WHERE p.id = ?
        ''', (project_id, project_id)).fetchall()
        
        # Получаем все задачи проекта с приоритетами и исполнителями
        tasks = conn.execute('''
            SELECT 
                t.id, t.title, t.status, t.duration, t.priority,
                GROUP_CONCAT(ta.user_id) as assignee_ids
            FROM tasks t
            LEFT JOIN task_assignees ta ON t.id = ta.task_id
            WHERE t.project_id = ?
            GROUP BY t.id
        ''', (project_id,)).fetchall()
        
        # Рассчитываем загрузку для каждого участника
        workload_data = []
        total_work_days = 30  # Общее количество рабочих дней в проекте (можно динамически рассчитывать)
        
        for member in members:
            user_id = member['user_id']
            user_tasks = [task for task in tasks if task['assignee_ids'] and str(user_id) in task['assignee_ids'].split(',')]
            
            total_duration = sum(task['duration'] for task in user_tasks)
            workload_percentage = min((total_duration / total_work_days) * 100, 200)  # Ограничиваем 200%
            
            # Рассчитываем сложность задач
            complexity_score = sum(
                task['duration'] * get_priority_multiplier(task['priority']) 
                for task in user_tasks
            )
            
            workload_data.append({
                'user_id': user_id,
                'username': member['username'],
                'email': member['email'],
                'role': member['role'],
                'task_count': len(user_tasks),
                'total_duration': total_duration,
                'workload_percentage': round(workload_percentage, 2),
                'complexity_score': round(complexity_score, 2),
                'tasks': [{
                    'id': task['id'],
                    'title': task['title'],
                    'duration': task['duration'],
                    'priority': task['priority'],
                    'status': task['status'],
                    'priority_multiplier': get_priority_multiplier(task['priority'])
                } for task in user_tasks]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'workload_data': workload_data,
            'total_work_days': total_work_days
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Получить данные о сложности задач
@app.route('/api/project/<int:project_id>/analytics/complexity')
@login_required
def api_get_complexity_analytics(project_id):
    """Получить данные о сложности задач"""
    try:
        conn = get_db_connection()
        
        # Проверяем доступ к проекту
        project = check_project_access(project_id, current_user.id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Получаем задачи с приоритетами
        tasks = conn.execute('''
            SELECT id, title, duration, priority, status
            FROM tasks 
            WHERE project_id = ?
        ''', (project_id,)).fetchall()
        
        # Рассчитываем сложность
        complexity_data = []
        total_complexity = 0
        
        for task in tasks:
            complexity = task['duration'] * get_priority_multiplier(task['priority'])
            total_complexity += complexity
            
            complexity_data.append({
                'id': task['id'],
                'title': task['title'],
                'duration': task['duration'],
                'priority': task['priority'],
                'status': task['status'],
                'complexity': round(complexity, 2),
                'percentage': 0  # Будет рассчитано ниже
            })
        
        # Рассчитываем проценты
        for task in complexity_data:
            if total_complexity > 0:
                task['percentage'] = round((task['complexity'] / total_complexity) * 100, 2)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'complexity_data': complexity_data,
            'total_complexity': round(total_complexity, 2)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_priority_multiplier(priority):
    """Возвращает множитель сложности для приоритета"""
    multipliers = {
        'low': 1.0,
        'medium': 1.5,
        'high': 2.0,
        'critical': 3.0
    }
    return multipliers.get(priority, 1.0)

# Добавьте в app.py для отладки
@app.route('/api/debug/project/<int:project_id>/tasks')
@login_required
def api_debug_project_tasks(project_id):
    """Отладочный endpoint для проверки задач проекта"""
    try:
        conn = get_db_connection()
        
        # Проверяем задачи
        tasks = conn.execute('''
            SELECT id, title, duration, priority, status 
            FROM tasks 
            WHERE project_id = ?
        ''', (project_id,)).fetchall()
        
        # Проверяем участников
        members = conn.execute('''
            SELECT pm.user_id, u.username
            FROM project_members pm 
            JOIN users u ON pm.user_id = u.id 
            WHERE pm.project_id = ?
            UNION
            SELECT p.user_id as user_id, u.username
            FROM projects p 
            JOIN users u ON p.user_id = u.id 
            WHERE p.id = ?
        ''', (project_id, project_id)).fetchall()
        
        conn.close()
        
        return jsonify({
            'tasks_count': len(tasks),
            'members_count': len(members),
            'tasks': [dict(task) for task in tasks],
            'members': [dict(member) for member in members]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)