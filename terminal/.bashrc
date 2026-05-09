# ghostpod session shell — runs as user `pi` inside an ephemeral container
[ -z "$PS1" ] && return

export TERM=xterm-256color
export PATH="$HOME/.local/bin:$PATH"
export HISTSIZE=1000
export HISTFILESIZE=0   # ephemeral session — no history persists across containers

# Coloured prompt
PS1='\[\e[1;32m\]\u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]\$ '

# Common aliases
alias ls='ls --color=auto'
alias ll='ls -lah --color=auto'
alias la='ls -A --color=auto'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

# Start tmux automatically on interactive shells unless already inside one
if command -v tmux >/dev/null && [ -z "$TMUX" ] && [ -n "$PS1" ]; then
    :  # left as opt-in — uncomment to auto-attach: tmux attach -t main || tmux new -s main
fi
