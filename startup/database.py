import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), 'instance', 'app.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# database.py - ОБНОВЛЕННАЯ функция init_db()
def init_db():
    """Инициализирует базу данных только если она не существует"""
    os.makedirs('instance', exist_ok=True)
    
    # Проверяем, существует ли уже база данных
    if os.path.exists(DATABASE):
        print("База данных уже существует, пропускаем создание...")
        return
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Создание таблицы пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(128) NOT NULL,
                menu_position VARCHAR(10) DEFAULT 'side',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Создаем таблицу проектов с user_id
        cursor.execute('''
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Создаем таблицу задач
        cursor.execute('''
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'planned',
                position INTEGER DEFAULT 0,
                duration INTEGER DEFAULT 1,
                start_date DATE,
                end_date DATE,
                dependencies TEXT DEFAULT '',
                assigned_to INTEGER,
                FOREIGN KEY (project_id) REFERENCES projects (id),
                FOREIGN KEY (assigned_to) REFERENCES users (id)
            )
        ''')

        # Создаем таблицу персональных задач с user_id
        cursor.execute('''
            CREATE TABLE personal_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'planned',
                position INTEGER DEFAULT 0,
                duration INTEGER DEFAULT 1,
                start_date DATE,
                end_date DATE,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Таблица зависимостей задач
        cursor.execute('''
            CREATE TABLE task_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                predecessor_id INTEGER NOT NULL,
                dependency_type TEXT NOT NULL DEFAULT 'FS',
                lag INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES tasks (id),
                FOREIGN KEY (predecessor_id) REFERENCES tasks (id),
                UNIQUE(task_id, predecessor_id)
            )
        ''')

        # Таблица вех
        cursor.execute('''
            CREATE TABLE milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                date DATE NOT NULL,
                color TEXT DEFAULT '#FFD700',
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        ''')
        
        # Таблица участников проекта
        cursor.execute('''
            CREATE TABLE project_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(project_id, user_id)
            )
        ''')

        # Таблица исполнителей задач (многие-ко-многим)
        cursor.execute('''
            CREATE TABLE task_assignees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(task_id, user_id)
            )
        ''')

         # Таблица для исполнителей задач
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_assignees (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 task_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
                  FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                  UNIQUE(task_id, user_id)
            )
         ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_assignees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(task_id, user_id)
            )
        ''')
        
        # Добавить таблицу для расширенных зависимостей (если еще нет)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                predecessor_id INTEGER NOT NULL,
                dependency_type TEXT DEFAULT 'FS',
                lag INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
                FOREIGN KEY (predecessor_id) REFERENCES tasks (id) ON DELETE CASCADE,
                UNIQUE(task_id, predecessor_id)
            )
        ''')


        conn.execute('''
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                start_date DATE NOT NULL,
                start_time TIME,
                end_date DATE,
                end_time TIME,
                duration_minutes INTEGER,
                all_day BOOLEAN DEFAULT FALSE,
                event_type TEXT DEFAULT 'custom', -- custom, meeting, reminder, etc.
                color TEXT DEFAULT '#3498db',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Создаем тестового пользователя
        password_hash = generate_password_hash('admin123')
        cursor.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            ('admin', 'admin@example.com', password_hash)
        )

        # Получаем ID созданного пользователя
        user_id = cursor.lastrowid

        # Добавляем тестовые данные для этого пользователя
        cursor.execute(
            "INSERT INTO projects (name, description, user_id) VALUES ('Первый проект', 'Тестовый проект для начала', ?)",
            (user_id,)
        )
        
        # Добавим тестовые задачи с датами
        today = datetime.now().date()
        
        # Задача 1 - назначена пользователю
        cursor.execute('''INSERT INTO tasks 
                        (project_id, title, description, status, duration, start_date, end_date) 
                        VALUES (1, 'Первая задача', 'Описание первой задачи', 'planned', 3, ?, ?)''',
                        (today, today + timedelta(days=3)))
        task1_id = cursor.lastrowid
        
        # Задача 2 - назначена пользователю
        cursor.execute('''INSERT INTO tasks 
                        (project_id, title, description, status, duration, start_date, end_date) 
                        VALUES (1, 'Вторая задача', 'Описание второй задачи', 'in_progress', 5, ?, ?)''',
                        (today, today + timedelta(days=5)))
        task2_id = cursor.lastrowid
        
        # Задача 3 - НЕ назначена пользователю (для теста)
        cursor.execute('''INSERT INTO tasks 
                        (project_id, title, description, status, duration, start_date, end_date) 
                        VALUES (1, 'Третья задача', 'Описание третьей задачи', 'completed', 2, ?, ?)''',
                        (today - timedelta(days=5), today - timedelta(days=3)))
        task3_id = cursor.lastrowid

        # Назначаем задачи пользователю через task_assignees
        cursor.execute('INSERT INTO task_assignees (task_id, user_id) VALUES (?, ?)', (task1_id, user_id))
        cursor.execute('INSERT INTO task_assignees (task_id, user_id) VALUES (?, ?)', (task2_id, user_id))
        # Задача 3 НЕ назначаем - она не должна показываться в "Мои задачи"

        # Добавляем тестовую персональную задачу
        cursor.execute('''INSERT INTO personal_tasks 
                        (title, description, status, duration, start_date, end_date, user_id) 
                        VALUES ('Моя персональная задача', 'Описание персональной задачи', 'planned', 2, ?, ?, ?)''',
                        (today, today + timedelta(days=1), user_id))

        conn.commit()
        print("База данных успешно создана с тестовыми назначениями задач!")
        
    except Exception as e:
        print(f"Ошибка при создании базы данных: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

# Функции для работы с пользователями
def create_user(username, email, password):
    conn = get_db_connection()
    try:
        password_hash = generate_password_hash(password)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def verify_password(username, password):
    user = get_user_by_username(username)
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None

# Обновляем существующие функции для учета user_id
def create_task(project_id, title, description, duration=1, start_date=None, end_date=None, assigned_to=None):
    conn = get_db_connection()
    
    if start_date is None:
        start_date = datetime.now().date().isoformat()
    if end_date is None and start_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = (start_dt + timedelta(days=duration-1)).strftime('%Y-%m-%d')
    elif end_date is None:
        end_date = (datetime.now().date() + timedelta(days=duration-1)).isoformat()
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (project_id, title, description, status, duration, start_date, end_date, assigned_to)
        VALUES (?, ?, ?, 'planned', ?, ?, ?, ?)
    ''', (project_id, title, description, duration, start_date, end_date, assigned_to))
    
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def create_personal_task(title, description, duration=1, start_date=None, end_date=None, user_id=None):
    conn = get_db_connection()
    
    if start_date is None:
        start_date = datetime.now().date().isoformat()
    if end_date is None:
        end_date = (datetime.now().date() + timedelta(days=duration-1)).isoformat()
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO personal_tasks (title, description, duration, start_date, end_date, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (title, description, duration, start_date, end_date, user_id))
    
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def update_task_status(task_id, status, position):
    conn = get_db_connection()
    conn.execute('UPDATE tasks SET status = ?, position = ? WHERE id = ?',
                 (status, position, task_id))
    conn.commit()
    conn.close()

