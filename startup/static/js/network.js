// network.js - Логика для сетевого графика с разными типами связей

const PROJECT_ID = parseInt(window.location.pathname.split('/')[2]);
let network = null;
let tasks = [];

// Типы зависимостей
const DEPENDENCY_TYPES = {
    'FS': 'Окончание-Начало',
    'SS': 'Начало-Начало', 
    'FF': 'Окончание-Окончание',
    'SF': 'Начало-Окончание'
};

document.addEventListener('DOMContentLoaded', function() {
    initNetworkGraph();
    initDependencyModal();
});

function initNetworkGraph() {
    fetch(`/api/project/${PROJECT_ID}/tasks`)
        .then(response => response.json())
        .then(data => {
            tasks = data;
            renderNetworkGraph();
        })
        .catch(error => console.error('Ошибка загрузки задач:', error));
}

function renderNetworkGraph() {
    const container = document.getElementById('network');
    
    // Создаем узлы для задач
    const nodes = new vis.DataSet(tasks.map(task => ({
        id: task.id,
        label: task.title,
        title: `${task.title}\nДлительность: ${task.duration}д\nСтатус: ${getStatusText(task.status)}`,
        color: getStatusColor(task.status),
        shape: 'box',
        margin: 10
    })));

    // Загружаем зависимости и создаем edges
    loadDependencies().then(edges => {
        const data = { nodes, edges };
        const options = {
            layout: {
                hierarchical: {
                    enabled: true,
                    direction: 'LR',
                    sortMethod: 'directed'
                }
            },
            edges: {
                arrows: { to: { enabled: true, scaleFactor: 1.2 } },
                color: { color: '#848484', highlight: '#848484' },
                font: { align: 'middle' }
            },
            physics: {
                enabled: true,
                hierarchicalRepulsion: {
                    nodeDistance: 120
                }
            }
        };

        network = new vis.Network(container, data, options);
    });
}

async function loadDependencies() {
    try {
        const response = await fetch(`/api/project/${PROJECT_ID}/dependencies`);
        const dependencies = await response.json();
        
        return new vis.DataSet(dependencies.map(dep => ({
            id: dep.id,
            from: dep.predecessor_id,
            to: dep.task_id,
            label: `${DEPENDENCY_TYPES[dep.dependency_type]}${dep.lag ? `+${dep.lag}д` : ''}`,
            arrows: 'to',
            color: getDependencyColor(dep.dependency_type),
            dashes: dep.dependency_type !== 'FS'
        })));
    } catch (error) {
        console.error('Ошибка загрузки зависимостей:', error);
        return new vis.DataSet();
    }
}

function getDependencyColor(type) {
    const colors = {
        'FS': '#2E7D32', // Зеленый
        'SS': '#1976D2', // Синий
        'FF': '#7B1FA2', // Фиолетовый
        'SF': '#D32F2F'  // Красный
    };
    return colors[type] || '#848484';
}

function getStatusColor(status) {
    const colors = {
        'planned': '#FFA726',
        'in_progress': '#42A5F5', 
        'completed': '#66BB6A'
    };
    return colors[status] || '#BDBDBD';
}

function getStatusText(status) {
    const statusMap = {
        'planned': 'Запланировано',
        'in_progress': 'В работе',
        'completed': 'Выполнено'
    };
    return statusMap[status] || status;
}

// Модальное окно для управления зависимостями
function initDependencyModal() {
    const modal = document.getElementById('dependencyModal');
    const createBtn = document.getElementById('createDependencyBtn');
    const closeBtn = document.querySelector('.close-dependency');
    const form = document.getElementById('dependencyForm');
    
    // Обработчик кнопки "Создать связь"
    createBtn.onclick = function() {
        openDependencyModal();
    }
    
    closeBtn.onclick = function() {
        modal.style.display = 'none';
    }
    
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        saveDependency();
    });
}

function openDependencyModal() {
    const modal = document.getElementById('dependencyModal');
    const predecessorSelect = document.getElementById('predecessorTask');
    const dependentSelect = document.getElementById('dependentTask');
    
    // Очищаем и заполняем оба списка задач
    predecessorSelect.innerHTML = '<option value="">Выберите задачу-предшественник</option>';
    dependentSelect.innerHTML = '<option value="">Выберите задачу-приемник</option>';
    
    tasks.forEach(task => {
        const option1 = document.createElement('option');
        option1.value = task.id;
        option1.textContent = task.title;
        predecessorSelect.appendChild(option1);
        
        const option2 = document.createElement('option');
        option2.value = task.id;
        option2.textContent = task.title;
        dependentSelect.appendChild(option2);
    });
    
    modal.style.display = 'block';
}

async function saveDependency() {
    const predecessorId = document.getElementById('predecessorTask').value;
    const dependentId = document.getElementById('dependentTask').value;
    const dependencyType = document.getElementById('dependencyType').value;
    const lag = parseInt(document.getElementById('dependencyLag').value) || 0;
    
    if (!predecessorId || !dependentId) {
        alert('Выберите обе задачи');
        return;
    }
    
    if (predecessorId === dependentId) {
        alert('Задача не может зависеть от самой себя');
        return;
    }
    
    try {
        const response = await fetch(`/api/task/${dependentId}/dependency`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                predecessor_id: predecessorId,
                dependency_type: dependencyType,
                lag: lag
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('dependencyModal').style.display = 'none';
            document.getElementById('dependencyForm').reset();
            renderNetworkGraph(); // Перерисовываем граф
            alert('Связь успешно создана!');
        } else {
            alert('Ошибка: ' + result.error);
        }
    } catch (error) {
        console.error('Ошибка при сохранении зависимости:', error);
        alert('Ошибка при сохранении зависимости');
    }
}