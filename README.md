# Gemini Actions Lab

<div align="center">
  <img src="https://img.shields.io/badge/GitHub%20Actions-AI-blue?style=for-the-badge&logo=github-actions&logoColor=white" alt="GitHub Actions" />
  <img src="https://img.shields.io/badge/Gemini-AI-4285F4?style=for-the-badge&logo=google-gemini&logoColor=white" alt="Gemini" />
</div>

---

## 📖 Overview

This repository serves as a laboratory and showcase for integrating Google's Gemini AI with GitHub Actions. It demonstrates how to automate various repository management tasks using the power of generative AI.

### 🎯 Key Features
- **AI-Powered Automation**: Leverage Gemini to handle tasks like issue triage, pull request reviews, and more.
- **CLI-like Interaction**: Interact with the AI assistant directly from issue comments.
- **Extensible Workflows**: Easily adapt and customize the workflows for your own projects.

---

## 🤖 Workflows

This repository contains the following GitHub Actions workflows:

### 📄 `gemini-cli.yml`
- **Trigger**: Issue comments.
- **Function**: Allows users to interact with a Gemini-powered CLI assistant by creating comments on issues (e.g., `@gemini-cli /do-something`). The assistant can perform actions on the repository based on the user's request.

###  triage `gemini-issue-automated-triage.yml`
- **Trigger**: Issue creation or edits.
- **Function**: Automatically triages new or updated issues. It can add labels, assignees, or post comments based on the issue's content, as determined by Gemini.

### 🕒 `gemini-issue-scheduled-triage.yml`
- **Trigger**: Scheduled cron job.
- **Function**: Periodically scans through open issues and performs triage tasks, such as identifying stale issues or suggesting priorities.

### 🔍 `gemini-pr-review.yml`
- **Trigger**: Pull request creation or updates.
- **Function**: Automatically reviews pull requests. Gemini can provide feedback on code quality, suggest improvements, or identify potential issues.

### 🔄 `sync-to-report-gh.yml`
- **Trigger**: Pushes to the main branch.
- **Function**: This is a legacy workflow from a previous template and is not actively used in this lab. It was designed to sync daily reports to a central repository.

---

## 🚀 Usage

To use these workflows in your own repository, you can copy the workflow files from the `.github/workflows` directory and adapt them to your needs. You will need to configure the necessary secrets, such as your Gemini API key.

---

## 📁 Directory Structure

```
.
├── .github/
│   └── workflows/
│       ├── gemini-cli.yml
│       ├── gemini-issue-automated-triage.yml
│       ├── gemini-issue-scheduled-triage.yml
│       ├── gemini-pr-review.yml
│       └── sync-to-report-gh.yml
├── .gitignore
├── LICENSE
└── README.md
```

---

## 📝 License

This project is licensed under the terms of the [LICENSE](LICENSE) file.

---

© 2025 Sunwood-ai-labsII