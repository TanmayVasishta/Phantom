# Bluetooth / Wi-Fi radio control via the WinRT Radio API.
#
# Chosen over Enable-PnpDevice/Disable-PnpDevice on the adapter, which is the
# more obvious route but requires an elevated shell — this one works as the
# logged-in user, which is what an assistant launched from the tray actually
# has. Windows still gates it behind RequestAccessAsync(); that returns
# "DeniedByUser"/"DeniedBySystem" rather than throwing, and is reported back
# as-is so the caller can say something truthful instead of silently failing.
#
# Usage:  radio_control.ps1 -Kind Bluetooth -Action state|on|off
param(
    [ValidateSet("Bluetooth", "WiFi")] [string]$Kind = "Bluetooth",
    [ValidateSet("state", "on", "off")] [string]$Action = "state"
)

$ErrorActionPreference = "Stop"

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime

    # WinRT's IAsyncOperation has no synchronous wait in PowerShell; this pulls
    # the generic AsTask overload out by reflection so each call can be awaited.
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and
            $_.GetParameters().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
        })[0]

    function Await($op, $resultType) {
        $asTask = $asTaskGeneric.MakeGenericMethod($resultType)
        $task = $asTask.Invoke($null, @($op))
        $task.Wait(10000) | Out-Null
        $task.Result
    }

    [Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime] | Out-Null
    [Windows.Devices.Radios.RadioAccessStatus, Windows.System.Devices, ContentType = WindowsRuntime] | Out-Null
    [Windows.Devices.Radios.RadioState, Windows.System.Devices, ContentType = WindowsRuntime] | Out-Null

    $access = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
    if ("$access" -ne "Allowed") {
        Write-Output "ERROR|radio access $access"
        exit 1
    }

    $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    $radio = $radios | Where-Object { "$($_.Kind)" -eq $Kind } | Select-Object -First 1
    if ($null -eq $radio) {
        Write-Output "ERROR|no $Kind radio on this machine"
        exit 1
    }

    if ($Action -eq "state") {
        Write-Output "OK|$($radio.State)"
        exit 0
    }

    $target = if ($Action -eq "on") { [Windows.Devices.Radios.RadioState]::On } else { [Windows.Devices.Radios.RadioState]::Off }
    $result = Await ($radio.SetStateAsync($target)) ([Windows.Devices.Radios.RadioAccessStatus])
    if ("$result" -ne "Allowed") {
        Write-Output "ERROR|set state refused: $result"
        exit 1
    }
    Write-Output "OK|$($radio.State)"
    exit 0
}
catch {
    Write-Output "ERROR|$($_.Exception.Message)"
    exit 1
}
