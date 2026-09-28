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

# Durable shells: `keep`
#
# This container is disposable by design — ttyd runs --once and the
# orchestrator deletes the container the moment the WebSocket drops. On a
# phone that fires constantly: iOS suspends a backgrounded tab, which closes
# the socket, so switching apps loses the session. No browser setting changes
# this; iOS gives a page no way to stay awake.
#
# So don't keep the work here. Keep it in tmux on a real host: the container
# still dies, your shell doesn't, and you reattach where you left off.
#
#   keep              attach (or create) session "phone" on gus
#   keep vic          same, on vic
#   keep vic build    session "build" on vic
keep() {
    local host=${1:-gus} name=${2:-phone}
    ssh -t "$host" "tmux new-session -A -s $(printf '%q' "$name")"
}

# Worth saying out loud, since the tab you read it in may not survive.
if [ -n "$PS1" ]; then
    printf '\033[2mtip: `keep` gives you a tmux shell on gus that survives this tab dying\033[0m\n'
fi
