document.addEventListener('DOMContentLoaded', () => {
    const todoInput = document.getElementById('todo-input');
    const addButton = document.getElementById('add-button');
    const todoList = document.getElementById('todo-list');

    // 追加ボタンのクリックイベント
    addButton.addEventListener('click', addTodo);

    // 入力欄でEnterキーを押したときのイベント
    todoInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            addTodo();
        }
    });

    // TODOを追加する関数
    function addTodo() {
        const todoText = todoInput.value.trim();
        if (todoText === '') {
            return; // 入力が空の場合は何もしない
        }

        const li = document.createElement('li');
        li.textContent = todoText;

        // 完了・未完了を切り替えるイベント
        li.addEventListener('click', () => {
            li.classList.toggle('completed');
        });

        // 削除ボタンを作成
        const deleteButton = document.createElement('button');
        deleteButton.textContent = '削除';
        deleteButton.classList.add('delete-button');
        deleteButton.addEventListener('click', (e) => {
            e.stopPropagation(); // 親要素へのイベント伝播を停止
            todoList.removeChild(li);
        });

        li.appendChild(deleteButton);
        todoList.appendChild(li);

        // 入力欄をクリア
        todoInput.value = '';
    }
});