# multizone_heating
Multizone heating integration for Homeassistant

ZoneMaster -> Zone -> Zone -> ...
(Zone level might be multiplied)

ZoneMaster has a switch, that controls the heating (on/off)
Zones have pumps and valves. Pump run the hot water in the circuit (typically a whole floor), and valve opens/closes different sections (typically a room). The final zone on a circuit will be a room in multizone. This romm will provide a switch, which can be operated according to the heating demand.

Pumps should be connected to a swicth entity. Multizone controls them as a switch.

Multizone may have an keep_active time, which will operate the pump a bit longer after switching it off. Always the last circuit, before the main switch turn off will run longer.
The main switch may have a keep_alive time, which will Keep the system alive (just like a watchdog). Currently this is a button. In the future it could be a service.

TBD:
Final zones provides a boost switch, which turns on the heeating for a given room for a given time. Default boost
time can be changed. After the timeout, the boost switch and the heating turns off automatically.

ToDos:
- Watchdog check on the whole system to avoid anomalies. Should be optionally disabled on a given branch.
- Force states of the pumps and valves