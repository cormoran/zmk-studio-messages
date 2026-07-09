# ZMK Studio Messages

This repository contains the message definitions used to interact with ZMK Studio enabled devices.

> **Note**
> This is a fork of [zmkfirmware/zmk-studio-messages](https://github.com/zmkfirmware/zmk-studio-messages).
> In addition to the upstream messages, it adds an **unofficial custom subsystem protocol**
> that lets ZMK modules expose their own RPC endpoints and companion UIs to ZMK Studio.
> See [Custom subsystem protocol](#custom-subsystem-protocol) below.

## Overview

The messages are defined as [Protocol Buffers](https://protobuf.dev/) (`proto3`) under
[`proto/zmk/`](proto/zmk). Each file maps to a *subsystem* of the RPC surface exposed by a device:

| File | Package | Description |
| --- | --- | --- |
| [`studio.proto`](proto/zmk/studio.proto) | `zmk.studio` | Top-level envelope that multiplexes all subsystems |
| [`meta.proto`](proto/zmk/meta.proto) | `zmk.meta` | Framing / error metadata |
| [`core.proto`](proto/zmk/core.proto) | `zmk.core` | Device info, lock state, resets |
| [`behaviors.proto`](proto/zmk/behaviors.proto) | `zmk.behaviors` | Behavior (binding) metadata |
| [`keymap.proto`](proto/zmk/keymap.proto) | `zmk.keymap` | Keymap read/write |
| [`custom.proto`](proto/zmk/custom.proto) | `zmk.custom` | **Custom subsystem protocol (this fork)** |

The `*.options.in` files carry [nanopb](https://github.com/nanopb/nanopb) options (max sizes, etc.)
that are expanded from Kconfig values at firmware build time.

Every request/response is wrapped in the top-level envelope defined in
[`studio.proto`](proto/zmk/studio.proto). A subsystem is selected via the `subsystem` `oneof`,
so each subsystem defines its own `Request`, `Response`, and `Notification` messages.

## Custom subsystem protocol

Upstream ZMK Studio only knows about the built-in subsystems (`core`, `behaviors`, `keymap`).
This fork adds a generic **`zmk.custom`** subsystem so that arbitrary ZMK modules can define and
expose their *own* protocol over the same ZMK Studio transport — without having to patch the core
message set for every feature.

### How it hooks into the envelope

The custom subsystem is attached to the top-level envelope using field number `100` (well outside
the range used by upstream subsystems, to avoid collisions when rebasing on upstream):

```proto
// studio.proto
message Request {
    uint32 request_id = 1;
    oneof subsystem {
        zmk.core.Request core = 3;
        zmk.behaviors.Request behaviors = 4;
        zmk.keymap.Request keymap = 5;
        zmk.custom.Request custom = 100;   // added by this fork
    }
}
// ...RequestResponse and Notification gain `zmk.custom` at field 100 as well.
```

### The `zmk.custom` messages

Defined in [`custom.proto`](proto/zmk/custom.proto):

- **`ListCustomSubsystemRequest` / `ListCustomSubsystemResponse`** — discovery. A client asks the
  device which custom subsystems are available. The response is a list of `CustomSubsystemInfo`.

- **`CustomSubsystemInfo`** — describes one custom subsystem:
  - `index` — a device-specific numeric handle used to address the subsystem in later calls.
    It is **not stable**: it may change on every firmware compile and potentially across reboots,
    so clients must resolve it via discovery rather than hard-coding it.
  - `identifier` — a stable, unique string identifier for the subsystem (this is what a client
    matches against).
  - `ui_url` — zero or more URLs pointing to web UIs that know how to talk to this subsystem.

- **`CallRequest` / `CallResponse`** — the actual RPC. Both carry a `subsystem_index` (matching
  `CustomSubsystemInfo.index`) and an opaque `payload` (`bytes`). The custom subsystem protocol is
  intentionally **transport-only**: the meaning of `payload` is defined entirely by the target
  subsystem, not by this schema. This lets a module ship its own encoding (its own protobuf, CBOR,
  raw bytes, …) and evolve it independently.

- **`CustomNotification`** — device-initiated (unsolicited) message from a custom subsystem to the
  client, again addressed by `subsystem_index` with an opaque `payload`.

### Typical flow

1. Client sends `custom.ListCustomSubsystemRequest`.
2. Device replies with `ListCustomSubsystemResponse` listing each `CustomSubsystemInfo`
   (`index`, `identifier`, `ui_url`).
3. Client matches the subsystem it cares about by `identifier`, remembers its current `index`,
   and (optionally) opens one of the `ui_url`s to drive it.
4. Client exchanges module-defined payloads via `CallRequest` / `CallResponse` on that `index`.
5. The device may push `CustomNotification`s at any time for that `index`.

### Build-time options

[`custom.options.in`](proto/zmk/custom.options.in) bounds the wire sizes via Kconfig-expanded
nanopb options:

- `CustomSubsystemInfo.identifier` → `CONFIG_ZMK_STUDIO_RPC_CUSTOM_SUBSYSTEM_IDENTIFIER_MAX_LEN`
- `CallRequest.payload` → `CONFIG_ZMK_STUDIO_RPC_CUSTOM_SUBSYSTEM_REQUEST_PAYLOAD_MAX_BYTES`

## TODO

* Document transport protocol used with these messages
* Release/versioning strategy
