function showNotification(message, isError = false) {
    // Check if notification already exists
    let notification = document.querySelector('.notification');
    
    // If exists, remove it first
    if (notification) {
        notification.remove();
    }

    // Create new notification
    notification = document.createElement('div');
    notification.className = 'notification';
    if (isError) {
        notification.style.backgroundColor = '#e74c3c';
    }
    notification.textContent = message;
    document.body.appendChild(notification);

    // Show notification
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);

    // Hide and remove notification after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 500);
    }, 3000);
}