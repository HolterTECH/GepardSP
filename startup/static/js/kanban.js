// Константы
const PROJECT_ID = parseInt(window.location.pathname.split('/')[2]);
const STATUS_MAP = {
    'planned': 'Запланировано',
    'in_progress': 'В работе', 
    'completed': 'Выполнено'
};

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    initDragAndDrop();
    initTaskForm();
    initEditForm();
    initDateCalculations();
});

// Drag and Drop функционал
function initDragAndDrop() {
    const taskCards = document.querySelectorAll('.task-card');
    const columns = document.querySelectorAll('.kanban-column');

    let draggedTask = null;

    taskCards.forEach(card => {
        card.addEventListener('dragstart', function(e) {
            draggedTask = this;
            this.classList.add('dragging');
            e.dataTransfer.setData('text/plain', this.dataset.taskId);
        });

        card.addEventListener('dblclick', function() {
            openEditModal(this.dataset.taskId);
        });
    });

    columns.forEach(column => {
        column.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.style.backgroundColor = '#d0d0d0';
        });

        column.addEventListener('dragleave', function() {
            this.style.backgroundColor = '#e0e0e0';
        });

        column.addEventListener('drop', function(e) {
            e.preventDefault();
            this.style.backgroundColor = '#e0e0e0';
            
            if (draggedTask) {
                const taskId = draggedTask.dataset.taskId;
                const newStatus = this.dataset.status;
                const tasksList = this.querySelector('.tasks-list');
                
                tasksList.appendChild(draggedTask);
                
                // Обновляем статус на сервере
                updateTaskStatus(taskId, newStatus);
            }
        });
    });
}

// Создание новой задачи
function initTaskForm() {
    const taskForm = document.getElementById('taskForm');
    
    taskForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const title = document.getElementById('taskTitle').value;
        const description = document.getElementById('taskDescription').value;
        const startDate = document.getElementById('taskStartDate').value;
        const endDate = document.getElementById('taskEndDate').value;
        const duration = parseInt(document.getElementById('taskDuration').value);
        
        createTask(title, description, duration, startDate, endDate);
        taskForm.reset();
    });
}

// Редактирование задачи
function initEditForm() {
    const modal = document.getElementById('editModal');
    const closeBtn = document.querySelector('.close');
    const editForm = document.getElementById('editTaskForm');
    
    closeBtn.onclick = function() {
        modal.style.display = 'none';
    }
    
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }
    
    editForm.addEventListener('submit', function(e) {
        e.preventDefault();
        saveTaskChanges();
    });
}

// Автоматический расчет дат
function initDateCalculations() {
    const startDateInput = document.getElementById('taskStartDate');
    const endDateInput = document.getElementById('taskEndDate');
    const durationInput = document.getElementById('taskDuration');
    
    // Устанавливаем сегодняшнюю дату по умолчанию
    const today = new Date().toISOString().split('T')[0];
    startDateInput.value = today;
    updateEndDateFromStartAndDuration();
    
    // Слушатели изменений
    startDateInput.addEventListener('change', function() {
        updateEndDateFromStartAndDuration();
    });
    
    durationInput.addEventListener('change', function() {
        updateEndDateFromStartAndDuration();
    });
    
    endDateInput.addEventListener('change', function() {
        updateDurationFromStartAndEnd();
    });
}

function updateEndDateFromStartAndDuration() {
    const startDate = document.getElementById('taskStartDate').value;
    const duration = parseInt(document.getElementById('taskDuration').value);
    
    if (startDate && duration) {
        const start = new Date(startDate);
        const endDate = new Date(start.getTime() + (duration - 1) * 24 * 60 * 60 * 1000);
        document.getElementById('taskEndDate').value = endDate.toISOString().split('T')[0];
    }
}

function updateDurationFromStartAndEnd() {
    const startDate = document.getElementById('taskStartDate').value;
    const endDate = document.getElementById('taskEndDate').value;
    
    if (startDate && endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        const duration = Math.ceil((end - start) / (24 * 60 * 60 * 1000)) + 1;
        document.getElementById('taskDuration').value = duration;
    }
}

// API функции
async function createTask(title, description, duration, startDate, endDate) {
    try {
        const priority = document.getElementById('taskPriority').value; // ← ДОБАВЬТЕ
        
        const response = await fetch(`/api/project/${PROJECT_ID}/task`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title,
                description,
                duration,
                start_date: startDate,
                end_date: endDate,
                priority: priority // ← ДОБАВЬТЕ
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            location.reload();
        } else {
            alert('Ошибка при создании задачи: ' + result.error);
        }
    } catch (error) {
        console.error('Ошибка при создании задачи:', error);
        alert('Ошибка при создании задачи');
    }
}

