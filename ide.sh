#!/bin/bash

# 1. Split right (ESC + \ + ghostty + action)
printf "\033]1337;GhosttyAction=new_split:right\007"
# Give it a tiny moment to initialize the pane before typing
sleep 0.2
printf "\033]1337;GhosttyAction=write_screen_text:nvim .\r\007"

# 2. Go back left
printf "\033]1337;GhosttyAction=goto_split:left\007"
sleep 0.1

# 3. Split down
printf "\033]1337;GhosttyAction=new_split:down\007"
sleep 0.1

# 4. Run Claude in the current (top-left) pane
claude code
