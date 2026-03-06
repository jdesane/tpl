#!/bin/bash

# ── TPL Collective Auto-Deploy ──
# Saves, commits, and pushes to GitHub → Vercel auto-deploys

cd ~/Desktop/tpl

# Check if there's anything to deploy
if [[ -z $(git status --porcelain) ]]; then
  echo "✦ Nothing to deploy — no changes detected."
  exit 0
fi

# Show what's being deployed
echo ""
echo "✦ TPL Collective — Deploying..."
echo "──────────────────────────────"
git status --short
echo "──────────────────────────────"

# Ask for a commit message (or use a default)
echo ""
read -p "Commit message (press Enter for 'site update'): " MSG
MSG=${MSG:-"site update"}

# Add, commit, push
git add .
git commit -m "$MSG"
git push

echo ""
echo "✦ Deployed! tplcollective.ai will be live in ~30 seconds."
echo ""
