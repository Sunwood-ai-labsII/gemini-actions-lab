<div align="center">

# Gemini Actions Lab

<a href="./README.md"><img src="https://img.shields.io/badge/English-Readme-blue?style=for-the-badge&logo=github&logoColor=white" alt="English" /></a>
<a href="./README.ja.md"><img src="https://img.shields.io/badge/日本語-Readme-red?style=for-the-badge&logo=github&logoColor=white" alt="日本語" /></a>

[![💬 Gemini CLI](https://github.com/Sunwood-ai-labsII/gemini-actions-lab/actions/workflows/gemini-cli.yml/badge.svg)](https://github.com/Sunwood-ai-labsII/gemini-actions-lab/actions/workflows/gemini-cli.yml)

![Image](https://github.com/user-attachments/assets/1e294058-a1e6-4b44-979d-f4c8f09cb8ae)

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

This repository includes the following GitHub Actions workflows:

### 📄 `gemini-cli-jp.yml`
- **Trigger**: Issue comments
- **Function**: Allows users to interact with a Gemini-powered CLI assistant by creating comments on issues (e.g., `@gemini-cli-jp /do-something`). The assistant can then perform actions on the repository based on the user's request.

###  triage `gemini-issue-automated-triage.yml`
- **Trigger**: Issue creation or edits
- **Function**: Automatically triages new or updated issues. It can add labels, assignees, or post comments based on the issue's content as determined by Gemini.

### 🕒 `gemini-issue-scheduled-triage.yml`
- **Trigger**: Scheduled cron job
- **Function**: Periodically scans open issues and performs triage tasks, such as identifying stale issues or suggesting priorities.

### 🔍 `gemini-pr-review.yml`
- **Trigger**: Pull request creation or updates
- **Function**: Automatically reviews pull requests. Gemini can provide feedback on code quality, suggest improvements, or identify potential issues.

### 🔄 `sync-to-report-gh.yml`
- **Trigger**: Push to the main branch
- **Function**: This is a legacy workflow from a previous template and is not actively used in this lab. It was designed to sync daily reports to a central repository.

---

## 📸 Screenshots & Examples

### 🤖 CLI Interaction Example
Create an issue and comment with `@gemini-cli /help` to see available commands:

```
@gemini-cli /help
```

The AI assistant will respond with available commands and usage examples.

### 🏗️ Workflow Architecture
```mermaid
graph TD
    A[GitHub Issue/PR] --> B[GitHub Actions Trigger]
    B --> C[Gemini CLI Workflow]
    C --> D[Gemini AI Processing]
    D --> E[Repository Actions]
    E --> F[Automated Response]

    G[Schedule/Cron] --> H[Automated Triage]
    H --> I[Issue Management]

    J[PR Created] --> K[PR Review Workflow]
    K --> L[Code Analysis]
    L --> M[Feedback & Suggestions]
```

### 💬 Example Interactions

**Code Review Request:**
```
@gemini-cli /review-pr
Please review this pull request and suggest improvements
```

**Issue Triage:**
```
@gemini-cli /triage
Analyze this issue and suggest appropriate labels and assignees
```

---

## 🛠️ Troubleshooting

### Common Issues

**❌ Workflow not triggering:**
- Check if GitHub Actions are enabled in repository settings
- Verify webhook delivery in repository settings
- Ensure the trigger conditions are met (e.g., `@gemini-cli` in comment)

**❌ Gemini API errors:**
- Verify `GEMINI_API_KEY` secret is configured
- Check API key permissions and quota
- Ensure the API key is valid and not expired

**❌ Permission errors:**
- Confirm the user has write permissions
- Check if the repository is private (affects trusted user detection)

### Getting Help
1. Check the [GitHub Issues](https://github.com/your-repo/issues) for similar problems
2. Create a new issue with detailed error logs
3. Include workflow run logs when reporting issues

---

## 🚀 Installation & Setup

### Prerequisites
- GitHub account with repository creation permissions
- Gemini API key from Google AI Studio
- Basic understanding of GitHub Actions

### Quick Start
1. **Fork this repository** to your GitHub account
2. **Configure GitHub Secrets** in your repository settings:
   - `GEMINI_API_KEY`: Your Gemini API key
   - `GITHUB_TOKEN`: (automatically provided)
3. **Copy workflow files** from `.github/workflows/` to your repository
4. **Customize workflows** according to your needs
5. **Test the setup** by creating an issue and commenting `@gemini-cli /help`

### Advanced Configuration
For additional features, configure these optional secrets:
- `APP_ID` and `APP_PRIVATE_KEY`: For GitHub App integration
- `GCP_WIF_PROVIDER` and related GCP variables: For Vertex AI usage

---

## 📁 Directory Structure

```
.
├── .github/
│   └── workflows/
│       ├── gemini-cli-jp.yml
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