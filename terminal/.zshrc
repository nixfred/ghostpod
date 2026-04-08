export TERM=xterm-256color
export PATH="$HOME/.local/bin:$PATH"
HISTSIZE=1000
SAVEHIST=0

source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

alias ls='ls --color=auto'
alias ll='ls -lah --color=auto'
alias grep='grep --color=auto'

eval "$(starship init zsh)"