async function updateTaskStatus(taskId, newStatus) {
    try {
        await fetch(`/api/task/${taskId}/status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                status: newStatus,
                position: 0
            })
        });
    } catch (error) {
        console.error('Ошибка при обновлении статуса:', error);
    }
}

// Обновите функцию openEditModal
async function openEditModal(taskId) {
    try {
        const response = await fetch(`/api/task/${taskId}`);
        const task = await response.json();
        
        document.getElementById('editTaskId').value = task.id;
        document.getElementById('editTaskTitle').value = task.title;
        document.getElementById('editTaskDescription').value = task.description;
        document.getElementById('editTaskPriority').value = task.priority || 'medium'; // ← ДОБАВЬТЕ
        document.getElementById('editTaskStatus').value = task.status; // ← ДОБАВЬТЕ
        document.getElementById('editStartDate').value = task.start_date;
        document.getElementById('editEndDate').value = task.end_date;
        document.getElementById('editDuration').value = task.duration;
        
        // Загружаем исполнителей
        await loadTaskAssignees(taskId);
        await loadAvailableAssignees();
        
        document.getElementById('editModal').style.display = 'block';
    } catch (error) {
        console.error('Ошибка при загрузке задачи:', error);
        alert('Ошибка при загрузке задачи');
    }
}

// Обновите функцию saveTaskChanges
async function saveTaskChanges() {
    const taskId = document.getElementById('editTaskId').value;
    const title = document.getElementById('editTaskTitle').value;
    const description = document.getElementById('editTaskDescription').value;
    const priority = document.getElementById('editTaskPriority').value; // ← ДОБАВЬТЕ
    const status = document.getElementById('editTaskStatus').value; // ← ДОБАВЬТЕ
    const startDate = document.getElementById('editStartDate').value;
    const endDate = document.getElementById('editEndDate').value;
    const duration = parseInt(document.getElementById('editDuration').value);
    
    try {
        // 1. Обновляем основные данные задачи (включая приоритет)
        const updateResponse = await fetch(`/api/task/${taskId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: title,
                description: description,
                priority: priority // ← ДОБАВЬТЕ
            })
        });

        const updateResult = await updateResponse.json();
        
        if (!updateResult.success) {
            throw new Error('Ошибка при обновлении задачи: ' + updateResult.error);
        }

        // 2. Обновляем статус (если изменился)
        if (status) {
            await fetch(`/api/task/${taskId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    status: status,
                    position: 0
                })
            });
        }

        // 3. Обновляем даты
        const datesResponse = await fetch(`/api/task/${taskId}/dates`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                start_date: startDate,
                end_date: endDate,
                duration: duration
            })
        });

        const datesResult = await datesResponse.json();
        
        if (datesResult.success) {
            document.getElementById('editModal').style.display = 'none';
            location.reload();
        } else {
            throw new Error('Ошибка при обновлении дат: ' + datesResult.error);
        }
        
    } catch (error) {
        console.error('Ошибка при сохранении изменений:', error);
        alert('Ошибка при сохранении: ' + error.message);
    }
}

// Добавьте эти функции в kanban.js

// Загрузка исполнителей задачи
async function loadTaskAssignees(taskId) {
    try {
        const response = await fetch(`/api/task/${taskId}/assignees`);
        const assignees = await response.json();
        
        const assigneesList = document.getElementById('assigneesList');
        assigneesList.innerHTML = '';
        
        assignees.forEach(assignee => {
            const assigneeElement = document.createElement('div');
            assigneeElement.className = 'assignee-item';
            assigneeElement.innerHTML = `
                <span>${assignee.username}</span>
                <button type="button" onclick="removeAssignee(${taskId}, ${assignee.id})">×</button>
            `;
            assigneesList.appendChild(assigneeElement);
        });
    } catch (error) {
        console.error('Ошибка при загрузке исполнителей:', error);
    }
}

// Загрузка доступных исполнителей
async function loadAvailableAssignees() {
    try {
        const response = await fetch(`/api/project/${PROJECT_ID}/available_assignees`);
        const assignees = await response.json();
        
        const select = document.getElementById('assigneeSelect');
        select.innerHTML = '<option value="">Выберите исполнителя...</option>';
        
        assignees.forEach(assignee => {
            const option = document.createElement('option');
            option.value = assignee.id;
            option.textContent = `${assignee.username} (${assignee.email})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Ошибка при загрузке доступных исполнителей:', error);
    }
}

// Добавление исполнителя
async function addAssignee() {
    const select = document.getElementById('assigneeSelect');
    const userId = select.value;
    const taskId = document.getElementById('editTaskId').value;
    
    if (!userId) {
        alert('Выберите исполнителя');
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
            loadTaskAssignees(taskId);
            select.value = '';
        } else {
            alert('Ошибка при добавлении исполнителя: ' + result.error);
        }
    } catch (error) {
        console.error('Ошибка при добавлении исполнителя:', error);
        alert('Ошибка при добавлении исполнителя');
    }
}

// Удаление исполнителя
async function removeAssignee(taskId, userId) {
    try {
        const response = await fetch(`/api/task/${taskId}/assignees/${userId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            loadTaskAssignees(taskId);
        } else {
            alert('Ошибка при удалении исполнителя: ' + result.error);
        }
    } catch (error) {
        console.error('Ошибка при удалении исполнителя:', error);
        alert('Ошибка при удалении исполнителя');
    }
}

// Обновите функцию openEditModal:
async function openEditModal(taskId) {
    try {
        const response = await fetch(`/api/task/${taskId}`);
        const task = await response.json();
        
        document.getElementById('editTaskId').value = task.id;
        document.getElementById('editTaskTitle').value = task.title;
        document.getElementById('editTaskDescription').value = task.description;
        document.getElementById('editStartDate').value = task.start_date;
        document.getElementById('editEndDate').value = task.end_date;
        document.getElementById('editDuration').value = task.duration;
        
        // Загружаем исполнителей
        await loadTaskAssignees(taskId);
        await loadAvailableAssignees();
        
        document.getElementById('editModal').style.display = 'block';
    } catch (error) {
        console.error('Ошибка при загрузке задачи:', error);
        alert('Ошибка при загрузке задачи');
    }
}