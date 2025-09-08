document.addEventListener('DOMContentLoaded', () => {
    const todoInput = document.getElementById('todo-input');
    const addButton = document.getElementById('add-button');
    const todoList = document.getElementById('todo-list');

    let todos = JSON.parse(localStorage.getItem('todos')) || [];

    const saveTodos = () => {
        localStorage.setItem('todos', JSON.stringify(todos));
    };

    const renderTodos = () => {
        todoList.innerHTML = '';
        todos.forEach((todo, index) => {
            const li = document.createElement('li');
            li.textContent = todo.text;
            if (todo.completed) {
                li.classList.add('completed');
            }

            li.addEventListener('click', () => {
                todos[index].completed = !todos[index].completed;
                saveTodos();
                renderTodos();
            });

            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete';
            deleteButton.classList.add('delete-button');
            deleteButton.addEventListener('click', (e) => {
                e.stopPropagation();
                todos.splice(index, 1);
                saveTodos();
                renderTodos();
            });

            li.appendChild(deleteButton);
            todoList.appendChild(li);
        });
    };

    addButton.addEventListener('click', () => {
        const text = todoInput.value.trim();
        if (text !== '') {
            todos.push({ text, completed: false });
            todoInput.value = '';
            saveTodos();
            renderTodos();
        }
    });

    todoInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            addButton.click();
        }
    });

    renderTodos();
});
