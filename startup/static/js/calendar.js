document.addEventListener('DOMContentLoaded', function() {
    let calendar;
    let allEvents = [];
    let selectedDate = null;
    
    console.log('Calendar script loaded'); // Отладочное сообщение
    
    // Инициализация календаря
    function initCalendar() {
        const calendarEl = document.getElementById('calendar');
        
        if (!calendarEl) {
            console.error('Calendar element not found!');
            return;
        }
        
        console.log('Initializing calendar...');
        
        calendar = new FullCalendar.Calendar(calendarEl, {
            locale: 'ru',
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay,listMonth'
            },
            buttonText: {
                today: 'Сегодня',
                month: 'Месяц',
                week: 'Неделя',
                day: 'День',
                list: 'Список'
            },
            events: function(fetchInfo, successCallback, failureCallback) {
                console.log('Loading calendar events...');
                loadCalendarEvents(successCallback, failureCallback);
            },
            eventClick: function(info) {
                console.log('Event clicked:', info.event);
                showEventDetails(info.event);
            },
            dateClick: function(info) {
                console.log('Date clicked:', info.dateStr);
                selectedDate = info.date;
                openCreateEventModal(info.dateStr);
            },
            eventDidMount: function(info) {
                console.log('Event mounted:', info.event); // Отладочная информация
                
                const props = info.event.extendedProps;
                const eventType = props.event_type;
                const isMilestone = eventType === 'milestone';
                const isCustom = eventType === 'custom' || props.source === 'custom';
                const isTask = eventType === 'task';
                
                console.log('Event props:', props); // Отладочная информация
                
                // Добавляем классы для разных типов событий
                if (isMilestone) {
                    info.el.classList.add('fc-event-milestone');
                    const titleEl = info.el.querySelector('.fc-event-title');
                    if (titleEl) {
                        titleEl.innerHTML = `⭐ ${titleEl.innerHTML}`;
                    }
                } else if (isCustom) {
                    info.el.classList.add('custom-event');
                    const titleEl = info.el.querySelector('.fc-event-title');
                    if (titleEl) {
                        titleEl.innerHTML = `📅 ${titleEl.innerHTML}`;
                    }
                } else if (isTask) {
                    const titleEl = info.el.querySelector('.fc-event-title');
                    if (titleEl) {
                        const taskType = props.type;
                        const icon = taskType === 'project_task' ? '📋' : '✅';
                        titleEl.innerHTML = `${icon} ${titleEl.innerHTML}`;
                    }
                }
                
                // Добавляем подсказку
                let tooltip = info.event.title;
                tooltip += `\nПроект: ${props.project_name || 'Мое событие'}`;
                
                if (isTask) {
                    tooltip += `\nСтатус: ${getStatusText(props.status)}`;
                } else if (isMilestone) {
                    tooltip += `\nТип: Веха`;
                } else {
                    tooltip += `\nТип: Событие`;
                }
                
                info.el.title = tooltip;
            },
            loading: function(isLoading) {
                if (isLoading) {
                    console.log('Calendar is loading...');
                } else {
                    console.log('Calendar loaded successfully');
                }
            }
        });
        
        calendar.render();
        console.log('Calendar rendered');
        
        // Обработчики
        setupFilters();
        setupEventHandlers();
        
        // Устанавливаем сегодняшнюю дату по умолчанию
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('eventStartDate').value = today;
    }
    
    // Загрузка событий для календаря
    function loadCalendarEvents(successCallback, failureCallback) {
        fetch('/api/calendar/events')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(events => {
                console.log('Loaded events:', events);
                allEvents = events;
                const filteredEvents = filterEvents(allEvents);
                successCallback(filteredEvents);
            })
            .catch(error => {
                console.error('Error loading calendar events:', error);
                if (failureCallback) {
                    failureCallback(error);
                }
                successCallback([]); // Всегда вызываем successCallback даже при ошибке
            });
    }
    
    // Фильтрация событий
    function filterEvents(events) {
        const showProjectTasks = document.getElementById('filterProjectTasks')?.checked ?? true;
        const showPersonalTasks = document.getElementById('filterPersonalTasks')?.checked ?? true;
        const showMilestones = document.getElementById('filterMilestones')?.checked ?? true;
        const showCustomEvents = document.getElementById('filterCustomEvents')?.checked ?? true;
        const showPlanned = document.getElementById('filterPlanned')?.checked ?? true;
        const showInProgress = document.getElementById('filterInProgress')?.checked ?? true;
        const showCompleted = document.getElementById('filterCompleted')?.checked ?? true;
        
        return events.filter(event => {
            const eventType = event.extendedProps?.event_type;
            const taskType = event.extendedProps?.type;
            const status = event.extendedProps?.status;
            
            // Фильтр по типу события
            if (eventType === 'milestone' && !showMilestones) return false;
            if (eventType === 'custom' && !showCustomEvents) return false;
            if (eventType === 'task') {
                if (taskType === 'project_task' && !showProjectTasks) return false;
                if (taskType === 'personal_task' && !showPersonalTasks) return false;
                
                // Фильтр по статусу для задач
                if (status === 'planned' && !showPlanned) return false;
                if (status === 'in_progress' && !showInProgress) return false;
                if (status === 'completed' && !showCompleted) return false;
            }
            
            return true;
        });
    }
    
    // Настройка фильтров
    function setupFilters() {
        const filterInputs = document.querySelectorAll('.calendar-filters input');
        filterInputs.forEach(input => {
            input.addEventListener('change', function() {
                console.log('Filter changed, updating calendar...');
                const filteredEvents = filterEvents(allEvents);
                calendar.removeAllEvents();
                calendar.addEventSource(filteredEvents);
            });
        });
    }
    
    // Настройка обработчиков событий
    function setupEventHandlers() {
        // Кнопка "Сегодня"
        document.getElementById('todayBtn')?.addEventListener('click', function() {
            calendar.today();
        });
        
        // Кнопка создания события
        document.getElementById('createEventBtn')?.addEventListener('click', function() {
            openCreateEventModal();
        });
        
        // Обработчики формы создания события
        setupCreateFormHandlers();
    }
    
    // Настройка обработчиков формы создания
    function setupCreateFormHandlers() {
        const timeOptions = document.querySelectorAll('input[name="time_option"]');
        const durationSelect = document.getElementById('eventDuration');
        const startTimeInput = document.getElementById('eventStartTime');
        
        // Переключение опций времени
        timeOptions.forEach(option => {
            option.addEventListener('change', function() {
                updateTimeOptions(this.value);
            });
        });
        
        // Обработка выбора продолжительности
        durationSelect?.addEventListener('change', function() {
            if (this.value === 'custom') {
                document.getElementById('customDuration').style.display = 'block';
            } else {
                document.getElementById('customDuration').style.display = 'none';
                updateTimePreview();
            }
        });
        
        // Обновление предпросмотра при изменении времени
        startTimeInput?.addEventListener('change', updateTimePreview);
        document.getElementById('eventCustomDuration')?.addEventListener('input', updateTimePreview);
        document.getElementById('eventStartDate')?.addEventListener('change', updateTimePreview);
        
        // Отправка формы
        document.getElementById('createEventForm')?.addEventListener('submit', function(e) {
            e.preventDefault();
            createCalendarEvent();
        });
    }
    
    // Обновление опций времени
    function updateTimeOptions(selectedOption) {
        const timeOptions = document.getElementById('timeOptions');
        
        switch(selectedOption) {
            case 'all_day':
                timeOptions.style.display = 'none';
                break;
            case 'no_time':
                timeOptions.style.display = 'none';
                break;
            case 'with_time':
                timeOptions.style.display = 'block';
                break;
        }
        
        updateTimePreview();
    }
    
    // Обновление предпросмотра времени
    function updateTimePreview() {
        const preview = document.getElementById('previewText');
        const selectedOption = document.querySelector('input[name="time_option"]:checked')?.value || 'all_day';
        const startDate = document.getElementById('eventStartDate')?.value;
        
        if (!preview || !startDate) return;
        
        let previewText = '';
        
        switch(selectedOption) {
            case 'all_day':
                previewText = `📅 Событие на весь день: ${formatDate(startDate)}`;
                break;
            case 'no_time':
                previewText = `⏳ Событие без указания времени: ${formatDate(startDate)}`;
                break;
            case 'with_time':
                const startTime = document.getElementById('eventStartTime')?.value;
                const duration = getDurationInMinutes();
                
                if (startTime) {
                    const endTime = calculateEndTime(startTime, duration);
                    previewText = `⏰ ${formatDate(startDate)} ${startTime} - ${endTime} (${duration} мин.)`;
                } else {
                    previewText = '⏰ Укажите время начала';
                }
                break;
        }
        
        preview.textContent = previewText;
    }
    
    // Расчет времени окончания
    function calculateEndTime(startTime, durationMinutes) {
        if (!startTime) return '';
        
        const [hours, minutes] = startTime.split(':').map(Number);
        const startDate = new Date();
        startDate.setHours(hours, minutes, 0, 0);
        
        const endDate = new Date(startDate.getTime() + durationMinutes * 60000);
        return endDate.toTimeString().slice(0, 5);
    }
    
    // Получение продолжительности в минутах
    function getDurationInMinutes() {
        const durationSelect = document.getElementById('eventDuration');
        if (!durationSelect) return 60;
        
        if (durationSelect.value === 'custom') {
            return parseInt(document.getElementById('eventCustomDuration')?.value) || 60;
        }
        return parseInt(durationSelect.value) || 60;
    }
    
    // Форматирование даты
    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });
    }
    
    // Открытие модального окна создания события
    function openCreateEventModal(dateStr = null) {
        if (dateStr) {
            document.getElementById('eventStartDate').value = dateStr;
        }
        
        // Сброс формы
        document.getElementById('createEventForm').reset();
        document.getElementById('timeOptions').style.display = 'none';
        document.getElementById('customDuration').style.display = 'none';
        
        // Установка сегодняшней даты по умолчанию
        if (!dateStr) {
            const today = new Date().toISOString().split('T')[0];
            document.getElementById('eventStartDate').value = today;
        }
        
        // Установка времени по умолчанию (следующий полный час)
        const now = new Date();
        const nextHour = new Date(now.getTime() + 60 * 60000);
        const timeString = nextHour.toTimeString().slice(0, 5);
        document.getElementById('eventStartTime').value = timeString;
        
        updateTimePreview();
        document.getElementById('createEventModal').style.display = 'block';
    }
    
    // Закрытие модального окна создания
    window.closeCreateModal = function() {
        document.getElementById('createEventModal').style.display = 'none';
    }
    
    // Создание события календаря
    function createCalendarEvent() {
        const formData = new FormData(document.getElementById('createEventForm'));
        const selectedOption = document.querySelector('input[name="time_option"]:checked').value;
        
        const eventData = {
            title: formData.get('title'),
            description: formData.get('description'),
            start_date: formData.get('start_date'),
            event_type: formData.get('event_type'),
            color: formData.get('color')
        };
        
        // Настройка параметров времени
        switch(selectedOption) {
            case 'all_day':
                eventData.all_day = true;
                break;
            case 'no_time':
                eventData.all_day = false;
                eventData.start_time = null;
                break;
            case 'with_time':
                eventData.all_day = false;
                eventData.start_time = formData.get('start_time');
                eventData.duration_minutes = getDurationInMinutes();
                break;
        }
        
        console.log('Creating event:', eventData);
        
        fetch('/api/calendar/event', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(eventData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeCreateModal();
                calendar.refetchEvents(); // Перезагружаем события
                showNotification('Событие успешно создано!', 'success');
            } else {
                showNotification('Ошибка при создании события: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Ошибка при создании события', 'error');
        });
    }
    
    // Показать детали события
    function showEventDetails(event) {
        const props = event.extendedProps;
        const isMilestone = props.event_type === 'milestone';
        const isTask = props.event_type === 'task';
        const isCustom = props.event_type === 'custom' || props.source === 'custom';
        
        document.getElementById('modalEventTitle').textContent = event.title;
        document.getElementById('modalProjectName').textContent = props.project_name || 'Мое событие';
        document.getElementById('modalEventDescription').textContent = props.description || 'Описание отсутствует';
        
        // Настройка типа события
        let eventTypeText = '';
        if (isMilestone) {
            eventTypeText = '⭐ Веха проекта';
        } else if (isTask) {
            eventTypeText = props.type === 'project_task' ? '📋 Задача проекта' : '✅ Персональная задача';
        } else if (isCustom) {
            eventTypeText = '📅 Мое событие';
        }
        document.getElementById('modalEventType').textContent = eventTypeText;
        
        // Настройка статуса (только для задач)
        const statusRow = document.getElementById('modalStatusRow');
        if (isTask) {
            statusRow.style.display = 'block';
            document.getElementById('modalEventStatus').textContent = getStatusText(props.status);
        } else {
            statusRow.style.display = 'none';
        }
        
        // Настройка дат
        let datesText = '';
        if (isMilestone || event.allDay) {
            datesText = event.startStr;
        } else {
            datesText = `${event.startStr} - ${event.endStr}`;
            if (props.duration) {
                datesText += ` (${props.duration} дн.)`;
            }
        }
        document.getElementById('modalEventDates').textContent = datesText;
        
        // Настройка кнопки перехода
        const goToEventBtn = document.getElementById('goToEventBtn');
        const editEventBtn = document.getElementById('editEventBtn');
        const deleteEventBtn = document.getElementById('deleteEventBtn');
        
        if (isTask && props.project_id) {
            goToEventBtn.style.display = 'inline-block';
            goToEventBtn.textContent = 'Перейти к задаче';
            goToEventBtn.onclick = function() {
                if (props.type === 'project_task') {
                    window.location.href = `/project/${props.project_id}/kanban`;
                } else {
                    window.location.href = '/my-tasks';
                }
            };
            editEventBtn.style.display = 'none';
            deleteEventBtn.style.display = 'none';
        } else if (isMilestone && props.project_id) {
            goToEventBtn.style.display = 'inline-block';
            goToEventBtn.textContent = 'Перейти к проекту';
            goToEventBtn.onclick = function() {
                window.location.href = `/project/${props.project_id}/gantt`;
            };
            editEventBtn.style.display = 'none';
            deleteEventBtn.style.display = 'none';
        } else if (isCustom) {
            goToEventBtn.style.display = 'none';
            editEventBtn.style.display = 'inline-block';
            deleteEventBtn.style.display = 'inline-block';
            
            // TODO: Реализовать редактирование и удаление кастомных событий
            editEventBtn.onclick = function() {
                showNotification('Редактирование событий будет реализовано в будущем', 'info');
            };
            
            // В функции showEventDetails замените блок удаления:
            deleteEventBtn.onclick = function() {
                if (confirm('Вы уверены, что хотите удалить это событие?')) {
                    deleteCalendarEvent(event.id);
                }
            };

            // Добавьте функцию удаления события
            function deleteCalendarEvent(eventId) {
                console.log('Deleting event:', eventId);
                
                fetch(`/api/calendar/event/${eventId}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        closeModal();
                        calendar.refetchEvents();
                        showNotification('Событие успешно удалено!', 'success');
                    } else {
                        showNotification('Ошибка при удалении: ' + data.error, 'error');
                    }
                })
                .catch(error => {
                    console.error('Error deleting event:', error);
                    showNotification('Ошибка при удалении события', 'error');
                });
            }
        } else {
            goToEventBtn.style.display = 'none';
            editEventBtn.style.display = 'none';
            deleteEventBtn.style.display = 'none';
        }
        
        document.getElementById('eventModal').style.display = 'block';
    }
    
    // Получить текст статуса
    function getStatusText(status) {
        const statusMap = {
            'planned': 'Запланировано',
            'in_progress': 'В работе',
            'completed': 'Завершено'
        };
        return statusMap[status] || status;
    }
    
    // Закрыть модальное окно
    window.closeModal = function() {
        document.getElementById('eventModal').style.display = 'none';
    }
    
    // Закрытие модального окна при клике вне его
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                if (this.id === 'createEventModal') {
                    closeCreateModal();
                } else {
                    closeModal();
                }
            }
        });
    });
    
    // Закрытие по крестику для модального окна события
    document.querySelector('#eventModal .close')?.addEventListener('click', closeModal);
    
    // Показать уведомление
    function showNotification(message, type) {
        // Простая реализация уведомлений
        alert(`${type === 'success' ? '✅' : '❌'} ${message}`);
    }
    
    // Получить текст статуса
    function getStatusText(status) {
        const statusMap = {
            'planned': 'Запланировано',
            'in_progress': 'В работе', 
            'completed': 'Завершено'
        };
        return statusMap[status] || status;
    }

    // Инициализация
    initCalendar();
}); // <-- ЗАКРЫВАЮЩАЯ СКОБКА ДЛЯ DOMContentLoaded