def update_task_dates(task_id, start_date=None, end_date=None, duration=None):
    conn = get_db_connection()
    
    try:
        if start_date and end_date:
            # Если изменились обе даты, пересчитываем длительность
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            new_duration = (end_dt - start_dt).days + 1
            conn.execute('UPDATE tasks SET start_date = ?, end_date = ?, duration = ? WHERE id = ?',
                         (start_date, end_date, new_duration, task_id))
        elif start_date and duration:
            # Если изменилась дата начала и длительность
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            new_end_date = (start_dt + timedelta(days=int(duration)-1)).strftime('%Y-%m-%d')
            conn.execute('UPDATE tasks SET start_date = ?, end_date = ?, duration = ? WHERE id = ?',
                         (start_date, new_end_date, duration, task_id))
        elif end_date and duration:
            # Если изменилась дата окончания и длительность
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            new_start_date = (end_dt - timedelta(days=int(duration)-1)).strftime('%Y-%m-%d')
            conn.execute('UPDATE tasks SET start_date = ?, end_date = ?, duration = ? WHERE id = ?',
                         (new_start_date, end_date, duration, task_id))
        
        conn.commit()
    except Exception as e:
        print(f"Ошибка при обновлении дат: {e}")
    finally:
        conn.close()

# Добавляем функцию для получения задачи по ID
def get_task_by_id(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    return task

# В database.py ДОБАВЛЯЕМ ТЕ ЖЕ ФУНКЦИИ
def update_dependent_tasks_status(task_id, new_status):
    """Автоматически обновляет статусы зависимых задач при изменении статуса текущей задачи"""
    conn = get_db_connection()
    
    try:
        # Получаем текущую задачу
        task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not task:
            return
        
        # Получаем ВСЕ зависимости где текущая задача является предшественником
        dependencies = conn.execute('''
            SELECT td.*, t.status as dependent_task_status 
            FROM task_dependencies td 
            JOIN tasks t ON td.task_id = t.id 
            WHERE td.predecessor_id = ?
        ''', (task_id,)).fetchall()
        
        for dep in dependencies:
            dependent_task_id = dep['task_id']
            dependency_type = dep['dependency_type']
            dependent_task_status = dep['dependent_task_status']
            
            if dependency_type == 'FS' and new_status == 'completed':
                if dependent_task_status == 'planned':
                    conn.execute('UPDATE tasks SET status = "in_progress" WHERE id = ?', 
                               (dependent_task_id,))
            
            elif dependency_type == 'SS' and new_status == 'in_progress':
                if dependent_task_status == 'planned':
                    conn.execute('UPDATE tasks SET status = "in_progress" WHERE id = ?', 
                               (dependent_task_id,))
            
            elif dependency_type == 'FF' and new_status == 'completed':
                if dependent_task_status == 'in_progress':
                    conn.execute('UPDATE tasks SET status = "completed" WHERE id = ?', 
                               (dependent_task_id,))
            
            elif dependency_type == 'SF' and new_status == 'in_progress':
                if dependent_task_status == 'in_progress':
                    conn.execute('UPDATE tasks SET status = "completed" WHERE id = ?', 
                               (dependent_task_id,))
        
        conn.commit()
        
    except Exception as e:
        print(f"Ошибка при обновлении зависимых задач: {e}")
    finally:
        conn.close()

# В database.py добавить эти функции после существующих

def update_user_profile(user_id, username, email):
    """Обновляет профиль пользователя (имя и email)"""
    conn = get_db_connection()
    try:
        conn.execute(
            'UPDATE users SET username = ?, email = ? WHERE id = ?',
            (username, email, user_id)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Если имя пользователя или email уже существуют
        return False
    finally:
        conn.close()

def update_user_password(user_id, new_password):
    """Обновляет пароль пользователя"""
    password_hash = generate_password_hash(new_password)
    conn = get_db_connection()
    conn.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (password_hash, user_id)
    )
    conn.commit()
    conn.close()

def verify_current_password(user_id, current_password):
    """Проверяет текущий пароль пользователя"""
    user = get_user_by_id(user_id)
    if user and check_password_hash(user['password_hash'], current_password):
        return True
    return False

def get_assigned_tasks(user_id):
    """Получить все задачи, назначенные пользователю"""
    conn = get_db_connection()
    
    tasks = conn.execute('''
        SELECT DISTINCT t.*, p.name as project_name, p.id as project_id
        FROM tasks t
        JOIN task_assignees ta ON t.id = ta.task_id
        JOIN projects p ON t.project_id = p.id
        LEFT JOIN project_members pm ON p.id = pm.project_id AND pm.user_id = ?
        WHERE ta.user_id = ? 
        AND (p.user_id = ? OR pm.user_id = ?)
        ORDER BY 
            CASE t.status 
                WHEN 'planned' THEN 1 
                WHEN 'in_progress' THEN 2 
                WHEN 'completed' THEN 3 
            END,
            t.start_date ASC
    ''', (user_id, user_id, user_id, user_id)).fetchall()
    
    conn.close()
    return tasks

# В database.py - обновить функцию create_user
def create_user(username, email, password, menu_position='side'):
    """Создать нового пользователя"""
    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (username, email, password_hash, menu_position) VALUES (?, ?, ?, ?)',
            (username, email, password_hash, menu_position)
        )
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

# Добавить функцию для обновления расположения меню
def update_user_menu_position(user_id, menu_position):
    """Обновить расположение меню пользователя"""
    conn = get_db_connection()
    try:
        conn.execute(
            'UPDATE users SET menu_position = ? WHERE id = ?',
            (menu_position, user_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка при обновлении расположения меню: {e}")
        return False
    finally:
        conn.close()

# Обновить функцию get_user_by_id
def get_user_by_id(user_id):
    """Получить пользователя по ID"""
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (user_id,)
    ).fetchone()
    conn.close()
    return user

def update_user_menu_position(user_id, menu_position):
    """Обновляет настройку расположения меню для пользователя"""
    try:
        conn = get_db_connection()
        conn.execute(
            'UPDATE users SET menu_position = ? WHERE id = ?',
            (menu_position, user_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при обновлении расположения меню: {e}")
        return False
    
def update_user_menu_position(user_id, menu_position):
    """Обновляет расположение меню пользователя"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET menu_position = ? WHERE id = ?',
            (menu_position, user_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при обновлении расположения меню: {e}")
        return False