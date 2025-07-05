document.querySelectorAll('.menu-link').forEach(link => {
  link.addEventListener('click', function (e) {
    e.preventDefault();

    document.querySelectorAll('.menu-link').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.form-section').forEach(el => el.style.display = 'none');

    this.classList.add('active');

    const targetId = this.getAttribute('data-target');
    document.getElementById(targetId).style.display = 'block';
  });
});

fetch('/api/get/user_data')
  .then(response => {
    if (!response.ok) {
      throw new Error('Ошибка загрузки данных');
    }
    return response.json();
  })
  .then(data => {
    updateUserData(data);
  })
  .catch(error => {
    console.error('Ошибка при получении данных:', error);
  });

const payButton = document.querySelector(".pay-button");

payButton.addEventListener("click", () => {
  const amountInput = document.getElementById("amount");
  const amount = parseInt(amountInput.value);

  if (isNaN(amount) || amount <= 0) {
    alert("Введите корректную сумму для пополнения.");
    return;
  }

  fetch("/api/deposit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      amount: amount
    })
  })
  .then(res => {
    if (!res.ok) throw new Error("Ошибка при отправке запроса.");
    return res.json();
  })
  .then(data => {
    return fetch("/api/get/user_data");
  })
  .then(res => res.json())
  .then(updateUserData)
  .catch(err => {
    console.error(err);
    alert("Произошла ошибка при пополнении.");
  });
});

function updateUserData(data) {
  const balanceElement = document.querySelector('.balance-text strong');
  balanceElement.textContent = `${data.balance} ₽`;

  const historyList = document.querySelector('#form-history ul');
  historyList.innerHTML = '';

  data.transactions.forEach(tx => {
    const li = document.createElement('li');
    const operation = tx.type === 'deposit' ? 'Пополнение' : 'Списание';
    li.textContent = `${tx.date} – ${operation} на ${tx.amount} ₽`;
    historyList.appendChild(li);
  });
}
