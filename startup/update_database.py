# update_database.py
import sqlite3
import os

def update_database():
    """Добавляет поле menu_position в таблицу users и priority в таблицу tasks"""
    
    # Путь к базе данных
    DATABASE = 'instance/app.db'
    
    # Проверяем существует ли база данных
    if not os.path.exists(DATABASE):
        print("База данных не найдена!")
        return
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # 1. Обновляем таблицу users (ваша существующая логика)
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'menu_position' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN menu_position TEXT DEFAULT "side"')
            print("✅ База данных успешно обновлена! Добавлено поле menu_position.")
        else:
            print("✅ Поле menu_position уже существует в таблице users.")
        
        # 2. ДОБАВЛЯЕМ: Обновляем таблицу tasks - добавляем поле priority
        cursor.execute("PRAGMA table_info(tasks)")
        task_columns = [column[1] for column in cursor.fetchall()]
        
        if 'priority' not in task_columns:
            cursor.execute('ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT "medium"')
            print("✅ Добавлено поле priority в таблицу tasks.")
            
            # Обновляем существующие задачи, устанавливая приоритет по умолчанию
            cursor.execute('UPDATE tasks SET priority = "medium" WHERE priority IS NULL')
            print("✅ Существующие задачи обновлены с приоритетом 'medium'.")
        else:
            print("✅ Поле priority уже существует в таблице tasks.")
        
        # 3. ДОБАВЛЯЕМ: Обновляем таблицу personal_tasks - тоже добавляем priority
        cursor.execute("PRAGMA table_info(personal_tasks)")
        personal_columns = [column[1] for column in cursor.fetchall()]
        
        if 'priority' not in personal_columns:
            cursor.execute('ALTER TABLE personal_tasks ADD COLUMN priority TEXT DEFAULT "medium"')
            print("✅ Добавлено поле priority в таблицу personal_tasks.")
            
            # Обновляем существующие персональные задачи
            cursor.execute('UPDATE personal_tasks SET priority = "medium" WHERE priority IS NULL')
            print("✅ Существующие персональные задачи обновлены с приоритетом 'medium'.")
        else:
            print("✅ Поле priority уже существует в таблице personal_tasks.")
        
        conn.commit()
        
        # 4. Проверяем текущие значения (ваша существующая логика)
        cursor.execute('SELECT id, username, menu_position FROM users')
        users = cursor.fetchall()
        print(f"👥 Найдено пользователей: {len(users)}")
        for user in users:
            print(f"   Пользователь: {user[1]} (ID: {user[0]}), menu_position: {user[2]}")
        
        # 5. ДОБАВЛЯЕМ: Проверяем задачи
        cursor.execute('SELECT COUNT(*) as task_count FROM tasks')
        task_count = cursor.fetchone()[0]
        print(f"📋 Найдено задач в проектах: {task_count}")
        
        cursor.execute('SELECT COUNT(*) as personal_count FROM personal_tasks')
        personal_count = cursor.fetchone()[0]
        print(f"📝 Найдено персональных задач: {personal_count}")
        
        # Показываем пример задач с приоритетами
        cursor.execute('SELECT id, title, priority FROM tasks LIMIT 5')
        sample_tasks = cursor.fetchall()
        if sample_tasks:
            print("📊 Пример задач:")
            for task in sample_tasks:
                print(f"   Задача: {task[1]} (ID: {task[0]}), приоритет: {task[2]}")
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении базы данных: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    print("🔄 Запуск обновления базы данных...")
    update_database()
    print("✅ Обновление завершено!")