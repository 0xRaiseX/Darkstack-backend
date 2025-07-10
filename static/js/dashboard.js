document.addEventListener('DOMContentLoaded', () => {
    let servicesCache = {};

    const modalConfig = {
        edit: {
            title: field => field === 'deployment_name' ? 'Изменить имя' : 'Изменить IP/домен',
            content: (_, field, currentValue) => `
                <div id="modal-title" style="margin: 0 0 15px 0;font-family: AeonikMedium;font-size: 1.4rem;">${modalConfig.edit.title(field)}</div>
                <span id="close-modal" style="position: absolute; top: 10px; right: 10px; cursor: pointer; font-size: 20px;">✖</span>
                <input type="text" id="new-value-input" style="width: 100%; margin: 10px 0; padding: 8px; box-sizing: border-box;" placeholder="Текущее: ${currentValue}">
                <div style="color: #000; font-size:0.9rem; min-height: 20px;text-align:center;">${field === 'deployment_name' ? 'Пользовательский внутренний маршрут будет обновлён. Базовый адрес http://u-...-app/ останется активным.' : 'Чтобы подключить домен нужно:<br>1) Впишите домен в поле выше без протокола<br>2) Укажите в A-записе вашего домена наш IP'}</div>
                <div id="error-message" style="color: #dc3545; font-size: 14px; min-height: 20px; margin-bottom: 10px;"></div>
                <div style="display: flex; justify-content: center;">
                    <button id="save-value-btn" style="padding: 8px 16px; background: #000; color: white; border: none; border-radius: 10px; cursor: pointer;width: 100%;">Сохранить</button>
                </div>
            `,
            handler: async (deploymentName, field, newValue) => {
                const showValidationError = msg => {
                    const errorEl = document.getElementById('error-message');
                    if (errorEl) errorEl.textContent = msg;
                    return false;
                };

                // Проверка DNS-1035 для имени Kubernetes
                function isValidDNS1035Label(name) {
                    const regex = /^[a-z]([-a-z0-9]*[a-z0-9])?$/;
                    return name.length >= 1 && name.length <= 63 && regex.test(name);
                }

                // Простая проверка домена или IP-адреса
                function isValidDomain(value) {
                    const domainRegex = /^(?!:\/\/)([a-zA-Z0-9-_]+\.)+[a-zA-Z]{2,}$/;
                    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
                    return domainRegex.test(value) || ipRegex.test(value);
                }

                if (field === 'deployment_name') {
                    if (!isValidDNS1035Label(newValue)) {
                        return showValidationError('Имя должно начинаться с буквы, содержать только строчные буквы, цифры или дефисы, и быть не длиннее 63 символов.');
                    }

                    const serviceData = servicesCache[deploymentName];
                    if (!serviceData) {
                        showError('Данные сервиса не найдены. Обновите страницу.');
                        return false;
                    }
                    if (serviceData.status === 'waitToPay') {
                        showError('Сервис должен быть запущен');
                        return false;
                    }
                }

                if (field !== 'deployment_name') {
                    if (!isValidDomain(newValue)) {
                        return showValidationError('Введите корректное доменное имя или IP-адрес (например: example.com, my.site.io).');
                    }

                    const serviceData = servicesCache[deploymentName];
                    if (!serviceData) {
                        showError('Данные сервиса не найдены. Обновите страницу.');
                        return false;
                    }
                    if (serviceData.status === 'waitToPay') {
                        showError('Сервис должен быть запущен');
                        return false;
                    }
                }

                const apiEndpoint = field === 'deployment_name' ? '/api/change/deployment_name' : '/api/change/domain';
                const payload = field === 'deployment_name' 
                    ? { deployment_name: deploymentName, new_deployment_name: newValue }
                    : { deployment_name: deploymentName, new_domain: newValue };
                
                return await makeApiRequest(apiEndpoint, payload, `${field === 'deployment_name' ? 'Название успешно изменено' : 'Домен успешно изменен'}`);
            }
        },
        delete: {
            title: 'Подтверждение удаления',
            content: deploymentName => `
                <div id="modal-title" style="margin: 0 0 15px 0;font-family: AeonikMedium;font-size: 1.4rem;">${modalConfig.delete.title}</div>
                <span id="close-modal" style="position: absolute; top: 10px; right: 10px; cursor: pointer; font-size: 20px;">✖</span>
                <p style="font-size: 1rem; margin-bottom: 20px;text-align:center;">Вы точно хотите удалить сервис ${deploymentName}? Это действие отменить невозможно.</p>
                <div id="error-message" style="color: #dc3545; font-size: 14px; min-height: 20px; margin-bottom: 10px;"></div>
                <div style="display: flex; justify-content: space-between;">
                    <button id="cancel-delete-btn" style="padding: 8px 16px; background: #ccc; color: #000; border: none; border-radius: 10px; cursor: pointer; width: 48%;">Отмена</button>
                    <button id="confirm-delete-btn" style="padding: 8px 16px; background: #dc3545; color: white; border: none; border-radius: 10px; cursor: pointer; width: 48%;">Удалить</button>
                </div>
            `,
            handler: async deploymentName => {
                return await makeApiRequest('/api/delete_service', 
                    { deployment_name: deploymentName }, 
                    `Сервис "${deploymentName}" успешно удален`);
            }
        },
        info: {
            title: 'Информация о сервисе',
            content: (_, __, ___, serviceData) => 
            `
                <div id="modal-title" style="margin: 0 0 15px 0;font-size: 1.4rem;text-align:center;">${modalConfig.info.title}</div>
                <span id="close-modal" style="position: absolute; top: 10px; right: 10px; cursor: pointer; font-size: 20px;">✖</span>
                <div style="font-size: 0.95rem;">
                    <p>Имя: ${serviceData?.user_deployment_name || serviceData?.deployment_name || '—'}</p>
                    <p>Образ: ${serviceData?.image || '—'}</p>
                    <p>Порт: ${serviceData?.port || '—'}</p>
                    <p>Тариф: ${serviceData?.tarif || '—'}</p>
                    <p>Тип: ${serviceData?.type || '—'}</p>
                    <p>Домен: ${serviceData?.domain || '—'}</p>
                    <p>Домен 2: ${serviceData?.user_domain || '—'}</p>
                    <p>Внутренний маршрут: ${serviceData?.deployment_name ? "http://" + serviceData.deployment_name + "/" : "—"}</p>
                    <p>Внутренний маршрут 2: ${serviceData?.user_deployment_name ? "http://" + serviceData.user_deployment_name + "/" : "—"}</p>
                    <p>Цена: ${renderPrice(serviceData) || '—'}</p>
                    <p>Активное время: ${getUptime(serviceData.uptime_start) || '—'}</p>
                    <p>Время оплаты: ${serviceData?.lastTimePay || '—'}</p>
                    <p>Статус: ${serviceData?.status || '—'}</p>
                </div>
                <div id="error-message" style="color: #dc3545; font-size: 14px; min-height: 20px; margin-bottom: 10px;"></div>
                <div style="display: flex; justify-content: center;">
                    <button id="close-info-btn" style="padding: 8px 16px; background: #000; color: #fff; border: none; border-radius: 12px; cursor: pointer; width: 100%;">Закрыть</button>
                </div>
            `,
            handler: () => true
        },
        restart: {
            title: 'Подтверждение перезапуска',
            content: deploymentName => `
                <div id="modal-title" style="margin: 0 0 15px 0;font-family: AeonikMedium;font-size: 1.4rem;">${modalConfig.restart.title}</div>
                <span id="close-modal" style="position: absolute; top: 10px; right: 10px; cursor: pointer; font-size: 20px;">✖</span>
                <p style="font-size: 1rem; margin-bottom: 20px;text-align:center;">Вы точно хотите перезапустить сервис ${deploymentName}? Образ будет загружен заново. </p>
                <div id="error-message" style="color: #dc3545; font-size: 14px; min-height: 20px; margin-bottom: 10px;"></div>
                <div style="display: flex; justify-content: space-between;">
                    <button id="cancel-delete-btn" style="padding: 8px 16px; background: #ccc; color: #000; border: none; border-radius: 10px; cursor: pointer; width: 48%;">Отмена</button>
                    <button id="confirm-restart-btn" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 10px; cursor: pointer; width: 48%;">Перезапустить</button>
                </div>
            `,
            handler: async deploymentName => {
                return await makeApiRequest('/api/deployment/restart', 
                    { deployment_name: deploymentName }, 
                    `Сервис "${deploymentName}" успешно перезапущен`);
            }
        }
    };

    // Create single modal
    const modal = document.createElement('div');
    modal.id = 'modal';
    modal.style.cssText = `
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.5);
        z-index: 1000;
        align-items: center;
        justify-content: center;
    `;
    modal.innerHTML = '<div id="modal-content" style="background: #fff; padding: 20px; border-radius: 15px; width: 300px; position: relative;"></div>';
    document.body.appendChild(modal);

    // Create context menu
    const contextMenu = document.createElement('div');
    contextMenu.id = 'context-menu';
    contextMenu.style.cssText = `
        display: none;
        position: absolute;
        background: #fff;
        border: 1px solid #ccc;
        border-radius: 12px;
        z-index: 1001;
        min-width: 200px;
        background-color: #fff;
        border: 1px solid #000;
        padding: 30px, 1px, 30px, 1px;
    `;
    contextMenu.innerHTML = `
        <div class="context-menu-item" data-action="info" style="cursor: pointer; font-weight: 500; font-size: 0.9rem;margin-top:15px;">
            <div style="display:flex;height:20%;align-items:center">  
                <img src="/static/images/info.png" alt="" style="width:18px;height:auto; margin-right: 10px;">
                Информация
            </div>
        </div>
        <div class="context-menu-item" data-action="logs" style="padding: 10px; cursor: pointer; font-weight: 500; font-size: 0.9rem;">
            <div style="display:flex;height:20%;align-items:center">  
                <img src="/static/images/logs2.png" alt="" style="width:18px;height:auto; margin-right: 10px;">
                Логи
            </div>
        </div>
        <div class="context-menu-item" data-action="restart" style="padding: 10px; cursor: pointer; font-weight: 500; font-size: 0.9rem;">
            <div style="display:flex;height:20%;align-items:center">  
                <img src="/static/images/restart.png" alt="" style="width:18px;height:auto; margin-right: 10px;">
                Перезагрузить
            </div>
        </div>
        <div class="context-menu-item" data-action="delete" style="padding: 10px; cursor: pointer; font-weight: 500; font-size: 0.9rem;margin-bottom:15px;margin-top:15px;">
            <div style="display:flex;height:20%;align-items:center">  
                <img src="/static/images/delete.png" alt="" style="width:18px;height:auto; margin-right: 10px;">
                Удалить
            </div>
        </div>
    `;
    document.body.appendChild(contextMenu);

    let currentState = {
        deploymentName: null,
        field: null,
        modalType: null,
        serviceData: null
    };

    const showError = message => {
        document.getElementById('error-message').textContent = message;
    };

    const clearError = () => {
        const errorDiv = document.getElementById('error-message');
        if (errorDiv) errorDiv.textContent = '';
    };

    const closeModal = () => {
        modal.style.display = 'none';
        currentState = { deploymentName: null, field: null, modalType: null, serviceData: null };
        clearError();
    };

    const closeContextMenu = () => {
        contextMenu.style.display = 'none';
    };

    const makeApiRequest = async (endpoint, payload, successMessage) => {
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json();
                let message = 'Неизвестная ошибка';

                if (errorData.detail === "Domain already exists") {
                    message = 'Такой домен уже существует';
                } else if (errorData.detail === "Deployment name already exists") {
                    message = 'Такое имя уже существует';
                } else if (errorData.detail) {
                    message = errorData.detail;
                } else if (errorData.message) {
                    message = errorData.message;
                }

                // Генерируем ошибку с нужным сообщением
                throw new Error(message);
            }

            showNotification(successMessage);
            await fetchServices();
            closeModal();
            return true;

        } catch (error) {
            console.error('API Error:', error);
            showError(`Ошибка: ${error.message}`);
            return false;
        }
    };

    const updateTableValue = (deploymentName, field, newValue) => {
        const cell = document.querySelector(`td:has([data-deployment-name="${deploymentName}"])`);
        if (!cell) {
            console.warn(`Не найдена ячейка для deployment_name: ${deploymentName}`);
            return;
        }
        
        if (field === 'deployment_name') {
            const nameElement = cell.querySelector('.deployment-name');
            if (nameElement) {
                nameElement.textContent = newValue;
                document.querySelectorAll(`[data-deployment-name="${deploymentName}"]`)
                    .forEach(pencil => {
                        pencil.dataset.deploymentName = newValue;
                    });
            }
        } else if (field === 'domain') {
            const row = cell.closest('tr');
            const domainCell = row.cells[3];
            const domainElement = domainCell.querySelector('.domain');
            if (domainElement) domainElement.textContent = newValue;
        }
    };

    // Modal handling
    const showModal = (type, deploymentName, field, currentValue, serviceData) => {
        currentState = { deploymentName, field, modalType: type, serviceData };
        const modalContent = document.getElementById('modal-content');
        modalContent.innerHTML = modalConfig[type].content(deploymentName, field, currentValue, serviceData);
        modal.style.display = 'flex';
        clearError();

        // Add event listeners for modal buttons
        const saveButton = document.getElementById('save-value-btn');
        const cancelButton = document.getElementById('cancel-delete-btn');
        const confirmStopButton = document.getElementById('confirm-stop-btn');
        const confirmRestartButton = document.getElementById('confirm-restart-btn');
        const confirmDeleteButton = document.getElementById('confirm-delete-btn');
        const closeInfoButton = document.getElementById('close-info-btn');
        const closeButton = document.getElementById('close-modal');

        if (saveButton) {
            saveButton.addEventListener('click', async () => {
                const newValue = document.getElementById('new-value-input').value.trim();
                if (!newValue) {
                    showError('Введите значение');
                    return;
                }
                if (await modalConfig[type].handler(deploymentName, field, newValue)) {
                    updateTableValue(deploymentName, field, newValue);
                }
            });
        }

        if (cancelButton) {
            cancelButton.addEventListener('click', closeModal);
        }

        if (confirmStopButton) {
            confirmStopButton.addEventListener('click', () => modalConfig['stop'].handler(deploymentName));
        }

        if (confirmRestartButton) {
            confirmRestartButton.addEventListener('click', () => modalConfig['restart'].handler(deploymentName));
        }

        if (confirmDeleteButton) {
            confirmDeleteButton.addEventListener('click', () => modalConfig['delete'].handler(deploymentName));
        }

        if (closeInfoButton) {
            closeInfoButton.addEventListener('click', closeModal);
        }

        if (closeButton) {
            closeButton.addEventListener('click', closeModal);
        }
    };

    // Fetch service data by deployment name
    const getServiceData = async (deploymentName) => {
        try {
            const response = await fetch('/api/deployments/by-user');
            if (!response.ok) throw new Error(`Ошибка запроса: ${response.status}`);
            const services = await response.json();
            const service = services.find(service => service.deployment_name === deploymentName);
            if (!service) {
                throw new Error(`Сервис с именем ${deploymentName} не найден`);
            }
            return service;
        } catch (error) {
            console.error('Ошибка при получении данных сервиса:', error);
            showError('Ошибка загрузки данных сервиса');
            return null;
        }
    };

    // Event delegation
    document.addEventListener('click', async e => {
        // Handle modal clicks
        if (e.target === modal || e.target.id === 'close-modal') {
            closeModal();
        }

        // Handle context menu
        if (!contextMenu.contains(e.target) && !e.target.classList.contains('action-arrow')) {
            closeContextMenu();
        }

        // Handle edit pencil clicks
        if (e.target.classList.contains('edit-pencil')) {
            const { deploymentName, field } = e.target.dataset;
            if (!deploymentName || !field) {
                showError('Ошибка: сервис или поле не выбрано');
                return;
            }

            const currentValue = field === 'deployment_name'
                ? e.target.closest('td').querySelector('.deployment-name').textContent.trim()
                : e.target.closest('tr').cells[3].querySelector('.domain').textContent.trim();

            showModal('edit', deploymentName, field, currentValue);
        }

        const menuItem = e.target.closest('.context-menu-item');
        if (menuItem) {
            const { action } = menuItem.dataset;
            const deploymentName = contextMenu.dataset.deploymentName;

            if (action === 'info') {
                const serviceData = await getServiceData(deploymentName);
                if (serviceData) {
                    showModal('info', deploymentName, null, null, serviceData);
                }
            } else if (['delete'].includes(action)) {
                showModal(action, deploymentName);
            } else if (action === 'restart') {
                if (servicesCache[deploymentName].status !== "running") {
                    showNotification("Сервис не запущен", true);
                    return;
                }
                showModal(action, deploymentName);
            } else if (action === 'logs') {
                if (servicesCache[deploymentName].status !== "running") {
                    showNotification("Сервис не запущен", true);
                    return;
                }
                window.location.href = "/dashboard/logs?deployment_name=" + deploymentName;
            }

            closeContextMenu();
        }

        // Handle action arrows
        if (e.target.classList.contains('action-arrow')) {
            e.stopPropagation();
            const { deploymentName } = e.target.dataset;
            if (!deploymentName) {
                showError('Ошибка: имя сервиса не найдено');
                return;
            }

            contextMenu.style.display = 'block';
            contextMenu.style.left = '-9999px';
            contextMenu.style.top = '-9999px';

            const rect = e.target.getBoundingClientRect();
            const menuWidth = contextMenu.offsetWidth;
            const viewportWidth = window.innerWidth;
            let leftPosition = rect.right + window.scrollX;

            if (leftPosition + menuWidth > viewportWidth) {
                leftPosition = rect.left - menuWidth + window.scrollX;
            }

            contextMenu.style.left = `${Math.max(0, leftPosition)}px`;
            contextMenu.style.top = `${rect.top + window.scrollY}px`;
            contextMenu.dataset.deploymentName = deploymentName;
        }
    });

    // Handle input keyboard events
    document.addEventListener('keydown', e => {
        if (currentState.modalType === 'edit' && e.target.id === 'new-value-input') {
            if (e.key === 'Enter' && e.target.value.trim()) {
                e.preventDefault();
                document.getElementById('save-value-btn').click();
            } else if (e.key === 'Escape') {
                closeModal();
            }
        }
    });

    async function fetchUserData() {
        try {
        const response = await fetch('/api/get/user_data');

        if (!response.ok) {
            throw new Error('Ошибка при получении данных пользователя');
        }

        const data = await response.json();

        const emailElement = document.getElementById('user-email');
        const balance = document.getElementById('balance');

        if (emailElement && data.email) {
            emailElement.textContent = data.email;
        } else {
            console.warn('Элемент или email не найден');
        }

        if (balance && data.balance) {
            balance.textContent = data.balance+" ₽";
        } else {
            console.warn('Элемент или balance не найден');
        }

        } catch (error) {
            console.error('Произошла ошибка:', error);
        }
    }

    const tarifs = {
    mini: {
        hourPrice: 0.104,
        monthPrice: 75,
        CPU: 0.2,
        RAM: 256,
    },
    standart: {
        hourPrice: 0.15,
        monthPrice: 105,
        CPU: 0.5,
        RAM: 512,
    },
    hard: {
        hourPrice: 0.21,
        monthPrice: 150,
        CPU: 1,
        RAM: 1024
    },
    premium: {
        hourPrice: 0.42,
        monthPrice: 300,
        CPU: 2,
        RAM: 2048
    }
};

    const tarifs_db = {
    mini: {
        hourPrice: 0.25,
        monthPrice: 180,
        CPU: 1,
        RAM: 1024,
    },
    standart: {
        hourPrice: 0.42,
        monthPrice: 300,
        CPU: 2,
        RAM: 2048,
    },
    hard: {
        hourPrice: 0.81,
        monthPrice: 580,
        CPU: 4,
        RAM: 4096
    },
    premium: {
        hourPrice: 1.25,
        monthPrice: 900,
        CPU: 6,
        RAM: 6144
    }
};

