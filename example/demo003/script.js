document.addEventListener('DOMContentLoaded', () => {
  const todoInput = document.getElementById('todo-input');
  const addButton = document.getElementById('add-button');
  const todoList = document.getElementById('todo-list');

  // ローカルストレージからTODOを読み込む
  const loadTodos = () => {
    const todos = JSON.parse(localStorage.getItem('todos')) || [];
    todos.forEach(todo => {
      addTodoToList(todo.text, todo.completed);
    });
  };

  // ローカルストレージにTODOを保存する
  const saveTodos = () => {
    const todos = [];
    todoList.querySelectorAll('li').forEach(item => {
      todos.push({
        text: item.querySelector('span').textContent,
        completed: item.classList.contains('completed')
      });
    });
    localStorage.setItem('todos', JSON.stringify(todos));
  };

  // TODOリストに新しいアイテムを追加する
  const addTodoToList = (text, completed = false) => {
    if (!text) return;

    const li = document.createElement('li');
    if (completed) {
      li.classList.add('completed');
    }

    const span = document.createElement('span');
    span.textContent = text;
    span.addEventListener('click', () => {
      li.classList.toggle('completed');
      saveTodos();
    });

    const deleteButton = document.createElement('button');
    deleteButton.textContent = '削除';
    deleteButton.classList.add('delete-button');
    deleteButton.addEventListener('click', () => {
      li.remove();
      saveTodos();
    });

    li.appendChild(span);
    li.appendChild(deleteButton);
    todoList.appendChild(li);
  };

  // 追加ボタンのクリックイベント
  addButton.addEventListener('click', () => {
    const text = todoInput.value.trim();
    if (text) {
      addTodoToList(text);
      saveTodos();
      todoInput.value = '';
      todoInput.focus();
    }
  });

  // EnterキーでTODOを追加
  todoInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      addButton.click();
    }
  });

  // 初期化
  loadTodos();
});