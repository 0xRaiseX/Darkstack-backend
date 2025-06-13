let allowSubmit = false;
setTimeout(() => { allowSubmit = true }, 3000);

// Функция показа уведомления
function showNotification(message, isError = false) {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.style.backgroundColor = isError ? '#f44336' : '#4CAF50';
    notification.style.display = 'block';

    // Делаем плавное появление
    setTimeout(() => {
        notification.style.opacity = '1';
    }, 10); // слегка задержка нужна, чтобы transition сработал

    // Плавное скрытие
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            notification.style.display = 'none';
        }, 500); // дожидаемся завершения transition
    }, 3000);
}

// Простая проверка email
function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

document.querySelector('.feedback-value-container').addEventListener('submit', async function(event) {
    event.preventDefault(); // Останавливает отправку формы

    if (!allowSubmit) {
        showNotification("Подожди немного!", true);
        return;
    }

    const name = document.getElementById('name-input').value.trim();
    const email = document.getElementById('email-input').value.trim();
    const data = document.getElementById('data-input').value.trim();

    if (!isValidEmail(email)) {
        showNotification("Пожалуйста, введите корректный email", true);
        return;
    }

    try {
        const response = await fetch("/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, name, data })
        });

        if (response.ok) {
            showNotification("Спасибо! Данные успешно отправлены!");
        } else {
            showNotification("Ошибка при отправке данных.", true);
        }
    } catch (err) {
        showNotification("Произошла ошибка при соединении.", true);
    }
});