function renderPrice(service) {
    if (service.tarif && tarifs[service.tarif] && service.type === "microservice") {
        const price = tarifs[service.tarif].hourPrice;
        return `${price} ₽/час`;
    }
    if (service.tarif && tarifs_db[service.tarif] && service.type === "database") {
        const price = tarifs_db[service.tarif].hourPrice;
        return `${price} ₽/час`;
    }
}

function getUptime(uptime_start) {
    const startTime = new Date(
        uptime_start.endsWith('Z') || uptime_start.includes('+')
            ? uptime_start
            : uptime_start + 'Z'
    );

    if (startTime.getFullYear() < 2025) {
        return;
    }

    const now = new Date();

    const diffMs = now.getTime() - startTime.getTime();
    const diffSec = Math.floor(diffMs / 1000);

    const days = Math.floor(diffSec / 86400);
    const hours = Math.floor((diffSec % 86400) / 3600);
    const minutes = Math.floor((diffSec % 3600) / 60);
    const seconds = diffSec % 60;

    if (diffSec <= 0) {
        return;
    }

    if (diffSec < 60) {
        return `${seconds}с`;
    } else if (diffSec < 3600) {
        return `${minutes}м`;
    } else if (diffSec < 86400) {
        return `${hours}ч ${minutes}м`;
    } else {
        return `${days}д ${hours}ч`;
    }
}

