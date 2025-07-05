
      document.addEventListener('DOMContentLoaded', async () => {
        try {
            const response = await fetch('/api/get/new_deployment_name');
            if (!response.ok) throw new Error('Ошибка при получении данных');

            const data = await response.json();
            document.getElementById('nameInput').value = data.deployment_name_new || '—';

        } catch (error) {
            console.error('Ошибка при загрузке данных:', error);
        }
      });

        
    const typeSelect = document.getElementById('typeSelect');
    const vaultSelect = document.getElementById('vaultSelect');
    const tarifSelect = document.getElementById('tarifSelect');
    const microserviceFields = document.getElementById('microserviceFields');
    const databaseFields = document.getElementById('databaseFields');
    const form = document.getElementById('serviceForm');
    const notification = document.getElementById('notification');
    const tarifSelectFields = document.getElementById('tarifSelectFields');

    typeSelect.addEventListener('change', () => {
      const selected = typeSelect.value;

      if (selected === 'microservice') {
        microserviceFields.classList.remove('hidden');
        databaseFields.classList.add('hidden');
        tarifSelectFields.classList.add('hidden');
      } else {
        microserviceFields.classList.add('hidden');
        databaseFields.classList.remove('hidden');
        tarifSelectFields.classList.remove('hidden');
      }
    });

    form.addEventListener('submit', async (e) => {
      event.preventDefault(); 

      const form = event.target;
      const type = document.getElementById('typeSelect').value;

      if (type === 'microservice') {
        const imageUrl = document.getElementById('imageInput').value.trim();
        const port = document.getElementById('portInput').value.trim();

        if (!imageUrl || !port) {
          if (!imageUrl) {
            showNotification('Заполните все поля', true);
            document.getElementById('imageInput').classList.add('error');
          } else {
            document.getElementById('imageInput').classList.remove('error');
          }
          if (!port) {
            showNotification('Заполните все поля', true);
            document.getElementById('portInput').classList.add('error');
          } else {
            document.getElementById('imageInput').classList.remove('error');
          }
          return;
        }

        const valid = /^((ghcr\.io|docker\.io)\/.+)$/.test(imageUrl);
        if (!valid) {
          showNotification('Неверный формат Docker-образа.', true);
          return;
        }

        try {
          const response = await fetch('/api/push_service', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageUrl, port: port, tarif: tarifSelect.value })
          });

          if (response.ok) {
            showNotification('Микросервис успешно отправлен!');
            form.reset();
            typeSelect.value = 'microservice';
            typeSelect.dispatchEvent(new Event('change'));
            window.location.href = "/dashboard";
          } else {
            const err = await response.text();
            showNotification('Ошибка: ' + err, true);
          }
        } catch (err) {
            console.log(err);
          showNotification('Ошибка соединения.', true);
        }
      } else {
        const db = document.getElementById('dbSelect').value;
        const tarifSelectDB = document.getElementById('tarifSelectDB').value;

        try {
          const data = { db_type: db.toLowerCase(), storage_size: "1Gi", tarif: tarifSelectDB };
          console.log(data);
       
          const response = await fetch('/api/create/database', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          });

          if (response.ok) {
            showNotification('База данных успешно выбрана!');
            form.reset();
            typeSelect.value = 'microservice';
            typeSelect.dispatchEvent(new Event('change'));
            window.location.href = "/dashboard";
          } else {
            const err = await response.text();
            showNotification('Ошибка: ' + err, true);
          }
        } catch (err) {
          showNotification('Ошибка соединения.', true);
        }
      }
    });