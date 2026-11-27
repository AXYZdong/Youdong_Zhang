# Windows 本地预览；优先使用 Jekyll，未安装 Ruby 时使用同一份源文件的 Python 预览。
param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Get-Command bundle -ErrorAction SilentlyContinue) {
    & bundle exec jekyll serve --livereload --host 127.0.0.1 --port $Port
} else {
    & python tools/preview.py --port $Port
}
exit $LASTEXITCODE
