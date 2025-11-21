// Функция для переключения видимости бокового меню
function toggleSidebar(sidebarId) {
    const sidebar = document.getElementById(sidebarId);
    const mainContent = document.querySelector('.main-content');
    const showSidebarBtn = document.getElementById(`show${sidebarId.charAt(0).toUpperCase() + sidebarId.slice(1)}Btn`);
    
    if (sidebar.classList.contains('sidebar-collapsed')) {
        // Показываем меню
        sidebar.classList.remove('sidebar-collapsed');
        mainContent.classList.remove('content-expanded');
        
        // Сохраняем состояние
        localStorage.setItem(sidebarId, 'expanded');
        
        // Скрываем кнопку показа
        if (showSidebarBtn) {
            showSidebarBtn.style.display = 'none';
        }
    } else {
        // Скрываем меню
        sidebar.classList.add('sidebar-collapsed');
        mainContent.classList.add('content-expanded');
        
        // Сохраняем состояние
        localStorage.setItem(sidebarId, 'collapsed');
        
        // Показываем кнопку показа
        if (showSidebarBtn) {
            showSidebarBtn.style.display = 'block';
        }
    }
}

// Восстановление состояния меню при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем все возможные меню
    const sidebars = ['mainSidebar', 'projectSidebar'];
    
    sidebars.forEach(sidebarId => {
        const sidebar = document.getElementById(sidebarId);
        const mainContent = document.querySelector('.main-content');
        const showSidebarBtn = document.getElementById(`show${sidebarId.charAt(0).toUpperCase() + sidebarId.slice(1)}Btn`);
        
        if (sidebar) {
            const savedState = localStorage.getItem(sidebarId);
            
            if (savedState === 'collapsed') {
                sidebar.classList.add('sidebar-collapsed');
                mainContent.classList.add('content-expanded');
                if (showSidebarBtn) {
                    showSidebarBtn.style.display = 'block';
                }
            } else {
                // По умолчанию меню развернуто
                if (showSidebarBtn) {
                    showSidebarBtn.style.display = 'none';
                }
            }
        }
    });
});

// Закрытие меню при клике вне его (для мобильных устройств)
document.addEventListener('click', function(event) {
    const sidebars = document.querySelectorAll('.sidebar:not(.sidebar-collapsed)');
    const showButtons = document.querySelectorAll('.show-sidebar-btn');
    
    sidebars.forEach(sidebar => {
        const sidebarId = sidebar.id;
        const showSidebarBtn = document.getElementById(`show${sidebarId.charAt(0).toUpperCase() + sidebarId.slice(1)}Btn`);
        
        if (!sidebar.contains(event.target) && 
            !(showSidebarBtn && showSidebarBtn.contains(event.target)) &&
            window.innerWidth <= 768) {
            toggleSidebar(sidebarId);
        }
    });
});