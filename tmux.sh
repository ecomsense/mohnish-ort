#!/bin/env sh

# Define the session name
sess="tmux-session"

# Check if payment is pending
if [ -f ~/no_payment.lock ]; then
  echo "**************************************************"
  echo "  ACCESS RESTRICTED: Payment Pending"
  echo "  Please contact the administrator to resume access."
  echo "**************************************************"
  exit 1
fi

# Check if the session exists
if tmux has-session -t "$sess" 2>/dev/null; then
  echo "Session $sess already exists. Attaching to it."
  tmux attach -t "$sess"
else
  # If the session doesn't exist, create it
  echo "updating"
  git reset --hard && git pull
  echo "Creating and attaching to session $sess."
  tmux new-session -d -s "$sess"
  tmux send-keys -t "$sess" "cd src" C-m
  tmux send-keys -t "$sess" "pwd" C-m
  tmux send-keys -t "$sess" "python3 main.py && tmux kill-session -t $sess" C-m
  tmux attach -t "$sess"
fi
