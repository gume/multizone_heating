# multizone_heating
Multizone heating integration for Homeassistant

ZoneMaster -> Zone -> SubZone
(Zone level might be multiplied)

ZoneMaster and Zone have pumps that control the heat flow for the given branch (typically a whole floor)
SubZone has valves that control the heat radiation for the given zone (typically a room)

Pumps should be connected to a swicth entity.
The switch may have an keep_active time, which will operate the pump longer after switching it off
The switch may have a keep_alive time, which will repeat the switch command on a given interval

SubZone provides a switch that turns on/off the heating for the given subzone. This is the input, the subzone
thermostat should be connected to this switch. Usually it is a climate control.
Valves may have keep_active and keep_alive times set.

SubZone provides a boost switch, which turns on the heeating for a given subzone for a given time. Default boost
time can be changed. After the timeout, the boost switch turns off automatically.

SubZone may connect a thermometer, but currently there is no function for this. This is for future functions.

Issues:
- Active time on pumps and valves can be interrupted manually. This could be considered as a feature..

ToDos:
- Watchdog check on the whole system to avoid anomalies. Should be optionally disabled on a given branch.
- Own thermostat with PID and external temperature read ?
- Multiple subzone termometers
