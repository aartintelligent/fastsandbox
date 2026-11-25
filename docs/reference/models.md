# Models

The payloads of the daemon API, as Pydantic models: field names are those of
`docker-sandbox`, unknown fields of a newer daemon are kept (`extra="allow"`),
and request models have the constructors of the library as class methods.
Every model is imported from `fastsandbox.models`; the most used are also
exported by `fastsandbox` itself.

## Sandboxes

Creation requests, their progress and result, the state of a sandbox, mounts and ports.

::: fastsandbox.models.Created
    options:
      heading_level: 3

::: fastsandbox.models.CreateEvent
    options:
      heading_level: 3

::: fastsandbox.models.CreateFailure
    options:
      heading_level: 3

::: fastsandbox.models.CreateProgress
    options:
      heading_level: 3

::: fastsandbox.models.CreateRequest
    options:
      heading_level: 3

::: fastsandbox.models.CreateResult
    options:
      heading_level: 3

::: fastsandbox.models.CreateUnknown
    options:
      heading_level: 3

::: fastsandbox.models.HostMount
    options:
      heading_level: 3

::: fastsandbox.models.PortBinding
    options:
      heading_level: 3

::: fastsandbox.models.PullPolicy
    options:
      heading_level: 3

::: fastsandbox.models.RuntimeMount
    options:
      heading_level: 3

::: fastsandbox.models.SandboxInfo
    options:
      heading_level: 3

::: fastsandbox.models.SandboxState
    options:
      heading_level: 3

::: fastsandbox.models.SavedImage
    options:
      heading_level: 3

::: fastsandbox.models.SkillsMode
    options:
      heading_level: 3

::: fastsandbox.models.SwapOutcome
    options:
      heading_level: 3

::: fastsandbox.models.SwapRequest
    options:
      heading_level: 3

::: fastsandbox.models.Workspace
    options:
      heading_level: 3

## Commands

Command specifications, their outputs and states, interactive sessions.

::: fastsandbox.models.AgentSessionSpec
    options:
      heading_level: 3

::: fastsandbox.models.AttachOutput
    options:
      heading_level: 3

::: fastsandbox.models.AttachSpec
    options:
      heading_level: 3

::: fastsandbox.models.ExecInspect
    options:
      heading_level: 3

::: fastsandbox.models.ExecOutput
    options:
      heading_level: 3

::: fastsandbox.models.ExecSpec
    options:
      heading_level: 3

::: fastsandbox.models.OutputChunk
    options:
      heading_level: 3

::: fastsandbox.models.TerminalSize
    options:
      heading_level: 3

## Credentials

Credentials pushed to a sandbox and the secrets of the daemon.

::: fastsandbox.models.CredentialSource
    options:
      heading_level: 3

::: fastsandbox.models.CredentialsUpdate
    options:
      heading_level: 3

::: fastsandbox.models.CustomSecret
    options:
      heading_level: 3

::: fastsandbox.models.ServiceCredential
    options:
      heading_level: 3

## Network policy

Rules, checks and the activity log of the network policy.

::: fastsandbox.models.CheckKind
    options:
      heading_level: 3

::: fastsandbox.models.CheckResult
    options:
      heading_level: 3

::: fastsandbox.models.CreatedRule
    options:
      heading_level: 3

::: fastsandbox.models.Decision
    options:
      heading_level: 3

::: fastsandbox.models.HostActivity
    options:
      heading_level: 3

::: fastsandbox.models.HttpTarget
    options:
      heading_level: 3

::: fastsandbox.models.NetworkCheck
    options:
      heading_level: 3

::: fastsandbox.models.NetworkLog
    options:
      heading_level: 3

::: fastsandbox.models.NetworkRule
    options:
      heading_level: 3

::: fastsandbox.models.NetworkRules
    options:
      heading_level: 3

::: fastsandbox.models.Protocol
    options:
      heading_level: 3

::: fastsandbox.models.RuleAction
    options:
      heading_level: 3

::: fastsandbox.models.RuleChange
    options:
      heading_level: 3

::: fastsandbox.models.RuleChangeResult
    options:
      heading_level: 3

## Images

Images of the daemon and the progress of a pull.

::: fastsandbox.models.ImageInspect
    options:
      heading_level: 3

::: fastsandbox.models.ImageSummary
    options:
      heading_level: 3

::: fastsandbox.models.LocalImageMetadata
    options:
      heading_level: 3

::: fastsandbox.models.ProgressDetail
    options:
      heading_level: 3

::: fastsandbox.models.PullProgress
    options:
      heading_level: 3

## MCP

The MCP gateway and the servers registered with it.

::: fastsandbox.models.GatewayMode
    options:
      heading_level: 3

::: fastsandbox.models.LoadedServer
    options:
      heading_level: 3

::: fastsandbox.models.McpGateway
    options:
      heading_level: 3

::: fastsandbox.models.McpServerCheck
    options:
      heading_level: 3

::: fastsandbox.models.McpServerKind
    options:
      heading_level: 3

::: fastsandbox.models.RegistrationCheck
    options:
      heading_level: 3

## Daemon

Health, information, settings and disk usage of the daemon.

::: fastsandbox.models.DaemonInfo
    options:
      heading_level: 3

::: fastsandbox.models.DiskUsage
    options:
      heading_level: 3

::: fastsandbox.models.DiskUsageSummary
    options:
      heading_level: 3

::: fastsandbox.models.Health
    options:
      heading_level: 3

::: fastsandbox.models.Setting
    options:
      heading_level: 3

## Events

The events of the daemon.

::: fastsandbox.models.DaemonEvent
    options:
      heading_level: 3

::: fastsandbox.models.EventKind
    options:
      heading_level: 3

## Prompts

The approval prompts of the daemon.

::: fastsandbox.models.PromptEvent
    options:
      heading_level: 3

## Kits

What a kit package records.

::: fastsandbox.models.PackageImage
    options:
      heading_level: 3

## Base

The base of every model and the helpers that give their wire shape.

::: fastsandbox.models.Model
    options:
      heading_level: 3

::: fastsandbox.models.expose_secret
    options:
      heading_level: 3

::: fastsandbox.models.wire
    options:
      heading_level: 3