function updateTotalResources(cpu, ram, storage) {
    document.querySelector('.top-view-block:nth-child(1) div:nth-child(2)').textContent = `${cpu.toFixed(1)}`;
    document.querySelector('.top-view-block:nth-child(2) div:nth-child(2)').textContent = `${ram.toFixed(0)} Mb`;
    document.querySelector('.top-view-block:nth-child(3) div:nth-child(2)').textContent = `${storage || 0} Gb`;
}

function getServiceType(type) {
    if (type === 'microservice') {
        return "Микросервис"
    } else if (type === 'database') {
        return "База данных"
    }
}

 async function fetchServices() {
    servicesCache = {};

    try {
        const response = await fetch('/api/deployments/by-user');
        if (!response.ok) throw new Error(`Ошибка запроса: ${response.status}`);

        const services = await response.json();

        const tbody = document.getElementById('service-table-body');
        const tableWrapper = document.querySelector('.table-wrapper');
        const emptyState = document.getElementById('empty-services');

        tbody.innerHTML = '';

        if (services.length === 0) {
            tableWrapper.style.display = 'none';
            emptyState.style.display = 'flex';
            updateTotalResources(0, 0, 0);
            return;
        } else {
            tableWrapper.style.display = 'block';
            emptyState.style.display = 'none';
        }

        let totalCPU = 0;
        let totalRAM = 0;
        let totalStorage = 0;

        function updateResoucesValue(service) {
            if (!service.tarif) return;

            const tarifKey = service.tarif.toLowerCase();
            let tarif;
            if (service.type === "microservice") {
                tarif = tarifs[tarifKey];
            } else if (service.type === "database") {
                tarif = tarifs_db[tarifKey];
            } else {
                console.log("ERROR Service type not found");
                return;
            }
           

            if (!tarif) return;

            totalCPU += tarif.CPU;
            totalRAM += tarif.RAM;

            // if (service.storage) {
            //     totalStorage += service.storage;
            // } else {
            //     // Или можно брать примерное значение, если есть
            //     // totalStorage += some_default_value;
            // }
        }

        function getDatabaseConnectionUri({
  type,      // 'mongodb', 'postgresql', 'mysql', etc.
  host,      // 'localhost' or IP/domain
  port,      // e.g. 27017, 5432, 3306
  user = 'user',      // username
  password = "123456",  // password
  database = "main",  // database name
  options = '' // optional params, e.g. '?authSource=admin'
}) {
  switch (type.toLowerCase()) {
    case 'mongodb':
      return `mongodb://${user}:${password}@${host}${options}`;
    case 'postgresql':
    case 'postgres':
      return `postgresql://${user}:${password}@${host}${options}`;
    case 'mysql':
      return `mysql://${user}:${password}@${host}}${options}`;
    case 'mariadb':
      return `mariadb://${user}:${password}@${host}${options}`;
    case 'redis':
      return `redis://${user}:${password}@${host}${options}`;
    case 'mssql':
    case 'sqlserver':
      return `mssql://${user}:${password}@${host}${options}`;
    case 'oracle':
      return `oracle://${user}:${password}@${host}${options}`;
    default:
      throw new Error(`Unsupported database type: ${type}`);
  }
}

        let hasRequestedService = false;

        services.forEach(service => {
            if (!service.deployment_name) {
                console.warn('Отсутствует deployment_name в данных:', service);
                return;
            }

            servicesCache[service.deployment_name] = service;

            const status = service.status || '—';
            const statusClass = {
                wantToPay: 'status-requested',
                requested: 'status-requested',
                pending: 'status-pending',
                running: 'status-running',
                error: 'status-error'
            }[status] || '';

            if (status === 'running') {
                updateResoucesValue(service);
            }

            if (status === 'requested') {
                hasRequestedService = true;
            }

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <span class="deployment-name">${service.user_deployment_name || service.deployment_name || '—'}</span>
                    ${service.order === 1 ? '<span class="main-badge">main</span>' : ''}
                    ${service.type === "database" ? '<span class="database-badge">database</span>' : ''}
                    <span class="edit-pencil" data-deployment-name="${service.deployment_name}" data-field="deployment_name" style="cursor: pointer; margin-left: 5px;">✏️</span>
                </td>
                <td id="tarif-th">${service.tarif || '—'}</td>
                <td id="type-th">${getServiceType(service.type) || '1'}</td>
                <td>
                    <div style="display:flex;flex-direction:column;">
                        ${service.type === 'microservice' ? `
                            <div>
                                <span class="domain">https://${service.user_domain || service.domain || '—'}/</span>
                                <span class="edit-pencil" data-deployment-name="${service.deployment_name}" data-field="domain" style="cursor: pointer; margin-left: 5px;">✏️</span>
                            </div>
                            <div>
                                <span style="font-size:0.8rem;">
                                    ${service.user_service_name 
                                        ? "http://" + service.user_service_name + "/" 
                                        : (service.deployment_name 
                                            ? "http://" + service.deployment_name + "/" 
                                            : "—")}
                                </span>
                            </div>
                        ` : service.type === 'database' ? `
                            <div style="display:flex;align-items:center;">
                                <span class="domain copy-target">${
                                    getDatabaseConnectionUri({
                                        type: 'mongodb',
                                        host: 'localhost',
                                        port: 27017,
                                        user: 'admin',
                                        password: 'secret',
                                        database: 'mydb',
                                        options: ''
                                        }) || '—'
                                }</span>
                                <img class="copy-button" src="/static/images/copy.png" alt="Copy" style="height:18px;cursor:pointer;margin-left: 5px;">
                            </div>
                        ` : ''}
                    </div>
                </td>
                <td id="price-th">${renderPrice(service) || '—'}</td>
                <td>${getUptime(service.uptime_start) || '—'}</td>
                <td><span class="status ${statusClass}">${status}</span></td>
                <td><span class="action-arrow" data-deployment-name="${service.deployment_name}" style="cursor: pointer;">→</span></td>
            `;
            tbody.appendChild(row);
        });

        updateTotalResources(totalCPU, totalRAM, totalStorage);

        if (hasRequestedService) {
            setTimeout(() => {
                fetchServices();
            }, 3000);
        }

    } catch (error) {
        console.error('Не удалось загрузить данные:', error);
        showError('Ошибка загрузки данных сервисов');
    }
}
    // Initialize
    fetchUserData();
    fetchServices();
});


document.addEventListener('DOMContentLoaded', () => {
    document.body.addEventListener('click', (e) => {
      if (e.target.classList.contains('copy-button')) {
        const span = e.target.closest('td')?.querySelector('.copy-target');
        if (span) {
          const text = span.textContent.trim();
          navigator.clipboard.writeText(text)
            .then(() => {
              showNotification("Скопировано!")
            })
            .catch(err => {
              console.error('Ошибка копирования:', err);
            });
        }
      }
    });
  });