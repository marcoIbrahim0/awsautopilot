param(
  [string]$NodePath = "C:\\Program Files\\nodejs\\node.exe",
  [string]$AgentPath = "C:\\Program Files\\AWS Security Autopilot\\local-agent\\src\\index.mjs",
  [string]$ServiceName = "AwsSecurityAutopilotLocalAgent"
)

$binPath = '"' + $NodePath + '" "' + $AgentPath + '"'
sc.exe create $ServiceName binPath= $binPath start= auto
sc.exe description $ServiceName "AWS Security Autopilot Local PTY Agent"
sc.exe failure $ServiceName reset= 60 actions= restart/5000/restart/5000/restart/5000

# Configure environment variables in registry for the service host account/profile setup.
Write-Host "Set AGENT_ALLOW_BROWSER=0 for the service account environment, then restart service."
Write-Host "Start service: sc.exe start $ServiceName"
