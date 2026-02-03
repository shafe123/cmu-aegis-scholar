#!/bin/bash
# Add container SSH key path to SSH agent if not already present
export SSH_KEY_PATH="/home/vscode/.ssh/personal"
if [ -f "$SSH_KEY_PATH" ] && ! ssh-add -l | grep -q "$(ssh-keygen -lf $SSH_KEY_PATH.pub 2>/dev/null | awk '{print $2}')"; then
  ssh-add "$SSH_KEY_PATH" 2>/dev/null || true
fi
