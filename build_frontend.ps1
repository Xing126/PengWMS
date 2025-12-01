$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\templates"
$env:NODE_OPTIONS = "--openssl-legacy-provider"
npx quasar build
