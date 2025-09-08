document.addEventListener('DOMContentLoaded', () => {
    const addForm = document.getElementById('add-form');
    const todoInput = document.getElementById('todo-input');
    const todoList = document.getElementById('todo-list');

    // ローカルストレージからTODOを読み込む
    const loadTodos = () => {
        const todos = JSON.parse(localStorage.getItem('todos')) || [];
        todos.forEach(todo => {
            addTodoToDOM(todo.text, todo.completed);
        });
    };

    // TODOをローカルストレージに保存する
    const saveTodos = () => {
        const todos = [];
        todoList.querySelectorAll('li').forEach(li => {
            todos.push({
                text: li.querySelector('span').textContent,
                completed: li.classList.contains('completed')
            });
        });
        localStorage.setItem('todos', JSON.stringify(todos));
    };

    // DOMにTODOアイテムを追加する
    const addTodoToDOM = (text, completed = false) => {
        const li = document.createElement('li');
        const span = document.createElement('span');
        const deleteButton = document.createElement('button');

        span.textContent = text;
        deleteButton.textContent = '削除';

        if (completed) {
            li.classList.add('completed');
        }

        li.appendChild(span);
        li.appendChild(deleteButton);
        todoList.appendChild(li);

        // クリックで完了状態を切り替え
        span.addEventListener('click', () => {
            li.classList.toggle('completed');
            saveTodos();
        });

        // 削除ボタンの処理
        deleteButton.addEventListener('click', () => {
            li.remove();
            saveTodos();
        });
    };

    // フォーム送信時の処理
    addForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const newTodoText = todoInput.value.trim();
        if (newTodoText) {
            addTodoToDOM(newTodoText);
            saveTodos();
            todoInput.value = '';
        }
    });

    // 初期読み込み
    loadTodos();
});
