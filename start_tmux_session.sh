#!/bin/bash

tmux new-session -d -s nhk

tmux split-window -h
tmux split-window -v
tmux select-pane -t 0
tmux split-window -v

tmux send-keys -t nhk:0.1 'source ./env/bin/activate && python3 src/main.py' ENTER
# tmux send-keys -t nhk:0.1 'sudo tcpdump -i wlan0 port 12345' ENTER
tmux send-keys -t nhk:0.2 'ping 192.168.0.50' ENTER
tmux send-keys -t nhk:0.3 'sudo tcpdump -i wlan0 port 12346' ENTER