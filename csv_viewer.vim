" csv_viewer.vim — Open CSV/TSV files in csv_reader from Vim/Neovim
"
" Usage:
"   :CsvViewer          Open current CSV/TSV buffer in csv_reader
"   <Leader>pv          Toggle viewer (default: \pv or ,pv)
"
" Setup:
"   1. Put csv_reader.py somewhere in your $PATH (or set g:csv_viewer_cmd)
"   2. Source this file in your vimrc:
"      source /path/to/csv_viewer.vim
"
" Configuration (optional):
"   let g:csv_viewer_cmd = '/path/to/csv_reader.py'   " custom path

let s:csv_viewer_buf = -1

function! s:FindCsvViewer() abort
  " User override
  if exists('g:csv_viewer_cmd') && executable(g:csv_viewer_cmd)
    return g:csv_viewer_cmd
  endif
  " Search PATH
  if executable('csv_reader')
    return 'csv_reader'
  endif
  if executable('csv_reader.py')
    return 'csv_reader.py'
  endif
  return ''
endfunction

function! CsvViewerToggle() abort
  " Close if already open
  if s:csv_viewer_buf != -1 && bufexists(s:csv_viewer_buf)
    let l:win = bufwinnr(s:csv_viewer_buf)
    if l:win != -1
      execute l:win . 'wincmd w'
      bwipeout!
      let s:csv_viewer_buf = -1
      return
    endif
  endif
  let s:csv_viewer_buf = -1

  let l:file = expand('%:p')
  if empty(l:file) || !filereadable(l:file)
    echohl WarningMsg | echo 'No readable file in current buffer' | echohl None
    return
  endif

  let l:ext = tolower(expand('%:e'))
  if l:ext !=# 'csv' && l:ext !=# 'tsv'
    echohl WarningMsg | echo 'Not a CSV/TSV file' | echohl None
    return
  endif

  let l:cmd = s:FindCsvViewer()
  if empty(l:cmd)
    echohl ErrorMsg
    echo 'csv_reader not found. Put it in $PATH or set g:csv_viewer_cmd'
    echohl None
    return
  endif

  if has('nvim')
    enew
    let s:csv_viewer_buf = bufnr('%')
    call termopen(l:cmd . ' ' . shellescape(l:file), {
          \ 'on_exit': function('s:OnCsvViewerExit')
          \ })
    setlocal nobuflisted
    startinsert
  else
    let l:full_cmd = l:cmd . ' ' . shellescape(l:file)
    let s:csv_viewer_buf = term_start(['/bin/sh', '-c', l:full_cmd], {
          \ 'term_finish': 'close',
          \ 'curwin': 1,
          \ 'exit_cb': function('s:OnCsvViewerExitVim'),
          \ })
    setlocal nobuflisted
  endif
endfunction

function! s:OnCsvViewerExit(job_id, code, event) abort
  if s:csv_viewer_buf != -1 && bufexists(s:csv_viewer_buf)
    execute 'bwipeout! ' . s:csv_viewer_buf
  endif
  let s:csv_viewer_buf = -1
endfunction

function! s:OnCsvViewerExitVim(job, status) abort
  if s:csv_viewer_buf != -1 && bufexists(s:csv_viewer_buf)
    execute 'bwipeout! ' . s:csv_viewer_buf
  endif
  let s:csv_viewer_buf = -1
endfunction

command! CsvViewer call CsvViewerToggle()
nnoremap <silent> <Leader>pv :CsvViewer<CR>
