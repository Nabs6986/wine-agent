# Git & GitHub CLI Reference

Quick reference for common git and gh commands for solo development.

## Daily Workflow (Simple)

```bash
# Check what's changed
git status

# Stage and commit all changes
git add .
git commit -m "description of changes"

# Push to GitHub
git push
```

## Viewing Changes

```bash
# See uncommitted changes
git diff

# See what's staged for commit
git diff --staged

# See commit history
git log --oneline

# See history with what changed
git log --oneline --stat

# See changes in a specific commit
git show <commit-hash>

# See who changed what (blame)
git blame filename.py
```

## Undoing Things

```bash
# Undo last commit (keep changes staged)
git reset --soft HEAD~1

# Undo last commit (keep changes unstaged)
git reset HEAD~1

# Discard all uncommitted changes (DESTRUCTIVE)
git checkout -- .

# Discard changes to a specific file
git checkout -- filename.py

# Amend last commit message
git commit --amend -m "new message"

# Add forgotten files to last commit
git add forgotten_file.py
git commit --amend --no-edit
```

## Branches (Optional for Solo)

```bash
# Create and switch to new branch
git checkout -b feature/new-thing

# Switch branches
git checkout main

# List branches
git branch

# Delete a branch
git branch -d branch-name

# Merge branch into current branch
git merge feature/new-thing
```

## Remote Operations

```bash
# Pull latest changes
git pull

# Push to remote
git push

# Push new branch and set upstream
git push -u origin branch-name

# See remote info
git remote -v
```

## GitHub CLI (gh)

### Repository

```bash
# Open repo in browser
gh repo view --web

# Clone a repo
gh repo clone owner/repo

# Create new repo from current directory
gh repo create repo-name --public --source=. --push
```

### Pull Requests

```bash
# Create PR
gh pr create --title "Title" --body "Description"

# Create PR with auto-filled info
gh pr create --fill

# List PRs
gh pr list

# View PR in browser
gh pr view --web

# Checkout a PR locally
gh pr checkout 123

# Merge PR
gh pr merge --squash --delete-branch
```

### Issues

```bash
# Create issue
gh issue create --title "Bug" --body "Description"

# List issues
gh issue list

# View issue
gh issue view 123

# Close issue
gh issue close 123
```

### Viewing Status

```bash
# Auth status
gh auth status

# PR status for current branch
gh pr status

# View GitHub Actions runs
gh run list
gh run view
```

## .gitignore Patterns

```gitignore
# Environment and secrets
.env
*.env.local

# Python
__pycache__/
*.pyc
venv/
*.egg-info/

# Database
*.db
*.sqlite3

# IDE
.idea/
.vscode/

# OS
.DS_Store

# Testing
.pytest_cache/
.coverage
```

## Commit Message Conventions

```bash
# Format: type: description

git commit -m "feat: add new export format"
git commit -m "fix: correct score calculation"
git commit -m "docs: update README"
git commit -m "refactor: simplify search logic"
git commit -m "test: add calibration tests"
git commit -m "chore: update dependencies"
```

## Useful Aliases (Optional)

Add to `~/.gitconfig`:

```ini
[alias]
    s = status
    co = checkout
    br = branch
    ci = commit
    lg = log --oneline --graph
    last = log -1 HEAD
    undo = reset --soft HEAD~1
```

Then use: `git s`, `git lg`, `git undo`, etc.

## Quick Recovery Scenarios

### "I committed to wrong branch"

```bash
# Move last commit to new branch
git branch new-branch      # create branch at current commit
git reset --hard HEAD~1    # remove commit from current branch
git checkout new-branch    # switch to new branch
```

### "I need to see what Claude changed"

```bash
git diff                   # uncommitted changes
git diff HEAD~1            # changes in last commit
git log --oneline -5       # last 5 commits
```

### "I want to start fresh from GitHub"

```bash
git fetch origin
git reset --hard origin/main
```

### "I accidentally deleted a file"

```bash
git checkout -- deleted_file.py
```

## Typical Solo Session

```bash
# Start of session - get latest
git pull

# ... make changes with Claude Code ...

# End of session - save progress
git add .
git commit -m "feat: add wine comparison view"
git push
```
