document.addEventListener('DOMContentLoaded', () => {
    const todoForm = document.getElementById('todo-form');
    const todoInput = document.getElementById('todo-input');
    const todoList = document.getElementById('todo-list');

    // ローカルストレージからTODOを読み込む
    let todos = JSON.parse(localStorage.getItem('todos')) || [];

    // TODOを保存する関数
    const saveTodos = () => {
        localStorage.setItem('todos', JSON.stringify(todos));
    };

    // TODOリストを描画する関数
    const renderTodos = () => {
        todoList.innerHTML = '';
        todos.forEach((todo, index) => {
            const li = document.createElement('li');
            li.className = todo.completed ? 'completed' : '';
            
            const span = document.createElement('span');
            span.className = 'todo-text';
            span.textContent = todo.text;
            span.addEventListener('click', () => toggleComplete(index));

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-btn';
            deleteBtn.textContent = '×';
            deleteBtn.addEventListener('click', () => deleteTodo(index));

            li.appendChild(span);
            li.appendChild(deleteBtn);
            todoList.appendChild(li);
        });
    };

    // TODOを追加する関数
    const addTodo = (text) => {
        if (text.trim() === '') return;
        todos.push({ text: text, completed: false });
        saveTodos();
        renderTodos();
    };

    // TODOの完了状態を切り替える関数
    const toggleComplete = (index) => {
        todos[index].completed = !todos[index].completed;
        saveTodos();
        renderTodos();
    };

    // TODOを削除する関数
    const deleteTodo = (index) => {
        todos.splice(index, 1);
        saveTodos();
        renderTodos();
    };

    // フォームの送信イベント
    todoForm.addEventListener('submit', (e) => {
        e.preventDefault();
        addTodo(todoInput.value);
        todoInput.value = '';
    });

    // 初期描画
    renderTodos();
});
