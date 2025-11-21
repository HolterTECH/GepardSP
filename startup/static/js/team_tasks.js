// static/js/team_tasks.js
class TeamTasksManager {
    constructor(projectId) {
        this.projectId = projectId;
        this.currentFilters = {
            member: 'all',
            status: 'all'
        };
        this.currentTaskId = null; // Для отслеживания текущей редактируемой задачи
        this.init();
    }

    init() {
        this.loadTeamTasks();
        this.setupEventListeners();
        this.setupModals();
    }

    setupEventListeners() {
        // Фильтры
        document.getElementById('memberFilter').addEventListener('change', (e) => {
            this.currentFilters.member = e.target.value;
            this.applyFilters();
        });

        document.getElementById('statusFilter').addEventListener('change', (e) => {
            this.currentFilters.status = e.target.value;
            this.applyFilters();
        });

        // Кнопка назначения задачи
        document.getElementById('assignTaskBtn').addEventListener('click', () => {
            this.openAssignModal();
        });

        // Форма назначения задачи
        document.getElementById('assignTaskForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.assignNewTask();
        });
    }

    setupModals() {
        // Закрытие модальных окон по крестику
        document.querySelectorAll('.close').forEach(closeBtn => {
            closeBtn.addEventListener('click', (e) => {
                e.target.closest('.modal').style.display = 'none';
            });
        });

        // Закрытие по клику вне модального окна
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.style.display = 'none';
                }
            });
        });

        // ✅ ДОБАВЛЯЕМ: Форма редактирования задачи
        document.getElementById('taskEditForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveTaskChanges();
        });

        // ✅ ДОБАВЛЯЕМ: Кнопка удаления задачи
        document.getElementById('deleteTaskBtn').addEventListener('click', () => {
            this.deleteCurrentTask();
        });

        // ✅ ДОБАВЛЯЕМ: Быстрая смена статуса
        document.querySelectorAll('.status-option').forEach(option => {
            option.addEventListener('click', (e) => {
                const status = e.currentTarget.dataset.status;
                this.changeTaskStatus(this.currentTaskId, status);
            });
        });
    }

    async loadTeamTasks() {
        try {
            const response = await fetch(`/api/project/${this.projectId}/team/tasks`);
            const data = await response.json();
            
            if (data.success) {
                this.renderTeamTasks(data.tasks);
                this.updateStats(data.stats);
            } else {
                console.error('Ошибка загрузки задач:', data.error);
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    }

    renderTeamTasks(tasks) {
        // Группируем задачи по исполнителям
        const tasksByMember = this.groupTasksByMember(tasks);
        
        // Очищаем контейнеры задач
        document.querySelectorAll('.member-tasks').forEach(container => {
            container.innerHTML = '';
        });

        // Рендерим задачи для каждого участника
        Object.entries(tasksByMember).forEach(([userId, userTasks]) => {
            this.renderMemberTasks(userId, userTasks);
        });

        // Обновляем счетчики задач
        this.updateTaskCounts(tasksByMember);
    }

    groupTasksByMember(tasks) {
        const grouped = {};
        
        tasks.forEach(task => {
            task.assignees.forEach(assignee => {
                if (!grouped[assignee.id]) {
                    grouped[assignee.id] = [];
                }
                grouped[assignee.id].push(task);
            });
        });

        return grouped;
    }

    // ✅ ОБНОВЛЯЕМ: Рендеринг карточек с кнопками действий
    renderMemberTasks(userId, tasks) {
        const container = document.getElementById(`tasks-${userId}`);
        if (!container) return;

        if (tasks.length === 0) {
            container.innerHTML = '<div class="empty-tasks">Нет назначенных задач</div>';
            return;
        }

        container.innerHTML = tasks.map(task => `
            <div class="task-card ${task.status}" 
                 onclick="teamTasksManager.openTaskEdit(${task.id})">
                <div class="task-actions">
                    <button class="task-action-btn" 
                            onclick="event.stopPropagation(); teamTasksManager.openQuickStatusChange(${task.id}, '${task.status}')"
                            title="Сменить статус">🔄</button>
                    <button class="task-action-btn" 
                            onclick="event.stopPropagation(); teamTasksManager.openTaskEdit(${task.id})"
                            title="Редактировать">✏️</button>
                </div>
                <div class="task-title">${this.escapeHtml(task.title)}</div>
                <div class="task-meta">
                    <span>${task.duration} дн.</span>
                    <span class="task-status status-${task.status}">
                        ${this.getStatusText(task.status)}
                    </span>
                </div>
                <div class="task-meta">
                    <small>${task.start_date} - ${task.end_date}</small>
                </div>
            </div>
        `).join('');
    }

    updateTaskCounts(tasksByMember) {
        Object.entries(tasksByMember).forEach(([userId, tasks]) => {
            const countElement = document.getElementById(`taskCount-${userId}`);
            if (countElement) {
                countElement.textContent = tasks.length;
            }
        });
    }

    updateStats(stats) {
        document.getElementById('totalTasks').textContent = stats.total;
        document.getElementById('inProgressTasks').textContent = stats.in_progress;
        document.getElementById('completedTasks').textContent = stats.completed;
    }

    applyFilters() {
        const memberColumns = document.querySelectorAll('.member-column');
        
        memberColumns.forEach(column => {
            const userId = column.dataset.userId;
            const shouldShow = 
                this.currentFilters.member === 'all' || 
                this.currentFilters.member === userId;
            
            column.style.display = shouldShow ? 'block' : 'none';
        });

        // Фильтрация по статусу
        if (this.currentFilters.status !== 'all') {
            document.querySelectorAll('.task-card').forEach(card => {
                const shouldShow = card.classList.contains(this.currentFilters.status);
                card.style.display = shouldShow ? 'block' : 'none';
            });
        } else {
            document.querySelectorAll('.task-card').forEach(card => {
                card.style.display = 'block';
            });
        }
    }

    openAssignModal() {
        document.getElementById('assignTaskModal').style.display = 'block';
    }

    closeAssignModal() {
        document.getElementById('assignTaskModal').style.display = 'none';
        document.getElementById('assignTaskForm').reset();
    }

    async assignNewTask() {
        const formData = new FormData(document.getElementById('assignTaskForm'));
        const taskData = {
            title: formData.get('title'),
            description: formData.get('description'),
            assignee_id: parseInt(formData.get('assignee_id')),
            duration: parseInt(formData.get('duration')),
            start_date: formData.get('start_date'),
            priority: formData.get('priority')
        };

        try {
            const response = await fetch(`/api/project/${this.projectId}/team/task`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(taskData)
            });

            const result = await response.json();

            if (result.success) {
                this.closeAssignModal();
                this.loadTeamTasks();
                this.showNotification('Задача успешно назначена!', 'success');
            } else {
                this.showNotification('Ошибка: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Ошибка:', error);
            this.showNotification('Ошибка при назначении задачи', 'error');
        }
    }

    // ✅ ДОБАВЛЯЕМ: ОТКРЫТИЕ РЕДАКТИРОВАНИЯ ЗАДАЧИ
    async openTaskEdit(taskId) {
        try {
            this.currentTaskId = taskId;
            
            const response = await fetch(`/api/task/${taskId}`);
            const task = await response.json();

            if (task) {
                this.populateEditForm(task);
                await this.loadAvailableAssignees();
                await this.loadTaskAssignees(taskId);
                this.openEditModal();
            }
        } catch (error) {
            console.error('Ошибка загрузки задачи:', error);
            this.showNotification('Ошибка загрузки задачи', 'error');
        }
    }

    // ✅ ДОБАВЛЯЕМ: ЗАПОЛНЕНИЕ ФОРМЫ РЕДАКТИРОВАНИЯ
    populateEditForm(task) {
        document.getElementById('editTaskId').value = task.id;
        document.getElementById('editTaskTitle').value = task.title;
        document.getElementById('editTaskDescription').value = task.description || '';
        document.getElementById('editTaskStatus').value = task.status;
        document.getElementById('editTaskDuration').value = task.duration;
        document.getElementById('editTaskStartDate').value = task.start_date;
        document.getElementById('editTaskEndDate').value = task.end_date;

        // Настройка автоматического расчета дат
        this.setupDateCalculations();
    }

    // ✅ ДОБАВЛЯЕМ: АВТОМАТИЧЕСКИЙ РАСЧЕТ ДАТ
    setupDateCalculations() {
        const startDateInput = document.getElementById('editTaskStartDate');
        const endDateInput = document.getElementById('editTaskEndDate');
        const durationInput = document.getElementById('editTaskDuration');

        const updateDates = () => {
            const startDate = startDateInput.value;
            const duration = parseInt(durationInput.value);
            
            if (startDate && duration) {
                const start = new Date(startDate);
                const endDate = new Date(start.getTime() + (duration - 1) * 24 * 60 * 60 * 1000);
                endDateInput.value = endDate.toISOString().split('T')[0];
            }
        };

        startDateInput.addEventListener('change', updateDates);
        durationInput.addEventListener('change', updateDates);
    }

    // ✅ ДОБАВЛЯЕМ: ЗАГРУЗКА ДОСТУПНЫХ ИСПОЛНИТЕЛЕЙ
    async loadAvailableAssignees() {
        try {
            const response = await fetch(`/api/project/${this.projectId}/available_assignees`);
            const assignees = await response.json();
            
            const select = document.getElementById('editAssigneeSelect');
            select.innerHTML = '<option value="">Добавить исполнителя...</option>';
            
            assignees.forEach(assignee => {
                const option = document.createElement('option');
                option.value = assignee.id;
                option.textContent = `${assignee.username} (${assignee.email})`;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Ошибка загрузки исполнителей:', error);
        }
    }

    // ✅ ДОБАВЛЯЕМ: ЗАГРУЗКА ИСПОЛНИТЕЛЕЙ ЗАДАЧИ
    async loadTaskAssignees(taskId) {
        try {
            const response = await fetch(`/api/task/${taskId}/assignees`);
            const assignees = await response.json();
            
            const container = document.getElementById('editAssigneesList');
            container.innerHTML = '';
            
            assignees.forEach(assignee => {
                const assigneeElement = document.createElement('div');
                assigneeElement.className = 'assignee-item';
                assigneeElement.innerHTML = `
                    <span>${this.escapeHtml(assignee.username)}</span>
                    <button type="button" class="remove-assignee" 
                            onclick="teamTasksManager.removeAssignee(${taskId}, ${assignee.id})">×</button>
                `;
                container.appendChild(assigneeElement);
            });
        } catch (error) {
            console.error('Ошибка загрузки исполнителей задачи:', error);
        }
    }

    // ✅ ДОБАВЛЯЕМ: ДОБАВЛЕНИЕ ИСПОЛНИТЕЛЯ
    async addAssigneeToTask() {
        const select = document.getElementById('editAssigneeSelect');
        const userId = select.value;
        const taskId = this.currentTaskId;
        
        if (!userId) {
            this.showNotification('Выберите исполнителя', 'warning');
            return;
        }
        
        try {
            const response = await fetch(`/api/task/${taskId}/assignees`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_id: parseInt(userId) })
            });
            
            const result = await response.json();
            
            if (result.success) {
                await this.loadTaskAssignees(taskId);
                select.value = '';
                this.showNotification('Исполнитель добавлен', 'success');
            } else {
                this.showNotification('Ошибка: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Ошибка добавления исполнителя:', error);
            this.showNotification('Ошибка добавления исполнителя', 'error');
        }
    }

    // ✅ ДОБАВЛЯЕМ: УДАЛЕНИЕ ИСПОЛНИТЕЛЯ
    async removeAssignee(taskId, userId) {
        try {
            const response = await fetch(`/api/task/${taskId}/assignees/${userId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                await this.loadTaskAssignees(taskId);
                this.showNotification('Исполнитель удален', 'success');
            } else {
                this.showNotification('Ошибка: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Ошибка удаления исполнителя:', error);
            this.showNotification('Ошибка удаления исполнителя', 'error');
        }
    }

    // ✅ ДОБАВЛЯЕМ: СОХРАНЕНИЕ ИЗМЕНЕНИЙ ЗАДАЧИ
    async saveTaskChanges() {
        const formData = new FormData(document.getElementById('taskEditForm'));
        const taskId = formData.get('task_id');
        
        const taskData = {
            title: formData.get('title'),
            description: formData.get('description'),
            status: formData.get('status'),
            duration: parseInt(formData.get('duration')),
            start_date: formData.get('start_date'),
            end_date: formData.get('end_date')
        };

        try {
            // 1. Обновляем основные данные задачи
            const updateResponse = await fetch(`/api/task/${taskId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: taskData.title,
                    description: taskData.description
                })
            });

            const updateResult = await updateResponse.json();
            
            if (!updateResult.success) {
                throw new Error('Ошибка при обновлении задачи: ' + updateResult.error);
            }

            // 2. Обновляем статус
            await fetch(`/api/task/${taskId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    status: taskData.status,
                    position: 0
                })
            });

            // 3. Обновляем даты
            const datesResponse = await fetch(`/api/task/${taskId}/dates`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    start_date: taskData.start_date,
                    end_date: taskData.end_date,
                    duration: taskData.duration
                })
            });

            const datesResult = await datesResponse.json();
            
            if (datesResult.success) {
                this.closeEditModal();
                this.loadTeamTasks(); // Перезагружаем задачи
                this.showNotification('Задача успешно обновлена!', 'success');
            } else {
                throw new Error('Ошибка при обновлении дат: ' + datesResult.error);
            }
            
        } catch (error) {
            console.error('Ошибка сохранения:', error);
            this.showNotification('Ошибка сохранения: ' + error.message, 'error');
        }
    }

    // ✅ ДОБАВЛЯЕМ: УДАЛЕНИЕ ЗАДАЧИ
    async deleteCurrentTask() {
        const taskId = this.currentTaskId;
        
        if (!confirm('Вы уверены, что хотите удалить эту задачу? Это действие нельзя отменить.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/task/${taskId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.closeEditModal();
                this.loadTeamTasks();
                this.showNotification('Задача удалена', 'success');
            } else {
                this.showNotification('Ошибка: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Ошибка удаления задачи:', error);
            this.showNotification('Ошибка удаления задачи', 'error');
        }
    }

    // ✅ ДОБАВЛЯЕМ: БЫСТРАЯ СМЕНА СТАТУСА
    async openQuickStatusChange(taskId, currentStatus) {
        this.currentTaskId = taskId;
        
        try {
            const response = await fetch(`/api/task/${taskId}`);
            const task = await response.json();
            
            document.getElementById('quickStatusTaskTitle').textContent = task.title;
            
            // Выделяем текущий статус
            document.querySelectorAll('.status-option').forEach(option => {
                option.classList.remove('selected');
                if (option.dataset.status === currentStatus) {
                    option.classList.add('selected');
                }
            });
            
            document.getElementById('quickStatusModal').style.display = 'block';
        } catch (error) {
            console.error('Ошибка загрузки задачи:', error);
        }
    }

    // ✅ ДОБАВЛЯЕМ: ИЗМЕНЕНИЕ СТАТУСА ЗАДАЧИ
    async changeTaskStatus(taskId, newStatus) {
        try {
            const response = await fetch(`/api/task/${taskId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    status: newStatus,
                    position: 0
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.closeQuickStatusModal();
                this.loadTeamTasks();
                this.showNotification(`Статус изменен на "${this.getStatusText(newStatus)}"`, 'success');
            } else {
                this.showNotification('Ошибка: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Ошибка смены статуса:', error);
            this.showNotification('Ошибка смены статуса', 'error');
        }
    }

    // ✅ ДОБАВЛЯЕМ: УПРАВЛЕНИЕ МОДАЛЬНЫМИ ОКНАМИ
    openEditModal() {
        document.getElementById('taskEditModal').style.display = 'block';
    }

    closeEditModal() {
        document.getElementById('taskEditModal').style.display = 'none';
        document.getElementById('taskEditForm').reset();
        this.currentTaskId = null;
    }

    closeQuickStatusModal() {
        document.getElementById('quickStatusModal').style.display = 'none';
        this.currentTaskId = null;
    }

    // Вспомогательные методы
    getStatusText(status) {
        const statusMap = {
            'planned': 'Запланировано',
            'in_progress': 'В работе',
            'completed': 'Завершено'
        };
        return statusMap[status] || status;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showNotification(message, type) {
        // Простая реализация уведомлений
        alert(`${type === 'success' ? '✅' : '❌'} ${message}`);
    }
}

// Глобальная переменная для доступа из HTML
let teamTasksManager;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    teamTasksManager = new TeamTasksManager(PROJECT_ID);
});

// Глобальные функции для вызова из HTML
function closeAssignModal() {
    teamTasksManager.closeAssignModal();
}

function closeEditModal() {
    teamTasksManager.closeEditModal();
}

function closeQuickStatusModal() {
    teamTasksManager.closeQuickStatusModal();
}