@gemini-cli ghコマンドを使用して、和モダンなサイコロアプリをSunwood-ai-labsII のリポジトリに作成して
https://github.com/Sunwood-ai-labsII/gemini-actions-lab
をテンプレートリポジトリにして作成して

HTMLでアプリを実際に作成して
READMEも刷新してね

下記のコードでpagesをactionsから有効にして
 
```
curl -L -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $(gh auth token)" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/$(gh api user --jq .login)/my-site/pages \
  -d '{"build_type":"workflow"}'
```
