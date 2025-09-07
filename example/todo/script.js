document.addEventListener('DOMContentLoaded', () => {
    const todoInput = document.getElementById('todo-input');
    const addButton = document.getElementById('add-button');
    const todoList = document.getElementById('todo-list');

    // ローカルストレージからタスクを読み込む
    const loadTasks = () => {
        const tasks = JSON.parse(localStorage.getItem('todos')) || [];
        tasks.forEach(task => createTaskElement(task.text, task.completed));
    };

    // タスクをローカルストレージに保存する
    const saveTasks = () => {
        const tasks = [];
        todoList.querySelectorAll('.todo-item').forEach(item => {
            tasks.push({
                text: item.querySelector('span').textContent,
                completed: item.classList.contains('completed')
            });
        });
        localStorage.setItem('todos', JSON.stringify(tasks));
    };

    // タスク要素を作成する
    const createTaskElement = (taskText, isCompleted = false) => {
        const li = document.createElement('li');
        li.classList.add('todo-item');
        if (isCompleted) {
            li.classList.add('completed');
        }

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = isCompleted;
        checkbox.addEventListener('change', () => {
            li.classList.toggle('completed');
            saveTasks();
        });

        const span = document.createElement('span');
        span.textContent = taskText;

        const deleteButton = document.createElement('button');
        deleteButton.textContent = '削除';
        deleteButton.classList.add('delete-button');
        deleteButton.addEventListener('click', () => {
            li.remove();
            saveTasks();
        });

        li.appendChild(checkbox);
        li.appendChild(span);
        li.appendChild(deleteButton);
        todoList.appendChild(li);
    };

    // タスクを追加する
    const addTask = () => {
        const taskText = todoInput.value.trim();
        if (taskText === '') {
            alert('タスクを入力してください。');
            return;
        }
        createTaskElement(taskText);
        saveTasks();
        todoInput.value = '';
        todoInput.focus();
    };

    // イベントリスナーを設定
    addButton.addEventListener('click', addTask);
    todoInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            addTask();
        }
    });

    // 初期タスクを読み込む
    loadTasks();
});
