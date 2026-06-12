# _wait_api (internal helper)

Waits for a RouterOS device to come back after a reboot-class operation. Not a
user entrypoint — the `reboot`, `reset`, `restore` and `upgrade` roles include
it after issuing a command that reboots the device:

    - ansible.builtin.include_role:
        name: david_igou.routeros_configuration._wait_api
      vars:
        _wait_api_timeout: "{{ routeros_reboot_timeout }}"

Two phases, because the API port accepts TCP before RouterOS's login subsystem
is ready:

1. `wait_for` the API TCP port (budget: `_wait_api_timeout`, first probe held
   off by `_wait_api_delay` so the old instance isn't mistaken for the new).
2. Retry a real `system identity` read until login succeeds
   (`_wait_api_login_retries` x `_wait_api_login_delay`).

Connection comes from the shared `routeros_api_*` variables, like every other
role in this collection.

## License

GPL-3.0-or-later
