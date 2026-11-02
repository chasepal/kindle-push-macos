#!/bin/zsh
cd -- "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
python3 -B ./kindle_push.py --interactive "$@"
status_code=$?
printf '\n按回车关闭窗口。'
read -r
exit "$status_code"
