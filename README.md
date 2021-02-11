# rooster

Send a Discord webhook when a YRDSB Google Meet is detected to be open

## Setup guide

Install dependencies:

```
pip3 install --requirement requirements.txt
```

Run the script:

```
python3 ./schoolschedule.py
```

## Usage

```
Usage:	python schoolschedule.py [options...]
  where options include:

General options
  --config <path>			Use configuration file at <path>.
  --verbose				Run with extended output (debug mode).
  --help, -h				Print this help screen.

Browser options
  --worker-visible			Run with the browser visible.
  --render-backend <driver>		Use <driver> as the browser backend (either "geckodriver" or "chromedriver").
  --driver-path <path>			Use <path> as the path to the driver executable.
  --driver-log <path>			Use <path> as the path to the driver log file.

Secrets options
  --gmail-address <address>		Use <address> as the Google account email address for Meet lookups.
  --yrdsb-password <password>		Use <password> as the password for authentication with YRDSB for Meet lookups.
  --discord-url <url>			Use <url> as the URL to send Discord webhooks to.
  --admin-user-id <id>			Use <id> as the Discord user ID to ping in case of emergencies.
```

Class data is stored in the `config.json` configuration file with each class requiring the following fields:

#### name: string

The name of the class used in debug messages and sent to Discord.

#### teacher: string

The name of the teacher sent to Discord.

#### start_time: string

Must be in 24-hour time, in the format `HH:mm`. The program starts checking if the meeting is open five minutes prior to this time.

#### end_time: string

Must be in 24-hour time, in the format `HH:mm`. The program stops checking if the meeting is open after this time.

#### period: integer

A currently unused variable, this field can be left empty.

#### role: integer/string

The Discord role ID that should be mentioned when a meeting is detected to be open. This can be obtained by right-clicking a role in Discord's desktop versions in developer mode and clicking "Copy ID". This role must be mentionable by all users.

#### link: string

The link that the program will scrape to check if a meeting is open. If the link is not a Google Meet link (does not contain `meet.google.com`), the program will send a webhook at the first available opportunity five minutes prior to the class's `start_time`.

#### enabled: boolean

This option controls whether this class will be searched for.
