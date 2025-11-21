from flask_login import UserMixin
from datetime import datetime

# В models.py - убедитесь, что класс User имеет menu_position
class User(UserMixin):
    def __init__(self, id, username, email, password_hash, created_at=None, menu_position='side'):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at or datetime.utcnow()
        self.menu_position = menu_position  # УБЕДИТЕСЬ, ЧТО ЭТО ЕСТЬ

    def get_id(self):
        return str(self.id)

class Project:
    def __init__(self, id, name, description, user_id=None):
        self.id = id
        self.name = name
        self.description = description
        self.user_id = user_id

class Task:
    def __init__(self, id, project_id, title, description, status, position, duration=0, dependencies="", assigned_to=None, start_date=None, end_date=None, priority='medium'):
        self.id = id
        self.project_id = project_id
        self.title = title
        self.description = description
        self.status = status
        self.position = position
        self.duration = duration
        self.dependencies = dependencies
        self.assigned_to = assigned_to
        self.start_date = start_date
        self.end_date = end_date
        self.priority = priority  # 'low', 'medium', 'high'

class Milestone:
    def __init__(self, id, project_id, title, description, date, color="#FFD700"):
        self.id = id
        self.project_id = project_id
        self.title = title
        self.description = description
        self.date = date
        self.color = color

class PersonalTask:
    def __init__(self, id, title, description, status, position, duration=0, start_date=None, end_date=None, user_id=None):
        self.id = id
        self.title = title
        self.description = description
        self.status = status
        self.position = position
        self.duration = duration
        self.start_date = start_date
        self.end_date = end_date
        self.user_id = user_id

class ProjectMember:
    def __init__(self, id, project_id, user_id, role='member', joined_at=None):
        self.id = id
        self.project_id = project_id
        self.user_id = user_id
        self.role = role
        self.joined_at = joined_at or datetime.utcnow()

# Добавить в models.py
class TaskAssignee:
    def __init__(self, id, task_id, user_id, assigned_at=None):
        self.id = id
        self.task_id = task_id
        self.user_id = user_id
        self.assigned_at = assigned_at

# Добавить в конец models.py
class CalendarEvent:
    def __init__(self, id, user_id, title, description, start_date, start_time=None, 
                 end_date=None, end_time=None, duration_minutes=None, all_day=False, 
                 event_type='custom', color='#3498db', created_at=None):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.description = description
        self.start_date = start_date
        self.start_time = start_time
        self.end_date = end_date
        self.end_time = end_time
        self.duration_minutes = duration_minutes
        self.all_day = all_day
        self.event_type = event_type
        self.color = color
        self.created_at = created_at or datetime.utcnow()
