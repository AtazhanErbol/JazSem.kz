param([Parameter(Mandatory=$true)][string]$Sender)
$ErrorActionPreference = 'Stop'
if ($Sender -notmatch '^[^\s@]+@[^\s@]+\.[^\s@]+$') { throw 'Enter a valid sender email.' }
$secret = Read-Host 'Google app password (input is hidden)' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $passwordValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Replace(' ', '')
    if ($passwordValue -notmatch '^[a-zA-Z0-9]{16}$') { throw 'Expected a 16-character Google app password.' }
    $envPath = Join-Path (Split-Path $PSScriptRoot -Parent) '.env.local'
    $lines = @(if (Test-Path -LiteralPath $envPath) { Get-Content -LiteralPath $envPath | Where-Object { $_ -notmatch '^(EMAIL_|DEFAULT_FROM_EMAIL=)' } })
    $lines += @('EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend','EMAIL_HOST=smtp.gmail.com','EMAIL_PORT=587','EMAIL_USE_TLS=true',"EMAIL_HOST_USER=$Sender","DEFAULT_FROM_EMAIL=JazSem <$Sender>","EMAIL_HOST_PASSWORD=$passwordValue")
    $lines | Set-Content -LiteralPath $envPath -Encoding utf8
    Write-Output 'Saved to ignored .env.local. Restart Django, worker and beat to apply. No test email was sent.'
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $passwordValue = $null
    $secret.Dispose()
}
