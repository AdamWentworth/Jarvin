[CmdletBinding()]
param(
  [string]$SdkRoot = $(if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } elseif ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA "Android\\Sdk" }),
  [string]$NdkVersion = "27.2.12479018",
  [string]$JavaHome = $(if ($env:JAVA_HOME) { $env:JAVA_HOME } else { "C:\\Program Files\\Java\\jdk-20" })
)

$ErrorActionPreference = "Stop"

function Assert-Path {
  param(
    [string]$PathValue,
    [string]$Label
  )

  if (-not (Test-Path $PathValue)) {
    throw "$Label not found at $PathValue"
  }
}

function Invoke-CheckedCommand {
  param(
    [scriptblock]$Command,
    [string]$FailureMessage
  )

  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw $FailureMessage
  }
}

function Ensure-ManifestPermission {
  param(
    [string]$ManifestPath,
    [string]$PermissionName
  )

  $content = Get-Content $ManifestPath -Raw
  if ($content -match [regex]::Escape($PermissionName)) {
    return
  }

  $insertion = "    <uses-permission android:name=`"$PermissionName`" />`r`n"
  $updated = $content -replace '(<manifest[^>]*>\s*)', "`$1$insertion"
  Set-Content -Path $ManifestPath -Value $updated -Encoding UTF8
}

$clientRoot = Split-Path $PSScriptRoot -Parent
$androidProjectRoot = Join-Path $clientRoot "src-tauri\\gen\\android"
$manifestPath = Join-Path $androidProjectRoot "app\\src\\main\\AndroidManifest.xml"
$apkRelativePath = "src-tauri\\gen\\android\\app\\build\\outputs\\apk\\arm64\\debug\\app-arm64-debug.apk"
$artifactDir = Join-Path $clientRoot "artifacts"
$artifactApkPath = Join-Path $artifactDir "jarvin-mobile-arm64-debug.apk"
$rustLibRelativePath = "src-tauri\\target\\aarch64-linux-android\\debug\\libjarvin_ui_lib.so"
$jniLibDir = Join-Path $androidProjectRoot "app\\src\\main\\jniLibs\\arm64-v8a"
$ndkHome = if ($env:NDK_HOME) { $env:NDK_HOME } else { Join-Path $SdkRoot "ndk\\$NdkVersion" }

Assert-Path $SdkRoot "Android SDK root"
Assert-Path $ndkHome "Android NDK"
Assert-Path $JavaHome "JAVA_HOME"

$env:ANDROID_HOME = $SdkRoot
$env:ANDROID_SDK_ROOT = $SdkRoot
$env:NDK_HOME = $ndkHome
$env:JAVA_HOME = $JavaHome

Write-Host "Using Android SDK: $SdkRoot"
Write-Host "Using Android NDK: $ndkHome"
Write-Host "Using JAVA_HOME: $JavaHome"

Push-Location $clientRoot
try {
  if (-not (Test-Path (Join-Path $androidProjectRoot "gradlew.bat"))) {
    Invoke-CheckedCommand { npm run tauri:android:init } "Tauri Android init failed."
  }

  Assert-Path $manifestPath "Android manifest"
  Ensure-ManifestPermission -ManifestPath $manifestPath -PermissionName "android.permission.RECORD_AUDIO"
  Ensure-ManifestPermission -ManifestPath $manifestPath -PermissionName "android.permission.MODIFY_AUDIO_SETTINGS"

  Invoke-CheckedCommand { rustup target add aarch64-linux-android } "Failed to install the aarch64 Android Rust target."
  & npm run tauri:android:build -- --debug --target aarch64
  $tauriBuildExit = $LASTEXITCODE

  if ($tauriBuildExit -ne 0) {
    $rustLibPath = Join-Path $clientRoot $rustLibRelativePath
    Assert-Path $rustLibPath "Built arm64 Rust library"

    Write-Host "Falling back to direct Gradle packaging because Windows blocked the Tauri symlink step."

    New-Item -ItemType Directory -Force $jniLibDir | Out-Null
    Copy-Item $rustLibPath (Join-Path $jniLibDir "libjarvin_ui_lib.so") -Force

    Push-Location $androidProjectRoot
    try {
      Invoke-CheckedCommand {
        .\gradlew.bat assembleArm64Debug -x rustBuildArm64Debug '-Pkotlin.incremental=false'
      } "Gradle fallback packaging failed."
    } finally {
      Pop-Location
    }
  }

  $apkPath = Join-Path $clientRoot $apkRelativePath
  Assert-Path $apkPath "Android debug APK"
  New-Item -ItemType Directory -Force $artifactDir | Out-Null
  Copy-Item $apkPath $artifactApkPath -Force
  Write-Host ""
  Write-Host "Jarvin mobile debug APK ready:"
  Write-Host $apkPath
  Write-Host ""
  Write-Host "Copied to easy-install path:"
  Write-Host $artifactApkPath
} finally {
  Pop-Location
}
