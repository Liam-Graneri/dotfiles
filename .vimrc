" ### Setup Vundle Plugin Manager ###
" set nocompatible
" filetype off
" set rtp+=~/.vim/bundle/Vundle.vim #Setup the runtime path to include Vundle
" call vundle#begin() #Initialise
" Plugin 'VundleVim/Vundle.vim' #Let vundle manage Vundle
" # Add plugins here #
" Plugin 'terminalnote/sway-vim-syntax'
" # End plugin list #


" When started as "evim", evim.vim will already have done these settings, bail
" out.
if v:progname =~? "evim"
  finish
endif

" Get the defaults that most users want.
source $VIMRUNTIME/defaults.vim

if has("vms")
  set nobackup		" do not keep a backup file, use versions instead
else
  set backup		" keep a backup file (restore to previous version)
  if has('persistent_undo')
    set undofile	" keep an undo file (undo changes after closing)
  endif
endif

if &t_Co > 2 || has("gui_running")
  " Switch on highlighting the last used search pattern.
  set hlsearch
endif

" Put these in an autocmd group, so that we can delete them easily.
augroup vimrcEx
  au!

  " For all text files set 'textwidth' to 78 characters.
  autocmd FileType text setlocal textwidth=78
augroup END

" Show line numbers by default
set number





" Add optional packages.
"
" The matchit plugin makes the % command work better, but it is not backwards
" compatible.
" The ! means the package won't be loaded right away but when plugins are
" loaded during initialization.
if has('syntax') && has('eval')
  packadd! matchit
endif

" Automatic Reloading of .vimrc
autocmd! bufwritepost .vimrc source %

"  Make search case insensitive
set hlsearch
set incsearch
set ignorecase
set smartcase

call pathogen#infect()
call pathogen#helptags()
set sessionoptions-=options

filetype plugin indent on
syntax on

" ===========================================================================
" 				PYTHON IDE SETUP
" ===========================================================================
" Settings for vim-powerline
set laststatus=2

" Settings for ctrlp
let g:ctrlp_max_height = 30
set wildignore+=*_build/*
set wildignore+=*/coverage/*

" Settings for python-mode
map <Leader>g :call RopeGotoDefinition()<CR>
let g:pymode_rope_goto_def_newwin = "vnew"
let g:pymode_rope_extended_complete = 1
let g:pymode_breakpoint = 0
let g:pymode_syntax = 1
let g:pymode_syntax_builtin_objs = 0
let g:pymode_syntax_builtin_funcs = 0
map <Leader>b 0import ipdb; ipdb.set_trace() # BREAKPOINT <C-c>
