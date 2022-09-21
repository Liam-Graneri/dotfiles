### Basic Configuration ###

# Lines configured by zsh-newuser-install
HISTFILE=~/.histfile
HISTSIZE=1000
SAVEHIST=1000
unsetopt beep

# Enable autocomplete (& menu-style selection within suggestions)
autoload -U compinit
zstyle ':completion:*' menu select
zmodload zsh/complist
compinit
_comp_options+=(globdots)

# Vi navigation in tab-complete menu
bindkey -M menuselect 'h' vi-backward-char
bindkey -M menuselect 'k' vi-up-line-or-history
bindkey -M menuselect 'l' vi-forward-char
bindkey -M menuselect 'j' vi-down-line-or-history
bindkey -v '^?' backward-delete-char

# Vi Mode
bindkey -v
export KEYTIMEOUT=1



### Use Starship ###

eval "$(starship init zsh)"
eval "$(thefuck --alias fuck)"


### Antigen-Managed Plugins: ###

source ~/.zsh_plugins.sh

eval $(thefuck --alias)
alias config='/usr/bin/git --git-dir=/home/liam/dotfiles --work-tree=/home/liam'
