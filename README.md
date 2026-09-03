# Amperfied Connect Modbus

Home Assistant integration for Amperfied Connect wallboxes using the local
Modbus TCP interface.

I started this project for my own Connect wallbox. The existing Heidelberg
integration already covered the basic registers, but I wanted the Eco mode,
the internal phase switch and the end of a charging session to work together
without several separate Home Assistant automations.

The integration is still young and has been tested on a Connect wallbox with
register layout `2.0.4`.

## What it does

- reads charging state, power, current, energy and diagnostic values;
- controls the charge-current limit and charge enable;
- switches the wallbox between Eco and manual charging;
- selects one- or three-phase charging on wallboxes with an internal phase
  switch;
- provides a **Stop charging** button for the current session;
- restores charge enable after the vehicle is unplugged, ready for the next
  RFID-authorized session.

When Eco mode is switched off, the integration can automatically return to
three-phase charging. A phase change is checked after the switching time stored
in the wallbox. If the requested state was not reached, the command is repeated
once. It will not keep retrying in a loop.

The manual phase selector is unavailable while Eco mode is active because the
wallbox controls the phases itself in that mode.

## Stop charging and Remote Lock

The **Stop charging** button sets the charge-current command to zero. Once the
vehicle is unplugged, the previous current limit is restored automatically.

This is separate from **Remote Lock**. Remote Lock blocks the wallbox globally;
it does not release the charging cable. Depending on the vehicle, it may still
need to be unlocked before the cable can be removed.

## Installation with HACS

Until the integration is included in the default HACS list, add this repository
as a custom repository:

`https://github.com/DerHimbeerHugo/heidelberg_energy_control`

Select **Integration** as the repository type, install **Amperfied Connect
Modbus**, restart Home Assistant and add the integration under **Settings ->
Devices & services**.

The wallbox accepts only one Modbus TCP connection. Do not run this integration
and another Modbus integration for the same wallbox at the same time.

## Options

The integration can be configured under **Settings -> Devices & services ->
Amperfied Connect Modbus -> Configure**.

Available options:

- polling interval;
- return to three phases when Eco mode is disabled;
- verify phase switching and retry once;
- restore charge enable after the vehicle is unplugged.

The three behavior options are enabled by default.

## Changing the wallbox address

If the IP address or Modbus settings change, open **Settings -> Devices &
services -> Amperfied Connect Modbus**, open the integration menu and select
**Reconfigure**. The new connection is tested before it is saved. The existing
device, entities, history and automations remain in place.

## Compatibility

Eco and phase-switch entities are added only when the corresponding Modbus
registers are available. The phase functions require Connect Solar / Solar Pro
hardware with the internal phase-switch contactor.

Register definitions are based on the official
[Modbus documentation for the Connect series](https://www.amperfied.de/wp-content/uploads/2025/05/Documentation-Modbus-Register-Layout-connect-series-20250422.pdf).

If you use the integration with another Connect model or register-layout
version, feedback is welcome through the GitHub issue tracker.

## Credits and license

This project is based on Bastian Schroll's
[`heidelberg_energy_control`](https://github.com/Schrolli91/heidelberg_energy_control)
integration and keeps its MIT license and copyright notice.

Amperfied and Heidelberg product names are used only to identify compatible
hardware. This is an independent community project and is not affiliated with
or endorsed by the manufacturer.

Modbus commands directly affect charging behavior. Use the integration only
with compatible hardware and follow the wallbox and electrical-installation
instructions.
